import asyncio
from datetime import datetime, timezone, timedelta
import logging
from typing import Optional, Dict, List, Any
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Rule, Deal, Setting, ScanLog
from app.services.ebay_client import EbayClient
from app.services.filter_engine import FilterEngine
from app.services.notifier import Notifier

logger = logging.getLogger("poller")


class DealPoller:
    """Async background worker that periodically evaluates active rules and discovers deals."""

    def __init__(self):
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._poll_interval = 120
        self._recent_logs: List[Dict[str, Any]] = []

    def start(self):
        """Starts the background worker task."""
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info("DealPoller background task started.")

    def stop(self):
        """Stops the background worker task."""
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("DealPoller background task stopped.")

    async def _run_loop(self):
        """Main periodic polling loop."""
        # Initial short delay on app startup before first poll
        await asyncio.sleep(5)

        while self._is_running:
            try:
                await self.poll_all_active_rules()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Unexpected error in poller loop: {exc}", exc_info=True)

            interval = self.get_current_poll_interval()
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break

    def get_current_poll_interval(self) -> int:
        """Fetch interval from DB settings or fallback to default."""
        try:
            with SessionLocal() as db:
                setting = db.query(Setting).filter(Setting.key == "poll_interval_seconds").first()
                if setting and setting.value:
                    val = int(setting.value)
                    return max(30, val)
        except Exception:
            pass
        return self._poll_interval

    def _get_settings(self, db: Session) -> Dict[str, str]:
        """Fetch all key-value settings as a dictionary."""
        settings = db.query(Setting).all()
        return {s.key: s.value for s in settings if s.value}

    def _log_event(
        self,
        db: Session,
        level: str,
        message: str,
        rule_id: Optional[int] = None,
        found: int = 0,
        matched: int = 0,
    ):
        """Persists a scan event to database and internal log."""
        try:
            log_entry = ScanLog(
                timestamp=datetime.now(timezone.utc),
                level=level,
                message=message,
                rule_id=rule_id,
                items_found=found,
                items_matched=matched,
            )
            db.add(log_entry)
            db.commit()
        except Exception as exc:
            logger.error(f"Failed to record log event: {exc}")
            db.rollback()

    async def poll_all_active_rules(self):
        """Iterates through all active rules and scans each one."""
        with SessionLocal() as db:
            active_rules = db.query(Rule).filter(Rule.is_active == True).all()  # noqa: E712
            if not active_rules:
                return

            settings = self._get_settings(db)
            ebay_client = EbayClient(
                app_id=settings.get("ebay_app_id"),
                cert_id=settings.get("ebay_cert_id"),
                environment=settings.get("ebay_environment", "PRODUCTION"),
            )

            for rule in active_rules:
                try:
                    await self._scan_rule(db, rule, ebay_client, settings)
                except Exception as exc:
                    logger.error(f"Error scanning rule '{rule.name or rule.search_query}': {exc}")
                    self._log_event(
                        db,
                        level="ERROR",
                        message=f"Error scanning rule '{rule.name or rule.search_query}': {str(exc)}",
                        rule_id=rule.id,
                    )

            # Check and run auto-archive if configured
            auto_archive_days = int(settings.get("auto_archive_days", 0) or 0)
            if auto_archive_days > 0:
                self._archive_old_deals(db, auto_archive_days)

    async def scan_single_rule_now(self, rule_id: int) -> Dict[str, Any]:
        """Manually triggered scan for a single rule."""
        with SessionLocal() as db:
            rule = db.query(Rule).filter(Rule.id == rule_id).first()
            if not rule:
                return {"success": False, "message": "Rule not found."}

            settings = self._get_settings(db)
            ebay_client = EbayClient(
                app_id=settings.get("ebay_app_id"),
                cert_id=settings.get("ebay_cert_id"),
                environment=settings.get("ebay_environment", "PRODUCTION"),
            )

            result = await self._scan_rule(db, rule, ebay_client, settings)
            return {"success": True, "result": result}

    async def _scan_rule(
        self,
        db: Session,
        rule: Rule,
        ebay_client: EbayClient,
        settings: Dict[str, str],
    ) -> Dict[str, Any]:
        """Executes search, filtering, database update, and alerts for a single rule."""
        rule_name = rule.name or rule.search_query
        items = await ebay_client.search_items(
            query=rule.search_query,
            category_id=rule.category_id,
            limit=50,
        )

        items_found = len(items)
        new_matches_count = 0

        for item in items:
            item_id = str(item.get("item_id"))
            if not item_id:
                continue

            # Check if this item is already recorded
            existing = db.query(Deal).filter(Deal.item_id == item_id).first()
            if existing:
                continue

            # Evaluate against filter engine
            is_match, deal_score, matched_kws, reject_reason = FilterEngine.evaluate_item(
                item=item,
                max_price=rule.max_price,
                min_price=rule.min_price,
                positive_kw_str=rule.positive_keywords,
                negative_kw_str=rule.negative_keywords,
            )

            if not is_match:
                continue

            # Save new deal
            matched_kws_str = ", ".join(matched_kws) if matched_kws else ""
            new_deal = Deal(
                item_id=item_id,
                rule_id=rule.id,
                title=item.get("title", ""),
                price=item.get("price", 0.0),
                shipping_price=item.get("shipping_price", 0.0),
                total_price=item.get("total_price", 0.0),
                currency=item.get("currency", "USD"),
                url=item.get("url", ""),
                image_url=item.get("image_url"),
                seller_username=item.get("seller_username"),
                seller_feedback_score=item.get("seller_feedback_score"),
                seller_positive_percent=item.get("seller_positive_percent"),
                matching_keywords=matched_kws_str,
                deal_score=deal_score,
                listing_type=item.get("listing_type", "FixedPrice"),
                date_found=datetime.now(timezone.utc),
                raw_data=item.get("raw_data"),
            )
            db.add(new_deal)
            db.flush()

            new_matches_count += 1

            # Webhook Notification Dispatch
            if rule.webhook_enabled:
                discord_url = rule.webhook_override_url or settings.get("discord_webhook_url")
                pushbullet_key = settings.get("pushbullet_api_key")
                generic_url = settings.get("generic_webhook_url")

                deal_dict = {
                    "item_id": new_deal.item_id,
                    "title": new_deal.title,
                    "price": new_deal.price,
                    "shipping_price": new_deal.shipping_price,
                    "total_price": new_deal.total_price,
                    "currency": new_deal.currency,
                    "url": new_deal.url,
                    "image_url": new_deal.image_url,
                    "seller_username": new_deal.seller_username,
                    "seller_feedback_score": new_deal.seller_feedback_score,
                    "seller_positive_percent": new_deal.seller_positive_percent,
                    "matching_keywords": new_deal.matching_keywords,
                    "deal_score": new_deal.deal_score,
                }
                # Fire and forget notification
                asyncio.create_task(
                    Notifier.dispatch_deal_notification(
                        deal_data=deal_dict,
                        rule_name=rule_name,
                        discord_url=discord_url,
                        pushbullet_key=pushbullet_key,
                        generic_url=generic_url,
                    )
                )

        # Update rule statistics
        rule.last_scanned_at = datetime.now(timezone.utc)
        rule.matches_count += new_matches_count
        db.commit()

        # Log results
        log_msg = f"Scanned '{rule_name}': {items_found} items found, {new_matches_count} new matching deals captured."
        self._log_event(
            db,
            level="SUCCESS" if new_matches_count > 0 else "INFO",
            message=log_msg,
            rule_id=rule.id,
            found=items_found,
            matched=new_matches_count,
        )

        return {
            "items_found": items_found,
            "new_matches": new_matches_count,
        }

    def _archive_old_deals(self, db: Session, days: int):
        """Auto-deletes or archives deals older than specified days unless starred."""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            deleted = db.query(Deal).filter(
                Deal.date_found < cutoff,
                Deal.is_starred == False,  # Never delete starred deals
            ).delete()
            if deleted > 0:
                db.commit()
                logger.info(f"Auto-archived {deleted} deals older than {days} days.")
        except Exception as exc:
            logger.error(f"Error archiving old deals: {exc}")
            db.rollback()


# Global poller instance
poller = DealPoller()

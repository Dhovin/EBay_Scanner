import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger("notifier")


class Notifier:
    """Dispatches deal notifications to Discord, Pushbullet, or Generic Webhooks."""

    @staticmethod
    async def dispatch_deal_notification(
        deal_data: Dict[str, Any],
        rule_name: str,
        discord_url: Optional[str] = None,
        pushbullet_key: Optional[str] = None,
        generic_url: Optional[str] = None,
    ) -> Dict[str, bool]:
        """Dispatches alerts across all configured channels."""
        results = {}

        if discord_url and discord_url.strip():
            results["discord"] = await Notifier.send_discord_embed(discord_url.strip(), deal_data, rule_name)

        if pushbullet_key and pushbullet_key.strip():
            results["pushbullet"] = await Notifier.send_pushbullet(pushbullet_key.strip(), deal_data, rule_name)

        if generic_url and generic_url.strip():
            results["generic"] = await Notifier.send_generic_webhook(generic_url.strip(), deal_data, rule_name)

        return results

    @staticmethod
    async def send_discord_embed(webhook_url: str, deal: Dict[str, Any], rule_name: str) -> bool:
        """Sends a rich Discord embed with thumbnail and deal breakdown."""
        score = deal.get("deal_score", 0)
        
        # Color coding: Green (great deal), Gold (solid deal), Gray/Blue (moderate)
        if score >= 75:
            color = 0x22C55E  # Emerald 500
            badge = "🔥 Excellent Deal"
        elif score >= 50:
            color = 0x3B82F6  # Blue 500
            badge = "⭐ Good Deal"
        else:
            color = 0xF59E0B  # Amber 500
            badge = "⚡ Matching Deal"

        title = deal.get("title", "eBay Deal")
        url = deal.get("url", "https://www.ebay.com")
        price = deal.get("price", 0.0)
        shipping = deal.get("shipping_price", 0.0)
        total_price = deal.get("total_price", 0.0)
        currency = deal.get("currency", "USD")
        matching_kws = deal.get("matching_keywords", "")
        seller = deal.get("seller_username") or "Unknown"
        seller_pct = deal.get("seller_positive_percent")
        seller_str = f"{seller} ({seller_pct:.1f}%)" if seller_pct else seller

        fields = [
            {
                "name": "💰 Total Price",
                "value": f"**${total_price:.2f} {currency}** (${price:.2f} + ${shipping:.2f} ship)",
                "inline": True,
            },
            {
                "name": "🎯 Deal Score",
                "value": f"**{score}/100** ({badge})",
                "inline": True,
            },
            {
                "name": "👤 Seller",
                "value": seller_str,
                "inline": True,
            },
        ]

        if matching_kws:
            fields.append({
                "name": "🏷️ Matched Keywords",
                "value": f"`{matching_kws}`",
                "inline": False,
            })

        embed: Dict[str, Any] = {
            "title": title[:250],
            "url": url,
            "color": color,
            "description": f"New match found for monitor: **{rule_name}**",
            "fields": fields,
            "footer": {
                "text": "eBay Deal Monitor for Unraid",
            },
        }

        image_url = deal.get("image_url")
        if image_url:
            embed["thumbnail"] = {"url": image_url}

        payload = {
            "username": "eBay Deal Monitor",
            "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/1/1b/EBay_logo.svg",
            "embeds": [embed],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(webhook_url, json=payload)
                if res.status_code in (200, 204):
                    logger.info(f"Discord notification sent for {deal.get('item_id')}")
                    return True
                else:
                    logger.warning(f"Discord notification failed: HTTP {res.status_code} - {res.text}")
                    return False
        except Exception as exc:
            logger.error(f"Error sending Discord notification: {exc}")
            return False

    @staticmethod
    async def send_pushbullet(api_key: str, deal: Dict[str, Any], rule_name: str) -> bool:
        """Sends a Pushbullet link push notification."""
        url = "https://api.pushbullet.com/v2/pushes"
        headers = {
            "Access-Token": api_key,
            "Content-Type": "application/json",
        }
        total_price = deal.get("total_price", 0.0)
        score = deal.get("deal_score", 0)
        title = f"eBay Deal: ${total_price:.2f} - {deal.get('title', '')[:80]}"
        body = (
            f"Monitor: {rule_name}\n"
            f"Score: {score}/100\n"
            f"Price: ${deal.get('price', 0):.2f} + ${deal.get('shipping_price', 0):.2f} shipping\n"
            f"Keywords: {deal.get('matching_keywords', 'N/A')}"
        )
        payload = {
            "type": "link",
            "title": title,
            "body": body,
            "url": deal.get("url", "https://www.ebay.com"),
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                return res.status_code == 200
        except Exception as exc:
            logger.error(f"Error sending Pushbullet notification: {exc}")
            return False

    @staticmethod
    async def send_generic_webhook(url: str, deal: Dict[str, Any], rule_name: str) -> bool:
        """Sends a generic JSON webhook payload."""
        payload = {
            "event": "new_deal_found",
            "monitor_rule": rule_name,
            "deal": deal,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                return res.status_code in (200, 201, 202, 204)
        except Exception as exc:
            logger.error(f"Error sending generic webhook: {exc}")
            return False

    @classmethod
    async def send_test_notification(
        cls,
        service: str,
        target_url_or_key: str,
    ) -> Dict[str, Any]:
        """Sends a simulated test notification to verify credentials."""
        sample_deal = {
            "item_id": "TEST-123456",
            "title": "Dell Wyse 5070 Thin Client (Intel J5005, 8GB RAM, Power Supply)",
            "price": 45.00,
            "shipping_price": 0.00,
            "total_price": 45.00,
            "currency": "USD",
            "url": "https://www.ebay.com",
            "image_url": "https://i.ebayimg.com/images/g/m4AAAOSwrRtnlK5M/s-l500.jpg",
            "seller_username": "tested_seller",
            "seller_feedback_score": 1520,
            "seller_positive_percent": 99.8,
            "matching_keywords": "J5005, 8GB, power supply",
            "deal_score": 92,
        }
        target = target_url_or_key.strip()
        if service == "discord":
            success = await cls.send_discord_embed(target, sample_deal, "Test Monitor Rule")
        elif service == "pushbullet":
            success = await cls.send_pushbullet(target, sample_deal, "Test Monitor Rule")
        elif service == "generic":
            success = await cls.send_generic_webhook(target, sample_deal, "Test Monitor Rule")
        else:
            return {"success": False, "message": f"Unsupported notification service '{service}'"}

        return {
            "success": success,
            "message": "Notification sent successfully!" if success else "Failed to send notification. Check logs/URL."
        }

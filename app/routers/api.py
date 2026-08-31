from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import Rule, Deal, ScanLog
from app.schemas import RuleResponse, RuleCreate, DealResponse, ScanLogResponse
from app.services.poller import poller

router = APIRouter(prefix="/api")


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "ebay-deal-monitor"}


@router.get("/status")
def service_status(db: Session = Depends(get_db)):
    rules_count = db.query(Rule).count()
    active_rules_count = db.query(Rule).filter(Rule.is_active == True).count()  # noqa: E712
    deals_count = db.query(Deal).count()
    last_log = db.query(ScanLog).order_by(desc(ScanLog.timestamp)).first()

    return {
        "status": "healthy",
        "rules_total": rules_count,
        "rules_active": active_rules_count,
        "deals_captured": deals_count,
        "poller_interval": poller.get_current_poll_interval(),
        "last_scan": last_log.timestamp.isoformat() if last_log else None,
    }


@router.get("/rules", response_model=List[RuleResponse])
def get_rules(db: Session = Depends(get_db)):
    return db.query(Rule).all()


@router.post("/rules", response_model=RuleResponse)
def create_rule_api(rule_in: RuleCreate, db: Session = Depends(get_db)):
    rule = Rule(**rule_in.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/deals", response_model=List[DealResponse])
def get_deals(
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    rule_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Deal)
    if rule_id:
        query = query.filter(Deal.rule_id == rule_id)
    return query.order_by(desc(Deal.date_found)).offset(offset).limit(limit).all()


@router.post("/scan-all")
async def trigger_scan_all():
    await poller.poll_all_active_rules()
    return {"status": "scan completed"}

from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Rule
from app.services.poller import poller

router = APIRouter(prefix="/rules")
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def rules_page(request: Request, db: Session = Depends(get_db)):
    rules = db.query(Rule).order_by(Rule.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="rules.html",
        context={"rules": rules},
    )


@router.post("/create")
async def create_rule(
    request: Request,
    name: Optional[str] = Form(None),
    search_query: str = Form(...),
    category_id: Optional[str] = Form(None),
    min_price: float = Form(0.0),
    max_price: float = Form(...),
    positive_keywords: Optional[str] = Form(""),
    negative_keywords: Optional[str] = Form(""),
    is_active: bool = Form(False),
    webhook_enabled: bool = Form(False),
    webhook_override_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    rule = Rule(
        name=name.strip() if name else None,
        search_query=search_query.strip(),
        category_id=category_id.strip() if category_id else None,
        min_price=float(min_price),
        max_price=float(max_price),
        positive_keywords=positive_keywords.strip() if positive_keywords else "",
        negative_keywords=negative_keywords.strip() if negative_keywords else "",
        is_active=is_active,
        webhook_enabled=webhook_enabled,
        webhook_override_url=webhook_override_url.strip() if webhook_override_url else None,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return RedirectResponse(url="/rules", status_code=303)


@router.get("/{rule_id}/modal", response_class=HTMLResponse)
async def get_rule_modal(rule_id: int, request: Request, db: Session = Depends(get_db)):
    if rule_id == 0:
        return templates.TemplateResponse(
            request=request,
            name="partials/rule_modal.html",
            context={"rule": None},
        )
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return templates.TemplateResponse(
        request=request,
        name="partials/rule_modal.html",
        context={"rule": rule},
    )



@router.post("/{rule_id}/edit")
async def update_rule(
    rule_id: int,
    name: Optional[str] = Form(None),
    search_query: str = Form(...),
    category_id: Optional[str] = Form(None),
    min_price: float = Form(0.0),
    max_price: float = Form(...),
    positive_keywords: Optional[str] = Form(""),
    negative_keywords: Optional[str] = Form(""),
    is_active: bool = Form(False),
    webhook_enabled: bool = Form(False),
    webhook_override_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.name = name.strip() if name else None
    rule.search_query = search_query.strip()
    rule.category_id = category_id.strip() if category_id else None
    rule.min_price = float(min_price)
    rule.max_price = float(max_price)
    rule.positive_keywords = positive_keywords.strip() if positive_keywords else ""
    rule.negative_keywords = negative_keywords.strip() if negative_keywords else ""
    rule.is_active = is_active
    rule.webhook_enabled = webhook_enabled
    rule.webhook_override_url = webhook_override_url.strip() if webhook_override_url else None

    db.commit()
    return RedirectResponse(url="/rules", status_code=303)


@router.post("/{rule_id}/toggle")
async def toggle_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_active = not rule.is_active
    db.commit()
    return RedirectResponse(url="/rules", status_code=303)


@router.post("/{rule_id}/scan")
async def run_rule_scan_now(rule_id: int):
    """Triggers an instant scan for this rule and returns JSON result."""
    result = await poller.scan_single_rule_now(rule_id)
    return result


@router.post("/{rule_id}/delete")
async def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.delete(rule)
    db.commit()
    return RedirectResponse(url="/rules", status_code=303)

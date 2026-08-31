from typing import Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from app.database import get_db
from app.models import Deal, Rule, Setting

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def query_deals(
    db: Session,
    rule_id: Optional[int] = None,
    sort_by: str = "date",
    status_filter: str = "active",
    search_query: Optional[str] = None,
):
    """Applies filters and ordering to deals query."""
    query = db.query(Deal)

    if rule_id and rule_id > 0:
        query = query.filter(Deal.rule_id == rule_id)

    if status_filter == "active":
        query = query.filter(Deal.is_dismissed == False)  # noqa: E712
    elif status_filter == "starred":
        query = query.filter(Deal.is_starred == True)  # noqa: E712
    elif status_filter == "dismissed":
        query = query.filter(Deal.is_dismissed == True)  # noqa: E712
    # "all" does not filter dismissal status

    if search_query and search_query.strip():
        term = f"%{search_query.strip()}%"
        query = query.filter(Deal.title.ilike(term) | Deal.matching_keywords.ilike(term))

    if sort_by == "price_asc":
        query = query.order_by(asc(Deal.total_price))
    elif sort_by == "price_desc":
        query = query.order_by(desc(Deal.total_price))
    elif sort_by == "score_desc":
        query = query.order_by(desc(Deal.deal_score), desc(Deal.date_found))
    else:  # default: date descending
        query = query.order_by(desc(Deal.date_found))

    return query.all()


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    rule_id: Optional[str] = None,
    sort_by: str = "date",
    status_filter: str = "active",
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    parsed_rule_id = int(rule_id) if rule_id and rule_id.strip().isdigit() else None
    rules = db.query(Rule).all()
    deals = query_deals(db, parsed_rule_id, sort_by, status_filter, q)
    total_deals = db.query(Deal).count()
    starred_count = db.query(Deal).filter(Deal.is_starred == True).count()  # noqa: E712
    app_id_setting = db.query(Setting).filter(Setting.key == "ebay_app_id").first()
    has_ebay_creds = bool(app_id_setting and app_id_setting.value and app_id_setting.value.strip())

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "rules": rules,
            "deals": deals,
            "selected_rule_id": parsed_rule_id,
            "sort_by": sort_by,
            "status_filter": status_filter,
            "q": q or "",
            "total_deals": total_deals,
            "starred_count": starred_count,
            "has_ebay_creds": has_ebay_creds,
        },
    )


@router.get("/deals/partial", response_class=HTMLResponse)
async def deals_partial(
    request: Request,
    rule_id: Optional[str] = None,
    sort_by: str = "date",
    status_filter: str = "active",
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """HTMX partial endpoint for dynamic search, sort, and live refresh."""
    parsed_rule_id = int(rule_id) if rule_id and rule_id.strip().isdigit() else None
    deals = query_deals(db, parsed_rule_id, sort_by, status_filter, q)
    return templates.TemplateResponse(
        request=request,
        name="partials/deals_table.html",
        context={
            "deals": deals,
        },
    )


@router.post("/deals/{deal_id}/star")
async def toggle_star(
    deal_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if deal:
        deal.is_starred = not deal.is_starred
        db.commit()
        db.refresh(deal)
        return templates.TemplateResponse(
            request=request,
            name="partials/deal_card.html",
            context={"deal": deal},
        )
    return Response(status_code=404)


@router.post("/deals/{deal_id}/dismiss")
async def toggle_dismiss(
    deal_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if deal:
        deal.is_dismissed = not deal.is_dismissed
        db.commit()
        db.refresh(deal)
        return templates.TemplateResponse(
            request=request,
            name="partials/deal_card.html",
            context={"deal": deal},
        )
    return Response(status_code=404)


@router.delete("/deals/{deal_id}")
async def delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if deal:
        db.delete(deal)
        db.commit()
        return Response(status_code=200)
    return Response(status_code=404)

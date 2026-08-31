from typing import Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import Setting, ScanLog
from app.services.notifier import Notifier

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory="app/templates")


def get_all_settings(db: Session) -> dict:
    rows = db.query(Setting).all()
    return {row.key: row.value for row in rows}


def save_setting(db: Session, key: str, value: Optional[str]):
    setting = db.query(Setting).filter(Setting.key == key).first()
    if not setting:
        setting = Setting(key=key, value=value)
        db.add(setting)
    else:
        setting.value = value
    db.commit()


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    settings = get_all_settings(db)
    logs = db.query(ScanLog).order_by(desc(ScanLog.timestamp)).limit(50).all()

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "settings": settings,
            "logs": logs,
        },
    )


@router.post("/save")
async def save_settings(
    request: Request,
    ebay_app_id: Optional[str] = Form(None),
    ebay_cert_id: Optional[str] = Form(None),
    ebay_environment: Optional[str] = Form("PRODUCTION"),
    poll_interval_seconds: Optional[int] = Form(120),
    discord_webhook_url: Optional[str] = Form(None),
    pushbullet_api_key: Optional[str] = Form(None),
    generic_webhook_url: Optional[str] = Form(None),
    auto_archive_days: Optional[int] = Form(0),
    db: Session = Depends(get_db),
):
    save_setting(db, "ebay_app_id", ebay_app_id.strip() if ebay_app_id else "")
    save_setting(db, "ebay_cert_id", ebay_cert_id.strip() if ebay_cert_id else "")
    save_setting(db, "ebay_environment", ebay_environment.strip() if ebay_environment else "PRODUCTION")
    save_setting(db, "poll_interval_seconds", str(poll_interval_seconds or 120))
    save_setting(db, "discord_webhook_url", discord_webhook_url.strip() if discord_webhook_url else "")
    save_setting(db, "pushbullet_api_key", pushbullet_api_key.strip() if pushbullet_api_key else "")
    save_setting(db, "generic_webhook_url", generic_webhook_url.strip() if generic_webhook_url else "")
    save_setting(db, "auto_archive_days", str(auto_archive_days or 0))

    return RedirectResponse(url="/settings?saved=true", status_code=303)


@router.post("/test-notification")
async def test_notification(
    service: str = Form(...),
    target: str = Form(...),
):
    """Sends a test alert to Discord, Pushbullet, or Generic Webhook."""
    result = await Notifier.send_test_notification(service, target)
    return JSONResponse(result)


@router.get("/logs/partial", response_class=HTMLResponse)
async def logs_partial(request: Request, db: Session = Depends(get_db)):
    """HTMX polling endpoint for live log streaming."""
    logs = db.query(ScanLog).order_by(desc(ScanLog.timestamp)).limit(50).all()
    return templates.TemplateResponse(
        request=request,
        name="partials/log_stream.html",
        context={"logs": logs},
    )


@router.post("/logs/clear")
async def clear_logs(db: Session = Depends(get_db)):
    """Clears all scan history logs."""
    db.query(ScanLog).delete()
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)

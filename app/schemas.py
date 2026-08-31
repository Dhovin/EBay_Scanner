from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class RuleBase(BaseModel):
    name: Optional[str] = None
    search_query: str = Field(..., min_length=1, max_length=500)
    category_id: Optional[str] = None
    min_price: float = Field(default=0.0, ge=0.0)
    max_price: float = Field(..., gt=0.0)
    positive_keywords: Optional[str] = ""
    negative_keywords: Optional[str] = ""
    is_active: bool = True
    webhook_enabled: bool = True
    webhook_override_url: Optional[str] = None


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    search_query: Optional[str] = None
    category_id: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    positive_keywords: Optional[str] = None
    negative_keywords: Optional[str] = None
    is_active: Optional[bool] = None
    webhook_enabled: Optional[bool] = None
    webhook_override_url: Optional[str] = None


class RuleResponse(RuleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    last_scanned_at: Optional[datetime] = None
    matches_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class DealBase(BaseModel):
    item_id: str
    rule_id: Optional[int] = None
    title: str
    price: float
    shipping_price: float = 0.0
    total_price: float
    currency: str = "USD"
    url: str
    image_url: Optional[str] = None
    seller_username: Optional[str] = None
    seller_feedback_score: Optional[int] = None
    seller_positive_percent: Optional[float] = None
    matching_keywords: str = ""
    deal_score: int = 0
    listing_type: str = "FixedPrice"
    is_starred: bool = False
    is_dismissed: bool = False


class DealResponse(DealBase):
    id: int
    date_found: datetime

    model_config = ConfigDict(from_attributes=True)


class SettingItem(BaseModel):
    key: str
    value: Optional[str] = None


class SettingsUpdate(BaseModel):
    ebay_app_id: Optional[str] = None
    ebay_cert_id: Optional[str] = None
    ebay_environment: Optional[str] = "PRODUCTION"
    poll_interval_seconds: Optional[int] = 120
    discord_webhook_url: Optional[str] = None
    pushbullet_api_key: Optional[str] = None
    generic_webhook_url: Optional[str] = None
    auto_archive_days: Optional[int] = 0


class ScanLogResponse(BaseModel):
    id: int
    timestamp: datetime
    level: str
    message: str
    rule_id: Optional[int] = None
    items_found: int = 0
    items_matched: int = 0

    model_config = ConfigDict(from_attributes=True)

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    search_query = Column(String(500), nullable=False)
    category_id = Column(String(50), nullable=True)
    min_price = Column(Float, default=0.0, nullable=False)
    max_price = Column(Float, nullable=False)
    positive_keywords = Column(Text, default="", nullable=False)  # Comma or newline separated
    negative_keywords = Column(Text, default="", nullable=False)  # Comma or newline separated
    is_active = Column(Boolean, default=True, nullable=False)
    webhook_enabled = Column(Boolean, default=True, nullable=False)
    webhook_override_url = Column(String(1000), nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    last_scanned_at = Column(DateTime, nullable=True)
    matches_count = Column(Integer, default=0, nullable=False)

    deals = relationship("Deal", back_populates="rule", cascade="all, delete-orphan")


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(String(100), unique=True, index=True, nullable=False)
    rule_id = Column(Integer, ForeignKey("rules.id", ondelete="CASCADE"), nullable=True, index=True)
    
    title = Column(String(500), nullable=False)
    price = Column(Float, nullable=False)
    shipping_price = Column(Float, default=0.0, nullable=False)
    total_price = Column(Float, nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    
    url = Column(String(1000), nullable=False)
    image_url = Column(String(1000), nullable=True)
    
    seller_username = Column(String(100), nullable=True)
    seller_feedback_score = Column(Integer, nullable=True)
    seller_positive_percent = Column(Float, nullable=True)
    
    matching_keywords = Column(Text, default="", nullable=False)
    deal_score = Column(Integer, default=0, nullable=False)  # 0 to 100
    listing_type = Column(String(50), default="FixedPrice", nullable=False)
    
    is_starred = Column(Boolean, default=False, nullable=False)
    is_dismissed = Column(Boolean, default=False, nullable=False)
    date_found = Column(DateTime, default=utc_now, nullable=False, index=True)
    raw_data = Column(Text, nullable=True)

    rule = relationship("Rule", back_populates="deals")

    __table_args__ = (
        Index("idx_deal_score_date", "deal_score", "date_found"),
    )


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class ScanLog(Base):
    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)
    level = Column(String(20), default="INFO", nullable=False)  # INFO, SUCCESS, WARNING, ERROR
    message = Column(Text, nullable=False)
    rule_id = Column(Integer, nullable=True)
    items_found = Column(Integer, default=0, nullable=False)
    items_matched = Column(Integer, default=0, nullable=False)

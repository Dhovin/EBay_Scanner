import pytest
from app.services.filter_engine import FilterEngine


def test_parse_keywords():
    raw = "J5005, Pentium, 8GB\npower adapter,  TEST "
    parsed = FilterEngine.parse_keywords(raw)
    assert parsed == ["j5005", "pentium", "8gb", "power adapter", "test"]

    assert FilterEngine.parse_keywords("") == []
    assert FilterEngine.parse_keywords(None) == []


def test_evaluate_item_price_limit():
    item = {
        "title": "Dell Wyse 5070 Thin Client",
        "price": 65.00,
        "shipping_price": 5.00,
        "total_price": 70.00,
    }

    # Max price $60 - should be rejected
    is_match, score, kws, reason = FilterEngine.evaluate_item(
        item=item,
        max_price=60.00,
        min_price=0.0,
    )
    assert not is_match
    assert "exceeds max" in reason


def test_evaluate_item_min_price():
    item = {
        "title": "Dell Wyse 5070 Thin Client",
        "price": 5.00,
        "shipping_price": 0.00,
        "total_price": 5.00,
    }

    # Min price $20 - should be rejected
    is_match, score, kws, reason = FilterEngine.evaluate_item(
        item=item,
        max_price=100.00,
        min_price=20.0,
    )
    assert not is_match
    assert "below min" in reason


def test_evaluate_item_negative_keyword():
    item = {
        "title": "Dell Wyse 5070 (NO POWER ADAPTER, PARTS ONLY)",
        "price": 30.00,
        "shipping_price": 10.00,
        "total_price": 40.00,
    }

    is_match, score, kws, reason = FilterEngine.evaluate_item(
        item=item,
        max_price=60.00,
        positive_kw_str="J5005, 8GB",
        negative_kw_str="parts only, broken, as-is",
    )
    assert not is_match
    assert "parts only" in reason


def test_evaluate_item_positive_keywords_and_scoring():
    item = {
        "title": "Dell Wyse 5070 Extended Intel J5005 8GB RAM 32GB eMMC Power Adapter",
        "price": 35.00,
        "shipping_price": 5.00,
        "total_price": 40.00,
        "seller_positive_percent": 99.8,
    }

    is_match, score, matched_kws, reason = FilterEngine.evaluate_item(
        item=item,
        max_price=80.00,
        positive_kw_str="J5005, 8GB, power adapter",
        negative_kw_str="parts only, broken",
    )

    assert is_match
    assert reason is None
    assert "j5005" in matched_kws
    assert "8gb" in matched_kws
    assert "power adapter" in matched_kws
    # 50% savings (25 pts), 3/3 kws (40 pts), 99.8% seller (10 pts) -> score around 75
    assert 70 <= score <= 100

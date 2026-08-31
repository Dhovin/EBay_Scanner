from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db, SessionLocal
from app.models import Rule, Deal, Setting


def setup_module():
    """Ensure database schema is created for test run."""
    init_db()


def test_health_check():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status_endpoint():
    client = TestClient(app)
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "rules_total" in data
    assert "deals_captured" in data


def test_html_pages_render():
    client = TestClient(app)

    # Dashboard
    res_dash = client.get("/")
    assert res_dash.status_code == 200
    assert "Deals Dashboard" in res_dash.text

    # Rules
    res_rules = client.get("/rules")
    assert res_rules.status_code == 200
    assert "Search Monitors" in res_rules.text

    # Settings
    res_settings = client.get("/settings")
    assert res_settings.status_code == 200
    assert "Settings &amp; Diagnostics" in res_settings.text or "Settings & Diagnostics" in res_settings.text


def test_rule_crud_lifecycle():
    client = TestClient(app)

    # Create rule via form POST
    form_data = {
        "name": "Integration Test Wyse",
        "search_query": "Dell Wyse 5070",
        "min_price": "10.00",
        "max_price": "65.00",
        "positive_keywords": "J5005, 8GB",
        "negative_keywords": "broken, as-is",
        "is_active": "true",
        "webhook_enabled": "true",
    }
    create_res = client.post("/rules/create", data=form_data, follow_redirects=False)
    assert create_res.status_code in (302, 303)

    # Find created rule in DB
    with SessionLocal() as db:
        rule = db.query(Rule).filter(Rule.name == "Integration Test Wyse").first()
        assert rule is not None
        rule_id = rule.id
        assert rule.max_price == 65.00
        assert rule.is_active is True

    # Test Rule Modal render
    modal_res = client.get(f"/rules/{rule_id}/modal")
    assert modal_res.status_code == 200
    assert "Edit Search Monitor" in modal_res.text

    # Toggle Rule
    toggle_res = client.post(f"/rules/{rule_id}/toggle", follow_redirects=False)
    assert toggle_res.status_code in (302, 303)
    with SessionLocal() as db:
        rule = db.query(Rule).filter(Rule.id == rule_id).first()
        assert rule.is_active is False

    # Delete Rule
    delete_res = client.post(f"/rules/{rule_id}/delete", follow_redirects=False)
    assert delete_res.status_code in (302, 303)
    with SessionLocal() as db:
        rule = db.query(Rule).filter(Rule.id == rule_id).first()
        assert rule is None


def test_deal_actions_and_partials():
    client = TestClient(app)

    import uuid
    test_item_id = f"TEST-ITEM-{uuid.uuid4().hex[:8]}"

    # Insert a dummy deal directly
    with SessionLocal() as db:
        deal = Deal(
            item_id=test_item_id,
            title="Dell Wyse 5070 J5005 8GB Desktop",
            price=40.00,
            shipping_price=5.00,
            total_price=45.00,
            currency="USD",
            url=f"https://www.ebay.com/itm/{test_item_id}",
            matching_keywords="J5005, 8GB",
            deal_score=85,
        )
        db.add(deal)
        db.commit()
        deal_id = deal.id

    # Test deals partial
    part_res = client.get("/deals/partial")
    assert part_res.status_code == 200
    assert test_item_id in part_res.text or "Dell Wyse 5070" in part_res.text

    # Star deal
    star_res = client.post(f"/deals/{deal_id}/star")
    assert star_res.status_code == 200
    with SessionLocal() as db:
        updated = db.query(Deal).filter(Deal.id == deal_id).first()
        assert updated.is_starred is True

    # Dismiss deal
    dismiss_res = client.post(f"/deals/{deal_id}/dismiss")
    assert dismiss_res.status_code == 200
    with SessionLocal() as db:
        updated = db.query(Deal).filter(Deal.id == deal_id).first()
        assert updated.is_dismissed is True

    # Delete deal
    del_res = client.delete(f"/deals/{deal_id}")
    assert del_res.status_code == 200
    with SessionLocal() as db:
        deleted = db.query(Deal).filter(Deal.id == deal_id).first()
        assert deleted is None

import pytest
from app.services.ebay_client import EbayClient


def test_extract_price_and_shipping():
    client = EbayClient()

    # Free shipping
    title = "Dell Wyse 5070 Slim Desktop Computer $45.00 Free shipping"
    summary = "Fast Intel CPU, in good condition."
    price, shipping = client._extract_price_and_shipping(title, summary)
    assert price == 45.00
    assert shipping == 0.00

    # With shipping cost
    title2 = "Dell Wyse 5070 Thin Client"
    summary2 = "Price: $39.99 + $8.50 shipping. Includes original adapter."
    price2, shipping2 = client._extract_price_and_shipping(title2, summary2)
    assert price2 == 39.99
    assert shipping2 == 8.50


def test_has_api_credentials():
    client_empty = EbayClient()
    assert not client_empty.has_api_credentials

    client_with_creds = EbayClient(app_id="app123", cert_id="cert456")
    assert client_with_creds.has_api_credentials

import base64
import logging
import re
import time
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx
import feedparser

logger = logging.getLogger("ebay_client")


class EbayClient:
    """Handles data ingestion from eBay Browse API with fallback to RSS feeds."""

    def __init__(
        self,
        app_id: Optional[str] = None,
        cert_id: Optional[str] = None,
        environment: str = "PRODUCTION",
    ):
        self.app_id = (app_id or "").strip()
        self.cert_id = (cert_id or "").strip()
        self.environment = environment.upper()
        self._oauth_token: Optional[str] = None
        self._token_expires_at: float = 0
        self.last_status_message: Optional[str] = None

    @property
    def has_api_credentials(self) -> bool:
        return bool(self.app_id and self.cert_id)

    @property
    def oauth_endpoint(self) -> str:
        if self.environment == "SANDBOX":
            return "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
        return "https://api.ebay.com/identity/v1/oauth2/token"

    @property
    def browse_endpoint(self) -> str:
        if self.environment == "SANDBOX":
            return "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
        return "https://api.ebay.com/buy/browse/v1/item_summary/search"

    async def get_access_token(self, client: httpx.AsyncClient) -> Optional[str]:
        """Fetch or return cached OAuth 2.0 Application access token."""
        if not self.has_api_credentials:
            return None

        # Return cached token if valid with 60s buffer
        if self._oauth_token and time.time() < (self._token_expires_at - 60):
            return self._oauth_token

        try:
            credentials = f"{self.app_id}:{self.cert_id}".encode("utf-8")
            b64_creds = base64.b64encode(credentials).decode("utf-8")

            headers = {
                "Authorization": f"Basic {b64_creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            data = {
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            }

            response = await client.post(
                self.oauth_endpoint,
                headers=headers,
                data=data,
                timeout=15.0,
            )

            if response.status_code == 200:
                payload = response.json()
                self._oauth_token = payload.get("access_token")
                expires_in = payload.get("expires_in", 7200)
                self._token_expires_at = time.time() + float(expires_in)
                logger.info("Successfully fetched eBay OAuth access token.")
                return self._oauth_token
            else:
                logger.warning(
                    f"eBay OAuth error: HTTP {response.status_code} - {response.text}"
                )
                return None
        except Exception as exc:
            logger.error(f"Failed to authenticate with eBay OAuth: {exc}")
            return None

    async def search_items(
        self,
        query: str,
        category_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search items using Browse API if credentials are set, else fallback to RSS."""
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            token = await self.get_access_token(client)
            if token:
                try:
                    items = await self._search_browse_api(client, token, query, category_id, limit)
                    if items is not None:
                        return items
                except Exception as exc:
                    logger.warning(f"Browse API search error: {exc}. Falling back to RSS feed.")

            # Fallback to RSS feed parsing
            return await self._search_rss(client, query, category_id)

    async def _search_browse_api(
        self,
        client: httpx.AsyncClient,
        token: str,
        query: str,
        category_id: Optional[str],
        limit: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """Queries the eBay Browse API v1 item_summary/search."""
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            "Content-Type": "application/json",
        }

        # Filter Buy It Now (fixed price) listings only
        params = {
            "q": query,
            "filter": "buyingOptions:{FIXED_PRICE}",
            "sort": "newlyListed",
            "limit": str(min(limit, 100)),
        }
        if category_id:
            params["category_ids"] = str(category_id)

        response = await client.get(self.browse_endpoint, headers=headers, params=params)

        if response.status_code != 200:
            logger.warning(f"Browse API query returned HTTP {response.status_code}: {response.text}")
            return None

        data = response.json()
        raw_items = data.get("itemSummaries", [])
        parsed_items: List[Dict[str, Any]] = []

        for item in raw_items:
            try:
                item_id = item.get("itemId", "")
                if not item_id:
                    continue

                # Parse price
                price_dict = item.get("price", {})
                price = float(price_dict.get("value", 0.0))
                currency = price_dict.get("currency", "USD")

                # Parse shipping
                shipping_price = 0.0
                shipping_options = item.get("shippingOptions", [])
                if shipping_options:
                    ship_cost = shipping_options[0].get("shippingCost", {})
                    shipping_price = float(ship_cost.get("value", 0.0))

                total_price = round(price + shipping_price, 2)

                # Parse image
                image_dict = item.get("image", {})
                image_url = image_dict.get("imageUrl")
                if not image_url and item.get("additionalImages"):
                    image_url = item["additionalImages"][0].get("imageUrl")

                # Parse seller
                seller = item.get("seller", {})
                seller_username = seller.get("username")
                seller_score_str = seller.get("feedbackScore")
                seller_feedback_score = int(seller_score_str) if seller_score_str else None
                seller_percent_str = seller.get("feedbackPercentage")
                seller_positive_percent = float(seller_percent_str) if seller_percent_str else None

                parsed_items.append({
                    "item_id": item_id,
                    "title": item.get("title", ""),
                    "price": price,
                    "shipping_price": shipping_price,
                    "total_price": total_price,
                    "currency": currency,
                    "url": item.get("itemWebUrl", ""),
                    "image_url": image_url,
                    "seller_username": seller_username,
                    "seller_feedback_score": seller_feedback_score,
                    "seller_positive_percent": seller_positive_percent,
                    "listing_type": "FixedPrice",
                    "raw_data": str(item),
                })
            except Exception as item_err:
                logger.debug(f"Failed to parse Browse API item: {item_err}")
                continue

        return parsed_items

    async def _search_rss(
        self,
        client: httpx.AsyncClient,
        query: str,
        category_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Parses eBay RSS search feed for Buy It Now newly listed items."""
        encoded_query = urllib.parse.quote_plus(query)
        # _sop=10 (newly listed), LH_BIN=1 (Buy It Now only), _rss=1
        rss_url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&_sop=10&LH_BIN=1&_rss=1"
        if category_id:
            rss_url += f"&_sacat={urllib.parse.quote_plus(str(category_id))}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }

        try:
            response = await client.get(rss_url, headers=headers)
            if response.status_code != 200:
                logger.warning(f"eBay RSS request returned HTTP {response.status_code}")
                if response.status_code in (403, 418):
                    self.last_status_message = (
                        f"eBay public RSS returned HTTP {response.status_code} (native RSS feeds discontinued by eBay). "
                        "Please add your free eBay App ID and Cert ID in Settings to enable the Browse API."
                    )
                else:
                    self.last_status_message = f"eBay RSS request returned HTTP {response.status_code}"
                return []

            content = response.text
            feed = feedparser.parse(content)
            parsed_items: List[Dict[str, Any]] = []

            for entry in feed.entries:
                try:
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    
                    # Extract Item ID from URL
                    match = re.search(r"/itm/(?:.*?/)?(\d{9,14})", link)
                    if match:
                        item_id = match.group(1)
                    else:
                        match_alt = re.search(r"(\d{9,14})", link)
                        item_id = match_alt.group(1) if match_alt else link

                    # Clean tracking parameters from link
                    clean_url = link.split("?")[0] if "?" in link else link

                    summary = entry.get("summary", "")
                    
                    # Extract Price from summary or title
                    price, shipping = self._extract_price_and_shipping(title, summary)
                    total_price = round(price + shipping, 2)

                    # Extract Image thumbnail
                    image_url = None
                    if "media_thumbnail" in entry and entry.media_thumbnail:
                        image_url = entry.media_thumbnail[0].get("url")
                    elif "enclosures" in entry and entry.enclosures:
                        image_url = entry.enclosures[0].get("href")
                    
                    if not image_url and summary:
                        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary, re.IGNORECASE)
                        if img_match:
                            image_url = img_match.group(1)

                    parsed_items.append({
                        "item_id": item_id,
                        "title": title,
                        "price": price,
                        "shipping_price": shipping,
                        "total_price": total_price,
                        "currency": "USD",
                        "url": clean_url,
                        "image_url": image_url,
                        "seller_username": None,
                        "seller_feedback_score": None,
                        "seller_positive_percent": None,
                        "listing_type": "FixedPrice",
                        "raw_data": str(entry),
                    })
                except Exception as entry_err:
                    logger.debug(f"Failed to parse RSS entry: {entry_err}")
                    continue

            return parsed_items
        except Exception as exc:
            logger.error(f"Error fetching/parsing eBay RSS feed for '{query}': {exc}")
            return []

    def _extract_price_and_shipping(self, title: str, summary: str) -> tuple[float, float]:
        """Extract price and shipping from eBay RSS title or summary HTML."""
        combined_text = f"{title} {summary}"
        
        # Look for shipping cost e.g. "Free shipping", "+$5.99 shipping", "$12.50 Shipping"
        shipping = 0.0
        ship_match = re.search(r"\+\s*\$([0-9]+(?:\.[0-9]{2})?)\s+shipping", combined_text, re.IGNORECASE)
        if ship_match:
            try:
                shipping = float(ship_match.group(1))
            except ValueError:
                shipping = 0.0

        # Look for dollar amounts e.g. "$45.00" or "$45"
        price_matches = re.findall(r"\$([0-9]+(?:\.[0-9]{2})?)", combined_text)
        price = 0.0
        if price_matches:
            try:
                # First price match usually represents item price
                price = float(price_matches[0])
            except ValueError:
                price = 0.0

        return price, shipping

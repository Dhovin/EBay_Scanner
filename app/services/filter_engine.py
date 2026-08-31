import re
from typing import List, Dict, Any, Optional, Tuple


class FilterEngine:
    """Evaluates raw eBay listings against user search rules and calculates Deal Scores."""

    @staticmethod
    def parse_keywords(kw_string: Optional[str]) -> List[str]:
        """Parses a comma or newline separated string of keywords into lowercase stripped tokens."""
        if not kw_string:
            return []
        raw_list = re.split(r"[\n,]+", kw_string)
        return [k.strip().lower() for k in raw_list if k.strip()]

    @classmethod
    def evaluate_item(
        cls,
        item: Dict[str, Any],
        max_price: float,
        min_price: float = 0.0,
        positive_kw_str: Optional[str] = "",
        negative_kw_str: Optional[str] = "",
    ) -> Tuple[bool, int, List[str], Optional[str]]:
        """
        Evaluates whether an item matches rule criteria.
        Returns:
            (is_match: bool, deal_score: int, matched_positive_keywords: list, rejection_reason: str|None)
        """
        title = item.get("title", "")
        title_lower = title.lower()
        total_price = float(item.get("total_price", 0.0))

        # Check Price Bounds
        if total_price > max_price:
            return False, 0, [], f"Total price (${total_price:.2f}) exceeds max (${max_price:.2f})"

        if min_price > 0 and total_price < min_price:
            return False, 0, [], f"Total price (${total_price:.2f}) below min (${min_price:.2f})"

        # Check Negative Keywords (immediate discard)
        negative_keywords = cls.parse_keywords(negative_kw_str)
        for neg_kw in negative_keywords:
            # Word boundary or phrase check
            pattern = rf"\b{re.escape(neg_kw)}\b" if len(neg_kw.split()) == 1 else re.escape(neg_kw)
            if re.search(pattern, title_lower):
                return False, 0, [], f"Matched negative keyword: '{neg_kw}'"

        # Check Positive Keywords
        positive_keywords = cls.parse_keywords(positive_kw_str)
        matched_positive = []
        for pos_kw in positive_keywords:
            pattern = rf"\b{re.escape(pos_kw)}\b" if len(pos_kw.split()) == 1 else re.escape(pos_kw)
            if re.search(pattern, title_lower):
                matched_positive.append(pos_kw)

        # Calculate Deal Score (0-100)
        # Factor 1: Price savings below max price (Up to 50 pts)
        if max_price > 0:
            savings_pct = max(0.0, (max_price - total_price) / max_price)
            price_score = min(50, int(savings_pct * 50))
        else:
            price_score = 25

        # Factor 2: Positive keyword match ratio (Up to 40 pts)
        if positive_keywords:
            kw_ratio = len(matched_positive) / len(positive_keywords)
            keyword_score = int(kw_ratio * 40)
        else:
            keyword_score = 20  # Neutral baseline if rule has no positive keywords

        # Factor 3: Seller rating boost (Up to 10 pts)
        seller_percent = item.get("seller_positive_percent")
        if seller_percent is not None:
            if seller_percent >= 99.0:
                seller_score = 10
            elif seller_percent >= 97.0:
                seller_score = 8
            elif seller_percent >= 95.0:
                seller_score = 6
            elif seller_percent >= 90.0:
                seller_score = 4
            else:
                seller_score = 0
        else:
            seller_score = 5  # Default neutral when rating not available (e.g. RSS)

        total_deal_score = min(100, max(0, price_score + keyword_score + seller_score))

        return True, total_deal_score, matched_positive, None

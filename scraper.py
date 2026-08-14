from __future__ import annotations

import json
import re
from typing import Dict, Optional, Tuple

from playwright.sync_api import Page, sync_playwright

from config import HEADLESS_BROWSER, REQUEST_TIMEOUT_SECONDS


class ScraperError(Exception):
    pass


REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


ANTI_BOT_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
)


PRICE_SELECTORS = (
    "div.Nx9bqj",
    "div._30jeq3",
    "div._16bR3d",
    "span._1vC2OE",
    "span._30jeq3",
    "div._25b18c",
    "div._1vC4OE",
    "span.a-price-whole",
    "span#priceblock_ourprice",
    "span.a-offscreen",
    ".pdp-price",
    ".Price__Component",
)

TITLE_SELECTORS = (
    "span.B_NuCI",
    "h1._631n2p",
    "span.VU-VGd",
    "span#productTitle",
    "h1",
)

META_PRICE_SELECTORS = (
    "meta[property='product:price:amount']",
    "meta[itemprop='price']",
    "meta[name='price']",
)


def _clean_price(raw_value: Optional[str]) -> Optional[float]:
    if not raw_value:
        return None
    cleaned = raw_value.replace("₹", "").replace("Rs.", "").replace("Rs", "")
    cleaned = cleaned.replace(",", "").strip()
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    if not cleaned or cleaned in {"-", "."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _is_in_stock(text: Optional[str]) -> int:
    if not text:
        return 0
    lowered = text.lower()
    if any(token in lowered for token in ["out of stock", "unavailable", "sold out", "currently unavailable", "not available"]):
        return 0
    if any(token in lowered for token in ["in stock", "available", "add to cart", "buy now", "add to bag", "buy now", "shipping soon"]):
        return 1
    return 0


def _extract_with_selector(page: Page, selector: str) -> Optional[str]:
    try:
        locator = page.locator(selector).first
        if locator.count() > 0:
            if selector.startswith("meta"):
                value = locator.get_attribute("content")
            else:
                value = locator.inner_text(timeout=2000)
            if value and value.strip():
                return value.strip()
    except Exception:
        pass
    return None


def _extract_texts(page: Page, selector: str) -> list[str]:
    texts: list[str] = []
    try:
        locator = page.locator(selector)
        count = locator.count()
        for index in range(count):
            try:
                value = locator.nth(index).inner_text(timeout=2000)
                if value and value.strip():
                    texts.append(value.strip())
            except Exception:
                continue
    except Exception:
        pass
    return texts


def _extract_price_candidates(page: Page, selector: str) -> list[float]:
    prices: list[float] = []
    if selector == "span.a-price-whole":
        whole_texts = _extract_texts(page, "span.a-price-whole")
        fraction_texts = _extract_texts(page, "span.a-price-fraction")
        for index, whole in enumerate(whole_texts):
            fraction = fraction_texts[index] if index < len(fraction_texts) else ""
            candidate = f"{whole}.{fraction}" if fraction else whole
            cleaned = _clean_price(candidate)
            if cleaned is not None:
                prices.append(cleaned)
    else:
        for raw_text in _extract_texts(page, selector):
            cleaned = _clean_price(raw_text)
            if cleaned is not None:
                prices.append(cleaned)
    return prices


def _extract_stock_status(page: Page, price_found: bool) -> int:
    positive_texts = [
        "add to cart",
        "add to bag",
        "buy now",
        "buy",
        "in stock",
        "available",
        "usually dispatched",
        "usually ships in",
        "avail",
    ]
    negative_texts = [
        "out of stock",
        "unavailable",
        "sold out",
        "currently unavailable",
        "not available",
        "temporarily unavailable",
    ]
    positive_locators = [
        "button:has-text(\"Add to cart\")",
        "button:has-text(\"Add to bag\")",
        "button:has-text(\"Buy now\")",
        "button:has-text(\"Buy\")",
        "button:has-text(\"ADD TO CART\")",
        "button:has-text(\"ADD TO BAG\")",
        "button:has-text(\"BUY NOW\")",
    ]

    try:
        body_text = page.locator("body").inner_text(timeout=5000) or ""
    except Exception:
        body_text = ""

    lowered_body = body_text.lower()
    if any(token in lowered_body for token in negative_texts):
        if any(token in lowered_body for token in positive_texts):
            return 1
        return 0
    if any(token in lowered_body for token in positive_texts):
        return 1

    for selector in positive_locators:
        try:
            if page.locator(selector).count() > 0:
                return 1
        except Exception:
            continue

    return 1 if price_found else 0


def _extract_json_ld_price(page: Page) -> Optional[str]:
    try:
        scripts = page.locator("script[type='application/ld+json']")
        for index in range(scripts.count()):
            raw = scripts.nth(index).inner_text(timeout=2000)
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                price = parsed.get("offers", {}).get("price")
                if price is not None:
                    return str(price)
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        price = item.get("offers", {}).get("price")
                        if price is not None:
                            return str(price)
    except Exception:
        pass
    return None


def _extract_regex_price(page: Page) -> Optional[str]:
    try:
        text = page.locator("body").inner_text(timeout=5000)
        regex = re.search(r"(?:₹|Rs\.?)[\s]*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)", text)
        if regex:
            return regex.group(1)
        regex = re.search(r'"price":\s*"?([0-9]+)"?', text)
        if regex:
            return regex.group(1)
    except Exception:
        pass
    return None


def scrape_product(url: str) -> Dict[str, Optional[object]]:
    title = "Product"
    price: Optional[float] = None
    in_stock = 0

    if not url:
        return {"title": title, "price": 0.0, "in_stock": in_stock}

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=HEADLESS_BROWSER,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                ],
            )
            context = browser.new_context(
                user_agent=REALISTIC_USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                },
            )
            context.add_init_script(ANTI_BOT_SCRIPT)
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.evaluate("window.scrollBy(0, 300)")
            page.wait_for_timeout(4000)

            for selector in TITLE_SELECTORS:
                extracted = _extract_with_selector(page, selector)
                if extracted:
                    title = extracted
                    break

            price_candidates: list[float] = []
            for selector in PRICE_SELECTORS:
                price_candidates.extend(_extract_price_candidates(page, selector))
            if price_candidates:
                price = min(price_candidates)

            if price is None:
                for selector in META_PRICE_SELECTORS:
                    extracted = _extract_with_selector(page, selector)
                    if extracted:
                        price = _clean_price(extracted)
                        if price is not None:
                            break

            if price is None:
                extracted = _extract_json_ld_price(page)
                price = _clean_price(extracted)

            if price is None:
                extracted = _extract_regex_price(page)
                price = _clean_price(extracted)

            price_found = price is not None and price > 0
            in_stock = _extract_stock_status(page, price_found)

            if price is None:
                body_text = page.locator("body").inner_text(timeout=5000)
                print(f"[scraper] price not found, body length={len(body_text)}")

            page.close()
            context.close()
            browser.close()
    except Exception:
        return {"title": title, "price": 0.0 if price is None else price, "in_stock": in_stock}

    return {"title": title, "price": 0.0 if price is None else price, "in_stock": in_stock}


__all__ = ["scrape_product", "ScraperError"]

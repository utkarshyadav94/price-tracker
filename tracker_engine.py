from __future__ import annotations

from typing import Optional

from database import add_product, get_all_products, log_price
from scraper import scrape_product
from telegram_bot import send_price_alert


def run_tracker_once() -> list[dict]:
    results: list[dict] = []
    products = get_all_products()
    for product in products:
        try:
            data = scrape_product(product["url"])
            title = data.get("title") or product["title"] or "Untitled product"
            price = data.get("price")
            in_stock = int(data.get("in_stock", 0))

            if product["id"] is None:
                continue

            log_price(product["id"], price, in_stock)

            previous_records = []
            from database import get_price_history

            previous_records = get_price_history(product["id"])
            previous_price = None
            if len(previous_records) >= 2:
                previous_price = previous_records[-2]["price"]
            elif len(previous_records) == 1:
                previous_price = previous_records[-1]["price"]

            target_price = product["target_price"]
            should_alert = False
            event_type = "price_drop"

            if previous_price is not None and price is not None:
                if price < previous_price:
                    should_alert = True
                elif previous_price == 0 and price is not None and price > 0:
                    should_alert = True
            if in_stock == 1 and previous_price is not None and price is not None and target_price is not None and price <= target_price:
                should_alert = True
                event_type = "price_drop"
            if previous_price is not None and price is not None and in_stock == 1 and previous_records and previous_records[-1]["in_stock"] == 0:
                should_alert = True
                event_type = "restock"

            if should_alert:
                send_price_alert(
                    product_title=title,
                    current_price=price,
                    previous_price=previous_price,
                    in_stock=in_stock,
                    event_type=event_type,
                )

            results.append(
                {
                    "id": product["id"],
                    "title": title,
                    "price": price,
                    "in_stock": in_stock,
                    "target_price": target_price,
                }
            )
        except Exception:
            results.append(
                {
                    "id": product["id"],
                    "title": product["title"] or "Untitled product",
                    "price": None,
                    "in_stock": 0,
                    "target_price": product["target_price"],
                }
            )

    return results


if __name__ == "__main__":
    run_tracker_once()

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


def _normalize_chat_id(chat_id: Any) -> Optional[int]:
    if chat_id is None:
        return None
    if isinstance(chat_id, int):
        return chat_id
    if isinstance(chat_id, str):
        value = chat_id.strip()
        if value.startswith("-") and value[1:].isdigit():
            return int(value)
        if value.isdigit():
            return int(value)
    return None


def validate_telegram_settings(
    token: Optional[str] = None,
    chat_id: Optional[Any] = None,
) -> Tuple[bool, str]:
    token_value = token if token is not None else TELEGRAM_BOT_TOKEN
    chat_id_value = chat_id if chat_id is not None else TELEGRAM_CHAT_ID

    if not isinstance(token_value, str) or not token_value.strip():
        return False, "Telegram bot token is missing."

    parts = token_value.split(":")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].strip():
        return False, "Telegram bot token format is invalid. Expected '<numeric-id>:<token>'"

    normalized_chat_id = _normalize_chat_id(chat_id_value)
    if normalized_chat_id is None:
        return False, "Telegram chat ID is invalid."

    return True, "Telegram settings look valid."


def format_alert_message(
    product_title: str,
    current_price: Optional[float],
    previous_price: Optional[float] = None,
    in_stock: Optional[int] = None,
    event_type: str = "price_drop",
) -> str:
    title = product_title or "Tracked product"
    current = current_price if current_price is not None else "N/A"
    previous = previous_price if previous_price is not None else "N/A"

    if event_type == "restock":
        stock_status = "In stock" if in_stock else "Out of stock"
        return (
            f"<b>Restock alert</b>\n"
            f"Product: {title}\n"
            f"Current price: {current}\n"
            f"Previous price: {previous}\n"
            f"Status: {stock_status}"
        )

    return (
        f"<b>Price alert</b>\n"
        f"Product: {title}\n"
        f"Current price: {current}\n"
        f"Previous price: {previous}"
    )


def send_telegram_message(
    message: str,
    token: Optional[str] = None,
    chat_id: Optional[Any] = None,
) -> Optional[dict]:
    is_valid, error_message = validate_telegram_settings(token, chat_id)
    if not is_valid:
        logger.warning("Telegram send skipped: %s", error_message)
        return None

    token_value = token if token is not None else TELEGRAM_BOT_TOKEN
    chat_id_value = _normalize_chat_id(chat_id if chat_id is not None else TELEGRAM_CHAT_ID)
    if chat_id_value is None:
        logger.warning("Telegram send skipped: chat ID could not be normalized.")
        return None

    url = f"https://api.telegram.org/bot{token_value}/sendMessage"
    payload = {
        "chat_id": chat_id_value,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Telegram request failed: %s", exc)
        return None

    try:
        body = response.json()
    except ValueError:
        logger.warning("Telegram API returned invalid JSON.")
        return None

    if not body.get("ok", False):
        logger.warning("Telegram API rejected the message: %s", body)
        return None

    return body


def send_price_alert(
    product_title: str,
    current_price: Optional[float],
    previous_price: Optional[float] = None,
    in_stock: Optional[int] = None,
    event_type: str = "price_drop",
    token: Optional[str] = None,
    chat_id: Optional[Any] = None,
) -> Optional[dict]:
    message = format_alert_message(
        product_title=product_title,
        current_price=current_price,
        previous_price=previous_price,
        in_stock=in_stock,
        event_type=event_type,
    )
    return send_telegram_message(message, token=token, chat_id=chat_id)


__all__ = [
    "validate_telegram_settings",
    "format_alert_message",
    "send_telegram_message",
    "send_price_alert",
]

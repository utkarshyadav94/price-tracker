from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                target_price REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                price REAL,
                in_stock INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def add_product(url: str, target_price: Optional[float] = None, title: Optional[str] = None) -> Optional[int]:
    if not url or not url.startswith(("http://", "https://")):
        return None

    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO products (url, title, target_price, created_at) VALUES (?, ?, ?, ?)",
            (url.strip(), title or "", target_price, datetime.utcnow().isoformat()),
        )
        conn.commit()
        return cursor.lastrowid if cursor.lastrowid else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def get_all_products() -> List[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, url, title, target_price, created_at FROM products ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()


def delete_product(product_id: int) -> bool:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM price_history WHERE product_id = ?", (product_id,))
        cursor = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def log_price(product_id: int, price: Optional[float], in_stock: Optional[int]) -> bool:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO price_history (product_id, price, in_stock, timestamp) VALUES (?, ?, ?, ?)",
            (product_id, price, in_stock, datetime.utcnow().isoformat()),
        )
        conn.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def get_price_history(product_id: int) -> List[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT price, in_stock, timestamp FROM price_history WHERE product_id = ? ORDER BY timestamp ASC",
            (product_id,),
        ).fetchall()
    finally:
        conn.close()


def get_latest_price(product_id: int) -> Tuple[Optional[float], int]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT price, in_stock FROM price_history WHERE product_id = ? ORDER BY timestamp DESC LIMIT 1",
            (product_id,),
        ).fetchone()
        if row:
            return row["price"], int(row["in_stock"] or 0)
        return None, 0
    finally:
        conn.close()


initialize_database()

__all__ = [
    "get_connection",
    "initialize_database",
    "add_product",
    "get_all_products",
    "delete_product",
    "log_price",
    "get_price_history",
]

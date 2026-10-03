"""Database helpers."""

import os
import sqlite3

from app.config import DATABASE_PATH


def create_connection(path: str | None = None) -> sqlite3.Connection:
    """Create a SQLite database connection using the configured path.

    The orders table is created lazily so the fixture runs standalone.
    """
    target = path or DATABASE_PATH
    connection = sqlite3.connect(target)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS orders ("
        "order_id TEXT PRIMARY KEY, username TEXT, total_charged REAL)"
    )
    return connection


def save_order(order_id: str, username: str, total_charged: float) -> None:
    connection = create_connection()
    try:
        connection.execute(
            "INSERT OR REPLACE INTO orders VALUES (?, ?, ?)",
            (order_id, username, total_charged),
        )
        connection.commit()
    finally:
        connection.close()


def orders_for(username: str) -> list[sqlite3.Row]:
    connection = create_connection()
    try:
        return connection.execute(
            "SELECT order_id, total_charged FROM orders WHERE username = ?",
            (username,),
        ).fetchall()
    finally:
        connection.close()


DEFAULT_PATH = os.environ.get("ORDERS_DB", "orders.db")  # kept for reference

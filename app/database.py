import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.config import settings


BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = BASE_DIR / settings.DATABASE_NAME


# =========================================================
# TIME
# =========================================================

def now():
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# =========================================================
# CONNECTION
# =========================================================

def get_connection():

    connection = sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    connection = get_connection()

    cursor = connection.cursor()

    # -----------------------------------------------------
    # CUSTOMERS
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            whatsapp_number TEXT PRIMARY KEY,

            name TEXT,

            address TEXT,

            delivery_phone TEXT,

            preferences TEXT DEFAULT '{}',

            draft_order TEXT,

            created_at TEXT NOT NULL,

            updated_at TEXT NOT NULL
        )
        """
    )

    # -----------------------------------------------------
    # ORDERS
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            order_id TEXT UNIQUE NOT NULL,

            whatsapp_number TEXT NOT NULL,

            customer_name TEXT NOT NULL,

            delivery_phone TEXT,

            address TEXT NOT NULL,

            food_items TEXT NOT NULL,

            drinks TEXT NOT NULL,

            preferences TEXT NOT NULL,

            payment_method TEXT NOT NULL,

            subtotal INTEGER NOT NULL,

            discount INTEGER NOT NULL DEFAULT 0,

            total INTEGER NOT NULL,

            status TEXT NOT NULL DEFAULT 'pending_manager',

            payment_status TEXT NOT NULL DEFAULT 'unconfirmed',

            created_at TEXT NOT NULL,

            manager_acknowledged_at TEXT,

            dispatched_at TEXT,

            received_at TEXT,

            last_manager_reminder_at TEXT
        )
        """
    )

    # -----------------------------------------------------
    # CONVERSATION MESSAGES
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            whatsapp_number TEXT NOT NULL,

            role TEXT NOT NULL,

            content TEXT NOT NULL,

            created_at TEXT NOT NULL
        )
        """
    )

    # -----------------------------------------------------
    # DUPLICATE WEBHOOK PROTECTION
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_messages (
            message_id TEXT PRIMARY KEY,

            processed_at TEXT NOT NULL
        )
        """
    )

    connection.commit()

    connection.close()


# =========================================================
# JSON HELPERS
# =========================================================

def json_dumps(value):

    return json.dumps(
        value,
        ensure_ascii=False,
    )


def json_loads(value, default):

    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    try:
        return json.loads(value)

    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return default


# =========================================================
# CUSTOMER
# =========================================================

def get_customer(whatsapp_number):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM customers
        WHERE whatsapp_number = ?
        """,
        (whatsapp_number,),
    ).fetchone()

    connection.close()

    if not row:
        return None

    data = dict(row)

    data["preferences"] = json_loads(
        data.get("preferences"),
        {},
    )

    data["draft_order"] = json_loads(
        data.get("draft_order"),
        None,
    )

    return data


def save_customer(
    whatsapp_number,
    name=None,
    address=None,
    delivery_phone=None,
    preferences=None,
):

    existing = get_customer(
        whatsapp_number
    )

    old_preferences = (
        existing.get("preferences", {})
        if existing
        else {}
    )

    merged_preferences = {
        **old_preferences,
        **(preferences or {}),
    }

    final_name = (
        name
        if name
        else (
            existing.get("name")
            if existing
            else None
        )
    )

    final_address = (
        address
        if address
        else (
            existing.get("address")
            if existing
            else None
        )
    )

    final_delivery_phone = (
        delivery_phone
        if delivery_phone
        else (
            existing.get("delivery_phone")
            if existing
            else None
        )
    )

    timestamp = now()

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO customers (
            whatsapp_number,
            name,
            address,
            delivery_phone,
            preferences,
            draft_order,
            created_at,
            updated_at
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(whatsapp_number)
        DO UPDATE SET
            name = excluded.name,
            address = excluded.address,
            delivery_phone = excluded.delivery_phone,
            preferences = excluded.preferences,
            updated_at = excluded.updated_at
        """,
        (
            whatsapp_number,
            final_name,
            final_address,
            final_delivery_phone,
            json_dumps(merged_preferences),
            (
                json_dumps(
                    existing.get("draft_order")
                )
                if existing and existing.get("draft_order")
                else None
            ),
            (
                existing["created_at"]
                if existing
                else timestamp
            ),
            timestamp,
        ),
    )

    connection.commit()

    connection.close()


# =========================================================
# CUSTOMER PREFERENCES
# =========================================================

def save_customer_preferences(
    whatsapp_number,
    preferences,
):

    existing = get_customer(
        whatsapp_number
    )

    old_preferences = (
        existing.get("preferences", {})
        if existing
        else {}
    )

    merged = {
        **old_preferences,
        **preferences,
    }

    save_customer(
        whatsapp_number=whatsapp_number,
        preferences=merged,
    )

    return merged


# =========================================================
# CUSTOMER DRAFT ORDER
# =========================================================

def set_draft_order(
    whatsapp_number,
    draft,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE customers
        SET draft_order = ?,
            updated_at = ?
        WHERE whatsapp_number = ?
        """,
        (
            json_dumps(draft),
            now(),
            whatsapp_number,
        ),
    )

    connection.commit()

    connection.close()


def get_draft_order(
    whatsapp_number,
):

    customer = get_customer(
        whatsapp_number
    )

    if not customer:
        return None

    return customer.get(
        "draft_order"
    )


def clear_draft_order(
    whatsapp_number,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE customers
        SET draft_order = NULL,
            updated_at = ?
        WHERE whatsapp_number = ?
        """,
        (
            now(),
            whatsapp_number,
        ),
    )

    connection.commit()

    connection.close()


# =========================================================
# CONVERSATION MEMORY
# =========================================================

def save_message(
    whatsapp_number,
    role,
    content,
):

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO messages (
            whatsapp_number,
            role,
            content,
            created_at
        )

        VALUES (?, ?, ?, ?)
        """,
        (
            whatsapp_number,
            role,
            content,
            now(),
        ),
    )

    connection.commit()

    connection.close()


def get_recent_messages(
    whatsapp_number,
    limit=12,
):

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT role, content, created_at
        FROM messages
        WHERE whatsapp_number = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            whatsapp_number,
            limit,
        ),
    ).fetchall()

    connection.close()

    rows = list(reversed(rows))

    return [
        {
            "role": row["role"],
            "content": row["content"],
        }
        for row in rows
    ]


# =========================================================
# CUSTOMER ORDERS
# =========================================================

def get_customer_orders(
    whatsapp_number,
):

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM orders
        WHERE whatsapp_number = ?
        ORDER BY created_at DESC
        """,
        (whatsapp_number,),
    ).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


def get_latest_customer_order(
    whatsapp_number,
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM orders
        WHERE whatsapp_number = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (whatsapp_number,),
    ).fetchone()

    connection.close()

    return (
        dict(row)
        if row
        else None
    )


# =========================================================
# ORDER LOOKUP FOR MANAGER
# =========================================================

def get_all_recent_orders(
    limit=50,
):

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM orders
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# ORDER
# =========================================================

def get_order(order_id):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM orders
        WHERE order_id = ?
        """,
        (order_id,),
    ).fetchone()

    connection.close()

    return (
        dict(row)
        if row
        else None
    )


def insert_order(order):

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO orders (
            order_id,
            whatsapp_number,
            customer_name,
            delivery_phone,
            address,
            food_items,
            drinks,
            preferences,
            payment_method,
            subtotal,
            discount,
            total,
            status,
            payment_status,
            created_at
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order["order_id"],
            order["whatsapp_number"],
            order["customer_name"],
            order["delivery_phone"],
            order["address"],
            json_dumps(order["food_items"]),
            json_dumps(order["drinks"]),
            json_dumps(order["preferences"]),
            order["payment_method"],
            order["subtotal"],
            order["discount"],
            order["total"],
            "pending_manager",
            "unconfirmed",
            now(),
        ),
    )

    connection.commit()

    connection.close()

    return get_order(
        order["order_id"]
    )


# =========================================================
# ORDER STATUS
# =========================================================

def update_order_status(
    order_id,
    status,
):

    timestamp = now()

    connection = get_connection()

    if status == "confirmed":

        connection.execute(
            """
            UPDATE orders

            SET status = ?,
                manager_acknowledged_at = ?

            WHERE order_id = ?
            """,
            (
                status,
                timestamp,
                order_id,
            ),
        )

    elif status == "out_for_delivery":

        connection.execute(
            """
            UPDATE orders

            SET status = ?,
                dispatched_at = ?

            WHERE order_id = ?
            """,
            (
                status,
                timestamp,
                order_id,
            ),
        )

    elif status == "received":

        connection.execute(
            """
            UPDATE orders

            SET status = ?,
                received_at = ?

            WHERE order_id = ?
            """,
            (
                status,
                timestamp,
                order_id,
            ),
        )

    else:

        connection.execute(
            """
            UPDATE orders
            SET status = ?
            WHERE order_id = ?
            """,
            (
                status,
                order_id,
            ),
        )

    connection.commit()

    connection.close()

    return get_order(
        order_id
    )


# =========================================================
# PAYMENT
# =========================================================

def update_payment_status(
    order_id,
    status,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE orders
        SET payment_status = ?
        WHERE order_id = ?
        """,
        (
            status,
            order_id,
        ),
    )

    connection.commit()

    connection.close()

    return get_order(
        order_id
    )


# =========================================================
# MANAGER REMINDERS
# =========================================================

def get_orders_waiting_for_manager():

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM orders

        WHERE status = 'pending_manager'

        AND datetime(created_at)
            <= datetime('now', '-20 minutes')

        AND (
            last_manager_reminder_at IS NULL

            OR datetime(last_manager_reminder_at)
               <= datetime('now', '-20 minutes')
        )

        ORDER BY created_at ASC
        """
    ).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


def mark_manager_reminded(
    order_id,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE orders
        SET last_manager_reminder_at = ?
        WHERE order_id = ?
        """,
        (
            now(),
            order_id,
        ),
    )

    connection.commit()

    connection.close()


# =========================================================
# DUPLICATE WEBHOOK PROTECTION
# =========================================================

def already_processed(
    message_id,
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT message_id
        FROM processed_messages
        WHERE message_id = ?
        """,
        (message_id,),
    ).fetchone()

    connection.close()

    return row is not None


def mark_processed(
    message_id,
):

    connection = get_connection()

    connection.execute(
        """
        INSERT OR IGNORE INTO processed_messages (
            message_id,
            processed_at
        )

        VALUES (?, ?)
        """,
        (
            message_id,
            now(),
        ),
    )

    connection.commit()

    connection.close()
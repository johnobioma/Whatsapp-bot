import random
from typing import Dict, List

from app.database import (
    get_customer_orders,
    insert_order,
)


# =========================================================
# RESTAURANT MENU
# =========================================================

MENU = {
    "jollof rice": 3000,
    "fried rice": 3000,
    "grilled chicken": 2500,
    "pepper soup": 2000,
    "egusi soup with pounded yam": 3500,
    "suya": 1500,
    "plantain": 800,
    "soft drink": 500,
    "water": 300,
}


# =========================================================
# ALIASES
# =========================================================

ALIASES = {

    "jollof": "jollof rice",

    "rice": "jollof rice",

    "fried rice": "fried rice",

    "chicken": "grilled chicken",

    "grilled chicken": "grilled chicken",

    "pepper soup": "pepper soup",

    "egusi": "egusi soup with pounded yam",

    "egusi soup": "egusi soup with pounded yam",

    "egusi and pounded yam":
        "egusi soup with pounded yam",

    "pounded yam":
        "egusi soup with pounded yam",

    "suya": "suya",

    "plantain": "plantain",

    "fried plantain": "plantain",

    "soft drink": "soft drink",

    "soft drinks": "soft drink",

    "drink": "soft drink",

    "water": "water",
}


# =========================================================
# RULES
# =========================================================

MINIMUM_FOOD_ORDER = 1000

MAX_LOYALTY_DISCOUNT_PERCENT = 3


# =========================================================
# ITEM NORMALIZATION
# =========================================================

def normalize_item_name(
    name: str,
):

    cleaned = (
        name
        .lower()
        .strip()
    )

    if cleaned in MENU:
        return cleaned

    if cleaned in ALIASES:
        return ALIASES[cleaned]

    raise ValueError(
        f"I couldn't find '{name}' on the restaurant menu."
    )


# =========================================================
# MENU
# =========================================================

def get_menu():

    return {
        "restaurant_menu": MENU.copy(),
        "minimum_food_order": MINIMUM_FOOD_ORDER,
    }


def get_price(
    name: str,
):

    normalized = normalize_item_name(
        name
    )

    return MENU[normalized]


# =========================================================
# ITEM BUILDER
# =========================================================

def build_item(
    name,
    quantity,
    details="",
):

    if quantity < 1:
        raise ValueError(
            "Quantity must be at least 1."
        )

    if quantity > 20:
        raise ValueError(
            "Quantity cannot be more than 20."
        )

    normalized = normalize_item_name(
        name
    )

    unit_price = MENU[
        normalized
    ]

    total_price = (
        unit_price * quantity
    )

    return {
        "name": normalized,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_price": total_price,
        "details": (
            details.strip()
            if details
            else ""
        ),
    }


# =========================================================
# DISCOUNT
# =========================================================

def calculate_loyalty_discount(
    subtotal,
    returning_customer,
):

    if not returning_customer:
        return 0

    discount = int(
        round(
            subtotal
            * (
                MAX_LOYALTY_DISCOUNT_PERCENT
                / 100
            )
        )
    )

    return discount


# =========================================================
# VALIDATION
# =========================================================

def validate_order(
    food_items,
    drinks,
):

    if not food_items:
        raise ValueError(
            "At least one food item is required."
        )

    food_subtotal = sum(
        item["total_price"]
        for item in food_items
    )

    if food_subtotal < MINIMUM_FOOD_ORDER:

        raise ValueError(
            f"The minimum food order is "
            f"₦{MINIMUM_FOOD_ORDER:,}."
        )

    for item in food_items:

        if item["unit_price"] < 1000:

            # Plantain is treated as an add-on,
            # but the overall food order must
            # still reach ₦1,000.
            if (
                item["name"] != "plantain"
            ):
                raise ValueError(
                    "A negotiated food item cannot "
                    "be reduced below ₦1,000."
                )

    return True


# =========================================================
# ORDER ID
# =========================================================

def generate_order_id():

    return (
        "DW-"
        f"{random.randint(10000000, 99999999)}"
        "-"
        f"{random.randint(100, 999)}"
    )


# =========================================================
# CREATE ORDER
# =========================================================

def create_order_from_draft(
    whatsapp_number,
    customer_name,
    delivery_phone,
    address,
    food_items,
    drinks,
    preferences,
    payment_method,
):

    previous_orders = (
        get_customer_orders(
            whatsapp_number
        )
    )

    returning_customer = (
        len(previous_orders) > 0
    )

    validated_food = []

    for item in food_items:

        validated_food.append(
            build_item(
                item["name"],
                int(item["quantity"]),
                item.get("details", ""),
            )
        )

    validated_drinks = []

    for item in drinks:

        validated_drinks.append(
            build_item(
                item["name"],
                int(item["quantity"]),
                item.get("details", ""),
            )
        )

    validate_order(
        validated_food,
        validated_drinks,
    )

    food_total = sum(
        item["total_price"]
        for item in validated_food
    )

    drink_total = sum(
        item["total_price"]
        for item in validated_drinks
    )

    subtotal = (
        food_total
        + drink_total
    )

    discount = (
        calculate_loyalty_discount(
            subtotal,
            returning_customer,
        )
    )

    total = max(
        0,
        subtotal - discount,
    )

    order = {

        "order_id":
            generate_order_id(),

        "whatsapp_number":
            whatsapp_number,

        "customer_name":
            customer_name,

        "delivery_phone":
            delivery_phone,

        "address":
            address,

        "food_items":
            validated_food,

        "drinks":
            validated_drinks,

        "preferences":
            preferences,

        "payment_method":
            payment_method,

        "subtotal":
            subtotal,

        "discount":
            discount,

        "total":
            total,
    }

    return insert_order(
        order
    )
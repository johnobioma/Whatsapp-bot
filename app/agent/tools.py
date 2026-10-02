import json
import re
from typing import Any

from app.config import settings
from app.database import (
    clear_draft_order,
    get_all_recent_orders,
    get_customer,
    get_customer_orders,
    get_draft_order,
    get_latest_customer_order,
    get_recent_messages,
    get_order,
    mark_manager_reminded,
    save_customer,
    save_customer_preferences,
    set_draft_order,
    update_order_status,
    update_payment_status,
)
from app.services.orders import (
    create_order_from_draft,
    get_menu,
    normalize_item_name,
)
from app.services.whatsapp import (
    send_text_message,
)


# =========================================================
# JSON
# =========================================================

def json_result(data):

    return json.dumps(
        data,
        ensure_ascii=False,
    )


# =========================================================
# PHONE
# =========================================================

def clean_phone(phone):

    if not phone:
        return ""

    return re.sub(
        r"\D",
        "",
        phone,
    )


# =========================================================
# ORDER REFERENCE NORMALIZATION
# =========================================================

def normalize_reference(
    reference,
):

    return re.sub(
        r"[^a-z0-9]",
        "",
        reference.lower(),
    )


# =========================================================
# MANAGER ORDER FINDER
# =========================================================

def find_order_for_manager(
    reference,
):

    reference = (
        reference or ""
    ).strip()

    orders = get_all_recent_orders(
        limit=100
    )

    if not orders:
        return None

    ref = normalize_reference(
        reference
    )

    # -----------------------------------------------------
    # Exact order ID
    # -----------------------------------------------------

    for order in orders:

        order_ref = normalize_reference(
            order["order_id"]
        )

        if (
            ref
            and ref == order_ref
        ):
            return order

    # -----------------------------------------------------
    # Order ID without DW prefix
    # -----------------------------------------------------

    for order in orders:

        order_ref = normalize_reference(
            order["order_id"]
        )

        if (
            ref
            and len(ref) >= 6
            and (
                ref in order_ref
                or order_ref.endswith(ref)
            )
        ):
            return order

    # -----------------------------------------------------
    # Customer name
    # -----------------------------------------------------

    reference_lower = (
        reference.lower()
    )

    for order in orders:

        name = (
            order["customer_name"]
            or ""
        ).lower()

        if (
            name
            and name in reference_lower
        ):
            return order

    # -----------------------------------------------------
    # WhatsApp number
    # -----------------------------------------------------

    cleaned_reference = clean_phone(
        reference
    )

    for order in orders:

        if (
            cleaned_reference
            and cleaned_reference
            == clean_phone(
                order["whatsapp_number"]
            )
        ):
            return order

    return None


# =========================================================
# CONFIRMATION DETECTOR
# =========================================================

def is_customer_confirmation(
    text,
):

    normalized = (
        text
        .lower()
        .strip()
        .replace(".", "")
        .replace("!", "")
    )

    confirmations = {

        "correct",

        "yes",

        "yes correct",

        "that's correct",

        "that is correct",

        "everything is correct",

        "confirmed",

        "confirm",

        "go ahead",

        "place it",

        "place the order",

        "i confirm",

        "confirm it",

        "okay",

        "ok",
    }

    return normalized in confirmations


# =========================================================
# CUSTOMER TOOLS
# =========================================================

def build_customer_tools(
    customer_number,
    current_user_text,
):

    # =====================================================
    # GET CUSTOMER PROFILE
    # =====================================================

    def get_customer_profile():

        customer = get_customer(
            customer_number
        )

        if not customer:

            return json_result({
                "exists": False,
                "message":
                    "No customer profile exists yet.",
            })

        return json_result({
            "exists": True,

            "name":
                customer.get("name"),

            "address":
                customer.get("address"),

            "delivery_phone":
                customer.get("delivery_phone"),

            "preferences":
                customer.get("preferences", {}),
        })

    # =====================================================
    # SAVE CUSTOMER DETAILS
    # =====================================================

    def save_customer_details(
        name,
        address,
        delivery_phone,
        preferences_json,
    ):

        try:
            preferences = json.loads(
                preferences_json
                or "{}"
            )

        except json.JSONDecodeError:

            preferences = {}

        save_customer(
            whatsapp_number=
                customer_number,

            name=
                name.strip()
                if name
                else None,

            address=
                address.strip()
                if address
                else None,

            delivery_phone=
                delivery_phone.strip()
                if delivery_phone
                else None,

            preferences=
                preferences,
        )

        return json_result({
            "success": True,
            "message":
                "Customer information saved.",
        })

    # =====================================================
    # GET MENU
    # =====================================================

    def menu():

        return json_result(
            get_menu()
        )

    # =====================================================
    # FOOD INFORMATION
    # =====================================================

    def get_food_information(
        food_name,
    ):

        food = (
            food_name
            .lower()
            .strip()
        )

        information = {

            "jollof rice": {
                "description":
                    "A Nigerian-style rice dish cooked with a tomato and pepper base.",

                "ingredients":
                    [
                        "tomatoes",
                        "pepper",
                        "onions",
                        "fresh groundnut oil",
                        "seasoning",
                        "special cooking sauce",
                        "peppered meat when ordered with meat",
                    ],

                "preparation":
                    "The rice is cooked in the seasoned tomato-pepper sauce until the flavours develop and the rice is properly cooked.",

                "important_note":
                    "These are the general ingredients/information provided for the restaurant description. Do not invent additional restaurant-specific ingredients.",
            },

            "fried rice": {
                "description":
                    "A seasoned rice dish prepared with vegetables and other ingredients.",

                "important_note":
                    "Use only information supplied by the restaurant. Do not invent a proprietary recipe.",
            },

            "pepper soup": {
                "description":
                    "A spicy Nigerian-style soup.",

                "important_note":
                    "Do not invent restaurant-specific ingredients unless they are supplied by the restaurant.",
            },

            "suya": {
                "description":
                    "Seasoned grilled meat prepared in a Nigerian suya style.",

                "important_note":
                    "Do not invent restaurant-specific preparation details.",
            },

            "egusi soup with pounded yam": {
                "description":
                    "Egusi soup served with pounded yam.",

                "important_note":
                    "Do not invent restaurant-specific ingredients.",
            },

            "grilled chicken": {
                "description":
                    "Grilled chicken.",

                "important_note":
                    "Do not invent restaurant-specific preparation details.",
            },

            "plantain": {
                "description":
                    "Plantain prepared as an accompaniment.",

                "important_note":
                    "Do not invent restaurant-specific preparation details.",
            },
        }

        normalized = food

        try:

            normalized = normalize_item_name(
                food
            )

        except ValueError:
            pass

        result = information.get(
            normalized
        )

        if not result:

            return json_result({
                "found": False,
                "message":
                    "No verified food information is available for that item.",
            })

        return json_result({
            "found": True,
            "food": normalized,
            **result,
        })

    # =====================================================
    # ORDER HISTORY
    # =====================================================

    def get_order_history():

        orders = get_customer_orders(
            customer_number
        )

        simplified = []

        for order in orders[:10]:

            simplified.append({

                "order_id":
                    order["order_id"],

                "customer_name":
                    order["customer_name"],

                "food_items":
                    json.loads(
                        order["food_items"]
                    ),

                "drinks":
                    json.loads(
                        order["drinks"]
                    ),

                "preferences":
                    json.loads(
                        order["preferences"]
                    ),

                "total":
                    order["total"],

                "status":
                    order["status"],

                "created_at":
                    order["created_at"],
            })

        return json_result({
            "orders":
                simplified
        })

    # =====================================================
    # LATEST ORDER STATUS
    # =====================================================

    def get_latest_order_status():

        order = get_latest_customer_order(
            customer_number
        )

        if not order:

            return json_result({
                "found": False,
                "message":
                    "This customer has no orders yet.",
            })

        return json_result({
            "found": True,

            "order_id":
                order["order_id"],

            "customer_name":
                order["customer_name"],

            "status":
                order["status"],

            "payment_method":
                order["payment_method"],

            "payment_status":
                order["payment_status"],

            "total":
                order["total"],

            "created_at":
                order["created_at"],
        })

    # =====================================================
    # GET PENDING DRAFT
    # =====================================================

    def get_pending_order_draft():

        draft = get_draft_order(
            customer_number
        )

        if not draft:

            return json_result({
                "exists": False,
                "message":
                    "There is no pending order draft.",
            })

        return json_result({
            "exists": True,
            "draft":
                draft,
        })

    # =====================================================
    # PREPARE ORDER
    # =====================================================

    def prepare_order(
        customer_name,
        delivery_phone,
        address,
        food_items,
        drinks,
        payment_method,
        preferences_json,
    ):

        try:

            preferences = json.loads(
                preferences_json
                or "{}"
            )

        except json.JSONDecodeError:

            return json_result({
                "success": False,
                "error":
                    "Preferences must be valid JSON.",
            })

        try:

            food = []

            for item in food_items:

                normalized_name = (
                    normalize_item_name(
                        item["name"]
                    )
                )

                food.append({

                    "name":
                        normalized_name,

                    "quantity":
                        int(
                            item["quantity"]
                        ),

                    "details":
                        item.get(
                            "details",
                            "",
                        ),
                })

            drink_list = []

            for item in drinks:

                normalized_name = (
                    normalize_item_name(
                        item["name"]
                    )
                )

                drink_list.append({

                    "name":
                        normalized_name,

                    "quantity":
                        int(
                            item["quantity"]
                        ),

                    "details":
                        item.get(
                            "details",
                            "",
                        ),
                })

            # ---------------------------------------------
            # Price using backend
            # ---------------------------------------------

            from app.services.orders import (
                build_item,
                validate_order,
                calculate_loyalty_discount,
            )

            priced_food = [
                build_item(
                    item["name"],
                    item["quantity"],
                    item["details"],
                )
                for item in food
            ]

            priced_drinks = [
                build_item(
                    item["name"],
                    item["quantity"],
                    item["details"],
                )
                for item in drink_list
            ]

            validate_order(
                priced_food,
                priced_drinks,
            )

            subtotal = (
                sum(
                    item["total_price"]
                    for item in priced_food
                )
                +
                sum(
                    item["total_price"]
                    for item in priced_drinks
                )
            )

            previous_orders = (
                get_customer_orders(
                    customer_number
                )
            )

            returning_customer = (
                len(previous_orders) > 0
            )

            discount = (
                calculate_loyalty_discount(
                    subtotal,
                    returning_customer,
                )
            )

            total = (
                subtotal - discount
            )

            draft = {

                "customer_name":
                    customer_name,

                "whatsapp_number":
                    customer_number,

                "delivery_phone":
                    delivery_phone
                    or customer_number,

                "address":
                    address,

                "food_items":
                    priced_food,

                "drinks":
                    priced_drinks,

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

            save_customer(
                whatsapp_number=
                    customer_number,

                name=
                    customer_name,

                address=
                    address,

                delivery_phone=
                    delivery_phone
                    or customer_number,

                preferences=
                    preferences,
            )

            set_draft_order(
                customer_number,
                draft,
            )

            return json_result({

                "success": True,

                "draft_saved": True,

                "requires_customer_confirmation":
                    True,

                "customer_name":
                    customer_name,

                "food_items":
                    priced_food,

                "drinks":
                    priced_drinks,

                "address":
                    address,

                "payment_method":
                    payment_method,

                "subtotal":
                    subtotal,

                "discount":
                    discount,

                "total":
                    total,

                "message":
                    "Order draft prepared. The customer must explicitly confirm it before create_confirmed_order can create the real order.",
            })

        except Exception as error:

            return json_result({

                "success": False,

                "error":
                    str(error),
            })

    # =====================================================
    # CREATE CONFIRMED ORDER
    # =====================================================

    async def create_confirmed_order():

        draft = get_draft_order(
            customer_number
        )

        if not draft:

            return json_result({

                "success": False,

                "error":
                    "There is no pending order draft to confirm.",
            })

        # -------------------------------------------------
        # Backend confirmation check
        # -------------------------------------------------

        if not is_customer_confirmation(
            current_user_text
        ):

            return json_result({

                "success": False,

                "error":
                    "The latest customer message is not an explicit order confirmation. Do not create the order.",
            })

        # -------------------------------------------------
        # Create real order
        # -------------------------------------------------

        try:

            order = create_order_from_draft(

                whatsapp_number=
                    customer_number,

                customer_name=
                    draft["customer_name"],

                delivery_phone=
                    draft["delivery_phone"],

                address=
                    draft["address"],

                food_items=
                    draft["food_items"],

                drinks=
                    draft["drinks"],

                preferences=
                    draft["preferences"],

                payment_method=
                    draft["payment_method"],
            )

        except Exception as error:

            return json_result({

                "success": False,

                "error":
                    str(error),
            })

        clear_draft_order(
            customer_number
        )

        # -------------------------------------------------
        # Notify manager
        # -------------------------------------------------

        manager_notified = True

        try:

            manager_message = (
                format_manager_order(
                    order
                )
            )

            await send_text_message(
                settings.OWNER_WHATSAPP_NUMBER,
                manager_message,
            )

        except Exception:

            manager_notified = False

        return json_result({

            "success": True,

            "order_created": True,

            "order_id":
                order["order_id"],

            "customer_name":
                order["customer_name"],

            "food_items":
                json.loads(
                    order["food_items"]
                ),

            "drinks":
                json.loads(
                    order["drinks"]
                ),

            "address":
                order["address"],

            "payment_method":
                order["payment_method"],

            "subtotal":
                order["subtotal"],

            "discount":
                order["discount"],

            "total":
                order["total"],

            "status":
                order["status"],

            "manager_notified":
                manager_notified,
        })

    # =====================================================
    # CUSTOMER RECEIVED FOOD
    # =====================================================

    async def report_food_received():

        order = get_latest_customer_order(
            customer_number
        )

        if not order:

            return json_result({

                "success": False,

                "error":
                    "No customer order was found.",
            })

        if order["status"] == "received":

            return json_result({

                "success": True,

                "already_received": True,

                "order_id":
                    order["order_id"],
            })

        updated = update_order_status(
            order["order_id"],
            "received",
        )

        manager_notified = True

        try:

            await send_text_message(
                settings.OWNER_WHATSAPP_NUMBER,
                (
                    "CUSTOMER RECEIVED ORDER\n\n"
                    f"Order ID: {order['order_id']}\n\n"
                    f"Customer: {order['customer_name']}\n\n"
                    f"WhatsApp: {order['whatsapp_number']}\n\n"
                    f"Customer message: {current_user_text}\n\n"
                    "The customer confirmed that the food was received.\n\n"
                    f"Payment status remains: "
                    f"{order['payment_status']}"
                ),
            )

        except Exception:

            manager_notified = False

        return json_result({

            "success": True,

            "order_id":
                updated["order_id"],

            "status":
                updated["status"],

            "payment_status":
                updated["payment_status"],

            "manager_notified":
                manager_notified,
        })

    return {

        "get_customer_profile":
            get_customer_profile,

        "save_customer_details":
            save_customer_details,

        "get_menu":
            menu,

        "get_food_information":
            get_food_information,

        "get_order_history":
            get_order_history,

        "get_latest_order_status":
            get_latest_order_status,

        "get_pending_order_draft":
            get_pending_order_draft,

        "prepare_order":
            prepare_order,

        "create_confirmed_order":
            create_confirmed_order,

        "report_food_received":
            report_food_received,
    }


# =========================================================
# MANAGER TOOLS
# =========================================================

def build_manager_tools(
    manager_number,
    current_user_text,
):

    # =====================================================
    # FIND ORDER
    # =====================================================

    def find_order(
        reference,
    ):

        order = find_order_for_manager(
            reference
        )

        if not order:

            return json_result({

                "found": False,

                "message":
                    "No matching order was found.",
            })

        return json_result({

            "found": True,

            "order_id":
                order["order_id"],

            "customer_name":
                order["customer_name"],

            "whatsapp_number":
                order["whatsapp_number"],

            "address":
                order["address"],

            "status":
                order["status"],

            "payment_status":
                order["payment_status"],

            "total":
                order["total"],
        })

    # =====================================================
    # ACKNOWLEDGE LATEST PENDING ORDER
    # =====================================================

    async def acknowledge_latest_pending_order():

        orders = get_all_recent_orders(
            limit=100
        )

        pending = [
            order
            for order in orders
            if order["status"]
            == "pending_manager"
        ]

        if not pending:

            return json_result({

                "success": False,

                "error":
                    "There is no order currently waiting for manager acknowledgement.",
            })

        order = pending[0]

        updated = update_order_status(
            order["order_id"],
            "confirmed",
        )

        await send_text_message(
            order["whatsapp_number"],
            (
                f"{order['customer_name']}, your order "
                f"{order['order_id']} has been confirmed "
                "by the restaurant. We will update you "
                "when it is being prepared or on the way."
            ),
        )

        return json_result({

            "success": True,

            "order_id":
                updated["order_id"],

            "customer_name":
                updated["customer_name"],

            "status":
                updated["status"],
        })

    # =====================================================
    # PREPARING
    # =====================================================

    async def mark_order_preparing(
        reference,
    ):

        order = find_order_for_manager(
            reference
        )

        if not order:

            return json_result({

                "success": False,

                "error":
                    "No matching order was found.",
            })

        updated = update_order_status(
            order["order_id"],
            "preparing",
        )

        await send_text_message(
            order["whatsapp_number"],
            (
                f"{order['customer_name']}, your order "
                f"{order['order_id']} is now being prepared "
                "by the restaurant."
            ),
        )

        return json_result({

            "success": True,

            "order_id":
                updated["order_id"],

            "status":
                updated["status"],
        })

    # =====================================================
    # OUT FOR DELIVERY
    # =====================================================

    async def mark_order_out_for_delivery(
        reference,
    ):

        order = find_order_for_manager(
            reference
        )

        if not order:

            return json_result({

                "success": False,

                "error":
                    "No matching order was found.",
            })

        updated = update_order_status(
            order["order_id"],
            "out_for_delivery",
        )

        await send_text_message(
            order["whatsapp_number"],
            (
                f"{order['customer_name']}, your food "
                "is on its way. Please let us know "
                "when it gets to you."
            ),
        )

        return json_result({

            "success": True,

            "order_id":
                updated["order_id"],

            "status":
                updated["status"],
        })

    # =====================================================
    # DELIVERED
    # =====================================================

    async def mark_order_received(
        reference,
    ):

        order = find_order_for_manager(
            reference
        )

        if not order:

            return json_result({

                "success": False,

                "error":
                    "No matching order was found.",
            })

        updated = update_order_status(
            order["order_id"],
            "received",
        )

        await send_text_message(
            order["whatsapp_number"],
            (
                f"{order['customer_name']}, your order "
                "has been marked as delivered. "
                "Please let us know how everything was."
            ),
        )

        return json_result({

            "success": True,

            "order_id":
                updated["order_id"],

            "status":
                updated["status"],
        })

    # =====================================================
    # PAYMENT
    # =====================================================

    async def confirm_payment(
        reference,
    ):

        order = find_order_for_manager(
            reference
        )

        if not order:

            return json_result({

                "success": False,

                "error":
                    "No matching order was found.",
            })

        updated = update_payment_status(
            order["order_id"],
            "confirmed",
        )

        await send_text_message(
            order["whatsapp_number"],
            (
                f"{order['customer_name']}, your payment "
                f"for order {order['order_id']} has been "
                "confirmed by the restaurant."
            ),
        )

        return json_result({

            "success": True,

            "order_id":
                updated["order_id"],

            "payment_status":
                updated["payment_status"],
        })

    return {

        "find_order":
            find_order,

        "acknowledge_latest_pending_order":
            acknowledge_latest_pending_order,

        "mark_order_preparing":
            mark_order_preparing,

        "mark_order_out_for_delivery":
            mark_order_out_for_delivery,

        "mark_order_received":
            mark_order_received,

        "confirm_payment":
            confirm_payment,
    }


# =========================================================
# MANAGER ORDER FORMAT
# =========================================================

def format_manager_order(
    order,
):

    food = json.loads(
        order["food_items"]
    )

    drinks = json.loads(
        order["drinks"]
    )

    preferences = json.loads(
        order["preferences"]
    )

    food_lines = []

    for item in food:

        details = item.get(
            "details",
            "",
        )

        detail_text = (
            f" | {details}"
            if details
            else ""
        )

        food_lines.append(
            f'{item["quantity"]} × '
            f'{item["name"]} '
            f'- ₦{item["total_price"]:,}'
            f'{detail_text}'
        )

    drink_lines = []

    for item in drinks:

        drink_lines.append(
            f'{item["quantity"]} × '
            f'{item["name"]} '
            f'- ₦{item["total_price"]:,}'
        )

    preference_text = (
        json.dumps(
            preferences,
            indent=2,
            ensure_ascii=False,
        )
        if preferences
        else "None"
    )

    return f"""
NEW ORDER

Order ID:
{order["order_id"]}

CUSTOMER

Name:
{order["customer_name"]}

WhatsApp:
{order["whatsapp_number"]}

Delivery phone:
{order["delivery_phone"]}

Address:
{order["address"]}

FOOD

{chr(10).join(food_lines) if food_lines else "None"}

DRINKS

{chr(10).join(drink_lines) if drink_lines else "None"}

PREFERENCES / SPECIAL DETAILS

{preference_text}

PAYMENT

Method:
{order["payment_method"]}

Payment status:
{order["payment_status"]}

PRICE

Subtotal:
₦{order["subtotal"]:,}

Discount:
₦{order["discount"]:,}

TOTAL:
₦{order["total"]:,}

STATUS:
{order["status"]}

Please acknowledge the order.
""".strip()


# =========================================================
# TOOL SCHEMAS
# =========================================================

CUSTOMER_TOOL_SCHEMAS = [

    {
        "type": "function",

        "function": {
            "name":
                "get_customer_profile",

            "description":
                "Read the customer's saved name, address, phone and preferences.",

            "parameters": {
                "type": "object",

                "properties": {},

                "required": [],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name":
                "save_customer_details",

            "description":
                "Save verified customer details that the customer has supplied.",

            "parameters": {

                "type":
                    "object",

                "properties": {

                    "name": {
                        "type":
                            "string",
                    },

                    "address": {
                        "type":
                            "string",
                    },

                    "delivery_phone": {
                        "type":
                            "string",
                    },

                    "preferences_json": {
                        "type":
                            "string",
                    },
                },

                "required": [
                    "name",
                    "address",
                    "delivery_phone",
                    "preferences_json",
                ],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name":
                "get_menu",

            "description":
                "Get the actual restaurant menu and prices. Always use this for current menu prices.",

            "parameters": {

                "type":
                    "object",

                "properties": {},

                "required": [],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name":
                "get_food_information",

            "description":
                "Get verified information about a food item, including available ingredients and preparation information.",

            "parameters": {

                "type":
                    "object",

                "properties": {

                    "food_name": {
                        "type":
                            "string",
                    },
                },

                "required": [
                    "food_name"
                ],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name":
                "get_order_history",

            "description":
                "Get the customer's previous restaurant orders and preferences.",

            "parameters": {

                "type":
                    "object",

                "properties": {},

                "required": [],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name":
                "get_latest_order_status",

            "description":
                "Get the real latest order status and payment status. Use this whenever the customer asks about an order status, delivery progress, whether food has been sent, or whether payment is confirmed.",

            "parameters": {

                "type":
                    "object",

                "properties": {},

                "required": [],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name":
                "get_pending_order_draft",

            "description":
                "Check whether the customer has a prepared order waiting for explicit confirmation.",

            "parameters": {

                "type":
                    "object",

                "properties": {},

                "required": [],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name":
                "prepare_order",

            "description":
                "Prepare and save an order draft after all required order information has been collected. This does NOT create the final order. The customer must explicitly confirm the resulting summary.",

            "parameters": {

                "type":
                    "object",

                "properties": {

                    "customer_name": {
                        "type":
                            "string",
                    },

                    "delivery_phone": {
                        "type":
                            "string",
                    },

                    "address": {
                        "type":
                            "string",
                    },

                    "food_items": {

                        "type":
                            "array",

                        "items": {

                            "type":
                                "object",

                            "properties": {

                                "name": {
                                    "type":
                                        "string",
                                },

                                "quantity": {
                                    "type":
                                        "integer",
                                },

                                "details": {
                                    "type":
                                        "string",
                                },
                            },

                            "required": [
                                "name",
                                "quantity",
                                "details",
                            ],

                            "additionalProperties":
                                False,
                        },
                    },

                    "drinks": {

                        "type":
                            "array",

                        "items": {

                            "type":
                                "object",

                            "properties": {

                                "name": {
                                    "type":
                                        "string",
                                },

                                "quantity": {
                                    "type":
                                        "integer",
                                },

                                "details": {
                                    "type":
                                        "string",
                                },
                            },

                            "required": [
                                "name",
                                "quantity",
                                "details",
                            ],

                            "additionalProperties":
                                False,
                        },
                    },

                    "payment_method": {
                        "type":
                            "string",
                    },

                    "preferences_json": {
                        "type":
                            "string",
                    },
                },

                "required": [
                    "customer_name",
                    "delivery_phone",
                    "address",
                    "food_items",
                    "drinks",
                    "payment_method",
                    "preferences_json",
                ],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name":
                "create_confirmed_order",

            "description":
                "Create the real restaurant order only after the customer has explicitly confirmed the pending order draft. Never use this before confirmation.",

            "parameters": {

                "type":
                    "object",

                "properties": {},

                "required": [],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {
            "name":
                "report_food_received",

            "description":
                "Use when the customer says they received or got their food. This updates the real order status and informs the manager. It does not mark payment as confirmed.",

            "parameters": {

                "type":
                    "object",

                "properties": {},

                "required": [],

                "additionalProperties":
                    False,
            },
        },
    },
]


MANAGER_TOOL_SCHEMAS = [

    {
        "type": "function",

        "function": {

            "name":
                "find_order",

            "description":
                "Find a restaurant order using customer name, order ID, order ID suffix, or customer WhatsApp number.",

            "parameters": {

                "type":
                    "object",

                "properties": {

                    "reference": {
                        "type":
                            "string",
                    },
                },

                "required": [
                    "reference"
                ],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {

            "name":
                "acknowledge_latest_pending_order",

            "description":
                "Acknowledge the newest order that is actually waiting for manager acknowledgement and notify the customer.",

            "parameters": {

                "type":
                    "object",

                "properties": {},

                "required": [],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {

            "name":
                "mark_order_preparing",

            "description":
                "Mark a specific order as preparing and notify the customer.",

            "parameters": {

                "type":
                    "object",

                "properties": {

                    "reference": {
                        "type":
                            "string",
                    },
                },

                "required": [
                    "reference"
                ],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {

            "name":
                "mark_order_out_for_delivery",

            "description":
                "Mark a specific order as out for delivery and notify the customer.",

            "parameters": {

                "type":
                    "object",

                "properties": {

                    "reference": {
                        "type":
                            "string",
                    },
                },

                "required": [
                    "reference"
                ],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {

            "name":
                "mark_order_received",

            "description":
                "Mark a specific order as delivered/received and notify the customer.",

            "parameters": {

                "type":
                    "object",

                "properties": {

                    "reference": {
                        "type":
                            "string",
                    },
                },

                "required": [
                    "reference"
                ],

                "additionalProperties":
                    False,
            },
        },
    },

    {
        "type": "function",

        "function": {

            "name":
                "confirm_payment",

            "description":
                "Confirm payment for a specific order only when the restaurant manager explicitly confirms payment was received.",

            "parameters": {

                "type":
                    "object",

                "properties": {

                    "reference": {
                        "type":
                            "string",
                    },
                },

                "required": [
                    "reference"
                ],

                "additionalProperties":
                    False,
            },
        },
    },
]
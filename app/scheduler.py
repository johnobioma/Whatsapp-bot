import asyncio
import json
import logging

from app.config import settings
from app.database import (
    get_orders_waiting_for_manager,
    mark_manager_reminded,
)
from app.services.whatsapp import (
    send_text_message,
)


logger = logging.getLogger(
    "scheduler"
)


# =========================================================
# FORMAT REMINDER
# =========================================================

def format_reminder(
    order,
):

    food = json.loads(
        order["food_items"]
    )

    food_lines = []

    for item in food:

        food_lines.append(
            f'{item["quantity"]} × '
            f'{item["name"]}'
        )

    return f"""
REMINDER — ORDER STILL AWAITING ACKNOWLEDGEMENT

Order ID:
{order["order_id"]}

Customer:
{order["customer_name"]}

WhatsApp:
{order["whatsapp_number"]}

Address:
{order["address"]}

Food:
{chr(10).join(food_lines)}

Total:
₦{order["total"]:,}

The order has been waiting for manager acknowledgement
for more than 20 minutes.

Please review and acknowledge it.
""".strip()


# =========================================================
# REMINDER LOOP
# =========================================================

async def manager_reminder_loop():

    while True:

        try:

            orders = (
                get_orders_waiting_for_manager()
            )

            for order in orders:

                try:

                    message = format_reminder(
                        order
                    )

                    await send_text_message(
                        settings.OWNER_WHATSAPP_NUMBER,
                        message,
                    )

                    mark_manager_reminded(
                        order["order_id"]
                    )

                    logger.info(
                        "Manager reminder sent for %s",
                        order["order_id"],
                    )

                except Exception as error:

                    logger.exception(
                        "Failed to send reminder for %s: %s",
                        order["order_id"],
                        error,
                    )

        except Exception as error:

            logger.exception(
                "Reminder loop error: %s",
                error,
            )

        await asyncio.sleep(
            60
        )
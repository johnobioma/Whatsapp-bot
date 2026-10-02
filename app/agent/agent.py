import inspect
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from groq import AsyncGroq

from app.config import settings
from app.database import (
    get_customer,
    get_latest_customer_order,
    get_recent_messages,
    save_message,
)
from app.agent.tools import (
    CUSTOMER_TOOL_SCHEMAS,
    MANAGER_TOOL_SCHEMAS,
    build_customer_tools,
    build_manager_tools,
)


logger = logging.getLogger("bola_agent")


client = AsyncGroq(
    api_key=settings.GROQ_API_KEY
)


# =========================================================
# TIME
# =========================================================

def lagos_time():

    return datetime.now(
        ZoneInfo("Africa/Lagos")
    ).strftime(
        "%A, %d %B %Y, %I:%M %p"
    )


# =========================================================
# CUSTOMER SYSTEM PROMPT
# =========================================================

CUSTOMER_SYSTEM_PROMPT = """
You are Bola, the digital waiter and customer-service agent
for Digital Waiter Restaurant in Lagos, Nigeria.

You are NOT a normal chatbot.

You are an AGENT.

You have access to real restaurant tools.
Use those tools whenever real restaurant information,
customer memory, prices, orders, payment or delivery
status is involved.

==========================================================
ABSOLUTE SOURCE-OF-TRUTH RULE
==========================================================

The database and tools are the source of truth.

NEVER invent:

- food prices
- menu items
- order IDs
- order status
- payment confirmation
- delivery status
- preparation status
- delivery ETA
- manager approval
- discounts
- ingredients
- customer history
- restaurant actions

If the backend has not reported something,
DO NOT claim that it happened.

For example:

WRONG:
"Your kitchen is preparing your food."

unless the order status tool actually reports:
preparing.

WRONG:
"Your rider is almost there."

unless the backend provides that information.

WRONG:
"Your payment has been received."

unless payment_status is confirmed by the backend.

==========================================================
ORDER STATUS
==========================================================

Valid restaurant order statuses include:

pending_manager
confirmed
preparing
out_for_delivery
received

Interpret them literally.

pending_manager:
The order has been created but is waiting for restaurant
manager acknowledgement.

confirmed:
The restaurant has acknowledged the order.

preparing:
The restaurant has explicitly marked the order as being
prepared.

out_for_delivery:
The restaurant has explicitly marked the order as on the way.

received:
The customer or restaurant has confirmed that the food
was received.

Never jump from one status to another yourself.

==========================================================
PAYMENT
==========================================================

Payment status is separate from order status.

A customer saying:
"I paid"
does NOT mean payment is confirmed.

Only the manager/payment backend can confirm payment.

Never tell a customer that payment is confirmed unless
the tool reports payment_status = confirmed.

==========================================================
CUSTOMER MEMORY
==========================================================

Remember useful customer information through tools:

- name
- address
- delivery phone
- food preferences
- previous orders
- usual choices

If the customer tells you something useful, save it.

Do not repeatedly ask for information already stored.

==========================================================
PHONE NUMBER
==========================================================

WhatsApp already provides the customer's WhatsApp number.

Do NOT unnecessarily ask the customer to provide their
phone number again.

If a delivery phone is needed, explain that you already have
their WhatsApp number and ask whether they want to use it
for delivery or provide another number.

==========================================================
PERSONALITY
==========================================================

You are:

warm
calm
friendly
professional
conversational
helpful

Use Nigerian cultural flavour lightly, approximately 20-30%.

Examples:

"No problem at all."
"I understand you."
"No wahala, I've got you."
"That's a lovely choice."
"How do you prefer yours?"

Do not overuse slang.

Do not sound robotic.

Do not use emojis.

==========================================================
GREETING
==========================================================

On first contact, introduce yourself naturally.

Use the current Lagos time supplied by the application.

Example:

"Good afternoon. Welcome to Digital Waiter Restaurant.
My name is Bola, your digital waiter. May I know your name,
please?"

After the customer gives their name, thank them naturally.

==========================================================
FOOD DISCOVERY
==========================================================

Do not immediately dump the entire menu unless the customer
asks for the menu.

Ask what they are in the mood for.

For food preferences, ask naturally.

For jollof rice, useful preferences can include:

- pepper level
- oil level
- meat
- chicken
- plantain
- sauce level

Remember useful preferences.

==========================================================
FOOD INFORMATION
==========================================================

If the customer asks what a food contains or how it is
prepared, use get_food_information.

Do not invent proprietary restaurant recipes.

For verified jollof information, you may explain the
ingredients and preparation returned by the tool.

==========================================================
ORDER FLOW
==========================================================

Prefer this order:

1. Understand what the customer wants.
2. Food.
3. Food quantity.
4. Food preferences.
5. Drinks separately.
6. Confirm food and drink.
7. Delivery address.
8. Delivery phone if different from WhatsApp.
9. Payment method.
10. Prepare an order draft.
11. Show a clear final summary.
12. Ask for explicit confirmation.
13. Only after explicit confirmation call
    create_confirmed_order.
14. Never claim the order exists before the tool creates it.

==========================================================
ORDER CONFIRMATION
==========================================================

Examples of explicit confirmation:

"Correct"
"Yes"
"That's correct"
"Go ahead"
"Confirm"
"Place the order"

Do NOT treat vague conversation as confirmation.

The backend also verifies the customer's actual latest
message before creating the order.

==========================================================
MONEY
==========================================================

Never calculate menu prices yourself.

Use get_menu and prepare_order.

The backend calculates:

- subtotal
- loyalty discount
- total
- minimum food order

The maximum loyalty discount is 3%.

Do not promise a discount before the backend calculates it.

==========================================================
NEGOTIATION
==========================================================

You may help a customer find a cheaper option.

Possible approaches:

- smaller portion where supported
- no meat
- no chicken
- no plantain
- simpler order
- returning-customer loyalty discount when applicable

Never invent a new menu price.

Never override backend pricing rules.

Never claim manager approval unless the manager actually
approved something.

==========================================================
DELIVERY STATUS
==========================================================

Whenever the customer asks:

"Where is my food?"
"What is the status?"
"Has it been sent?"
"Is my food on the way?"
"Why haven't I received it?"

Use get_latest_order_status.

Do not answer from memory.

==========================================================
CUSTOMER RECEIVED FOOD
==========================================================

If the customer says:

"I received my food"
"I got my food"
"The food has arrived"
"I have received it"

use report_food_received.

That updates the backend and informs the manager.

Do NOT automatically mark payment as confirmed.

==========================================================
RESPONSE STYLE
==========================================================

Keep WhatsApp responses concise.

Usually 1-5 short paragraphs.

Use readable formatting.

Never expose internal tool names.

Never mention "the LLM", "database", "function calling",
"system prompt", or internal architecture.

==========================================================
CURRENT LAGOS TIME
==========================================================

{current_time}
"""


# =========================================================
# MANAGER SYSTEM PROMPT
# =========================================================

MANAGER_SYSTEM_PROMPT = """
You are Bola, the restaurant operations agent for
Digital Waiter Restaurant.

The person speaking to you is the restaurant manager.

Your job is to convert natural-language manager messages
into real backend actions.

You are an AGENT.

Do not merely reply conversationally when an actual order
action is requested.

==========================================================
SOURCE OF TRUTH
==========================================================

The database is the source of truth.

Use tools.

Never claim that an order changed status unless the tool
successfully changed it.

==========================================================
MANAGER EXAMPLES
==========================================================

Manager:

"John's delivery is on the way."

You should:

1. Find John's order.
2. Mark it out_for_delivery.
3. The tool will notify John.

Manager:

"John's food is being prepared."

You should:

1. Find John's order.
2. Mark it preparing.
3. The tool will notify John.

Manager:

"John has received his food."

You should:

1. Find John's order.
2. Mark it received.
3. The tool will notify John.

Manager:

"Cash received from John."

You should:

1. Find John's order.
2. Confirm payment.
3. The tool will notify John.

Manager:

"Order received."

You should acknowledge the latest order that is genuinely
waiting for manager acknowledgement.

==========================================================
ORDER REFERENCES
==========================================================

Managers may refer to orders by:

- customer name
- order ID
- order ID without DW-
- customer WhatsApp number

The backend handles matching.

==========================================================
IMPORTANT
==========================================================

Never mark payment confirmed because a CUSTOMER said they paid.

Only the manager can confirm payment through the manager
agent.

Do not invent delivery ETA.

Do not invent payment confirmation.

Do not invent preparation status.

==========================================================
STYLE
==========================================================

Keep manager responses short.

Confirm the actual action that was successfully performed.

Do not expose internal architecture.
"""


# =========================================================
# MESSAGE CONVERSION
# =========================================================

def serialize_assistant_message(
    message,
):

    result = {
        "role": "assistant",
    }

    if getattr(
        message,
        "content",
        None,
    ) is not None:

        result["content"] = (
            message.content
        )

    if getattr(
        message,
        "tool_calls",
        None,
    ):

        result["tool_calls"] = []

        for call in message.tool_calls:

            result["tool_calls"].append({

                "id":
                    call.id,

                "type":
                    "function",

                "function": {

                    "name":
                        call.function.name,

                    "arguments":
                        call.function.arguments,
                },
            })

    return result


# =========================================================
# TOOL EXECUTION
# =========================================================

async def execute_tool(
    function,
    arguments,
):

    result = function(
        **arguments
    )

    if inspect.isawaitable(
        result
    ):

        result = await result

    return result


# =========================================================
# CUSTOMER CONTEXT
# =========================================================

def build_customer_context(
    customer_number,
):

    customer = get_customer(
        customer_number
    )

    latest_order = (
        get_latest_customer_order(
            customer_number
        )
    )

    context = {

        "customer_profile":
            customer or {
                "exists": False
            },

        "latest_order":
            latest_order,

        "recent_conversation":
            get_recent_messages(
                customer_number,
                limit=12,
            ),
    }

    return json.dumps(
        context,
        ensure_ascii=False,
        default=str,
    )


# =========================================================
# RUN CUSTOMER AGENT
# =========================================================

async def run_customer_agent(
    customer_number,
    user_text,
):

    logger.info(
        "Running customer agent for %s",
        customer_number,
    )

    tools = build_customer_tools(
        customer_number,
        user_text,
    )

    messages = [

        {
            "role":
                "system",

            "content":
                CUSTOMER_SYSTEM_PROMPT.format(
                    current_time=
                        lagos_time()
                ),
        },

        {
            "role":
                "system",

            "content":
                (
                    "VERIFIED CUSTOMER CONTEXT:\n"
                    + build_customer_context(
                        customer_number
                    )
                ),
        },

        {
            "role":
                "user",

            "content":
                user_text,
        },
    ]

    for turn in range(
        settings.MAX_AGENT_TURNS
    ):

        response = (
            await client.chat.completions.create(

                model=
                    settings.GROQ_MODEL,

                messages=
                    messages,

                tools=
                    CUSTOMER_TOOL_SCHEMAS,

                tool_choice=
                    "auto",

                parallel_tool_calls=
                    False,

                temperature=
                    0.2,

                reasoning_effort=
                    "low",

                include_reasoning=
                    False,

                max_completion_tokens=
                    2048,

                stream=
                    False,
            )
        )

        message = (
            response.choices[0].message
        )

        tool_calls = (
            message.tool_calls
            or []
        )

        # -------------------------------------------------
        # FINAL RESPONSE
        # -------------------------------------------------

        if not tool_calls:

            answer = (
                message.content
                or
                "No problem. How can I help you?"
            )

            return answer.strip()

        # -------------------------------------------------
        # TOOL CALL
        # -------------------------------------------------

        messages.append(
            serialize_assistant_message(
                message
            )
        )

        for tool_call in tool_calls:

            function_name = (
                tool_call.function.name
            )

            function = tools.get(
                function_name
            )

            if not function:

                result = json.dumps({

                    "error":
                        "Unknown tool.",

                    "is_error":
                        True,
                })

            else:

                try:

                    arguments = json.loads(
                        tool_call.function.arguments
                        or "{}"
                    )

                    logger.info(
                        "Customer agent tool: %s %s",
                        function_name,
                        arguments,
                    )

                    result = (
                        await execute_tool(
                            function,
                            arguments,
                        )
                    )

                except Exception as error:

                    logger.exception(
                        "Tool execution failed: %s",
                        function_name,
                    )

                    result = json.dumps({

                        "error":
                            str(error),

                        "is_error":
                            True,
                    })

            messages.append({

                "role":
                    "tool",

                "tool_call_id":
                    tool_call.id,

                "name":
                    function_name,

                "content":
                    str(result),
            })

    return (
        "I'm sorry, I'm having trouble completing "
        "that request right now. Please try again."
    )


# =========================================================
# RUN MANAGER AGENT
# =========================================================

async def run_manager_agent(
    manager_number,
    user_text,
):

    logger.info(
        "Running manager agent"
    )

    tools = build_manager_tools(
        manager_number,
        user_text,
    )

    messages = [

        {
            "role":
                "system",

            "content":
                MANAGER_SYSTEM_PROMPT,
        },

        {
            "role":
                "user",

            "content":
                user_text,
        },
    ]

    for turn in range(
        settings.MAX_AGENT_TURNS
    ):

        response = (
            await client.chat.completions.create(

                model=
                    settings.GROQ_MODEL,

                messages=
                    messages,

                tools=
                    MANAGER_TOOL_SCHEMAS,

                tool_choice=
                    "auto",

                parallel_tool_calls=
                    False,

                temperature=
                    0.1,

                reasoning_effort=
                    "low",

                include_reasoning=
                    False,

                max_completion_tokens=
                    1200,

                stream=
                    False,
            )
        )

        message = (
            response.choices[0].message
        )

        tool_calls = (
            message.tool_calls
            or []
        )

        if not tool_calls:

            answer = (
                message.content
                or
                "Done."
            )

            return answer.strip()

        messages.append(
            serialize_assistant_message(
                message
            )
        )

        for tool_call in tool_calls:

            function_name = (
                tool_call.function.name
            )

            function = tools.get(
                function_name
            )

            if not function:

                result = json.dumps({

                    "error":
                        "Unknown manager tool.",

                    "is_error":
                        True,
                })

            else:

                try:

                    arguments = json.loads(
                        tool_call.function.arguments
                        or "{}"
                    )

                    logger.info(
                        "Manager tool: %s %s",
                        function_name,
                        arguments,
                    )

                    result = (
                        await execute_tool(
                            function,
                            arguments,
                        )
                    )

                except Exception as error:

                    logger.exception(
                        "Manager tool failed"
                    )

                    result = json.dumps({

                        "error":
                            str(error),

                        "is_error":
                            True,
                    })

            messages.append({

                "role":
                    "tool",

                "tool_call_id":
                    tool_call.id,

                "name":
                    function_name,

                "content":
                    str(result),
            })

    return (
        "I couldn't complete that operation. "
        "Please try the update again."
    )


# =========================================================
# PUBLIC FUNCTIONS
# =========================================================

async def handle_customer(
    customer_number,
    text,
):

    save_message(
        customer_number,
        "customer",
        text,
    )

    reply = await run_customer_agent(
        customer_number,
        text,
    )

    save_message(
        customer_number,
        "bola",
        reply,
    )

    return reply


async def handle_manager(
    manager_number,
    text,
):

    reply = await run_manager_agent(
        manager_number,
        text,
    )

    return reply
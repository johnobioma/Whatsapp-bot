import logging
import re

from fastapi import (
    APIRouter,
    Query,
    Request,
    Response,
)

from fastapi.responses import (
    PlainTextResponse,
)

from app.config import settings
from app.database import (
    already_processed,
    init_db,
    mark_processed,
)
from app.agent.agent import (
    handle_customer,
    handle_manager,
)
from app.services.audio import (
    transcribe_audio,
)
from app.services.whatsapp import (
    download_media,
    get_media_url,
    send_text_message,
)


logger = logging.getLogger(
    "webhook"
)


router = APIRouter()


# =========================================================
# INITIALIZE DATABASE
# =========================================================

init_db()


# =========================================================
# PHONE
# =========================================================

def clean_phone(
    phone,
):

    if not phone:
        return ""

    return re.sub(
        r"\D",
        "",
        phone,
    )


def is_manager(
    phone,
):

    return (
        clean_phone(phone)
        ==
        clean_phone(
            settings.OWNER_WHATSAPP_NUMBER
        )
    )


# =========================================================
# VERIFY WEBHOOK
# =========================================================

@router.get("/webhook")
async def verify_webhook(

    hub_mode: str = Query(
        None,
        alias="hub.mode",
    ),

    hub_challenge: str = Query(
        None,
        alias="hub.challenge",
    ),

    hub_verify_token: str = Query(
        None,
        alias="hub.verify_token",
    ),
):

    if (
        hub_mode == "subscribe"
        and
        hub_verify_token
        == settings.VERIFY_TOKEN
    ):

        logger.info(
            "Webhook verification successful"
        )

        return PlainTextResponse(
            content=
                hub_challenge,

            status_code=
                200,
        )

    logger.warning(
        "Webhook verification failed"
    )

    return Response(
        status_code=403
    )


# =========================================================
# PROCESS TEXT
# =========================================================

async def process_text_message(
    from_number,
    text,
):

    text = (
        text
        or ""
        .strip()
    )

    if not text:
        return

    # -----------------------------------------------------
    # MANAGER
    # -----------------------------------------------------

    if is_manager(
        from_number
    ):

        reply = await handle_manager(
            from_number,
            text,
        )

        await send_text_message(
            from_number,
            reply,
        )

        return

    # -----------------------------------------------------
    # CUSTOMER
    # -----------------------------------------------------

    reply = await handle_customer(
        from_number,
        text,
    )

    await send_text_message(
        from_number,
        reply,
    )


# =========================================================
# PROCESS AUDIO
# =========================================================

async def process_audio_message(
    from_number,
    message,
):

    audio_id = (
        message
        .get("audio", {})
        .get("id")
    )

    if not audio_id:

        await send_text_message(
            from_number,
            "I couldn't find the voice note. Please send it again.",
        )

        return

    try:

        media_url = (
            await get_media_url(
                audio_id
            )
        )

        audio_bytes = (
            await download_media(
                media_url
            )
        )

        transcript = (
            await transcribe_audio(
                audio_bytes
            )
        )

        transcript = (
            transcript
            or ""
            .strip()
        )

        if not transcript:

            await send_text_message(
                from_number,
                "I couldn't hear that voice note clearly. Please send it again or type your message.",
            )

            return

        logger.info(
            "Voice transcript for %s: %s",
            from_number,
            transcript,
        )

        await process_text_message(
            from_number,
            transcript,
        )

    except Exception as error:

        logger.exception(
            "Audio processing failed: %s",
            error,
        )

        await send_text_message(
            from_number,
            "I couldn't process that voice note. Please send it again or type your message.",
        )


# =========================================================
# WEBHOOK POST
# =========================================================

@router.post("/webhook")
async def receive_message(
    request: Request,
):

    try:

        body = await request.json()

        logger.info(
            "Incoming webhook payload received"
        )

        entries = body.get(
            "entry",
            [],
        )

        for entry in entries:

            changes = entry.get(
                "changes",
                [],
            )

            for change in changes:

                value = change.get(
                    "value",
                    {},
                )

                messages = value.get(
                    "messages",
                    [],
                )

                if not messages:
                    continue

                for message in messages:

                    message_id = (
                        message.get("id")
                    )

                    if not message_id:
                        continue

                    # -------------------------------------
                    # DUPLICATE PROTECTION
                    # -------------------------------------

                    if already_processed(
                        message_id
                    ):

                        logger.info(
                            "Duplicate ignored: %s",
                            message_id,
                        )

                        continue

                    mark_processed(
                        message_id
                    )

                    from_number = (
                        message.get("from")
                    )

                    message_type = (
                        message.get("type")
                    )

                    if not from_number:
                        continue

                    logger.info(
                        "Message from %s type=%s",
                        from_number,
                        message_type,
                    )

                    # =====================================
                    # TEXT
                    # =====================================

                    if message_type == "text":

                        text = (
                            message
                            .get("text", {})
                            .get("body", "")
                        )

                        await process_text_message(
                            from_number,
                            text,
                        )

                    # =====================================
                    # AUDIO
                    # =====================================

                    elif message_type == "audio":

                        await process_audio_message(
                            from_number,
                            message,
                        )

                    # =====================================
                    # UNSUPPORTED
                    # =====================================

                    else:

                        await send_text_message(
                            from_number,
                            "I can currently help with text messages and voice notes. Please send your request as text or a voice note.",
                        )

        return {
            "status":
                "ok"
        }

    except Exception as error:

        logger.exception(
            "Webhook processing error: %s",
            error,
        )

        # Always return 200 to Meta.
        return {
            "status":
                "ok"
        }
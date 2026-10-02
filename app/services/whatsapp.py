import logging

import httpx

from app.config import settings


logger = logging.getLogger("whatsapp")


# =========================================================
# GRAPH API URL
# =========================================================

def graph_url(path):

    return (
        f"https://graph.facebook.com/"
        f"{settings.GRAPH_API_VERSION}/"
        f"{path}"
    )


# =========================================================
# SEND TEXT
# =========================================================

async def send_text_message(
    recipient,
    text,
):

    url = graph_url(
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization":
            f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",

        "Content-Type":
            "application/json",
    }

    payload = {

        "messaging_product":
            "whatsapp",

        "to":
            recipient,

        "type":
            "text",

        "text": {
            "body":
                text,
        },
    }

    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        response = await client.post(
            url,
            headers=headers,
            json=payload,
        )

    if response.status_code >= 400:

        logger.error(
            "WhatsApp send failed: %s %s",
            response.status_code,
            response.text,
        )

        response.raise_for_status()

    return response.json()


# =========================================================
# GET MEDIA URL
# =========================================================

async def get_media_url(
    media_id,
):

    url = graph_url(
        media_id
    )

    headers = {
        "Authorization":
            f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
    }

    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        response = await client.get(
            url,
            headers=headers,
        )

    response.raise_for_status()

    data = response.json()

    return data["url"]


# =========================================================
# DOWNLOAD MEDIA
# =========================================================

async def download_media(
    media_url,
):

    headers = {
        "Authorization":
            f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
    }

    async with httpx.AsyncClient(
        timeout=60
    ) as client:

        response = await client.get(
            media_url,
            headers=headers,
        )

    response.raise_for_status()

    return response.content
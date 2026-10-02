import io

from groq import AsyncGroq

from app.config import settings


client = AsyncGroq(
    api_key=settings.GROQ_API_KEY
)


async def transcribe_audio(
    audio_bytes,
):

    audio_file = io.BytesIO(
        audio_bytes
    )

    audio_file.name = "whatsapp_audio.ogg"

    transcription = (
        await client.audio.transcriptions.create(
            file=(
                "whatsapp_audio.ogg",
                audio_bytes,
            ),

            model=
                settings.GROQ_TRANSCRIPTION_MODEL,

            language="en",

            response_format="json",

            temperature=0,
        )
    )

    return (
        transcription.text
        if transcription
        else ""
    )
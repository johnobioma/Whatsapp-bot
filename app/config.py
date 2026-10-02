from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Groq
    GROQ_API_KEY: str
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    AI_TRANSCRIPTION_MODEL: str = "whisper-large-v3-turbo"

    # Meta WhatsApp
    VERIFY_TOKEN: str
    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    OWNER_WHATSAPP_NUMBER: str
    GRAPH_API_VERSION: str = "v20.0"

    # Restaurant
    RESTAURANT_NAME: str = "Digital Waiter Restaurant"
    RESTAURANT_LOCATION: str = "Lagos, Nigeria"

    # Database
    DATABASE_NAME: str = "restaurant_agent.db"

    # Agent
    MAX_AGENT_TURNS: int = 8

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
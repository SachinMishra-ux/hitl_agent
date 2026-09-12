import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Settings
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.7

    # LinkedIn Settings
    LINKEDIN_ACCESS_TOKEN: Optional[str] = None
    LINKEDIN_AUTHOR_URN: Optional[str] = None
    LINKEDIN_API_VERSION: str = "202511"
    LINKEDIN_SIMULATION_MODE: bool = False

    # Email / Notification Settings
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    NOTIFICATION_EMAIL: Optional[str] = "sachin19566@gmail.com"
    SENDER_EMAIL: Optional[str] = "no-reply@hitlagent.local"

    # Application & Persistence Settings
    APP_NAME: str = "Human-in-the-Loop LinkedIn Agent"
    BASE_URL: str = "http://localhost:8000"
    DATA_DIR: str = str(BASE_DIR / "data")
    SQLITE_DB_PATH: str = str(BASE_DIR / "data" / "checkpoints.db")
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # Logging Settings


settings = Settings()

# Ensure data directory exists
os.makedirs(settings.DATA_DIR, exist_ok=True)

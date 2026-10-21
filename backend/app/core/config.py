from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Vietnamese Bonded Warehouse AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Gemini API Settings (Backend Only - NEVER exposed to frontend)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_TIMEOUT_SECONDS: int = 60

    # Database
    DATABASE_URL: str = "sqlite:///./bonded_warehouse.db"

    # Storage Paths (Preserved original documents stored in data/uploads/)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOAD_DIR: Path = BASE_DIR.parent / "data" / "uploads"
    MAX_UPLOAD_SIZE_MB: int = 25

    DEMO_ONLY: bool = False
    DEMO_AI_REQUESTS_PER_HOUR: int = 20
    DEMO_SAMPLES_DIR: Path = BASE_DIR.parent / "frontend" / "public" / "samples"
    FRONTEND_DIR: Path = BASE_DIR.parent / "frontend" / "dist"

    # CORS settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://*.vercel.app",
        "*"
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure uploads directory exists safely on Windows 10
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Medquest Proof Corrector"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "postgresql://user:password@localhost/medquest_corrector"
    REDIS_URL: str = "redis://localhost:6379/0"

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_VISION_MODEL: str = "qwen/qwen2.5-vl-72b-instruct"
    OPENROUTER_VISION_FALLBACKS: str = (
        "qwen/qwen2.5-vl-32b-instruct,qwen/qwen-2.5-vl-7b-instruct,google/gemini-2.5-flash"
    )
    OPENROUTER_TEXT_MODEL: str = "openai/gpt-oss-120b"
    OPENROUTER_TEXT_FALLBACKS: str = (
        "openai/gpt-oss-20b,meta-llama/llama-3.1-8b-instruct,qwen/qwen3-235b-a22b-2507"
    )
    OPENROUTER_HTTP_REFERER: str = ""
    OPENROUTER_APP_TITLE: str = "MedQuest Discursive Grading"
    OPENROUTER_TIMEOUT_SECONDS: float = 90.0
    OCR_PROVIDER: str = "mistral,google_vision"
    MISTRAL_API_KEY: str = ""
    MISTRAL_OCR_MODEL: str = "mistral-ocr-latest"
    GOOGLE_VISION_API_KEY: str = ""

    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    UPLOAD_DIR: Path = Path("uploads")
    MAX_UPLOAD_MB: int = 40

    MAX_CSV_MB: int = 5
    MAX_CSV_ROWS: int = 2000

    JWT_SECRET_KEY: str = "dev-only-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    def cors_origin_list(self) -> List[str]:
        parts = [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]
        return parts if parts else ["http://localhost:3000"]


settings = Settings()

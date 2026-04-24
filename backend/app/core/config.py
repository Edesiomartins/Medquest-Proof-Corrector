from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Medquest Proof Corrector"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "postgresql://user:password@localhost/medquest_corrector"
    REDIS_URL: str = "redis://localhost:6379/0"

    OPENROUTER_API_KEY: str = ""
    OCR_PROVIDER: str = "google_vision"
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

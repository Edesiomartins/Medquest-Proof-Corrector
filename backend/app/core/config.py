from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Medquest Proof Corrector"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/medquest_corrector"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # OpenRouter
    OPENROUTER_API_KEY: str = ""

    # Azure OCR
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = ""
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str = ""

    # CORS — lista separada por vírgula; dev padrão inclui Next.js local
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Armazenamento local de uploads (dev / até integrar S3)
    UPLOAD_DIR: Path = Path("uploads")
    MAX_UPLOAD_MB: int = 40

    # CSV de turmas
    MAX_CSV_MB: int = 5
    MAX_CSV_ROWS: int = 2000

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    def cors_origin_list(self) -> List[str]:
        parts = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        return parts if parts else ["http://localhost:3000"]


settings = Settings()

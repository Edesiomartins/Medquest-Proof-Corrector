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

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()

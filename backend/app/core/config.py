from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl

class Settings(BaseSettings):
    """
    Application settings managed by pydantic-settings.
    Values can be overridden by environment variables (e.g., PROJECT_NAME="My App").
    """
    PROJECT_NAME: str = "AURORA"
    ENVIRONMENT: str = "development"
    
    # API prefix for all v1 routes
    API_V1_STR: str = "/api/v1"
    
    # CORS Origins
    # In development, we typically allow localhost. In production, this should be restricted.
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Configuration for loading environment variables from a .env file (if present)
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

# Instantiate a global settings object to be used throughout the app
settings = Settings()

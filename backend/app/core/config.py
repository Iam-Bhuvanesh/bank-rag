import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Base Directory of the backend project (backend/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Detect and resolve the path to the .env file in multiple environments (local / docker)
ENV_FILE_PATH = Path(".env")
if not ENV_FILE_PATH.exists():
    # If run from backend/app/, check parent directory (backend/)
    backend_env = BASE_DIR / ".env"
    if backend_env.exists():
        ENV_FILE_PATH = backend_env
    else:
        # If run from root (e.g. docker-compose), check root directory (one level up from backend/)
        root_env = BASE_DIR.parent / ".env"
        if root_env.exists():
            ENV_FILE_PATH = root_env

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and config files.
    Includes validation and default fallbacks.
    """
    # Project Details
    PROJECT_NAME: str = Field(default="AI-Powered Bank Statement Analysis System")
    PROJECT_VERSION: str = Field(default="1.0.0")
    API_V1_STR: str = Field(default="/api/v1")

    # PostgreSQL Database Credentials
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="secure_postgres_password_change_me")
    POSTGRES_DB: str = Field(default="bank_statement_rag")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)

    # ChromaDB Configuration
    CHROMA_HOST: str = Field(default="localhost")
    CHROMA_PORT: int = Field(default=8000)

    # LLM Settings
    OPENAI_API_KEY: str = Field(default="")

    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO")

    # Settings configurations
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH) if ENV_FILE_PATH.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def database_url(self) -> str:
        """
        Dynamically constructs the synchronous SQLAlchemy PostgreSQL connection URI (for Alembic).
        """
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def async_database_url(self) -> str:
        """
        Dynamically constructs the asynchronous SQLAlchemy PostgreSQL connection URI (for FastAPI).
        """
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

# Global settings instance
settings = Settings()

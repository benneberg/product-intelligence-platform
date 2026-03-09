"""
Application configuration using Pydantic Settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "Product Intelligence Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    POSTGRES_USER: str = "pip_user"
    POSTGRES_PASSWORD: str = "pip_password"
    POSTGRES_DB: str = "pip_db"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://pip_user:pip_password@postgres:5432/pip_db"
    )

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    CELERY_BROKER_URL: str = Field(
        default="redis://redis:6379/0"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://redis:6379/1"
    )

    # Browser Automation
    PLAYWRIGHT_BROWSERS_PATH: str = "/ms-playwright"
    HEADLESS: bool = True
    VIEWPORT_WIDTH: int = 1920
    VIEWPORT_HEIGHT: int = 1080
    DEFAULT_USER_AGENT: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # AI Configuration (OpenAI)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 1000

    # AI Configuration (Anthropic)
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"

    # AI Configuration (Groq)
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama3-70b-8192"

    # AI Configuration (OpenRouter)
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "meta-llama/llama-3-70b-instruct"

    # Provider selection
    LLM_PROVIDER: str = "openai"

    # Simulation Settings
    MAX_STEPS: int = 50
    MAX_DURATION_SECONDS: int = 900
    DEFAULT_PERSONA: str = "curious_beginner"
    EXPLORATION_PROBABILITY: float = 0.25
    MISTAKE_PROBABILITY: float = 0.10
    MIN_PAUSE_SECONDS: float = 2.0
    MAX_PAUSE_SECONDS: float = 5.0


# Create settings instance
settings = Settings()

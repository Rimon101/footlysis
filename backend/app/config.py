from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    DATABASE_URL: str = "sqlite+aiosqlite:///./footlysis.db"

    @property
    def get_database_url(self) -> str:
        # Render supplies postgres:// but SQLAlchemy async needs postgresql+asyncpg://
        if self.DATABASE_URL.startswith("postgres://"):
            return self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        return self.DATABASE_URL
    SECRET_KEY: str = "footlysis-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    FOOTBALL_DATA_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    ENVIRONMENT: str = "development"


settings = Settings()

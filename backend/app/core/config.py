from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEAMFLOW_",
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["development", "production", "test"] = "development"
    database_url: str = "sqlite:///./data/teamflow.db"
    upload_dir: Path = Path("./data/uploads")
    max_upload_mb: int = 10

    session_idle_hours: int = 12
    session_max_days: int = 7
    cookie_secure: bool = False
    session_cookie_name: str = "teamflow_session"
    csrf_cookie_name: str = "teamflow_csrf"
    csrf_header_name: str = "X-CSRF-Token"

    login_max_failures: int = 5
    login_lockout_minutes: int = 15

    cors_origins: Annotated[list[str], NoDecode] = []
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _resolve_sqlite_path(cls, value: str) -> str:
        # Relative SQLite paths resolve from backend/, not from whatever the CWD happens to be.
        prefix = "sqlite:///"
        if value.startswith(prefix) and not value.startswith(prefix + "/") and ":memory:" not in value:
            path = Path(value[len(prefix) :])
            if not path.is_absolute():
                return prefix + (BACKEND_DIR / path).resolve().as_posix()
        return value

    @field_validator("upload_dir")
    @classmethod
    def _resolve_upload_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()

    @model_validator(mode="after")
    def _production_checks(self) -> "Settings":
        if self.env == "production" and not self.cookie_secure:
            raise ValueError("TEAMFLOW_COOKIE_SECURE must be true in production (serve over HTTPS)")
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()

import logging

from app.core.config import get_settings


def configure_logging() -> None:
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Uvicorn's access log records paths and status codes only (no bodies, cookies or headers).

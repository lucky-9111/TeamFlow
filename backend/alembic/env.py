from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import create_db_engine
from app.models import Base
from app.models.base import UTCDateTime

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _render_item(type_, obj, autogen_context):
    # Keep migrations independent of app code: UTCDateTime is a plain DateTime(timezone=True).
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def _database_url() -> str:
    # Tests pass an explicit URL via the Alembic config; otherwise use app settings.
    return config.attributes.get("database_url") or get_settings().database_url


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=url.startswith("sqlite"),
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _database_url()
    is_sqlite = url.startswith("sqlite")
    engine = create_db_engine(url, enforce_foreign_keys=False)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
            compare_type=True,
            render_item=_render_item,
        )
        with context.begin_transaction():
            context.run_migrations()
            if is_sqlite:
                violations = connection.execute(text("PRAGMA foreign_key_check")).fetchall()
                if violations:
                    raise RuntimeError(f"Migration left foreign key violations: {violations[:10]}")
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

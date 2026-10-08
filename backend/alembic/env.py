from alembic import context

import app.db.models  # noqa: F401  (registers tables)
from app.db.session import Base, get_engine

target_metadata = Base.metadata


def run_migrations_online():
    with get_engine().connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True,
                          render_as_batch=conn.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()


def run_migrations_offline():
    from app.core.settings import get_settings
    context.configure(url=get_settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

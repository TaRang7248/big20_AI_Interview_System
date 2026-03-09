from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context # runtime-injected by Alembic. 
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from dotenv import load_dotenv

# from IMH.IMH_no_api.IMH_no_api.db.base import Base
# from IMH.IMH_no_api.IMH_no_api.models import user, auth_token, candidate_profile, interview, transcript, event_log, qa  # noqa: F401

from IMH.IMH_with_api.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# .env 로드 (alembic 명령 실행 위치가 루트라는 가정)
load_dotenv()
POSTGRES_CONNECTION_STRING = os.getenv("POSTGRES_CONNECTION_STRING")
if not POSTGRES_CONNECTION_STRING:
    raise RuntimeError("POSTGRES_CONNECTION_STRING is not set. Check your .env")

# alembic.ini의 sqlalchemy.url 값을 런타임에 덮어쓰기
config.set_main_option("sqlalchemy.url", POSTGRES_CONNECTION_STRING)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """오프라인 모드 마이그레이션 실행.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection) -> None:
    """실제 마이그레이션 실행."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """온라인(Async) 모드 마이그레이션 실행.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        
    await connectable.dispose()
    

if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
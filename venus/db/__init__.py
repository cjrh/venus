import asyncio
import json
import logging
from typing import Awaitable

import asyncpg
import asyncpg.pool
import biodome

logger = logging.getLogger(__name__)


DATABASE_POOL: asyncpg.pool.Pool = None


get_db_username = biodome.environ.get_callable('DB_USERNAME', 'postgres')
get_db_name = biodome.environ.get_callable('DB_NAME', 'venus')
get_db_password = biodome.environ.get_callable('DB_PASSWORD', 'password')
get_db_host = biodome.environ.get_callable('DB_HOST', 'localhost')
get_db_port = biodome.environ.get_callable('DB_PORT', 5432)


def create_pool() -> Awaitable[asyncpg.pool.Pool]:
    """ Helper to implicitly use the env vars """
    db_url = (
        f'postgres://{get_db_username()}:{get_db_password()}'
        f'@{get_db_host()}:{get_db_port()}/{get_db_name()}'
    )
    db_url_safe = (
        f'postgres://{get_db_username()}:XXXXXXXXX'
        f'@{get_db_host()}:{get_db_port()}/{get_db_name()}'
    )
    logging.debug(f'Connecting to database: {db_url_safe}')
    # Create the pool with no connections pre-initialised. This allows us
    # to create the pool instance outside of the main application loop.
    # If min_size > 0, and a connection create attempt (made while creating
    # the pool instance) failed, it would prevent the main application loop
    # from coming up.
    return asyncpg.create_pool(db_url, init=set_json_charset, min_size=0,
                               # There is only one writer.
                               max_size=2)


async def set_json_charset(connection):
    """
    Allow asyncpg to encode/decode JSONB types with the ::json suffix in
    queries. Used in create_pool.
    """

    await connection.set_type_codec(
        'json',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog'
    )


async def init_database_pool():
    """Set the module-level identifier with a new database pool object."""
    global DATABASE_POOL
    if not DATABASE_POOL:
        DATABASE_POOL = await create_pool()


async def destroy_database_pool():
    global DATABASE_POOL
    if DATABASE_POOL:
        await DATABASE_POOL.close()
        DATABASE_POOL = None


class DatabasePool:
    """ A context manager for pool handling."""
    async def __aenter__(self) -> asyncpg.pool.Pool:
        await init_database_pool()
        return DATABASE_POOL

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await destroy_database_pool()


def get_db_pool():
    return DATABASE_POOL


async def activate():
    """Decorator for maintaining the db pool"""
    await init_database_pool()
    try:
        await asyncio.sleep(1e9)
    except asyncio.CancelledError:
        await destroy_database_pool()

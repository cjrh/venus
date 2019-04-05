import json
import pathlib
import random
import sys
import asyncio
import uuid
import asyncpg
import os

from contextlib import contextmanager
from datetime import datetime, timezone

import biodome
import pytest
import dockerctx
import alembic.config
import logging
import sqlalchemy
from typing import NamedTuple

from asyncpg import Connection

from venus.db import (
    init_database_pool,
    get_db_pool,
    destroy_database_pool,
    create_pool
)


# Alembic only works from the project root, so let's just go there.
os.chdir(pathlib.Path(__file__).parent.parent)


logger = logging.getLogger(__name__)
logging.basicConfig(level='DEBUG', stream=sys.stdout)

get_db_username = biodome.environ.get_callable('DB_USERNAME', 'postgres')
get_db_name = biodome.environ.get_callable('DB_NAME', 'venus')
get_db_password = biodome.environ.get_callable('DB_PASSWORD', 'password')
get_db_host = biodome.environ.get_callable('DB_HOST', 'localhost')
get_db_port = biodome.environ.get_callable('DB_PORT', 55432)
os.environ['DEV_DBPORT'] = '55432'
os.environ['ENABLE_CONSUL_REFRESH'] = 'False'
MAX_BYTES = 2147483647
MAX_SPEED = 500000  # bps


@pytest.fixture(scope='module')
def db_pool():
    """ This fixture will set the application-level DB
    pool. Application code will use the created pool
    via the "get_db_pool()" function in the db module."""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_database_pool())
    try:
        yield get_db_pool()
    finally:
        loop.run_until_complete(destroy_database_pool())


@contextmanager
def db_pool_session():
    """ This DB pool is only for test functions and
    utilities, and is not available to application code."""
    loop = asyncio.get_event_loop()
    db_pool = loop.run_until_complete(create_pool())
    try:
        yield db_pool
    finally:
        loop.run_until_complete(db_pool.close())


@pytest.fixture(scope='session')
def db_fixture():
    db_username = 'postgres'  # default POSTGRES_USER value inside container
    db_password = 'password'
    db_host = 'localhost'
    db_port = biodome.environ.get('DEV_DBPORT', 0) or dockerctx.get_open_port()
    db_name = 'postgres'
    image_name = 'timescale/timescaledb:latest-pg10'

    with dockerctx.new_container(
            image_name=image_name,
            ports={'5432/tcp': db_port},
            tmpfs=['/tmp', '/var/lib/postgresql/data:rw'],
            ready_test=lambda: dockerctx.pg_ready(host=db_host, port=db_port),
            environment=['POSTGRES_PASSWORD=password'],
    ) as container:
        logger.info(
            f'Started {image_name} container with name {container.name}'
        )

        service_db_username = biodome.environ.get('DB_USERNAME', 'venus')
        service_db_password = biodome.environ.get('DB_PASSWORD', 'venus')
        service_db_name = biodome.environ.get('DB_NAME', 'venus')

        logger.debug(f'Creating database {service_db_name}')

        # Connect to the DB and add slump user + perms.
        # We still run all operations as postgres user, but connect as the
        # slump user during tests.
        db_connection_url = (
            f'postgres://{db_username}:{db_password}@'
            f'{db_host}:{db_port}/{db_name}'
        )
        engine = sqlalchemy.create_engine(db_connection_url)
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        engine.raw_connection().set_isolation_level(
            ISOLATION_LEVEL_AUTOCOMMIT
        )

        # CREATE DATABASE needs to happen outside of a transaction, so run the
        # other operations that need to run as user postgres on db postgres at
        # the same time.
        engine.execute(f"""CREATE ROLE {service_db_username} WITH LOGIN;""")
        engine.execute(
            f"""ALTER ROLE {service_db_username} WITH PASSWORD '{service_db_password}';""")
        engine.execute(f"""CREATE DATABASE {service_db_name}""")
        engine.dispose()

        db_connection_url = (
            f'postgres://{db_username}:{db_password}@'
            f'{db_host}:{db_port}/{service_db_name}'
        )

        with sqlalchemy.create_engine(db_connection_url,
                                      echo=True).connect() as connection:
            connection.execute(
                f"""CREATE SCHEMA {service_db_username} AUTHORIZATION {service_db_username};""")
            # Have to run these here because only superuser can install
            # these extensions.
            connection.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            connection.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')
            connection.execute('CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;')

        logger.debug(f'Running migrations on: {db_connection_url}')

        # Change to the slump user instead of the postgres user to run the
        # migrations.
        db_connection_url = (
            f'postgres://{service_db_username}:{service_db_password}@'
            f'{db_host}:{db_port}/{service_db_name}'
        )
        alembic.config.main(
            argv=['-x', f'url={db_connection_url}', 'upgrade', 'head'])

        os.environ['DB_USERNAME'] = service_db_username
        os.environ['DB_PASSWORD'] = service_db_password
        os.environ['DB_HOST'] = db_host
        os.environ['DB_PORT'] = str(db_port)
        os.environ['DB_NAME'] = service_db_name

        yield db_port


@pytest.fixture(scope='module')
def randomly_generated_data(request, db_fixture):
    loop = asyncio.get_event_loop()
    with db_pool_session() as db_pool:
        loop.run_until_complete(insert_data(db_pool))


async def insert_data(db_pool):
    t = datetime.now(tz=timezone.utc)

    """
    select *, data->'b'->'msg' from logs
    where
        -- Need to extract value "msg" before you can compare
        data->'b'->>'msg' ILIKE ANY(ARRAY['%tru%', '%he%'])
    """
    d = dict(
        a=1,
        b=dict(
            name='caleb',
            msg='hey this is what I was trying to say'
        )
    )

    async with db_pool.acquire() as conn:
        conn: Connection
        await conn.execute('''
            INSERT INTO logs VALUES (
                $1, $2, $3, $4
            )
        ''', t, 'blah blah blah', uuid.uuid4(), json.dumps(d))


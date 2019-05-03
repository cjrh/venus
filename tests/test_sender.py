import asyncio
import json
import os
import subprocess as sp
import sys
from pprint import pprint
from uuid import uuid4

import biodome
import portpicker
import pytest
from asyncpg import Connection

from venus import main, io, db


@pytest.fixture(scope='module')
def venus_runner(loop):
    port = portpicker.pick_unused_port()
    with biodome.env_change('VENUS_PORT', port), \
         io.zmq_context():
        venus_main_task = loop.create_task(main.amain(None))
        yield loop, port


def run_app(port, iterations, delay=0.2, env=None):
    if env:
        env = {**os.environ, **env}
    proc = sp.Popen([f'{sys.executable}', 'tests/sender.py',
                     '-p', f'{port}',
                     '-i', f'{iterations}',
                     '-d', f'{delay}'
                     ], env=env)
    return proc


def test_send_logs(db_fixture, db_pool_session, venus_runner):
    loop, port = venus_runner

    message_uuids = [str(uuid4()) for i in range(10)]
    env = dict(SENDER_ITEMS=str(message_uuids))

    with biodome.env_change('MAX_BATCH_SIZE', 1):
        proc = run_app(port, iterations=10, env=env)
        loop.run_until_complete(asyncio.sleep(3))
        if proc.poll() is None:
            proc.kill()

        # Fetch records from the DB to verify that the log messages arrived.
        async def get():
            # Cannot use the db_pool fixture, because it mutates the
            # db.DATABASE_POOL global, which is what main.amain *also* does.
            async with db_pool_session.acquire() as conn:
                conn: Connection
                return await conn.fetch('SELECT * FROM logs')

        records = loop.run_until_complete(get())
        pprint(records)
        logged_message_ids = {r['message'] for r in records}
        pprint(logged_message_ids)
        pprint(message_uuids)
        pprint(set(message_uuids) - logged_message_ids)
        assert logged_message_ids.issuperset(message_uuids)


def test_send_double(db_fixture, db_pool_session, venus_runner):
    loop, port = venus_runner

    message_uuids1 = [str(uuid4()) for i in range(10)]
    message_uuids2 = [str(uuid4()) for i in range(10)]
    env1 = dict(SENDER_ITEMS=str(message_uuids1))
    env2 = dict(SENDER_ITEMS=str(message_uuids2))

    with biodome.env_change('MAX_BATCH_SIZE', 1):
        proc1 = run_app(port, iterations=10, env=env1)
        proc2 = run_app(port, iterations=10, env=env2)
        loop.run_until_complete(asyncio.sleep(3))
        if proc1.poll() is None:
            proc1.kill()
        if proc2.poll() is None:
            proc2.kill()

        # Fetch records from the DB to verify that the log messages arrived.
        async def get():
            # Cannot use the db_pool fixture, because it mutates the
            # db.DATABASE_POOL global, which is what main.amain *also* does.
            async with db_pool_session.acquire() as conn:
                conn: Connection
                return await conn.fetch('SELECT * FROM logs')

        records = loop.run_until_complete(get())
        pprint(records)
        logged_message_ids = {r['message'] for r in records}
        pprint(logged_message_ids)
        assert logged_message_ids.issuperset(message_uuids1)
        assert logged_message_ids.issuperset(message_uuids2)


def test_extra(db_fixture, db_pool_session, venus_runner):
    loop, port = venus_runner

    messages = [
        dict(
            message='blah blah blah',
            correlation_id=str(uuid4()),
            random_timing_data=1.23,
            random_counter_data=42,
        ) for i in range(10)
    ]
    env = dict(SENDER_ITEMS=repr(messages))

    with biodome.env_change('MAX_BATCH_SIZE', 1):
        proc = run_app(port, iterations=10, delay=0.2, env=env)
        loop.run_until_complete(asyncio.sleep(3))
        if proc.poll() is None:
            proc.kill()

        # Fetch records from the DB to verify that the log messages arrived.
        async def get():
            # Cannot use the db_pool fixture, because it mutates the
            # db.DATABASE_POOL global, which is what main.amain *also* does.
            async with db_pool_session.acquire() as conn:
                conn: Connection
                return await conn.fetch('SELECT * FROM logs')

        records = loop.run_until_complete(get())

    expected_correlation_ids = {m['correlation_id'] for m in messages}
    pprint(records)
    my_data = [r for r in records if str(r['correlation_id']) in expected_correlation_ids]
    pprint(my_data)

    rec = my_data[0]
    assert rec['message'] == 'blah blah blah'

    fields = loop.run_until_complete(
        db.read.get_extra_data(rec['id'], pool=db_pool_session)
    )

    df = {
        f['name']: f['value'] for f in fields
    }

    assert df['filename'] == 'sender.py'
    assert df['pathname'] == 'tests/sender.py'
    assert df['random_timing_data'] == 1.23
    assert df['random_counter_data'] == 42

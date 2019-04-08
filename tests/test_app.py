import asyncio
import os
import signal
import subprocess as sp
import sys
import time
from pprint import pprint
from uuid import uuid4

import biodome
import portpicker
import pytest
from asyncpg import Connection


@pytest.fixture(scope='module')
def venus_runner(db_fixture):
    """This is the venus application"""
    port = portpicker.pick_unused_port()
    env = {**os.environ, **{k: str(v) for k, v in dict(MAX_BATCH_SIZE=1).items()}}
    proc = sp.Popen(['venus', '--port', str(port)], env=env)
    try:
        yield proc, port
    finally:
        print('Sending SIGTERM signal')
        proc.send_signal(signal.SIGTERM)

    try:
        proc.wait(timeout=2.0)
    except sp.TimeoutExpired:
        print('Process did not shutdown in 2 seconds. Killing.')
        proc.kill()


def run_app(port, iterations, delay=0.2, env=None):
    """This is a fake microservice"""
    if env:
        env = {**os.environ, **env}
    proc = sp.Popen([f'{sys.executable}', 'tests/sender.py',
                     '-p', f'{port}',
                     '-i', f'{iterations}',
                     '-d', f'{delay}'
                     ], env=env)
    return proc


def test_send_logs(db_fixture, db_pool_session, venus_runner):
    proc_venus, port = venus_runner
    # Give it a moment to start up
    time.sleep(1)

    message_uuids = [str(uuid4()) for i in range(10)]
    env = dict(SENDER_ITEMS=str(message_uuids))

    with biodome.env_change('MAX_BATCH_SIZE', 1):
        proc_app = run_app(port, iterations=10, env=env)
        time.sleep(3)  # Wait for the app to finish
        if not proc_app.poll():
            print('Fake app still not finished. Killing.')
            proc_app.kill()

        # Fetch records from the DB to verify that the log messages arrived.
        async def get():
            # Cannot use the db_pool fixture, because it mutates the
            # db.DATABASE_POOL global, which is what main.amain *also* does.
            async with db_pool_session.acquire() as conn:
                conn: Connection
                return await conn.fetch('SELECT * FROM logs')

        loop = asyncio.get_event_loop()
        records = loop.run_until_complete(get())
        pprint(records)
        logged_message_ids = {r['message'] for r in records}
        pprint(logged_message_ids)
        assert logged_message_ids.issuperset(message_uuids)

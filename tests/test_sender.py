import asyncio
import os
import subprocess as sp
import sys
from pprint import pprint

import biodome
import portpicker
import pytest
from asyncpg import Connection

from venus import main, io


def run_app(port, iterations, delay):
    proc = sp.Popen([f'{sys.executable}', 'tests/sender.py',
                     '-p', f'{port}',
                     '-i', f'{iterations}',
                     ])
    return proc


def test_send_logs(randomly_generated_data, db_pool):
    port = portpicker.pick_unused_port()

    if os.name == 'ntt':
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    message_uuids = set()

    with biodome.env_change('VENUS_PORT', port), \
            biodome.env_change('MAX_BATCH_SIZE', 1), \
            io.zmq_context():
        venus_main_task = loop.create_task(main.amain(None))
        run_app(port, iterations=10, delay=1.0)
        loop.run_until_complete(asyncio.sleep(12))

        # Fetch records from the DB to verify that the log messages arrived.
        async def get():
            async with db_pool.acquire() as conn:
                conn: Connection
                return await conn.fetch('SELECT * FROM logs')

        records = loop.run_until_complete(get())

        # Clean up. Cancel the main app
        venus_main_task.cancel()
        loop.run_until_complete(venus_main_task)

        pprint(records)
        logged_message_ids = {r['message'] for r in records}
        pprint(logged_message_ids)
        assert logged_message_ids.issuperset(message_uuids)

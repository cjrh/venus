import asyncio
import logging
import time
from collections import defaultdict
from pprint import pprint

import logjson
import pytest
import zmq
from asyncpg import Connection
from zmq.log.handlers import PUBHandler
from venus import main, io


@pytest.fixture(scope='function')
def pull_sock():
    ctx = zmq.Context()
    sock: zmq.Socket = ctx.socket(zmq.PUSH)
    try:
        yield sock
    finally:
        sock.close(1)
        ctx.term()


@pytest.fixture(scope='function')
def logr(pull_sock):
    pull_sock.connect('tcp://127.0.0.1:12345')
    handler = PUBHandler(pull_sock)
    handler.setLevel('INFO')
    # Override all the level formatters to use JSON
    handler.formatters = defaultdict(logjson.JSONFormatter)

    logging.basicConfig(level='DEBUG')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield logger
    finally:
        logger.removeHandler(handler)


def test_send_logs(randomly_generated_data, db_pool, logr):
    from uuid import uuid4
    import threading

    loop = asyncio.get_event_loop()
    task = loop.create_task(main.amain(None))

    message_uuids = set()

    def worker():
        time.sleep(1)
        for i in range(10):
            new_id = str(uuid4())
            message_uuids.add(new_id)
            logr.info(f'{new_id}')
            time.sleep(1)
        task.cancel()
        time.sleep(1)

    t = threading.Thread(target=worker)
    t.start()
    try:
        with io.zmq_context() as ctx:
            loop.run_until_complete(task)
    except asyncio.CancelledError:
        pass
    t.join()

    # Fetch records from the DB to verify that the log messages arrived.
    async def get():
        async with db_pool.acquire() as conn:
            conn: Connection
            return await conn.fetch('SELECT * FROM logs')

    records = loop.run_until_complete(get())
    pprint(records)
    logged_message_ids = {r['message'] for r in records}
    pprint(logged_message_ids)
    assert logged_message_ids.issuperset(message_uuids)

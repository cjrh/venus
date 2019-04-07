from __future__ import annotations
import logging
import asyncio
import json
from datetime import datetime
from typing import List, Dict
from uuid import UUID

from asyncpg import Connection
import aiodec

from .. import settings
from . import get_db_pool
from ..types import Message

logger = logging.getLogger(__name__)


async def collect(q: asyncio.Queue[Message]):
    batch = []
    try:
        while True:
            try:
                msg = await asyncio.wait_for(
                    q.get(), timeout=settings.MAX_BATCH_AGE_SECONDS())
            except asyncio.TimeoutError:
                if batch:
                    await write_and_clear(batch, len(batch))
                continue

            try:
                logger.debug(f'Got message in collect: {msg}')
                d = json.loads(msg.message)
            except json.JSONDecodeError:
                logger.exception(f'JSON decoding failed on: {msg.message}')
                continue

            # The received JSON will be saved into the DB, but we extract
            # a few fields that will be used often in queries.
            # TODO: currently the DB type is TIMESTAMPTZ. Might need TIMESTAMP
            time = extract_safe(d, 'created', datetime.fromtimestamp)
            if not time:
                logger.info('Message does not have a "created" field. Dropping.')
                continue

            message = extract_safe(d, 'message')
            correlation_id = extract_safe(d, 'correlation_id', UUID)

            # Besides the ones extracted above, we also remove a few more
            # that we don't care about.
            remove_unwanted_keys(d)
            data = json.dumps(d)

            batch.append(
                (time, message, correlation_id, data)
            )

            if len(batch) >= settings.MAX_BATCH_SIZE():
                await write_and_clear(batch, len(batch))
    except asyncio.CancelledError:
        if batch:
            await write_and_clear(batch, len(batch))


def remove_unwanted_keys(data: Dict):
    for key in settings.DROP_FIELDS():
        data.pop(key, None)


@aiodec.astopwatch(message_template='Inserting $size records took $time_ sec')
async def write_and_clear(records: List, size: int):
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:  # type: Connection
            # TODO: keep track of https://github.com/MagicStack/asyncpg/pull/295
            # TODO: `executemany` performance is being optimized.
            logger.debug(f'Writing records to DB: {records}')
            await conn.executemany('INSERT INTO logs VALUES ($1, $2, $3, $4)',
                                   records)
    except Exception as e:
        logger.exception('Error while writing records. The pending record '
                         'set will not be cleared.')
    else:
        records.clear()


def extract_safe(d, key, constructor=lambda x: x):
    if key not in d:
        return None

    return constructor(d.pop(key))

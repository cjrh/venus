from __future__ import annotations
import logging
import asyncio
import json
from collections import deque
from datetime import datetime
from typing import List, Dict, Tuple, NamedTuple, Deque
from uuid import UUID
import functools

from asyncpg import Connection
import aiodec
from async_lru import alru_cache

from .. import settings
from . import get_db_pool
from ..models import Message

logger = logging.getLogger(__name__)

class TypeData(NamedTuple):
    type_: str
    field_table: str
    set_table: str

SUPPORTED_TYPES = {
    "str": TypeData(type_="text", field_table="logfieldtext", set_table="logsettext"),
    "int": TypeData(type_="int", field_table="logfieldint", set_table="logsetint"),
    "float": TypeData(type_="float", field_table="logfieldfloat", set_table="logsetfloat"),
}


async def collect(q: asyncio.Queue[Message]):
    batch = deque()
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
            data = d

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


@alru_cache(maxsize=2**24)
async def get_vocab_id(text: str, value) -> Tuple[int, TypeData]:
    """ Get (or insert and return) a new vocabulary entry """
    type_data = SUPPORTED_TYPES[type(value).__name__]
    pool = get_db_pool()
    async with pool.acquire() as conn:
        sql = r"SELECT id FROM vocab WHERE value = $1"
        id_ = await conn.fetchval(sql, text)
        if id_ is None:
            sql = r"INSERT INTO vocab(value, type) VALUES ($1, $2) RETURNING id"
            id_ = await conn.fetchval(sql, text, type_data.type_)

    return id_, type_data


@alru_cache(maxsize=2**24)
async def get_field_id(name: str, value) -> Tuple[int, TypeData]:
    """Covers these tables: logfieldint, logfieldfloat, logfieldtext"""
    vocab_id, type_data = await get_vocab_id(name, value)
    if type_data.type_ == 'text':
        # For text values in the logs, we also substitute out those
        # text strings for index integers
        value_vocab_id, value_type_data = await get_vocab_id(value, "text")
        value = value_vocab_id  # This is now the value to store
    pool = get_db_pool()
    async with pool.acquire() as conn:
        sql = (
            f"SELECT id FROM {type_data.field_table} " 
            f"WHERE name = $1 AND value = $2"
        )
        id_ = await conn.fetchval(sql, vocab_id, value)
        if id_ is None:
            sql = (
                f"INSERT INTO {type_data.field_table} (name, value) "
                f"VALUES ($1, $2) RETURNING id"
            )
            id_ = await conn.fetchval(sql, vocab_id, value)

    return id_, type_data


async def insert_set(log_id: int, name: str, value) -> None:
    if type(value) not in [int, float, str]:
        value = str(value)
    field_id, type_data = await get_field_id(name, value)
    pool = get_db_pool()
    async with pool.acquire() as conn:
        sql = (
            f"INSERT INTO {type_data.set_table} (log_id, field_id) "
            f"VALUES ($1, $2)"
        )
        await conn.execute(sql, log_id, field_id)


@aiodec.astopwatch(message_template='Inserting $size records took $time_ sec')
async def write_and_clear(records: Deque, size: int):
    try:
        pool = get_db_pool()
        async with pool.acquire() as conn:  # type: Connection
            # TODO: keep track of https://github.com/MagicStack/asyncpg/pull/295
            # TODO: `executemany` performance is being optimized.
            logger.debug(f'Writing records to DB: {records}')
            while records:
                time_, message, correlation_id, data = records.popleft()
                sql = (
                    f"INSERT INTO logs (time, message, correlation_id) "
                    f"VALUES ($1, $2, $3) RETURNING id"
                )
                # Main log record
                log_id = await conn.fetchval(sql, time_, message, correlation_id)
                # Attributes
                for name, value in data.items():
                    # TODO: this loop could be done with `executemany` instead.
                    await insert_set(log_id, name, value)
    except Exception as e:
        logger.exception('Error while writing records. The pending record '
                         'set will not be cleared.')
    else:
        records.clear()


def extract_safe(d, key, constructor=lambda x: x):
    if key not in d:
        return None

    return constructor(d.pop(key))

import asyncio
from pprint import pprint

from asyncpg import Connection


def test_hit_db(randomly_generated_data, db_pool):
    async def get():
        async with db_pool.acquire() as conn:
            conn: Connection
            return await conn.fetch('SELECT * FROM logs')

    loop = asyncio.get_event_loop()
    records = loop.run_until_complete(get())
    pprint(records)

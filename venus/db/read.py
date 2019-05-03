from . import get_db_pool


# Need to get the additional data from the other tables
async def get_extra_data(log_id: int, pool=None):
    pool = pool or get_db_pool()
    async with pool.acquire() as conn:
        sql = """
                SELECT 
                    $1::INT4,
                    v1.value as name,
                    sv.value as value
                FROM 
                    logsetint ss 
                    INNER JOIN logfieldint sv ON sv.id = ss.field_id
                    INNER JOIN vocab v1 ON v1.id = sv.name
                WHERE
                    ss.log_id = $1
            """
        rows_int = await conn.fetch(sql, log_id)

        sql = """
                SELECT 
                    $1::INT4,
                    v2.value as name,
                    fv.value as value
                FROM 
                    logsetfloat ff
                    INNER JOIN logfieldfloat fv ON fv.id = ff.field_id
                    INNER JOIN vocab v2 ON v2.id = fv.name
                WHERE
                    ff.log_id = $1
            """
        rows_float = await conn.fetch(sql, log_id)

        sql = """
                SELECT 
                    $1::INT4,
                    v3.value as name,
                    v4.value as value
                FROM 
                    logsettext tt
                    INNER JOIN logfieldtext tv ON tv.id = tt.field_id
                    INNER JOIN vocab v3 ON v3.id = tv.name
                    INNER JOIN vocab v4 ON v4.id = tv.value
                WHERE
                    tt.log_id = $1;
            """
        rows_text = await conn.fetch(sql, log_id)

        rows = rows_int + rows_float + rows_text
    return rows

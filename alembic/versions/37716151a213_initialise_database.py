"""initialise database

Revision ID: 37716151a213
Revises: 
Create Date: 2017-08-17 15:24:16.294622

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '37716151a213'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute('CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')

    # https://stackoverflow.com/questions/1566717/postgresql-like-query-performance-variations
    # install pg_trgm

    op.execute("""
        CREATE TABLE vocab (
          id                  SERIAL PRIMARY KEY,
          value               TEXT,
          type                TEXT             
    );
    """)  # 4-n but size doesn't matter because this vocab will be shared.
    # INSERT INTO vocab (id, value, type) VALUES (...) ON CONFLICT (value) DO NOTHING RETURNING id
    # https://dba.stackexchange.com/a/129591

    # https://dbfiddle.uk/?rdbms=postgres_10&fiddle=f7a0bf501d5e15f7a4fd558ce309158e
    # WITH cte AS (
    #     INSERT INTO "user"(timestamp, user_id, member_id)
    # values (now(), 1,1)
    # ON CONFLICT (user_id, member_id) DO NOTHING
    # RETURNING "user".id
    # )
    # SELECT id AS result from cte  -- successful insert
    # UNION ALL
    # SELECT id from "user" WHERE NOT EXISTS (select 1 FROM cte)  -- already existed
    # ;

    op.execute("""
        CREATE TABLE logfieldint (
          id                  SERIAL PRIMARY KEY,
          name                int4 REFERENCES vocab(id),
          value               int8
    );
    """)  # 14 bytes. TODO: make index covering (name,value)

    op.execute("""
        CREATE TABLE logfieldfloat (
          id                  SERIAL PRIMARY KEY,
          name                int4 REFERENCES vocab(id),
          value               double precision
    );
    """)  # 16bytes. TODO: make index covering (name,value)

    op.execute("""
        CREATE TABLE logfieldtext (
          id                  SERIAL PRIMARY KEY,
          name                int4 REFERENCES vocab(id),
          value               int4 REFERENCES vocab(id)
    );
    """)  # 12 bytes. TODO: make index covering (name,value)

    op.execute("""
        CREATE TABLE logs (
          time                TIMESTAMPTZ NOT NULL,
          id                  SERIAL,  
          message             TEXT,
          correlation_id      UUID
    );
    """)  # 8 + 4 + 16 + n (text) = 28 + n bytes

    op.execute("CREATE INDEX idxcor ON logs (correlation_id);")
    op.execute("CREATE INDEX idxgin_trgm_msg  ON logs USING gin (message gin_trgm_ops);")

    op.execute("""
        SELECT create_hypertable(
          'logs', 'time', chunk_time_interval => 43200
        );
    """)

    # Join the main "log" table to each of the fields in that log record.
    # "Which fields are present in which logs?"
    op.execute("""
        CREATE TABLE logsetint (
          log_id              int4,
          field_id            int4
        );
    """)
    # 8 bytes. But we need an index on each column, so that we can
    #   a) find fields from a main log record (correlation id)
    #   b) find main log records from searching on a particular field.

    op.execute("""
        CREATE TABLE logsetfloat (
          log_id              int4,
          field_id            int4
        );
    """)
    # 8 bytes. But we need an index on each column, so that we can
    #   a) find fields from a main log record (correlation id)
    #   b) find main log records from searching on a particular field.

    op.execute("""
        CREATE TABLE logsettext (
          log_id              int4,
          field_id            int4
        );
    """)
    # 8 bytes. But we need an index on each column, so that we can
    #   a) find fields from a main log record (correlation id)
    #   b) find main log records from searching on a particular field.

    ##########################################################################

    op.execute("""
        CREATE TABLE context (
            correlation_id  UUID PRIMARY KEY,
            data            JSONB NOT NULL
        );
    """)

    op.execute("CREATE INDEX idxgin_context_data ON context USING GIN (data jsonb_path_ops);")

    op.execute("""
        CREATE TABLE span (
            span_id         UUID PRIMARY KEY ,
            correlation_id  UUID,
            description     TEXT,
            time_start      TIMESTAMPTZ NOT NULL,
            time_end        TIMESTAMPTZ NOT NULL
        );
    """)

    op.execute("CREATE INDEX idxcor_span ON span (correlation_id);")

    op.execute("""
        CREATE TABLE metric (
          time                TIMESTAMPTZ NOT NULL,
          data                JSONB NOT NULL
    );
    """)

    op.execute("CREATE INDEX idxgin_metric_data ON metric USING GIN (data jsonb_path_ops);")
    op.execute("""
        SELECT create_hypertable(
          'metric', 'time', chunk_time_interval => 43200
        );
    """)


def downgrade():
    op.execute('DROP TABLE span;')
    op.execute('DROP TABLE context;')

    op.execute('DROP TABLE logs;')
    op.execute('DROP EXTENSION IF EXISTS "pg_trgm";')
    op.execute('DROP EXTENSION IF EXISTS "timescaledb" CASCADE;')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp";')


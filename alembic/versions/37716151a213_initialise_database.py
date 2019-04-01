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
        CREATE TABLE logs (
          time                TIMESTAMPTZ,
          message             TEXT,
          correlation_id      UUID,
          data                JSONB NOT NULL
    );
    """)

    op.execute("CREATE INDEX idxcor ON logs (correlation_id);")
    op.execute("CREATE INDEX idxgin_trgm_msg  ON logs USING gin (message gin_trgm_ops);")
    op.execute("CREATE INDEX idxgin_data ON logs USING GIN (data jsonb_path_ops);")

    op.execute("""
        SELECT create_hypertable(
          'logs', 'time', chunk_time_interval => 43200
        );
    """)


def downgrade():
    op.execute('DROP TABLE logs;')
    op.execute('DROP EXTENSION IF EXISTS "pg_trgm";')
    op.execute('DROP EXTENSION IF EXISTS "timescaledb" CASCADE;')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp";')

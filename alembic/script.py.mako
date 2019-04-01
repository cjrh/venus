"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}


def add_primary_uuid_column():
    return sa.Column(
        'id',
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text(u'uuid_generate_v4()'),
        nullable=False,
        unique=True,
    )


def add_timestamp_columns():
    return sa.Column(
        'created_at',
        sa.DateTime(timezone=False),
        nullable=False,
        server_default=sa.text("timezone('utc'::text, now())"),
    ), sa.Column(
        'deleted_at',
        sa.DateTime(timezone=False),
        nullable=True,
    ), sa.Column(
        'updated_at',
        sa.DateTime(timezone=False),
        nullable=False,
        server_default=sa.text("timezone('utc'::text, now())"),
    )


def enable_autoupdate_timestamp(table_name):
    op.execute(
        f'''CREATE TRIGGER set_timestamp
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW
            EXECUTE PROCEDURE trigger_set_timestamp();'''
    )

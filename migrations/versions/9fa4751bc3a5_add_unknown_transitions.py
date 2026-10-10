"""add_unknown_transitions

Revision ID: 9fa4751bc3a5
Revises: f04b2a9a12e2
Create Date: 2026-10-10 14:07:14.478040

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9fa4751bc3a5'
down_revision: Union[str, None] = 'f04b2a9a12e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO allowed_transitions (from_status, to_status) VALUES
        ('processing', 'unknown'),
        ('unknown', 'captured'),
        ('unknown', 'failed')
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM allowed_transitions WHERE from_status = 'processing' AND to_status = 'unknown';
        DELETE FROM allowed_transitions WHERE from_status = 'unknown' AND to_status = 'captured';
        DELETE FROM allowed_transitions WHERE from_status = 'unknown' AND to_status = 'failed';
        """
    )

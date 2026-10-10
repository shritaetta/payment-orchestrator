"""ops_phase_1_correlation_id

Revision ID: b42cffdc4f59
Revises: 662ab2c8d02b
Create Date: 2026-10-10 14:29:54.733732

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b42cffdc4f59'
down_revision: Union[str, None] = '662ab2c8d02b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('payment_attempts', sa.Column('correlation_id', sa.String(36), nullable=True))
    op.add_column('outbox_events', sa.Column('correlation_id', sa.String(36), nullable=True))

def downgrade() -> None:
    op.drop_column('outbox_events', 'correlation_id')
    op.drop_column('payment_attempts', 'correlation_id')

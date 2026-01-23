"""add_listing_lifecycle_fields

Revision ID: 002
Revises: 001
Create Date: 2026-01-23

Add lifecycle tracking fields to listings table:
- status: ACTIVE or DELISTED
- status_changed_at: timestamp when status changed
- consecutive_misses: counter for tracking missed scrapes
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, Sequence[str], None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add lifecycle tracking columns to listings."""
    with op.batch_alter_table("listings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.Enum("ACTIVE", "DELISTED", name="listingstatus"),
                nullable=False,
                server_default="ACTIVE",
            )
        )
        batch_op.add_column(sa.Column("status_changed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("consecutive_misses", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.create_index(batch_op.f("ix_listings_status"), ["status"], unique=False)


def downgrade() -> None:
    """Remove lifecycle tracking columns from listings."""
    with op.batch_alter_table("listings", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_listings_status"))
        batch_op.drop_column("consecutive_misses")
        batch_op.drop_column("status_changed_at")
        batch_op.drop_column("status")

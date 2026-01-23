"""baseline_existing_schema

Revision ID: 001
Revises:
Create Date: 2026-01-23

Baseline migration for existing database schema. This migration is a no-op
because the database was created before Alembic was introduced.
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    No-op: Database schema already exists from init_db().
    """
    pass


def downgrade() -> None:
    """Downgrade schema.

    No-op: Cannot downgrade baseline.
    """
    pass

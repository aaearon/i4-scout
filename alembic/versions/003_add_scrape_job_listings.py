"""add_scrape_job_listings

Revision ID: 003
Revises: 002
Create Date: 2026-01-24

Add scrape_job_listings junction table to track which listings
were processed by which scrape job, with status (new/updated/unchanged).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, Sequence[str], None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create scrape_job_listings table."""
    op.create_table(
        "scrape_job_listings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "scrape_job_id",
            sa.Integer(),
            sa.ForeignKey("scrape_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "listing_id",
            sa.Integer(),
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scrape_job_id", "listing_id", name="uq_job_listing"),
    )
    op.create_index(
        "ix_scrape_job_listings_job_id",
        "scrape_job_listings",
        ["scrape_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_scrape_job_listings_listing_id",
        "scrape_job_listings",
        ["listing_id"],
        unique=False,
    )
    op.create_index(
        "ix_scrape_job_listings_job_status",
        "scrape_job_listings",
        ["scrape_job_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop scrape_job_listings table."""
    op.drop_index("ix_scrape_job_listings_job_status", table_name="scrape_job_listings")
    op.drop_index("ix_scrape_job_listings_listing_id", table_name="scrape_job_listings")
    op.drop_index("ix_scrape_job_listings_job_id", table_name="scrape_job_listings")
    op.drop_table("scrape_job_listings")

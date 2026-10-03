"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-03

Creates the §13 entity tables from the declarative metadata. Kept metadata-
driven so the ORM stays the single schema definition for the MVP; hand-written
table-by-table migrations follow once the schema stabilizes.
"""

from __future__ import annotations

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.persistence.models import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from app.persistence.models import Base

    Base.metadata.drop_all(bind=op.get_bind())

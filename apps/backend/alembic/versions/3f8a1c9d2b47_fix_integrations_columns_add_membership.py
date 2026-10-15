"""Fix integrations column drift (platform/credentials -> provider/status), add
client_memberships

The original migration (c9b6d896812b) created `integrations` with `platform`/
`credentials` columns, but the ORM model (api/models/integrations.py) has always
declared `provider`/`status` - a drift confirmed in docs/CLAUDE_CODE_AUDIT.md. This
table was never reachable through a working code path before this repair pass (every
router that touched it was a stub), so there is no real data to migrate; the fix is a
straight drop/add rather than a backfill.

Also adds `client_memberships` (api/models/membership.py), new in this repair pass -
the table backing tenant-ownership checks (api.core.security.assert_client_access).

Revision ID: 3f8a1c9d2b47
Revises: 2c5439b43816
Create Date: 2026-08-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from api.models.types import EncryptedString


# revision identifiers, used by Alembic.
revision: str = '3f8a1c9d2b47'
down_revision: Union[str, Sequence[str], None] = '2c5439b43816'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- integrations: platform/credentials -> provider/status ---
    op.drop_column('integrations', 'platform')
    op.drop_column('integrations', 'credentials')
    # Added nullable first, then tightened to NOT NULL below: this is safe on an empty
    # table (the expected/documented state) and fails loudly rather than silently
    # dropping data if any row happens to already exist without a provider value.
    op.add_column('integrations', sa.Column('provider', sa.String(), nullable=True))
    op.alter_column('integrations', 'provider', nullable=False)
    op.add_column('integrations', sa.Column('status', sa.String(), nullable=True, server_default='pending'))

    # The original FK had no ON DELETE behavior; the model declares CASCADE.
    op.drop_constraint('integrations_client_id_fkey', 'integrations', type_='foreignkey')
    op.create_foreign_key(
        'integrations_client_id_fkey', 'integrations', 'clients',
        ['client_id'], ['id'], ondelete='CASCADE',
    )

    # --- client_memberships ---
    op.create_table(
        'client_memberships',
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'client_id', name='uq_client_membership_user_client'),
    )
    op.create_index(op.f('ix_client_memberships_id'), 'client_memberships', ['id'], unique=False)
    op.create_index(op.f('ix_client_memberships_user_id'), 'client_memberships', ['user_id'], unique=False)
    op.create_index(op.f('ix_client_memberships_client_id'), 'client_memberships', ['client_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_client_memberships_client_id'), table_name='client_memberships')
    op.drop_index(op.f('ix_client_memberships_user_id'), table_name='client_memberships')
    op.drop_index(op.f('ix_client_memberships_id'), table_name='client_memberships')
    op.drop_table('client_memberships')

    op.drop_constraint('integrations_client_id_fkey', 'integrations', type_='foreignkey')
    op.create_foreign_key(
        'integrations_client_id_fkey', 'integrations', 'clients', ['client_id'], ['id'],
    )
    op.drop_column('integrations', 'status')
    op.drop_column('integrations', 'provider')
    op.add_column('integrations', sa.Column('credentials', EncryptedString(), nullable=True))
    op.add_column('integrations', sa.Column('platform', sa.String(), nullable=False, server_default=''))

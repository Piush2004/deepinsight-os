"""Add remaining integrations domain tables (api/models/integrations.py):
integration_accounts, connector_tokens, integration_syncs, connector_logs,
normalized_metrics.

`connector_tokens.access_token`/`refresh_token` use EncryptedString (encrypted at
rest via api.utils.encryption.encryption_service) - see docs/CLAUDE_CODE_AUDIT.md,
"P0 - Plaintext OAuth token storage" finding, fixed in this repair pass.

Revision ID: 1d6f8b2a4e93
Revises: 9b5c3e1f7a24
Create Date: 2026-08-16 00:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from api.models.types import EncryptedString


# revision identifiers, used by Alembic.
revision: str = '1d6f8b2a4e93'
down_revision: Union[str, Sequence[str], None] = '9b5c3e1f7a24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'integration_accounts',
        sa.Column('integration_id', UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('account_name', sa.String(), nullable=False),
        sa.Column('property_id', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['integration_id'], ['integrations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_integration_accounts_id'), 'integration_accounts', ['id'], unique=False)
    op.create_index(op.f('ix_integration_accounts_client_id'), 'integration_accounts', ['client_id'], unique=False)

    op.create_table(
        'connector_tokens',
        sa.Column('integration_id', UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('access_token', EncryptedString(), nullable=False),
        sa.Column('refresh_token', EncryptedString(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['integration_id'], ['integrations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('integration_id', name='uq_connector_tokens_integration_id'),
    )
    op.create_index(op.f('ix_connector_tokens_id'), 'connector_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_connector_tokens_client_id'), 'connector_tokens', ['client_id'], unique=False)

    op.create_table(
        'integration_syncs',
        sa.Column('integration_id', UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('records_processed', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['integration_id'], ['integrations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_integration_syncs_id'), 'integration_syncs', ['id'], unique=False)
    op.create_index(op.f('ix_integration_syncs_client_id'), 'integration_syncs', ['client_id'], unique=False)
    # Supports reconcile_stale_syncs() (api/core/tasks.py) - scans for status='running'
    # rows past a staleness threshold.
    op.create_index('ix_integration_syncs_status', 'integration_syncs', ['status'], unique=False)

    op.create_table(
        'connector_logs',
        sa.Column('sync_id', UUID(as_uuid=True), nullable=True),
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('level', sa.String(), nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['sync_id'], ['integration_syncs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_connector_logs_id'), 'connector_logs', ['id'], unique=False)
    op.create_index(op.f('ix_connector_logs_client_id'), 'connector_logs', ['client_id'], unique=False)

    op.create_table(
        'normalized_metrics',
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('integration_id', UUID(as_uuid=True), nullable=False),
        sa.Column('metric_type', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('dimension_1', sa.String(), nullable=True),
        sa.Column('dimension_2', sa.String(), nullable=True),
        sa.Column('value_1', sa.Float(), nullable=True),
        sa.Column('value_2', sa.Float(), nullable=True),
        sa.Column('value_3', sa.Float(), nullable=True),
        sa.Column('value_4', sa.Float(), nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['integration_id'], ['integrations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_normalized_metrics_id'), 'normalized_metrics', ['id'], unique=False)
    op.create_index(op.f('ix_normalized_metrics_client_id'), 'normalized_metrics', ['client_id'], unique=False)
    # Supports the idempotency lookup in sync_integration_data() (api/core/tasks.py) -
    # find-existing-by-natural-key before inserting a duplicate metric row.
    op.create_index(
        'ix_normalized_metrics_dedupe_key', 'normalized_metrics',
        ['integration_id', 'metric_type', 'timestamp', 'dimension_1', 'dimension_2'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_normalized_metrics_dedupe_key', table_name='normalized_metrics')
    op.drop_index(op.f('ix_normalized_metrics_client_id'), table_name='normalized_metrics')
    op.drop_index(op.f('ix_normalized_metrics_id'), table_name='normalized_metrics')
    op.drop_table('normalized_metrics')

    op.drop_index(op.f('ix_connector_logs_client_id'), table_name='connector_logs')
    op.drop_index(op.f('ix_connector_logs_id'), table_name='connector_logs')
    op.drop_table('connector_logs')

    op.drop_index('ix_integration_syncs_status', table_name='integration_syncs')
    op.drop_index(op.f('ix_integration_syncs_client_id'), table_name='integration_syncs')
    op.drop_index(op.f('ix_integration_syncs_id'), table_name='integration_syncs')
    op.drop_table('integration_syncs')

    op.drop_index(op.f('ix_connector_tokens_client_id'), table_name='connector_tokens')
    op.drop_index(op.f('ix_connector_tokens_id'), table_name='connector_tokens')
    op.drop_table('connector_tokens')

    op.drop_index(op.f('ix_integration_accounts_client_id'), table_name='integration_accounts')
    op.drop_index(op.f('ix_integration_accounts_id'), table_name='integration_accounts')
    op.drop_table('integration_accounts')

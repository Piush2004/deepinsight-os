"""Add reporting domain tables (api/models/reporting.py)

Includes report_comments, new in this repair pass (parity with content_comments,
which already existed - reports had no comment table at all before).

Revision ID: 9b5c3e1f7a24
Revises: 7e2d4f6a8c19
Create Date: 2026-08-16 00:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '9b5c3e1f7a24'
down_revision: Union[str, Sequence[str], None] = '7e2d4f6a8c19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'reports',
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('reporting_period', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reports_id'), 'reports', ['id'], unique=False)
    op.create_index(op.f('ix_reports_client_id'), 'reports', ['client_id'], unique=False)

    op.create_table(
        'report_versions',
        sa.Column('report_id', UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content', sa.JSON(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_report_versions_id'), 'report_versions', ['id'], unique=False)
    op.create_index(op.f('ix_report_versions_report_id'), 'report_versions', ['report_id'], unique=False)

    op.create_table(
        'approval_requests',
        sa.Column('report_id', UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('approver_id', UUID(as_uuid=True), nullable=True),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id']),
        sa.ForeignKeyConstraint(['approver_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_approval_requests_id'), 'approval_requests', ['id'], unique=False)
    op.create_index(op.f('ix_approval_requests_report_id'), 'approval_requests', ['report_id'], unique=False)

    op.create_table(
        'report_comments',
        sa.Column('report_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_report_comments_id'), 'report_comments', ['id'], unique=False)
    op.create_index(op.f('ix_report_comments_report_id'), 'report_comments', ['report_id'], unique=False)

    op.create_table(
        'agent_runs',
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('errors', sa.Text(), nullable=True),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_agent_runs_id'), 'agent_runs', ['id'], unique=False)
    op.create_index(op.f('ix_agent_runs_client_id'), 'agent_runs', ['client_id'], unique=False)

    op.create_table(
        'execution_metrics',
        sa.Column('agent_run_id', UUID(as_uuid=True), nullable=False),
        sa.Column('execution_time_ms', sa.Integer(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('prompt_version', sa.String(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('estimated_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('retrieved_documents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['agent_run_id'], ['agent_runs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_execution_metrics_id'), 'execution_metrics', ['id'], unique=False)
    op.create_index(op.f('ix_execution_metrics_agent_run_id'), 'execution_metrics', ['agent_run_id'], unique=False)

    op.create_table(
        'prompt_versions',
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('content_hash', sa.String(), nullable=False),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_prompt_versions_id'), 'prompt_versions', ['id'], unique=False)
    op.create_index(op.f('ix_prompt_versions_name'), 'prompt_versions', ['name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_prompt_versions_name'), table_name='prompt_versions')
    op.drop_index(op.f('ix_prompt_versions_id'), table_name='prompt_versions')
    op.drop_table('prompt_versions')

    op.drop_index(op.f('ix_execution_metrics_agent_run_id'), table_name='execution_metrics')
    op.drop_index(op.f('ix_execution_metrics_id'), table_name='execution_metrics')
    op.drop_table('execution_metrics')

    op.drop_index(op.f('ix_agent_runs_client_id'), table_name='agent_runs')
    op.drop_index(op.f('ix_agent_runs_id'), table_name='agent_runs')
    op.drop_table('agent_runs')

    op.drop_index(op.f('ix_report_comments_report_id'), table_name='report_comments')
    op.drop_index(op.f('ix_report_comments_id'), table_name='report_comments')
    op.drop_table('report_comments')

    op.drop_index(op.f('ix_approval_requests_report_id'), table_name='approval_requests')
    op.drop_index(op.f('ix_approval_requests_id'), table_name='approval_requests')
    op.drop_table('approval_requests')

    op.drop_index(op.f('ix_report_versions_report_id'), table_name='report_versions')
    op.drop_index(op.f('ix_report_versions_id'), table_name='report_versions')
    op.drop_table('report_versions')

    op.drop_index(op.f('ix_reports_client_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_id'), table_name='reports')
    op.drop_table('reports')

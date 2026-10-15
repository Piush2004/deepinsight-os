"""Add SEO Intelligence domain tables (api/models/seo.py)

Phase 4 - SEO Intelligence Platform. Mirrors the reporting/content domains' own
one-approval-table-per-artifact-type convention (seo_approval_requests, not a shared
polymorphic table) and comment-thread convention (seo_opportunity_comments).

Revision ID: 8e4c2a6d9f13
Revises: 5a3c7e9f1b62
Create Date: 2026-08-23 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '8e4c2a6d9f13'
down_revision: Union[str, Sequence[str], None] = '5a3c7e9f1b62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'seo_analyses',
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='running'),
        sa.Column('data_provider', sa.String(), nullable=False),
        sa.Column('period_start', sa.String(), nullable=False),
        sa.Column('period_end', sa.String(), nullable=False),
        sa.Column('executive_summary', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_seo_analyses_id'), 'seo_analyses', ['id'], unique=False)
    op.create_index(op.f('ix_seo_analyses_client_id'), 'seo_analyses', ['client_id'], unique=False)

    op.create_table(
        'seo_opportunities',
        sa.Column('analysis_id', UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('opportunity_type', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('source_entity', sa.String(), nullable=False),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('metrics', sa.JSON(), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('priority_score', sa.Float(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('impact_score', sa.Float(), nullable=False),
        sa.Column('effort_estimate', sa.String(), nullable=False),
        sa.Column('recommended_actions', sa.JSON(), nullable=False),
        sa.Column('strategic_explanation', sa.Text(), nullable=True),
        sa.Column('evaluation_scores', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending_review'),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['analysis_id'], ['seo_analyses.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_seo_opportunities_id'), 'seo_opportunities', ['id'], unique=False)
    op.create_index(op.f('ix_seo_opportunities_analysis_id'), 'seo_opportunities', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_seo_opportunities_client_id'), 'seo_opportunities', ['client_id'], unique=False)

    op.create_table(
        'seo_approval_requests',
        sa.Column('opportunity_id', UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('approver_id', UUID(as_uuid=True), nullable=True),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['opportunity_id'], ['seo_opportunities.id']),
        sa.ForeignKeyConstraint(['approver_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_seo_approval_requests_id'), 'seo_approval_requests', ['id'], unique=False)
    op.create_index(op.f('ix_seo_approval_requests_opportunity_id'), 'seo_approval_requests', ['opportunity_id'], unique=False)

    op.create_table(
        'seo_opportunity_comments',
        sa.Column('opportunity_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['opportunity_id'], ['seo_opportunities.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_seo_opportunity_comments_id'), 'seo_opportunity_comments', ['id'], unique=False)
    op.create_index(op.f('ix_seo_opportunity_comments_opportunity_id'), 'seo_opportunity_comments', ['opportunity_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_seo_opportunity_comments_opportunity_id'), table_name='seo_opportunity_comments')
    op.drop_index(op.f('ix_seo_opportunity_comments_id'), table_name='seo_opportunity_comments')
    op.drop_table('seo_opportunity_comments')

    op.drop_index(op.f('ix_seo_approval_requests_opportunity_id'), table_name='seo_approval_requests')
    op.drop_index(op.f('ix_seo_approval_requests_id'), table_name='seo_approval_requests')
    op.drop_table('seo_approval_requests')

    op.drop_index(op.f('ix_seo_opportunities_client_id'), table_name='seo_opportunities')
    op.drop_index(op.f('ix_seo_opportunities_analysis_id'), table_name='seo_opportunities')
    op.drop_index(op.f('ix_seo_opportunities_id'), table_name='seo_opportunities')
    op.drop_table('seo_opportunities')

    op.drop_index(op.f('ix_seo_analyses_client_id'), table_name='seo_analyses')
    op.drop_index(op.f('ix_seo_analyses_id'), table_name='seo_analyses')
    op.drop_table('seo_analyses')

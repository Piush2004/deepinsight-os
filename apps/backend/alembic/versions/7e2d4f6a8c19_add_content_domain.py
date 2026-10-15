"""Add content domain tables (api/models/content.py)

These 8 tables/associations existed in the ORM but had never been migrated - the
entire Content Intelligence Platform (Phase 3) had no schema at all until this
migration. See docs/CLAUDE_CODE_AUDIT.md, "Database models & migrations" finding.

Revision ID: 7e2d4f6a8c19
Revises: 3f8a1c9d2b47
Create Date: 2026-08-16 00:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '7e2d4f6a8c19'
down_revision: Union[str, Sequence[str], None] = '3f8a1c9d2b47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'content_tags',
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_tags_id'), 'content_tags', ['id'], unique=False)
    op.create_index(op.f('ix_content_tags_client_id'), 'content_tags', ['client_id'], unique=False)

    op.create_table(
        'content',
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('scheduled_date', sa.DateTime(), nullable=True),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=True),
        sa.Column('campaign', sa.String(), nullable=True),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_id'), 'content', ['id'], unique=False)
    op.create_index(op.f('ix_content_client_id'), 'content', ['client_id'], unique=False)

    op.create_table(
        'content_tags_association',
        sa.Column('content_id', UUID(as_uuid=True), nullable=True),
        sa.Column('tag_id', UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['content_id'], ['content.id']),
        sa.ForeignKeyConstraint(['tag_id'], ['content_tags.id']),
    )

    op.create_table(
        'content_versions',
        sa.Column('content_id', UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('diff', sa.Text(), nullable=True),
        sa.Column('author_id', UUID(as_uuid=True), nullable=True),
        sa.Column('ai_model', sa.String(), nullable=True),
        sa.Column('prompt_version', sa.String(), nullable=True),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['content_id'], ['content.id']),
        sa.ForeignKeyConstraint(['author_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_versions_id'), 'content_versions', ['id'], unique=False)
    op.create_index(op.f('ix_content_versions_content_id'), 'content_versions', ['content_id'], unique=False)

    op.create_table(
        'content_comments',
        sa.Column('version_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['version_id'], ['content_versions.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_comments_id'), 'content_comments', ['id'], unique=False)
    op.create_index(op.f('ix_content_comments_version_id'), 'content_comments', ['version_id'], unique=False)

    op.create_table(
        'content_scores',
        sa.Column('version_id', UUID(as_uuid=True), nullable=False),
        sa.Column('originality', sa.Float(), nullable=False),
        sa.Column('readability', sa.Float(), nullable=False),
        sa.Column('grammar', sa.Float(), nullable=False),
        sa.Column('professional_tone', sa.Float(), nullable=False),
        sa.Column('brand_consistency', sa.Float(), nullable=False),
        sa.Column('citation_coverage', sa.Float(), nullable=False),
        sa.Column('hallucination_risk', sa.Float(), nullable=False),
        sa.Column('completeness', sa.Float(), nullable=False),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['version_id'], ['content_versions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_scores_id'), 'content_scores', ['id'], unique=False)
    op.create_index(op.f('ix_content_scores_version_id'), 'content_scores', ['version_id'], unique=False)

    op.create_table(
        'content_approval_requests',
        sa.Column('content_id', UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('approver_id', UUID(as_uuid=True), nullable=True),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['content_id'], ['content.id']),
        sa.ForeignKeyConstraint(['approver_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_approval_requests_id'), 'content_approval_requests', ['id'], unique=False)
    op.create_index(op.f('ix_content_approval_requests_content_id'), 'content_approval_requests', ['content_id'], unique=False)

    op.create_table(
        'content_templates',
        sa.Column('client_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('template_type', sa.String(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_templates_id'), 'content_templates', ['id'], unique=False)
    op.create_index(op.f('ix_content_templates_client_id'), 'content_templates', ['client_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_content_templates_client_id'), table_name='content_templates')
    op.drop_index(op.f('ix_content_templates_id'), table_name='content_templates')
    op.drop_table('content_templates')

    op.drop_index(op.f('ix_content_approval_requests_content_id'), table_name='content_approval_requests')
    op.drop_index(op.f('ix_content_approval_requests_id'), table_name='content_approval_requests')
    op.drop_table('content_approval_requests')

    op.drop_index(op.f('ix_content_scores_version_id'), table_name='content_scores')
    op.drop_index(op.f('ix_content_scores_id'), table_name='content_scores')
    op.drop_table('content_scores')

    op.drop_index(op.f('ix_content_comments_version_id'), table_name='content_comments')
    op.drop_index(op.f('ix_content_comments_id'), table_name='content_comments')
    op.drop_table('content_comments')

    op.drop_index(op.f('ix_content_versions_content_id'), table_name='content_versions')
    op.drop_index(op.f('ix_content_versions_id'), table_name='content_versions')
    op.drop_table('content_versions')

    op.drop_table('content_tags_association')

    op.drop_index(op.f('ix_content_client_id'), table_name='content')
    op.drop_index(op.f('ix_content_id'), table_name='content')
    op.drop_table('content')

    op.drop_index(op.f('ix_content_tags_client_id'), table_name='content_tags')
    op.drop_index(op.f('ix_content_tags_id'), table_name='content_tags')
    op.drop_table('content_tags')

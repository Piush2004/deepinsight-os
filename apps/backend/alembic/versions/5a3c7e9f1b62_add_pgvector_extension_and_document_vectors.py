"""Add pgvector extension and document_vectors table

Previously this table was created ad hoc at runtime by
PgVectorStore._ensure_table() (api/services/knowledge/vector_store.py) via
`CREATE TABLE IF NOT EXISTS` on every service instantiation - entirely outside the
migration system, flagged in docs/CLAUDE_CODE_AUDIT.md. This migration is the real
source of truth for the table now; the runtime DDL was removed from
PgVectorStore.__init__ in the same repair pass that added this migration.

Uses raw SQL for the `vector` column type since the codebase doesn't depend on the
`pgvector` Python package (no SQLAlchemy `Vector` type available) - consistent with
how PgVectorStore's own queries already use raw parameterized SQL for vector ops.

1024 dimensions matches BGE-M3's real embedding size (api/services/knowledge/
embeddings.py); the LocalHashingEmbeddingProvider fallback also targets 1024 for
drop-in compatibility (BGE_M3_DIMENSION in that module).

Revision ID: 5a3c7e9f1b62
Revises: 1d6f8b2a4e93
Create Date: 2026-08-16 00:20:00.000000
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5a3c7e9f1b62'
down_revision: Union[str, Sequence[str], None] = '1d6f8b2a4e93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""
        CREATE TABLE document_vectors (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id uuid NOT NULL,
            document_id uuid NOT NULL,
            chunk_id uuid NOT NULL,
            embedding vector(1024),
            metadata jsonb DEFAULT '{}'::jsonb
        )
    """)
    op.execute("CREATE INDEX ix_document_vectors_client_id ON document_vectors (client_id)")
    op.execute("CREATE INDEX ix_document_vectors_document_id ON document_vectors (document_id)")
    op.execute("CREATE INDEX ix_document_vectors_chunk_id ON document_vectors (chunk_id)")
    # IVFFlat index for approximate nearest-neighbor cosine search at scale - exact
    # search (no index) works but degrades linearly; this is the standard pgvector
    # production index for the cosine (<=>) operator PgVectorStore.similarity_search
    # already uses. Requires at least one row to build well in practice, but CREATE
    # works on an empty table too (just starts with zero lists' worth of clustering
    # until ANALYZE runs after data exists).
    op.execute(
        "CREATE INDEX ix_document_vectors_embedding_cosine ON document_vectors "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS document_vectors")
    # Deliberately not dropping the `vector` extension itself - other objects/sessions
    # may depend on it, and CREATE EXTENSION IF NOT EXISTS is idempotent/cheap to
    # re-run, so there's no matching "undo" that's safe to do unconditionally here.

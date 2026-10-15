"""Regression test for a real bug found during dev/demo-mode implementation
(docs/DEV_DEMO_MODE.md): PgVectorRetriever.retrieve() raised
`AttributeError: 'str' object has no attribute 'hex'` when run against SQLite, because
it filtered DocumentChunk.id (a postgresql.UUID column) with plain string chunk_ids.
This works transparently against a real Postgres server (which is why it was never
caught by the Postgres-gated e2e tests) but not against SQLite's bind processor for the
same column type - exactly the class of thing that only surfaces once a second real
database backend is actually exercised, per this project's own "never fabricate
verification" rule.

Hermetic: uses an in-memory SQLite engine, no Postgres, no external services.
"""
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.models.base import Base
import api.models  # noqa: F401 - registers every model on Base.metadata
from api.models.client import Client
from api.models.knowledge import Document, DocumentVersion, DocumentChunk
from api.services.knowledge.vector_store import InMemoryVectorStore
from api.services.knowledge.retrieval import PgVectorRetriever


class _FixedEmbeddingProvider:
    """Returns the same embedding regardless of input text - good enough to prove
    retrieval plumbing works without needing a real embedding model."""

    def embed_text(self, text):
        return [1.0, 0.0, 0.0]

    def embed_batch(self, texts):
        return [self.embed_text(t) for t in texts]


def test_retrieve_works_against_sqlite_with_string_chunk_ids():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    client = Client(name="SQLite Compat Test Client")
    db.add(client)
    db.flush()

    document = Document(client_id=client.id, title="doc.txt", source_type="upload",
                         mime_type="text/plain", file_size=10, checksum="abc123", status="completed")
    db.add(document)
    db.flush()

    version = DocumentVersion(document_id=document.id, version=1, raw_text="hello world",
                               processing_status="completed")
    db.add(version)
    db.flush()

    chunk = DocumentChunk(version_id=version.id, chunk_index=0, chunk_text="hello world",
                           token_count=2, embedding_status="completed")
    db.add(chunk)
    db.flush()
    db.commit()

    vector_store = InMemoryVectorStore()
    # Deliberately a plain string, matching exactly what PgVectorStore/InMemoryVectorStore
    # both actually produce (str(chunk.id)) - this is what triggered the bug.
    vector_store.add_documents(
        [{"document_id": str(document.id), "chunk_id": str(chunk.id),
          "embedding": [1.0, 0.0, 0.0], "metadata": {"chunk_text": "hello world"}}],
        client_id=str(client.id),
    )

    retriever = PgVectorRetriever(_FixedEmbeddingProvider(), vector_store, db)

    results = retriever.retrieve("hello", client.id, top_k=5)

    assert len(results) == 1
    assert results[0]["chunk_id"] == str(chunk.id)
    assert results[0]["chunk_text"] == "hello world"
    assert results[0]["document_id"] == document.id

    db.close()


def test_retrieve_returns_empty_for_unknown_client_uuid_not_a_crash():
    """A client with zero chunks (or a client_id that was never seeded) must return an
    empty list, not raise - guards against the UUID cast in the fix breaking on a
    query that legitimately has no chunk_ids to look up."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    vector_store = InMemoryVectorStore()
    retriever = PgVectorRetriever(_FixedEmbeddingProvider(), vector_store, db)

    results = retriever.retrieve("anything", uuid4(), top_k=5)

    assert results == []
    db.close()

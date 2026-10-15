from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from api.core.interfaces.retriever import Retriever
from api.core.interfaces.knowledge_query_service import KnowledgeQueryService
from api.core.interfaces.embedding_provider import EmbeddingProvider
from api.core.interfaces.vector_store import VectorStore
from api.models.knowledge import Document, DocumentVersion, DocumentChunk


class PgVectorRetriever(Retriever):
    """Real similarity-search retrieval: embeds the query, searches the vector store,
    then resolves each hit's chunk_id back to real chunk text + parent document title via
    SQL so results always carry a traceable citation - never a fabricated one."""

    def __init__(self, embedding_provider: EmbeddingProvider, vector_store: VectorStore, db: Session):
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.db = db

    def retrieve(self, query: str, client_id: UUID, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        query_embedding = self.embedding_provider.embed_text(query)
        hits = self.vector_store.similarity_search(query_embedding, str(client_id), top_k=top_k, filters=filters)
        if not hits:
            return []

        # Cast to real UUID objects, not just strings: SQLAlchemy's postgresql.UUID
        # column type binds plain strings transparently against a real Postgres
        # server, but its SQLite bind-processor requires an actual uuid.UUID instance
        # (calls .hex on it) - without this cast, filtering by chunk_id here raises
        # AttributeError: 'str' object has no attribute 'hex' whenever the app runs
        # against SQLite (e.g. VECTOR_STORE_PROVIDER=memory dev/demo mode). Both
        # PgVectorStore and InMemoryVectorStore return chunk_id as a string, so this
        # is always safe.
        chunk_ids = [UUID(hit["chunk_id"]) for hit in hits]
        rows = (
            self.db.query(DocumentChunk, DocumentVersion, Document)
            .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .filter(DocumentChunk.id.in_(chunk_ids), Document.client_id == client_id, Document.is_deleted == False)
            .all()
        )
        chunk_lookup = {
            str(chunk.id): {"chunk": chunk, "document": document}
            for chunk, _version, document in rows
        }

        results = []
        for hit in hits:
            resolved = chunk_lookup.get(hit["chunk_id"])
            if not resolved:
                # The vector store had it, but the SQL row is gone (deleted doc) or
                # belongs to a different tenant - never surface it as a citation.
                continue
            results.append({
                "chunk_id": hit["chunk_id"],
                "document_id": resolved["document"].id,
                "document_title": resolved["document"].title,
                "chunk_text": resolved["chunk"].chunk_text,
                "distance": hit.get("distance"),
            })
        return results


class RagKnowledgeQueryService(KnowledgeQueryService):
    """Real RAG: retrieves grounded chunks and assembles a context string plus a
    traceable citations list. Returns an empty/unsure result rather than ever inventing
    an answer when nothing relevant is found."""

    def __init__(self, retriever: Retriever, top_k: int = 5):
        self.retriever = retriever
        self.top_k = top_k

    def query(self, question: str, client_id: UUID, context_filters: Dict[str, Any] = None) -> Dict[str, Any]:
        chunks = self.retriever.retrieve(question, client_id, top_k=self.top_k, filters=context_filters)

        if not chunks:
            return {
                "content": "No relevant knowledge base content was found for this query.",
                "sources": [],
                "grounded": False,
            }

        content = "\n\n".join(
            f"[Source: {c['document_title']}]\n{c['chunk_text']}" for c in chunks
        )
        sources = [str(c["chunk_id"]) for c in chunks]

        return {
            "content": content,
            "sources": sources,
            "grounded": True,
            "citations": [
                {"chunk_id": str(c["chunk_id"]), "document_id": str(c["document_id"]), "document_title": c["document_title"]}
                for c in chunks
            ],
        }

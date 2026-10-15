import json
import math
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.core.interfaces.vector_store import VectorStore
from api.core.config import settings

class PgVectorStore(VectorStore):
    """
    Concrete implementation of VectorStore using PostgreSQL and pgvector.
    The underlying table 'document_vectors' is assumed to have:
    - id (UUID)
    - client_id (UUID)
    - document_id (UUID)
    - chunk_id (UUID)
    - embedding (vector(1024)) # BGE-M3 dimension
    - metadata (JSONB)
    """
    def __init__(self, db_session: Session):
        self.db = db_session
        # Schema (extension + table) is owned by
        # alembic/versions/5a3c7e9f1b62_add_pgvector_extension_and_document_vectors.py -
        # deliberately NOT created here at runtime. Creating it ad hoc on every
        # instantiation (the previous behavior) put the schema outside the migration
        # system entirely, which docs/CLAUDE_CODE_AUDIT.md flagged; tests that need
        # this table set it up via tests/conftest.py's db_session fixture instead.

    def add_documents(self, documents: List[Dict[str, Any]], client_id: str) -> None:
        """
        Expects documents as:
        [
            {
                "document_id": "uuid",
                "chunk_id": "uuid",
                "embedding": [0.1, 0.2, ...],
                "metadata": {"chunk_text": "..."}
            }
        ]
        """
        for doc in documents:
            embedding_str = f"[{','.join(map(str, doc['embedding']))}]"
            metadata_str = json.dumps(doc.get('metadata', {}))
            
            self.db.execute(
                text("""
                    INSERT INTO document_vectors (client_id, document_id, chunk_id, embedding, metadata)
                    VALUES (:client_id, :doc_id, :chunk_id, :embedding, :metadata)
                """),
                {
                    "client_id": client_id,
                    "doc_id": doc.get("document_id"),
                    "chunk_id": doc.get("chunk_id"),
                    "embedding": embedding_str,
                    "metadata": metadata_str
                }
            )
        self.db.commit()

    def similarity_search(
        self, 
        query_embedding: List[float], 
        client_id: str, 
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        
        # L2 Distance Operator: <->
        # Inner Product: <#>
        # Cosine Distance: <=>
        
        # We use Cosine Distance for BGE-M3
        query = """
            SELECT id, client_id, document_id, chunk_id, metadata, embedding <=> :embedding AS distance
            FROM document_vectors
            WHERE client_id = :client_id
            ORDER BY distance ASC
            LIMIT :top_k
        """
        
        result = self.db.execute(
            text(query),
            {
                "client_id": client_id,
                "embedding": embedding_str,
                "top_k": top_k
            }
        )
        
        documents = []
        for row in result:
            documents.append({
                "id": str(row.id),
                "client_id": str(row.client_id),
                "document_id": str(row.document_id),
                "chunk_id": str(row.chunk_id),
                "metadata": row.metadata,
                "distance": row.distance
            })
            
        return documents

    def delete_by_document_id(self, document_id: str, client_id: str) -> None:
        self.db.execute(
            text("""
                DELETE FROM document_vectors
                WHERE client_id = :client_id AND document_id = :document_id
            """),
            {
                "client_id": client_id,
                "document_id": document_id
            }
        )
        self.db.commit()


class InMemoryVectorStore(VectorStore):
    """
    Zero-dependency, process-local VectorStore for development/demo use when a real
    pgvector-backed Postgres isn't available. Implements the identical VectorStore
    interface as PgVectorStore - nothing above this layer (Retriever,
    KnowledgeQueryService, agents) knows or cares which one is active; selection is
    purely configuration-driven via get_vector_store() below, per this project's own
    rule that infrastructure must stay replaceable behind interfaces (docs/PROJECT_RULES.md
    Rule 6).

    Real cosine-similarity math, not a stub - just an in-memory store instead of SQL.
    Not persisted across process restarts and not safe across multiple worker
    processes (each has its own copy) - intentionally scoped to a single-process
    dev/demo server, never production.
    """

    _store: Dict[str, List[Dict[str, Any]]] = {}

    def add_documents(self, documents: List[Dict[str, Any]], client_id: str) -> None:
        bucket = self._store.setdefault(client_id, [])
        for doc in documents:
            bucket.append({
                "id": doc["chunk_id"],
                "client_id": client_id,
                "document_id": doc.get("document_id"),
                "chunk_id": doc.get("chunk_id"),
                "embedding": doc["embedding"],
                "metadata": doc.get("metadata", {}),
            })

    @staticmethod
    def _cosine_distance(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0
        return 1.0 - (dot / (norm_a * norm_b))

    def similarity_search(
        self,
        query_embedding: List[float],
        client_id: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        bucket = self._store.get(client_id, [])
        scored = [
            {**row, "distance": self._cosine_distance(query_embedding, row["embedding"])}
            for row in bucket
        ]
        scored.sort(key=lambda r: r["distance"])
        return scored[:top_k]

    def delete_by_document_id(self, document_id: str, client_id: str) -> None:
        bucket = self._store.get(client_id, [])
        self._store[client_id] = [r for r in bucket if r.get("document_id") != document_id]


def get_vector_store(db: Session) -> VectorStore:
    """Selects the concrete VectorStore implementation via VECTOR_STORE_PROVIDER -
    'pgvector' (default, requires a real Postgres+pgvector) or 'memory' (dev/demo,
    zero-dependency, process-local). Every caller in this codebase should go through
    this factory rather than constructing PgVectorStore directly, so the concrete
    infrastructure stays swappable purely through configuration."""
    if settings.VECTOR_STORE_PROVIDER == "memory":
        return InMemoryVectorStore()
    return PgVectorStore(db)

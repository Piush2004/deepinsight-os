# Phase 1: Deep Insight Knowledge Base

## Core Principles
Phase 1 establishes the foundational Knowledge Base that every future agent will depend upon. It is designed around the 7 Core Rules of DeepInsight OS, ensuring extreme abstraction, modularity, tenant isolation, and observability.

## Document Processing Pipeline
Every document uploaded to the system goes through a strict pipeline:
1. **Upload**: Receive file binary.
2. **Validate**: Check file type, size, tenant quotas.
3. **Virus Scan**: Stream scanning (placeholder/mockable abstraction for now).
4. **Metadata Extraction**: Extract author, date, native source info.
5. **Text Extraction**: Parse PDF/DOCX/HTML into raw text via `DocumentLoader`.
6. **Chunking**: Apply a `ChunkingStrategy` (Semantic, Recursive, etc.).
7. **Embedding**: Pass chunks to `EmbeddingProvider` (e.g., BGE-M3).
8. **Store**: Persist chunks and vectors to `VectorStore` (e.g., pgvector).
9. **Index**: Ensure appropriate indices exist for fast retrieval.
10. **Verification**: Mark status and confirm completion.

### Document Model tracking parameters:
- Document ID (UUID)
- Client ID (UUID) -> **Crucial for Rule 2**
- Version
- Source
- Hash (SHA-256 for duplication detection)
- Upload Time
- Status
- Processing Status
- Embedding Status

## Module Architecture
The Knowledge Base layer is segmented into the following services:
- `DocumentService`: Coordinates the ingestion pipeline.
- `MetadataService`: Handles document relational metadata mapping.
- `EmbeddingService`: Wraps the `EmbeddingProvider` abstraction.
- `ChunkingService`: Wraps the `ChunkingStrategy` abstraction.
- `VectorStore`: Abstract interface for saving/retrieving vectors.
- `RetrievalService`: Handles similarity search algorithms.
- `QueryService`: Interface for higher-level RAG formulation.
- `KnowledgeAPI`: External-facing endpoints for agents.
- `AuditService`: Observability and AI tracking logs (Rule 5).

## Next Steps for Implementation
1. **Directory Structure Setup**: Scaffold the abstract base classes in `apps/backend/api/core/interfaces/`.
2. **Database Models**: Create the Document and AI Audit models in PostgreSQL via SQLAlchemy (ensuring `client_id` sits on every table).
3. **Pipeline Skeleton**: Build the `DocumentService` flow using dependency injection for the chunker and embedder.
4. **Implementations**: Implement the specific `PgVectorStore`, `BGEEmbeddingProvider`, and `RecursiveChunkingStrategy` classes.

import io

from tests.conftest import requires_postgres
from api.models.client import Client
from api.models.knowledge import DocumentVersion, DocumentChunk
from api.services.knowledge.pipeline import (
    ValidationService, MetadataService, ExtractionService, CleaningService,
    ChunkingService, EmbeddingService, StorageService, VerificationService,
    DocumentUploadService,
)
from api.services.knowledge.loaders import TextLoader
from api.services.knowledge.chunking import RecursiveChunkingStrategy
from api.services.knowledge.embeddings import LocalHashingEmbeddingProvider
from api.services.knowledge.vector_store import PgVectorStore
from api.services.knowledge.retrieval import PgVectorRetriever, RagKnowledgeQueryService


def _build_upload_service(db):
    return DocumentUploadService(
        db=db,
        validation=ValidationService(),
        metadata=MetadataService(),
        extraction=ExtractionService(TextLoader()),
        cleaning=CleaningService(),
        chunking=ChunkingService(RecursiveChunkingStrategy(chunk_size=200)),
        embedding=EmbeddingService(LocalHashingEmbeddingProvider()),
        storage=StorageService(PgVectorStore(db), db),
        verification=VerificationService(db),
    )


@requires_postgres
def test_upload_extracts_chunks_embeds_and_stores_real_rows(db_session):
    client = Client(name="Acme Corp")
    db_session.add(client)
    db_session.flush()

    content = (
        b"Acme Corp brand voice is confident and technical. "
        b"Our target audience is enterprise marketing directors. "
        b"We never use the word 'cheap' in any content."
    )
    service = _build_upload_service(db_session)
    document = service.process_upload(client.id, io.BytesIO(content), "brand_voice.txt", "text/plain")

    assert document.status == "completed"
    assert document.checksum

    version = db_session.query(DocumentVersion).filter_by(document_id=document.id).first()
    assert version is not None
    assert version.version == 1
    assert "confident and technical" in version.raw_text

    chunks = db_session.query(DocumentChunk).filter_by(version_id=version.id).all()
    assert len(chunks) > 0
    assert all(c.embedding_status == "completed" for c in chunks)


@requires_postgres
def test_duplicate_upload_creates_new_version_not_new_document(db_session):
    client = Client(name="Acme Corp")
    db_session.add(client)
    db_session.flush()

    content = b"Identical content for dedupe test."
    service = _build_upload_service(db_session)

    doc1 = service.process_upload(client.id, io.BytesIO(content), "a.txt", "text/plain")
    doc2 = service.process_upload(client.id, io.BytesIO(content), "a-renamed.txt", "text/plain")

    assert doc1.id == doc2.id  # same checksum -> same Document, new version

    versions = db_session.query(DocumentVersion).filter_by(document_id=doc1.id).all()
    assert len(versions) == 2


@requires_postgres
def test_retrieval_returns_real_grounded_citation(db_session):
    client = Client(name="Acme Corp")
    db_session.add(client)
    db_session.flush()

    content = b"Acme Corp never discounts pricing. Our brand voice avoids the word cheap entirely."
    service = _build_upload_service(db_session)
    service.process_upload(client.id, io.BytesIO(content), "pricing_policy.txt", "text/plain")

    retriever = PgVectorRetriever(LocalHashingEmbeddingProvider(), PgVectorStore(db_session), db_session)
    rag = RagKnowledgeQueryService(retriever)

    result = rag.query("What is our pricing and discount policy?", client.id)

    assert result["grounded"] is True
    assert len(result["sources"]) > 0
    assert "discount" in result["content"].lower() or "cheap" in result["content"].lower()


@requires_postgres
def test_retrieval_is_tenant_isolated(db_session):
    client_a = Client(name="Client A")
    client_b = Client(name="Client B")
    db_session.add_all([client_a, client_b])
    db_session.flush()

    service = _build_upload_service(db_session)
    service.process_upload(client_a.id, io.BytesIO(b"Client A's secret roadmap is Project Nightingale."),
                            "a.txt", "text/plain")
    service.process_upload(client_b.id, io.BytesIO(b"Client B's secret roadmap is Project Falcon."),
                            "b.txt", "text/plain")

    retriever = PgVectorRetriever(LocalHashingEmbeddingProvider(), PgVectorStore(db_session), db_session)
    rag = RagKnowledgeQueryService(retriever)

    result_for_b = rag.query("What is the secret roadmap project name?", client_b.id)

    combined_content = result_for_b["content"]
    assert "Nightingale" not in combined_content  # Client A's data must never leak into Client B's query

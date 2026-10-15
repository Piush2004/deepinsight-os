import os
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from api.database.session import get_db
from api.core.security import require_role, require_client_access, assert_client_access
from api.models.user import User
from api.models.knowledge import Document, DocumentVersion, AuditLog
from api.services.knowledge.pipeline import (
    ValidationService, MetadataService, ExtractionService, CleaningService,
    ChunkingService, EmbeddingService, StorageService, VerificationService,
    DocumentUploadService, log_audit,
)
from api.services.knowledge.loaders import get_loader_for_mime_type
from api.services.knowledge.chunking import RecursiveChunkingStrategy
from api.services.knowledge.embeddings import get_embedding_provider
from api.services.knowledge.vector_store import get_vector_store
from api.services.knowledge.retrieval import PgVectorRetriever, RagKnowledgeQueryService
import time

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])
document_router = APIRouter(prefix="/documents", tags=["Documents"])

EXTENSION_MIME_FALLBACK = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".pdf": "application/pdf",
}


def _resolve_mime_type(filename: str, declared_content_type: Optional[str]) -> str:
    from api.services.knowledge.pipeline import ALLOWED_MIME_TYPES
    if declared_content_type in ALLOWED_MIME_TYPES:
        return declared_content_type
    ext = os.path.splitext(filename or "")[1].lower()
    return EXTENSION_MIME_FALLBACK.get(ext, declared_content_type or "application/octet-stream")


def _build_upload_service(db: Session, mime_type: str) -> DocumentUploadService:
    loader = get_loader_for_mime_type(mime_type)
    embedding_provider = get_embedding_provider()
    return DocumentUploadService(
        db=db,
        validation=ValidationService(),
        metadata=MetadataService(),
        extraction=ExtractionService(loader),
        cleaning=CleaningService(),
        chunking=ChunkingService(RecursiveChunkingStrategy()),
        embedding=EmbeddingService(embedding_provider),
        storage=StorageService(get_vector_store(db), db),
        verification=VerificationService(db),
        embedding_model_name=embedding_provider.__class__.__name__,
    )


def _get_owned_document(db: Session, user: User, document_id: UUID) -> Document:
    document = db.query(Document).filter(Document.id == document_id, Document.is_deleted == False).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    assert_client_access(db, user, document.client_id)
    return document


@document_router.post("/upload")
async def upload_document(
    client_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    """Uploads a document to the knowledge base and runs it through the full ingestion
    pipeline synchronously (validate -> extract -> chunk -> embed -> store -> verify)."""
    assert_client_access(db, user, client_id)
    mime_type = _resolve_mime_type(file.filename, file.content_type)

    try:
        service = _build_upload_service(db, mime_type)
        document = service.process_upload(UUID(client_id), file.file, file.filename, mime_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "message": "Document uploaded successfully",
        "document_id": document.id,
        "filename": file.filename,
        "status": document.status,
    }

@document_router.get("")
async def get_documents(
    client_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_client_access("client_id")),
):
    """List all documents for the client."""
    documents = (
        db.query(Document)
        .filter(Document.client_id == client_id, Document.is_deleted == False)
        .order_by(Document.created_at.desc())
        .offset(skip).limit(limit)
        .all()
    )
    return {
        "documents": [
            {
                "id": d.id, "title": d.title, "status": d.status,
                "mime_type": d.mime_type, "file_size": d.file_size,
                "created_at": d.created_at,
            }
            for d in documents
        ]
    }

@document_router.get("/{document_id}")
async def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Analyst"]))
):
    """Get a specific document by ID, including its latest version's extracted text."""
    document = _get_owned_document(db, user, document_id)
    latest_version = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version.desc())
        .first()
    )
    return {
        "id": document.id,
        "title": document.title,
        "status": document.status,
        "mime_type": document.mime_type,
        "file_size": document.file_size,
        "checksum": document.checksum,
        "created_at": document.created_at,
        "latest_version": latest_version.version if latest_version else None,
        "raw_text": latest_version.raw_text if latest_version else None,
    }

@document_router.delete("/{document_id}")
async def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    """Soft delete a document and purge its vectors from the vector store."""
    document = _get_owned_document(db, user, document_id)
    document.is_deleted = True
    db.add(document)
    db.commit()

    get_vector_store(db).delete_by_document_id(str(document.id), str(document.client_id))
    log_audit(db, client_id=document.client_id, document_id=document.id, action="Delete",
              pipeline_stage=None, status="success", started_at=time.monotonic())

    return {"message": "Document deleted successfully"}

@document_router.post("/{document_id}/reindex")
async def reindex_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    """Re-chunks and re-embeds the document's latest extracted text into a new version."""
    document = _get_owned_document(db, user, document_id)
    latest_version = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version.desc())
        .first()
    )
    if not latest_version or not latest_version.raw_text:
        raise HTTPException(status_code=400, detail="Document has no extracted text to reindex.")

    started_at = time.monotonic()
    chunking = ChunkingService(RecursiveChunkingStrategy())
    embedding_provider = get_embedding_provider()
    embedding = EmbeddingService(embedding_provider)
    storage = StorageService(get_vector_store(db), db)
    verification = VerificationService(db)

    chunks = chunking.chunk_document(latest_version.raw_text)
    embeddings = embedding.embed_chunks(chunks)

    new_version = DocumentVersion(
        document_id=document.id,
        version=latest_version.version + 1,
        raw_text=latest_version.raw_text,
        processing_status="processing",
    )
    db.add(new_version)
    db.flush()

    storage.store(document.client_id, document.id, new_version.id, chunks, embeddings, {},
                  embedding_model=embedding_provider.__class__.__name__)
    verification.verify_and_complete(document, new_version, chunk_count=len(chunks))

    log_audit(db, client_id=document.client_id, document_id=document.id, action="Re-index",
              pipeline_stage="complete", status="success", started_at=started_at)

    return {"message": "Document reindexing complete", "new_version": new_version.version}

@router.post("/query")
async def query_knowledge(
    query: str,
    client_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Analyst"]))
):
    """Query the knowledge base using real semantic (vector similarity) search."""
    assert_client_access(db, user, client_id)
    embedding_provider = get_embedding_provider()
    retriever = PgVectorRetriever(embedding_provider, get_vector_store(db), db)
    service = RagKnowledgeQueryService(retriever)
    result = service.query(query, client_id)
    return {"query": query, **result}

@router.get("/history")
async def get_knowledge_history(
    client_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_client_access("client_id")),
):
    """Retrieve audit history for knowledge base actions."""
    entries = (
        db.query(AuditLog)
        .filter(AuditLog.client_id == client_id)
        .order_by(AuditLog.created_at.desc())
        .offset(skip).limit(limit)
        .all()
    )
    return {
        "history": [
            {
                "id": e.id, "document_id": e.document_id, "action": e.action,
                "pipeline_stage": e.pipeline_stage, "status": e.status,
                "execution_time_ms": e.execution_time_ms, "errors": e.errors,
                "created_at": e.created_at,
            }
            for e in entries
        ]
    }

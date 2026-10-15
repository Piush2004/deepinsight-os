import time
from typing import Any, Dict, BinaryIO, List, Optional
import hashlib
from uuid import UUID
from sqlalchemy.orm import Session

from api.models.knowledge import Document, DocumentVersion, DocumentChunk, EmbeddingRecord, KnowledgeMetadata, AuditLog
from api.core.interfaces.document_loader import DocumentLoader
from api.core.interfaces.chunking_strategy import ChunkingStrategy
from api.core.interfaces.embedding_provider import EmbeddingProvider
from api.core.interfaces.vector_store import VectorStore

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB
ALLOWED_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "application/pdf",
}


class ValidationService:
    def validate(self, file: BinaryIO, filename: str, mime_type: str, file_size: int) -> None:
        """Validates file type and size. Raises ValueError if invalid."""
        if file_size <= 0:
            raise ValueError("Uploaded file is empty.")
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.")
        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported file type '{mime_type}'. Allowed types: {', '.join(sorted(ALLOWED_MIME_TYPES))}")
        if not filename or not filename.strip():
            raise ValueError("A filename is required.")


class MetadataService:
    def extract_metadata(self, loader_metadata: Dict[str, Any], filename: str, client_id: UUID) -> Dict[str, Any]:
        """Merges loader-provided metadata (e.g. PDF page count) with basic file metadata."""
        return {
            "filename": filename,
            **(loader_metadata or {}),
        }


class ExtractionService:
    def __init__(self, loader: DocumentLoader):
        self.loader = loader

    def extract(self, file: BinaryIO) -> Dict[str, Any]:
        """Extracts raw text + format-specific metadata using the appropriate DocumentLoader."""
        return self.loader.load(file)


class CleaningService:
    def clean(self, raw_text: str) -> str:
        """Cleans and normalizes the extracted text."""
        # Collapse excessive blank lines/whitespace left over from PDF extraction while
        # preserving paragraph breaks the chunker relies on.
        lines = [line.strip() for line in raw_text.splitlines()]
        cleaned_lines = []
        blank_run = 0
        for line in lines:
            if line == "":
                blank_run += 1
                if blank_run > 1:
                    continue
            else:
                blank_run = 0
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()


class ChunkingService:
    def __init__(self, strategy: ChunkingStrategy):
        self.strategy = strategy

    def chunk_document(self, text: str) -> List[str]:
        """Splits the text into chunks using the provided strategy."""
        return self.strategy.chunk(text)


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider):
        self.provider = provider

    def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        """Generates embeddings for all chunks."""
        if not chunks:
            return []
        return self.provider.embed_batch(chunks)


class StorageService:
    EMBEDDING_MODEL_NAME = "local"  # overridden per-call via store(..., embedding_model=...)

    def __init__(self, vector_store: VectorStore, db: Session):
        self.vector_store = vector_store
        self.db = db

    def store(
        self,
        client_id: UUID,
        document_id: UUID,
        version_id: UUID,
        chunk_texts: List[str],
        embeddings: List[List[float]],
        metadata: Dict[str, Any],
        embedding_model: str = "local-hashing",
    ) -> List[DocumentChunk]:
        """Persists chunk rows + embedding-record rows in SQL, and the vectors themselves
        in the VectorStore (pgvector). Both sides reference the same chunk_id so a
        similarity hit can always be resolved back to its chunk text and parent document."""
        chunk_rows: List[DocumentChunk] = []
        vector_documents = []

        for index, (chunk_text, embedding) in enumerate(zip(chunk_texts, embeddings)):
            chunk = DocumentChunk(
                version_id=version_id,
                chunk_index=index,
                chunk_text=chunk_text,
                token_count=max(1, len(chunk_text.split())),
                embedding_status="completed",
            )
            self.db.add(chunk)
            self.db.flush()  # need chunk.id before referencing it in EmbeddingRecord/vector store

            self.db.add(EmbeddingRecord(
                chunk_id=chunk.id,
                embedding_model=embedding_model,
                embedding_dimension=len(embedding),
                vector_reference=str(chunk.id),
            ))

            vector_documents.append({
                "document_id": str(document_id),
                "chunk_id": str(chunk.id),
                "embedding": embedding,
                "metadata": {"chunk_text": chunk_text, **(metadata or {})},
            })
            chunk_rows.append(chunk)

        if vector_documents:
            self.vector_store.add_documents(vector_documents, client_id=str(client_id))

        if metadata:
            self.db.add(KnowledgeMetadata(document_id=document_id, custom_metadata=metadata))

        self.db.commit()
        return chunk_rows


class VerificationService:
    def __init__(self, db: Session):
        self.db = db

    def verify_and_complete(self, document: Document, version: DocumentVersion, chunk_count: int) -> None:
        """Marks the document/version as complete once chunks + embeddings are persisted."""
        version.processing_status = "completed"
        document.status = "completed" if chunk_count > 0 else "empty"
        self.db.add(version)
        self.db.add(document)
        self.db.commit()


def log_audit(db: Session, *, client_id: UUID, document_id: Optional[UUID], action: str,
              pipeline_stage: Optional[str], status: str, started_at: float,
              errors: Optional[str] = None) -> None:
    db.add(AuditLog(
        client_id=client_id,
        document_id=document_id,
        action=action,
        pipeline_stage=pipeline_stage,
        execution_time_ms=int((time.monotonic() - started_at) * 1000),
        status=status,
        errors=errors,
    ))
    db.commit()


class DocumentUploadService:
    def __init__(
        self,
        db: Session,
        validation: ValidationService,
        metadata: MetadataService,
        extraction: ExtractionService,
        cleaning: CleaningService,
        chunking: ChunkingService,
        embedding: EmbeddingService,
        storage: StorageService,
        verification: VerificationService,
        embedding_model_name: str = "local-hashing",
    ):
        self.db = db
        self.validation = validation
        self.metadata = metadata
        self.extraction = extraction
        self.cleaning = cleaning
        self.chunking = chunking
        self.embedding = embedding
        self.storage = storage
        self.verification = verification
        self.embedding_model_name = embedding_model_name

    def process_upload(self, client_id: UUID, file: BinaryIO, filename: str, mime_type: str) -> Document:
        """Orchestrates the entire document ingestion pipeline: validate -> hash -> extract
        -> clean -> chunk -> embed -> store -> verify. Deduplicates by (client_id, checksum):
        re-uploading identical content creates a new version on the existing Document
        instead of a duplicate Document row."""
        started_at = time.monotonic()

        file.seek(0, 2)  # seek to end
        file_size = file.tell()
        file.seek(0)

        self.validation.validate(file, filename, mime_type, file_size)

        file_hash = hashlib.sha256(file.read()).hexdigest()
        file.seek(0)

        existing = (
            self.db.query(Document)
            .filter(Document.client_id == client_id, Document.checksum == file_hash, Document.is_deleted == False)
            .first()
        )

        if existing:
            document = existing
            next_version_number = (
                self.db.query(DocumentVersion)
                .filter(DocumentVersion.document_id == document.id)
                .count()
            ) + 1
        else:
            document = Document(
                client_id=client_id,
                title=filename,
                source_type="upload",
                mime_type=mime_type,
                file_size=file_size,
                checksum=file_hash,
                status="processing",
            )
            self.db.add(document)
            self.db.flush()
            next_version_number = 1

        try:
            extraction_result = self.extraction.extract(file)
            raw_text = extraction_result.get("text", "")
            loader_metadata = extraction_result.get("metadata", {})

            cleaned_text = self.cleaning.clean(raw_text)
            chunks = self.chunking.chunk_document(cleaned_text)
            embeddings = self.embedding.embed_chunks(chunks)

            version = DocumentVersion(
                document_id=document.id,
                version=next_version_number,
                raw_text=cleaned_text,
                processing_status="processing",
            )
            self.db.add(version)
            self.db.flush()

            metadata = self.metadata.extract_metadata(loader_metadata, filename, client_id)
            self.storage.store(
                client_id, document.id, version.id, chunks, embeddings, metadata,
                embedding_model=self.embedding_model_name,
            )
            self.verification.verify_and_complete(document, version, chunk_count=len(chunks))

            log_audit(
                self.db, client_id=client_id, document_id=document.id, action="Upload",
                pipeline_stage="complete", status="success", started_at=started_at,
            )
        except Exception as exc:
            document.status = "failed"
            self.db.add(document)
            self.db.commit()
            log_audit(
                self.db, client_id=client_id, document_id=document.id, action="Upload",
                pipeline_stage="failed", status="error", started_at=started_at, errors=str(exc),
            )
            raise

        return document

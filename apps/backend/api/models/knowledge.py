from sqlalchemy import Column, String, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from api.models.base import BaseModel

class Document(BaseModel):
    __tablename__ = "documents"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), index=True, nullable=False)
    title = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    checksum = Column(String, nullable=False)
    status = Column(String, default="processing", nullable=False)
    
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    metadata_entries = relationship("KnowledgeMetadata", back_populates="document", cascade="all, delete-orphan")

class DocumentVersion(BaseModel):
    __tablename__ = "document_versions"
    
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True, nullable=False)
    version = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=True)
    processing_status = Column(String, default="pending", nullable=False)
    
    document = relationship("Document", back_populates="versions")
    chunks = relationship("DocumentChunk", back_populates="version", cascade="all, delete-orphan")

class DocumentChunk(BaseModel):
    __tablename__ = "document_chunks"
    
    version_id = Column(UUID(as_uuid=True), ForeignKey("document_versions.id"), index=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False)
    embedding_status = Column(String, default="pending", nullable=False)
    
    version = relationship("DocumentVersion", back_populates="chunks")
    embeddings = relationship("EmbeddingRecord", back_populates="chunk", cascade="all, delete-orphan")

class EmbeddingRecord(BaseModel):
    __tablename__ = "embedding_records"
    
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id"), index=True, nullable=False)
    embedding_model = Column(String, nullable=False)
    embedding_dimension = Column(Integer, nullable=False)
    vector_reference = Column(String, nullable=False, index=True) # ID referencing the vector in VectorStore
    
    chunk = relationship("DocumentChunk", back_populates="embeddings")

class KnowledgeMetadata(BaseModel):
    __tablename__ = "knowledge_metadata"
    
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True, nullable=False)
    tags = Column(JSON, nullable=True)
    author = Column(String, nullable=True)
    language = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    campaign = Column(String, nullable=True)
    visibility = Column(String, nullable=True)
    custom_metadata = Column(JSON, nullable=True)
    
    document = relationship("Document", back_populates="metadata_entries")

class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    
    client_id = Column(UUID(as_uuid=True), index=True, nullable=False)
    document_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    version = Column(Integer, nullable=True)
    action = Column(String, nullable=False) # Upload, Delete, Re-index, Embedding, Retrieval, Errors
    pipeline_stage = Column(String, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    status = Column(String, nullable=False)
    errors = Column(Text, nullable=True)

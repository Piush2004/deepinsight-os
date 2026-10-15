from sqlalchemy import Column, String, Integer, Text, ForeignKey, Float, DateTime, Table
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from api.models.base import BaseModel

# Association table for content tags
content_tags_association = Table(
    'content_tags_association', BaseModel.metadata,
    Column('content_id', UUID(as_uuid=True), ForeignKey('content.id')),
    Column('tag_id', UUID(as_uuid=True), ForeignKey('content_tags.id'))
)

class ContentTag(BaseModel):
    __tablename__ = "content_tags"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), index=True, nullable=False)
    name = Column(String, nullable=False)

class Content(BaseModel):
    __tablename__ = "content"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), index=True, nullable=False)
    title = Column(String, nullable=False)
    content_type = Column(String, nullable=False) # Blog, LinkedIn, Email, etc.
    status = Column(String, default="draft", nullable=False) # draft, pending_review, needs_changes, approved, rejected, published, archived
    
    # Calendar tracking
    scheduled_date = Column(DateTime, nullable=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    campaign = Column(String, nullable=True)
    
    versions = relationship("ContentVersion", back_populates="content", cascade="all, delete-orphan")
    tags = relationship("ContentTag", secondary=content_tags_association)
    approval_requests = relationship("ContentApprovalRequest", back_populates="content", cascade="all, delete-orphan")

class ContentVersion(BaseModel):
    __tablename__ = "content_versions"
    
    content_id = Column(UUID(as_uuid=True), ForeignKey("content.id"), index=True, nullable=False)
    version = Column(Integer, nullable=False)
    body = Column(Text, nullable=False)
    diff = Column(Text, nullable=True) # Diff from previous version
    
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True) # None if AI
    ai_model = Column(String, nullable=True)
    prompt_version = Column(String, nullable=True)
    
    content = relationship("Content", back_populates="versions")
    comments = relationship("ContentComment", back_populates="version", cascade="all, delete-orphan")
    scores = relationship("ContentScore", back_populates="version", uselist=False, cascade="all, delete-orphan")

class ContentComment(BaseModel):
    __tablename__ = "content_comments"
    
    version_id = Column(UUID(as_uuid=True), ForeignKey("content_versions.id"), index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    comment = Column(Text, nullable=False)
    
    version = relationship("ContentVersion", back_populates="comments")

class ContentScore(BaseModel):
    __tablename__ = "content_scores"
    
    version_id = Column(UUID(as_uuid=True), ForeignKey("content_versions.id"), index=True, nullable=False)
    originality = Column(Float, nullable=False)
    readability = Column(Float, nullable=False)
    grammar = Column(Float, nullable=False)
    professional_tone = Column(Float, nullable=False)
    brand_consistency = Column(Float, nullable=False)
    citation_coverage = Column(Float, nullable=False)
    hallucination_risk = Column(Float, nullable=False)
    completeness = Column(Float, nullable=False)
    overall_score = Column(Float, nullable=False)
    
    version = relationship("ContentVersion", back_populates="scores")

class ContentApprovalRequest(BaseModel):
    __tablename__ = "content_approval_requests"
    
    content_id = Column(UUID(as_uuid=True), ForeignKey("content.id"), index=True, nullable=False)
    status = Column(String, default="pending", nullable=False)
    comments = Column(Text, nullable=True)
    approver_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    content = relationship("Content", back_populates="approval_requests")

class ContentTemplate(BaseModel):
    __tablename__ = "content_templates"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    template_type = Column(String, nullable=False)
    body = Column(Text, nullable=False)

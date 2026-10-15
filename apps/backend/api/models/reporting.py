from sqlalchemy import Column, String, Integer, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from api.models.base import BaseModel

class Report(BaseModel):
    __tablename__ = "reports"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), index=True, nullable=False)
    title = Column(String, nullable=False)
    reporting_period = Column(String, nullable=False)
    status = Column(String, default="draft", nullable=False) # draft, pending_approval, approved, rejected, archived
    
    versions = relationship("ReportVersion", back_populates="report", cascade="all, delete-orphan")
    approval_requests = relationship("ApprovalRequest", back_populates="report", cascade="all, delete-orphan")
    comments = relationship("ReportComment", back_populates="report", cascade="all, delete-orphan")

class ReportVersion(BaseModel):
    __tablename__ = "report_versions"
    
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), index=True, nullable=False)
    version = Column(Integer, nullable=False)
    content = JSON # Structured JSON with sections (Executive Summary, Wins, etc.)
    content_text = Column(Text, nullable=True) # Full markdown or text version
    
    report = relationship("Report", back_populates="versions")

class ApprovalRequest(BaseModel):
    __tablename__ = "approval_requests"

    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), index=True, nullable=False)
    status = Column(String, default="pending", nullable=False)
    comments = Column(Text, nullable=True)
    approver_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    report = relationship("Report", back_populates="approval_requests")

class ReportComment(BaseModel):
    __tablename__ = "report_comments"

    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"), index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    comment = Column(Text, nullable=False)

    report = relationship("Report", back_populates="comments")

class AgentRun(BaseModel):
    __tablename__ = "agent_runs"
    
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), index=True, nullable=False)
    agent_name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    errors = Column(Text, nullable=True)
    
    metrics = relationship("ExecutionMetric", back_populates="agent_run", uselist=False, cascade="all, delete-orphan")

class ExecutionMetric(BaseModel):
    __tablename__ = "execution_metrics"
    
    agent_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), index=True, nullable=False)
    execution_time_ms = Column(Integer, nullable=False)
    model = Column(String, nullable=False)
    prompt_version = Column(String, nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    estimated_cost = Column(Float, nullable=False, default=0.0)
    retrieved_documents = Column(Integer, nullable=False, default=0)
    
    agent_run = relationship("AgentRun", back_populates="metrics")

class PromptVersion(BaseModel):
    __tablename__ = "prompt_versions"
    
    name = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)

from sqlalchemy import Column, String, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from api.models.base import BaseModel


class SEOAnalysis(BaseModel):
    """One row per 'Run Analysis' action for a client - mirrors Report's role for the
    Reporting Agent (api/models/reporting.py). Owns the opportunities it produced."""
    __tablename__ = "seo_analyses"

    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), index=True, nullable=False)
    status = Column(String, default="running", nullable=False)  # running, completed, failed
    data_provider = Column(String, nullable=False)  # "dev" or a future real provider name - never hidden from the record
    period_start = Column(String, nullable=False)
    period_end = Column(String, nullable=False)
    executive_summary = Column(Text, nullable=True)  # LLM-generated, covers the whole analysis
    error = Column(Text, nullable=True)

    opportunities = relationship("SEOOpportunity", back_populates="analysis", cascade="all, delete-orphan")


class SEOOpportunity(BaseModel):
    """One detected opportunity - the structured contract described in
    docs/SEO_INTELLIGENCE_IMPLEMENTATION_REPORT.md. client_id is denormalized (not
    derivable only via analysis_id) so client-scoped queries/tenant checks don't
    require a join, matching how Document/Report/Content all carry client_id directly."""
    __tablename__ = "seo_opportunities"

    analysis_id = Column(UUID(as_uuid=True), ForeignKey("seo_analyses.id"), index=True, nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), index=True, nullable=False)

    opportunity_type = Column(String, nullable=False)  # CTR_OPTIMIZATION, PAGE_ONE_OPTIMIZATION, ...
    category = Column(String, nullable=False)  # QUICK_WIN, GROWTH_OPPORTUNITY, PERFORMANCE_RISK, EMERGING_MOMENTUM
    title = Column(String, nullable=False)

    source_entity = Column(String, nullable=False)  # the keyword or page
    source_type = Column(String, nullable=False)  # "keyword" | "page"

    metrics = Column(JSON, nullable=False)  # the real evidence numbers
    evidence = Column(JSON, nullable=False)  # human-readable evidence strings, deterministically generated

    priority_score = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False)
    impact_score = Column(Float, nullable=False)
    effort_estimate = Column(String, nullable=False)  # Low, Medium, High

    recommended_actions = Column(JSON, nullable=False)  # list[str], deterministic

    strategic_explanation = Column(Text, nullable=True)  # LLM-generated, grounded-only
    evaluation_scores = Column(JSON, nullable=True)  # EvaluationEngine.evaluate() output, for transparency

    status = Column(String, default="pending_review", nullable=False)  # pending_review, approved, rejected

    analysis = relationship("SEOAnalysis", back_populates="opportunities")
    approval_requests = relationship("SEOApprovalRequest", back_populates="opportunity", cascade="all, delete-orphan")
    comments = relationship("SEOOpportunityComment", back_populates="opportunity", cascade="all, delete-orphan")


class SEOApprovalRequest(BaseModel):
    """Mirrors ApprovalRequest (reporting) / ContentApprovalRequest (content) exactly -
    this codebase's established one-approval-table-per-artifact-type convention,
    not a shared/polymorphic table."""
    __tablename__ = "seo_approval_requests"

    opportunity_id = Column(UUID(as_uuid=True), ForeignKey("seo_opportunities.id"), index=True, nullable=False)
    status = Column(String, default="pending", nullable=False)
    comments = Column(Text, nullable=True)
    approver_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    opportunity = relationship("SEOOpportunity", back_populates="approval_requests")


class SEOOpportunityComment(BaseModel):
    """Mirrors ReportComment/ContentComment - a running discussion thread, distinct
    from the single rejection-reason `comments` field on SEOApprovalRequest."""
    __tablename__ = "seo_opportunity_comments"

    opportunity_id = Column(UUID(as_uuid=True), ForeignKey("seo_opportunities.id"), index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    comment = Column(Text, nullable=False)

    opportunity = relationship("SEOOpportunity", back_populates="comments")

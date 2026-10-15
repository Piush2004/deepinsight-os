from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from api.database.session import get_db
from api.core.security import require_role, require_client_access, assert_client_access
from api.models.user import User
from api.models.seo import SEOAnalysis, SEOOpportunity, SEOApprovalRequest, SEOOpportunityComment
from api.models.knowledge import AuditLog
from api.core.tasks import process_seo_analysis

router = APIRouter(prefix="/seo", tags=["SEO Intelligence"])

# Every category the deterministic detector can produce (opportunity_detector._category) -
# the frontend's four opportunity cards map 1:1 onto these, never onto a free-typed string.
OPPORTUNITY_CATEGORIES = ("QUICK_WIN", "GROWTH_OPPORTUNITY", "PERFORMANCE_RISK", "EMERGING_MOMENTUM")


def _get_owned_opportunity(db: Session, user: User, opportunity_id: UUID) -> SEOOpportunity:
    opportunity = (
        db.query(SEOOpportunity)
        .filter(SEOOpportunity.id == opportunity_id, SEOOpportunity.is_deleted == False)
        .first()
    )
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    assert_client_access(db, user, opportunity.client_id)
    return opportunity


def _opportunity_summary(o: SEOOpportunity) -> dict:
    return {
        "id": o.id,
        "opportunity_type": o.opportunity_type,
        "category": o.category,
        "title": o.title,
        "source_entity": o.source_entity,
        "source_type": o.source_type,
        "priority_score": o.priority_score,
        "confidence_score": o.confidence_score,
        "impact_score": o.impact_score,
        "effort_estimate": o.effort_estimate,
        "status": o.status,
        "created_at": o.created_at,
    }


@router.post("/analyze")
async def analyze_seo(
    client_id: UUID,
    period_start: str,
    period_end: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Analyst"]))
):
    """
    Dispatches the real SEOAgent as a Celery background job (SEODataProvider ->
    deterministic rule engine -> opportunity scoring -> client knowledge context -> LLM
    strategic explanation -> Evaluation Engine -> persist -> approval queue). Returns
    immediately with a Celery task ID for status polling, matching
    generate_report/generate_content.
    """
    assert_client_access(db, user, client_id)

    try:
        task = process_seo_analysis.delay(str(client_id), period_start, period_end)
    except Exception as exc:
        # See api/routers/reports.py's identical branch - CELERY_EAGER dev mode
        # propagates the task's exception right here.
        db.add(AuditLog(client_id=client_id, document_id=None, action="SEOAnalysisQueued",
                         pipeline_stage="queued", execution_time_ms=None, status="failed", errors=str(exc)))
        db.commit()
        return {"message": "SEO analysis failed", "client_id": client_id, "status": "failed", "error": str(exc)}

    db.add(AuditLog(client_id=client_id, document_id=None, action="SEOAnalysisQueued",
                     pipeline_stage="queued", execution_time_ms=None, status="success", errors=None))
    db.commit()

    response = {"message": "SEO analysis started", "client_id": client_id, "task_id": task.id, "status": "processing"}
    if task.ready():
        # CELERY_EAGER dev mode: the task already ran synchronously by the time
        # .delay() returned above.
        response["status"] = "completed" if task.successful() else "failed"
        response["result"] = task.result if task.successful() else str(task.result)
    return response


@router.get("/summary")
async def get_seo_summary(
    client_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_client_access("client_id")),
):
    """Hero/summary view: the most recent analysis (if any) plus a real count of
    non-deleted, non-rejected opportunities per category - drives the four opportunity
    cards (Quick Wins / Growth Opportunities / Performance Risks / Emerging Momentum)
    from actual persisted, deterministic data, not a frontend guess."""
    latest_analysis = (
        db.query(SEOAnalysis)
        .filter(SEOAnalysis.client_id == client_id, SEOAnalysis.is_deleted == False)
        .order_by(SEOAnalysis.created_at.desc())
        .first()
    )

    counts = {category: 0 for category in OPPORTUNITY_CATEGORIES}
    opportunities = (
        db.query(SEOOpportunity)
        .filter(SEOOpportunity.client_id == client_id, SEOOpportunity.is_deleted == False,
                SEOOpportunity.status != "rejected")
        .all()
    )
    for o in opportunities:
        if o.category in counts:
            counts[o.category] += 1

    return {
        "has_analysis": latest_analysis is not None,
        "latest_analysis": (
            {
                "id": latest_analysis.id,
                "status": latest_analysis.status,
                "data_provider": latest_analysis.data_provider,
                "period_start": latest_analysis.period_start,
                "period_end": latest_analysis.period_end,
                "executive_summary": latest_analysis.executive_summary,
                "created_at": latest_analysis.created_at,
            }
            if latest_analysis else None
        ),
        "category_counts": counts,
        "total_open_opportunities": sum(counts.values()),
    }


@router.get("/opportunities")
async def list_opportunities(
    client_id: UUID,
    category: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_client_access("client_id")),
):
    """List detected opportunities for a client, optionally filtered by category
    (QUICK_WIN, GROWTH_OPPORTUNITY, PERFORMANCE_RISK, EMERGING_MOMENTUM) or status."""
    query = db.query(SEOOpportunity).filter(
        SEOOpportunity.client_id == client_id, SEOOpportunity.is_deleted == False
    )
    if category:
        query = query.filter(SEOOpportunity.category == category)
    if status:
        query = query.filter(SEOOpportunity.status == status)
    items = query.order_by(SEOOpportunity.priority_score.desc()).offset(skip).limit(limit).all()
    return {"opportunities": [_opportunity_summary(o) for o in items]}


@router.get("/history")
async def get_seo_history(
    client_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_client_access("client_id")),
):
    """Get the audit history of SEO analysis runs for a client.
    NOTE: registered before /opportunities/{opportunity_id} - a literal path must come
    before a dynamic UUID path segment or FastAPI will try (and fail) to parse
    "history" as an opportunity_id."""
    entries = (
        db.query(AuditLog)
        .filter(AuditLog.client_id == client_id, AuditLog.action.ilike("SEO%"))
        .order_by(AuditLog.created_at.desc())
        .offset(skip).limit(limit)
        .all()
    )
    return {
        "history": [
            {"id": e.id, "action": e.action, "status": e.status, "created_at": e.created_at}
            for e in entries
        ]
    }


@router.get("/opportunities/{opportunity_id}")
async def get_opportunity(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Client", "Analyst"]))
):
    """Full opportunity detail: evidence, deterministic metrics, LLM strategic
    explanation, Evaluation Engine scores, and the comment thread - everything the
    Opportunity Detail screen's Evidence/Why It Matters/Strategic Context/
    Quality-Evaluation sections need."""
    opportunity = _get_owned_opportunity(db, user, opportunity_id)
    comments = (
        db.query(SEOOpportunityComment)
        .filter(SEOOpportunityComment.opportunity_id == opportunity.id)
        .order_by(SEOOpportunityComment.created_at.asc())
        .all()
    )
    approval = (
        db.query(SEOApprovalRequest)
        .filter(SEOApprovalRequest.opportunity_id == opportunity.id)
        .order_by(SEOApprovalRequest.created_at.desc())
        .first()
    )
    return {
        "id": opportunity.id,
        "analysis_id": opportunity.analysis_id,
        "opportunity_type": opportunity.opportunity_type,
        "category": opportunity.category,
        "title": opportunity.title,
        "source_entity": opportunity.source_entity,
        "source_type": opportunity.source_type,
        "metrics": opportunity.metrics,
        "evidence": opportunity.evidence,
        "priority_score": opportunity.priority_score,
        "confidence_score": opportunity.confidence_score,
        "impact_score": opportunity.impact_score,
        "effort_estimate": opportunity.effort_estimate,
        "recommended_actions": opportunity.recommended_actions,
        "strategic_explanation": opportunity.strategic_explanation,
        "evaluation_scores": opportunity.evaluation_scores,
        "status": opportunity.status,
        "created_at": opportunity.created_at,
        "approval": (
            {"status": approval.status, "comments": approval.comments, "approver_id": approval.approver_id}
            if approval else None
        ),
        "comments": [
            {"id": c.id, "user_id": c.user_id, "comment": c.comment, "created_at": c.created_at}
            for c in comments
        ],
    }


@router.put("/opportunities/{opportunity_id}")
async def update_opportunity(
    opportunity_id: UUID,
    title: Optional[str] = None,
    recommended_actions: Optional[list[str]] = Body(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Analyst"]))
):
    """Human edit of an opportunity's title/recommended actions before approval - the
    deterministic evidence/metrics/scores are never editable here (they're computed
    facts, not opinions); only the human-facing framing is. Sends the opportunity back
    to pending_review, matching update_content's identical behavior."""
    opportunity = _get_owned_opportunity(db, user, opportunity_id)
    if title is None and recommended_actions is None:
        raise HTTPException(status_code=400, detail="Provide at least one of: title, recommended_actions")

    if title is not None:
        opportunity.title = title
    if recommended_actions is not None:
        opportunity.recommended_actions = recommended_actions
    opportunity.status = "pending_review"
    db.add(opportunity)
    db.commit()
    return {"message": "Opportunity updated"}


@router.post("/opportunities/{opportunity_id}/approve")
async def approve_opportunity(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    """Approves an opportunity in the Approval Queue."""
    opportunity = _get_owned_opportunity(db, user, opportunity_id)
    approval = (
        db.query(SEOApprovalRequest)
        .filter(SEOApprovalRequest.opportunity_id == opportunity.id)
        .order_by(SEOApprovalRequest.created_at.desc())
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="No pending approval request for this opportunity")

    approval.status = "approved"
    approval.approver_id = user.id
    opportunity.status = "approved"
    db.add_all([approval, opportunity])
    db.commit()
    return {"message": "Opportunity approved"}


@router.post("/opportunities/{opportunity_id}/reject")
async def reject_opportunity(
    opportunity_id: UUID,
    reason: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    """Rejects an opportunity."""
    opportunity = _get_owned_opportunity(db, user, opportunity_id)
    approval = (
        db.query(SEOApprovalRequest)
        .filter(SEOApprovalRequest.opportunity_id == opportunity.id)
        .order_by(SEOApprovalRequest.created_at.desc())
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="No pending approval request for this opportunity")

    approval.status = "rejected"
    approval.approver_id = user.id
    approval.comments = reason
    opportunity.status = "rejected"
    db.add_all([approval, opportunity])
    db.commit()
    return {"message": "Opportunity rejected"}


@router.post("/opportunities/{opportunity_id}/comment")
async def comment_opportunity(
    opportunity_id: UUID,
    comment: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Client", "Analyst"]))
):
    """Add a comment to a specific opportunity."""
    opportunity = _get_owned_opportunity(db, user, opportunity_id)
    db.add(SEOOpportunityComment(opportunity_id=opportunity.id, user_id=user.id, comment=comment))
    db.commit()
    return {"message": "Comment added"}

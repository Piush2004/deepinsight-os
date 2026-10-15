from uuid import UUID
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.database.session import get_db
from api.core.security import require_role, require_client_access, assert_client_access
from api.models.user import User
from api.models.reporting import Report, ReportVersion, ApprovalRequest, ReportComment
from api.models.knowledge import AuditLog
from api.core.tasks import process_report_generation

router = APIRouter(prefix="/reports", tags=["Reports"])


def _get_owned_report(db: Session, user: User, report_id: UUID) -> Report:
    report = db.query(Report).filter(Report.id == report_id, Report.is_deleted == False).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    assert_client_access(db, user, report.client_id)
    return report


@router.post("/generate")
async def generate_report(
    client_id: UUID,
    reporting_period: str,
    metrics: Dict[str, Any],
    historical_metrics: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Analyst"]))
):
    """
    Dispatches the real ReportingAgent as a Celery background job (gather context ->
    Intelligence Layer -> LLM -> validate -> persist -> approval queue). Returns
    immediately with a Celery task ID for status polling.
    """
    assert_client_access(db, user, client_id)
    if not metrics:
        raise HTTPException(status_code=400, detail="metrics is required and cannot be empty.")

    try:
        task = process_report_generation.delay(str(client_id), reporting_period, metrics, historical_metrics)
    except Exception as exc:
        # In CELERY_EAGER dev mode the task runs synchronously and its exception
        # propagates right here (task_eager_propagates=True) - surface it as a clean,
        # informative response instead of letting it fall through to the generic
        # global 500 handler, which would hide exactly the "why did generation fail"
        # detail this workflow needs to show the user. Against a real Celery worker
        # this branch never runs - .delay() only enqueues and can't fail this way.
        db.add(AuditLog(client_id=client_id, document_id=None, action="ReportGenerationQueued",
                         pipeline_stage="queued", execution_time_ms=None, status="failed", errors=str(exc)))
        db.commit()
        return {"message": "Report generation failed", "client_id": client_id, "status": "failed", "error": str(exc)}

    db.add(AuditLog(client_id=client_id, document_id=None, action="ReportGenerationQueued",
                     pipeline_stage="queued", execution_time_ms=None, status="success", errors=None))
    db.commit()

    response = {"message": "Report generation started", "client_id": client_id, "task_id": task.id, "status": "processing"}
    if task.ready():
        # CELERY_EAGER dev mode: the task already ran synchronously by the time
        # .delay() returned above - surface the outcome immediately instead of making
        # the caller poll GET /jobs/{task_id} for a result that already exists.
        response["status"] = "completed" if task.successful() else "failed"
        response["result"] = task.result if task.successful() else str(task.result)
    return response

@router.get("")
async def get_reports(
    client_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_client_access("client_id")),
):
    """List all reports for a specific client."""
    reports = (
        db.query(Report)
        .filter(Report.client_id == client_id, Report.is_deleted == False)
        .order_by(Report.created_at.desc())
        .offset(skip).limit(limit)
        .all()
    )
    return {
        "reports": [
            {"id": r.id, "title": r.title, "reporting_period": r.reporting_period,
             "status": r.status, "created_at": r.created_at}
            for r in reports
        ]
    }

@router.get("/history")
async def get_report_history(
    client_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_client_access("client_id")),
):
    """Get the audit history of report generation and approvals for a client.
    NOTE: registered before /{report_id} - a literal path must come before a dynamic
    UUID path segment or FastAPI will try (and fail) to parse "history" as a report_id."""
    entries = (
        db.query(AuditLog)
        .filter(AuditLog.client_id == client_id, AuditLog.action.ilike("Report%"))
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

@router.get("/{report_id}")
async def get_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Client", "Analyst"]))
):
    """Retrieve a specific report and its versions."""
    report = _get_owned_report(db, user, report_id)
    versions = (
        db.query(ReportVersion)
        .filter(ReportVersion.report_id == report.id)
        .order_by(ReportVersion.version.desc())
        .all()
    )
    return {
        "id": report.id,
        "title": report.title,
        "status": report.status,
        "reporting_period": report.reporting_period,
        "versions": [
            {"version": v.version, "content": v.content, "content_text": v.content_text}
            for v in versions
        ],
    }

@router.post("/{report_id}/approve")
async def approve_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    """Approves a report in the Approval Queue."""
    report = _get_owned_report(db, user, report_id)
    approval = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.report_id == report.id)
        .order_by(ApprovalRequest.created_at.desc())
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="No pending approval request for this report")

    approval.status = "approved"
    approval.approver_id = user.id
    report.status = "approved"
    db.add_all([approval, report])
    db.commit()

    return {"message": "Report approved"}

@router.post("/{report_id}/reject")
async def reject_report(
    report_id: UUID,
    reason: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    """Rejects a report and sends it back for revision."""
    report = _get_owned_report(db, user, report_id)
    approval = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.report_id == report.id)
        .order_by(ApprovalRequest.created_at.desc())
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="No pending approval request for this report")

    approval.status = "rejected"
    approval.approver_id = user.id
    approval.comments = reason
    report.status = "rejected"
    db.add_all([approval, report])
    db.commit()

    return {"message": "Report rejected"}

@router.post("/{report_id}/comment")
async def comment_report(
    report_id: UUID,
    comment: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Client"]))
):
    """Add a comment to a specific report."""
    report = _get_owned_report(db, user, report_id)
    db.add(ReportComment(report_id=report.id, user_id=user.id, comment=comment))
    db.commit()
    return {"message": "Comment added"}

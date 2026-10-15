from uuid import UUID
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.database.session import get_db
from api.core.security import require_role, require_client_access, assert_client_access
from api.models.user import User
from api.models.content import Content, ContentVersion, ContentComment, ContentApprovalRequest
from api.models.knowledge import AuditLog
from api.core.tasks import process_content_generation

router = APIRouter(prefix="/content", tags=["Content"])


def _get_owned_content(db: Session, user: User, content_id: UUID) -> Content:
    content = db.query(Content).filter(Content.id == content_id, Content.is_deleted == False).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    assert_client_access(db, user, content.client_id)
    return content


@router.post("/generate")
async def generate_content(
    client_id: UUID,
    content_type: str,
    target_audience: str,
    goal: str,
    content_id: Optional[UUID] = None,
    title: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Content Writer"]))
):
    """
    Dispatches the real ContentAgent as a Celery background job (knowledge retrieval ->
    Intelligence Layer -> LLM -> brand voice validation -> quality scoring -> persist ->
    approval queue). Returns immediately with a Celery task ID for status polling.
    """
    assert_client_access(db, user, client_id)
    if content_id:
        _get_owned_content(db, user, content_id)  # verify ownership before queuing a version

    try:
        task = process_content_generation.delay(
            str(client_id), content_type, target_audience, goal,
            str(content_id) if content_id else None, title,
        )
    except Exception as exc:
        # See api/routers/reports.py's identical branch for why this exists -
        # CELERY_EAGER dev mode propagates the task's exception right here.
        db.add(AuditLog(client_id=client_id, document_id=None, action="ContentGenerationQueued",
                         pipeline_stage="queued", execution_time_ms=None, status="failed", errors=str(exc)))
        db.commit()
        return {"message": "Content generation failed", "client_id": client_id, "status": "failed", "error": str(exc)}

    db.add(AuditLog(client_id=client_id, document_id=None, action="ContentGenerationQueued",
                     pipeline_stage="queued", execution_time_ms=None, status="success", errors=None))
    db.commit()

    response = {"message": "Content generation started", "client_id": client_id, "task_id": task.id, "status": "processing"}
    if task.ready():
        response["status"] = "completed" if task.successful() else "failed"
        response["result"] = task.result if task.successful() else str(task.result)
    return response

@router.get("")
async def list_content(
    client_id: UUID,
    content_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_client_access("client_id")),
):
    """Search and List Content Library"""
    query = db.query(Content).filter(Content.client_id == client_id, Content.is_deleted == False)
    if content_type:
        query = query.filter(Content.content_type == content_type)
    if status:
        query = query.filter(Content.status == status)
    items = query.order_by(Content.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "content": [
            {"id": c.id, "title": c.title, "content_type": c.content_type,
             "status": c.status, "scheduled_date": c.scheduled_date, "created_at": c.created_at}
            for c in items
        ]
    }

@router.get("/calendar")
async def get_content_calendar(
    client_id: UUID,
    month: int,
    year: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_client_access("client_id")),
):
    """Retrieve scheduled content for the calendar view."""
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    items = (
        db.query(Content)
        .filter(
            Content.client_id == client_id,
            Content.is_deleted == False,
            Content.scheduled_date >= start,
            Content.scheduled_date < end,
        )
        .order_by(Content.scheduled_date.asc())
        .all()
    )
    return {
        "calendar": [
            {"id": c.id, "title": c.title, "content_type": c.content_type,
             "status": c.status, "scheduled_date": c.scheduled_date}
            for c in items
        ]
    }

@router.get("/history")
async def get_content_history(
    client_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_client_access("client_id")),
):
    """Get the audit history of content generation.
    NOTE: registered before /{content_id} - a literal path must come before a dynamic
    UUID path segment or FastAPI will try (and fail) to parse "history" as a content_id."""
    entries = (
        db.query(AuditLog)
        .filter(AuditLog.client_id == client_id, AuditLog.action.ilike("Content%"))
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

@router.get("/{content_id}")
async def get_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Client", "Content Writer"]))
):
    """Retrieve specific content and its versions."""
    content = _get_owned_content(db, user, content_id)
    versions = (
        db.query(ContentVersion)
        .filter(ContentVersion.content_id == content.id)
        .order_by(ContentVersion.version.desc())
        .all()
    )
    latest = versions[0] if versions else None
    return {
        "content_id": content.id,
        "title": content.title,
        "content_type": content.content_type,
        "status": content.status,
        "body": latest.body if latest else "",
        "versions": [{"version": v.version, "body": v.body} for v in versions],
        "scheduled_date": content.scheduled_date,
    }

@router.put("/{content_id}")
async def update_content(
    content_id: UUID,
    body: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Content Writer"]))
):
    """Edit content (creates a new, human-authored ContentVersion)."""
    content = _get_owned_content(db, user, content_id)
    next_version_number = (
        db.query(ContentVersion).filter(ContentVersion.content_id == content.id).count()
    ) + 1
    version = ContentVersion(content_id=content.id, version=next_version_number, body=body, author_id=user.id)
    db.add(version)
    content.status = "pending_review"
    db.add(content)
    db.commit()
    return {"message": "Content updated", "version": next_version_number}

@router.post("/{content_id}/schedule")
async def schedule_content(
    content_id: UUID,
    scheduled_date: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    """Sets (or clears, if scheduled_date is omitted) the calendar date content is
    planned to go out on. Deliberately separate from update_content: scheduling
    shouldn't create a new ContentVersion or reset status back to pending_review -
    it's calendar metadata on already-approved (or in-flight) content, not an edit."""
    content = _get_owned_content(db, user, content_id)
    if scheduled_date:
        try:
            content.scheduled_date = datetime.fromisoformat(scheduled_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="scheduled_date must be an ISO 8601 date/datetime string.")
    else:
        content.scheduled_date = None
    db.add(content)
    db.commit()
    return {"message": "Schedule updated", "scheduled_date": content.scheduled_date}

@router.delete("/{content_id}")
async def delete_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    """Archive content."""
    content = _get_owned_content(db, user, content_id)
    content.status = "archived"
    content.is_deleted = True
    db.add(content)
    db.commit()
    return {"message": "Content archived"}

@router.post("/{content_id}/approve")
async def approve_content(
    content_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    """Approves content in the Approval Queue."""
    content = _get_owned_content(db, user, content_id)
    approval = (
        db.query(ContentApprovalRequest)
        .filter(ContentApprovalRequest.content_id == content.id)
        .order_by(ContentApprovalRequest.created_at.desc())
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="No pending approval request for this content")

    approval.status = "approved"
    approval.approver_id = user.id
    content.status = "approved"
    db.add_all([approval, content])
    db.commit()
    return {"message": "Content approved"}

@router.post("/{content_id}/reject")
async def reject_content(
    content_id: UUID,
    reason: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    """Rejects content and sends it back for revision."""
    content = _get_owned_content(db, user, content_id)
    approval = (
        db.query(ContentApprovalRequest)
        .filter(ContentApprovalRequest.content_id == content.id)
        .order_by(ContentApprovalRequest.created_at.desc())
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="No pending approval request for this content")

    approval.status = "rejected"
    approval.approver_id = user.id
    approval.comments = reason
    content.status = "needs_changes"
    db.add_all([approval, content])
    db.commit()
    return {"message": "Content rejected"}

@router.post("/{content_id}/comment")
async def comment_content(
    content_id: UUID,
    comment: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(["Admin", "Marketing Manager", "Client", "Content Writer"]))
):
    """Add an editorial comment to a specific content version (defaults to the latest)."""
    content = _get_owned_content(db, user, content_id)
    latest_version = (
        db.query(ContentVersion)
        .filter(ContentVersion.content_id == content.id)
        .order_by(ContentVersion.version.desc())
        .first()
    )
    if not latest_version:
        raise HTTPException(status_code=400, detail="Content has no versions to comment on yet.")

    db.add(ContentComment(version_id=latest_version.id, user_id=user.id, comment=comment))
    db.commit()
    return {"message": "Comment added"}

from fastapi import APIRouter, Depends
from api.core.celery_app import celery_app
from api.core.security import get_current_db_user
from api.models.user import User

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# Celery task states, per Celery's own state machine - surfaced as-is rather than
# remapped, so the frontend's polling logic matches real Celery semantics whether a
# task ran against a real worker or synchronously in CELERY_EAGER dev mode.
_TERMINAL_STATES = {"SUCCESS", "FAILURE"}


@router.get("/{task_id}")
async def get_job_status(task_id: str, user: User = Depends(get_current_db_user)):
    """
    Polls a Celery task's status by ID - the same task_id returned by
    /reports/generate and /content/generate. Works identically whether the task ran
    against a real worker or synchronously (CELERY_EAGER=true dev mode), since both
    paths populate the same AsyncResult backend.

    Not tenant-scoped by client_id (a task_id is an unguessable UUID, not a resource
    identifier a caller could enumerate) - the caller must already be an authenticated
    user, which is enforced above.
    """
    result = celery_app.AsyncResult(task_id)
    response = {
        "task_id": task_id,
        "status": result.status,
        "done": result.status in _TERMINAL_STATES,
    }
    if result.status == "SUCCESS":
        response["result"] = result.result
    elif result.status == "FAILURE":
        response["error"] = str(result.result) if result.result else "Task failed"
    return response

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.database.session import get_db
from api.models.integrations import Integration, IntegrationSync
from api.core.tasks import sync_integration_data
from api.core.connectors.factory import get_connector
from api.core.security import require_role, assert_client_access
from api.models.user import User

router = APIRouter()

VIEW_ROLES = ["Admin", "Marketing Manager", "Analyst", "Client"]
MANAGE_ROLES = ["Admin", "Marketing Manager"]


@router.get("/")
def list_integrations(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(VIEW_ROLES)),
):
    assert_client_access(db, current_user, client_id)
    integrations = db.query(Integration).filter(Integration.client_id == client_id).all()
    return {"integrations": integrations}

@router.post("/{provider}/connect")
def connect_integration(
    provider: str,
    client_id: UUID,
    auth_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(MANAGE_ROLES)),
):
    """Handles OAuth callback logic by passing auth_code to the connector."""
    assert_client_access(db, current_user, client_id)
    # Ensure integration record exists
    integration = db.query(Integration).filter(
        Integration.client_id == client_id,
        Integration.provider == provider
    ).first()

    if not integration:
        integration = Integration(client_id=client_id, provider=provider, status="pending")
        db.add(integration)
        db.commit()
        db.refresh(integration)

    connector = get_connector(provider, client_id, integration.id, db)
    result = connector.authenticate(auth_code)

    if result.get("status") == "success":
        integration.status = "connected"
        db.commit()

    return result

@router.post("/{integration_id}/sync")
def trigger_sync(
    integration_id: UUID,
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(MANAGE_ROLES)),
):
    """Triggers manual background sync."""
    assert_client_access(db, current_user, client_id)
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.client_id == client_id
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    # Celery tasks receive plain str args (JSON-serialized) - see api/core/tasks.py.
    sync_integration_data.delay(str(client_id), str(integration.id))

    return {"status": "sync_started", "integration_id": str(integration_id)}

@router.get("/{integration_id}/status")
def get_sync_status(
    integration_id: UUID,
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(VIEW_ROLES)),
):
    """Gets the latest sync status."""
    assert_client_access(db, current_user, client_id)
    latest_sync = db.query(IntegrationSync).filter(
        IntegrationSync.integration_id == integration_id,
        IntegrationSync.client_id == client_id
    ).order_by(IntegrationSync.started_at.desc()).first()

    return {"latest_sync": latest_sync}

@router.delete("/{integration_id}/disconnect")
def disconnect_integration(
    integration_id: UUID,
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(MANAGE_ROLES)),
):
    """Disconnects and revokes tokens."""
    assert_client_access(db, current_user, client_id)
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.client_id == client_id
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    connector = get_connector(integration.provider, client_id, integration.id, db)
    connector.disconnect()

    integration.status = "disconnected"
    db.commit()

    return {"status": "disconnected"}

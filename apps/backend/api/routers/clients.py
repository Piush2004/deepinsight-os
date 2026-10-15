from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from api.database.session import get_db
from api.schemas.client import ClientCreate, ClientUpdate, ClientResponse
from api.services.client_service import ClientService
from api.core.security import require_role, assert_client_access
from api.models.user import User

router = APIRouter()

@router.get("/", response_model=List[ClientResponse])
def get_clients(
    skip: int = 0,
    limit: int = 100,
    q: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Marketing Manager", "Analyst"]))
):
    if q:
        return ClientService.search_clients(db, current_user, query=q, skip=skip, limit=limit)
    return ClientService.get_clients(db, current_user, skip=skip, limit=limit)

@router.post("/", response_model=ClientResponse)
def create_client(
    client_in: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    return ClientService.create_client(db, client_in, creator=current_user)

@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Marketing Manager", "Analyst", "Client"]))
):
    assert_client_access(db, current_user, client_id)
    client = ClientService.get_client(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: str,
    client_in: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Marketing Manager"]))
):
    assert_client_access(db, current_user, client_id)
    client = ClientService.update_client(db, client_id, client_in)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.delete("/{client_id}", response_model=ClientResponse)
def delete_client(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin"]))
):
    # Admin-only, and Admins already bypass assert_client_access - no extra call needed.
    client = ClientService.delete_client(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

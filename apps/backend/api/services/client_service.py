from sqlalchemy.orm import Session
from api.repositories.client_repository import client_repository
from api.schemas.client import ClientCreate, ClientUpdate
from api.models.membership import ClientMembership
from api.models.user import User
from api.core.security import ADMIN_ROLE
from typing import Any

class ClientService:
    @staticmethod
    def get_client(db: Session, client_id: Any):
        return client_repository.get(db, id=client_id)

    @staticmethod
    def get_clients(db: Session, user: User, skip: int = 0, limit: int = 100):
        if user.role == ADMIN_ROLE:
            return client_repository.get_multi(db, skip=skip, limit=limit)
        return client_repository.get_multi_for_user(db, user_id=user.id, skip=skip, limit=limit)

    @staticmethod
    def search_clients(db: Session, user: User, query: str, skip: int = 0, limit: int = 100):
        if user.role == ADMIN_ROLE:
            return client_repository.search(db, query=query, skip=skip, limit=limit)
        return client_repository.search_for_user(db, user_id=user.id, query=query, skip=skip, limit=limit)

    @staticmethod
    def create_client(db: Session, client_in: ClientCreate, creator: User):
        client = client_repository.create(db, obj_in=client_in)
        if creator.role != ADMIN_ROLE:
            db.add(ClientMembership(user_id=creator.id, client_id=client.id))
            db.commit()
        return client

    @staticmethod
    def update_client(db: Session, client_id: Any, client_in: ClientUpdate):
        db_client = client_repository.get(db, id=client_id)
        if not db_client:
            return None
        return client_repository.update(db, db_obj=db_client, obj_in=client_in)

    @staticmethod
    def delete_client(db: Session, client_id: Any):
        db_client = client_repository.get(db, id=client_id)
        if not db_client:
            return None
        return client_repository.remove(db, id=client_id)

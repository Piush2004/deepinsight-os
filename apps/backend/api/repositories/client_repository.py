from api.repositories.base import BaseRepository
from api.models.client import Client
from api.models.membership import ClientMembership
from api.schemas.client import ClientCreate, ClientUpdate
from sqlalchemy.orm import Session

class ClientRepository(BaseRepository[Client, ClientCreate, ClientUpdate]):
    def search(self, db: Session, query: str, skip: int = 0, limit: int = 100):
        return db.query(self.model).filter(
            self.model.is_deleted == False,
            self.model.name.ilike(f"%{query}%")
        ).offset(skip).limit(limit).all()

    def get_multi_for_user(self, db: Session, user_id, skip: int = 0, limit: int = 100):
        """Clients the given user has an explicit ClientMembership for."""
        return (
            db.query(self.model)
            .join(ClientMembership, ClientMembership.client_id == self.model.id)
            .filter(self.model.is_deleted == False, ClientMembership.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def search_for_user(self, db: Session, user_id, query: str, skip: int = 0, limit: int = 100):
        return (
            db.query(self.model)
            .join(ClientMembership, ClientMembership.client_id == self.model.id)
            .filter(
                self.model.is_deleted == False,
                ClientMembership.user_id == user_id,
                self.model.name.ilike(f"%{query}%"),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

client_repository = ClientRepository(Client)

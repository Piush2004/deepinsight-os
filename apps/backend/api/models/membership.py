from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from api.models.base import BaseModel


class ClientMembership(BaseModel):
    """Grants a User access to a Client's data. Admin users bypass this table entirely
    (see api.core.security.user_has_client_access) and are authorized for every client."""
    __tablename__ = "client_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "client_id", name="uq_client_membership_user_client"),
    )

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)

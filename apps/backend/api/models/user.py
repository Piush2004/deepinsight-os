from sqlalchemy import Column, String
from api.models.base import BaseModel

class User(BaseModel):
    __tablename__ = "users"
    
    clerk_id = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, default="Marketing Manager", nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)

from sqlalchemy import Column, String, Text
from api.models.base import BaseModel

class Client(BaseModel):
    __tablename__ = "clients"
    
    name = Column(String, index=True, nullable=False)
    industry = Column(String, nullable=True)
    website = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="active", nullable=False) # active, archived


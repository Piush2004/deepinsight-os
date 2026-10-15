from pydantic import BaseModel, UUID4, ConfigDict
from typing import Optional
from datetime import datetime

class ClientBase(BaseModel):
    name: str
    industry: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = "active"

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class ClientResponse(ClientBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    
    model_config = ConfigDict(from_attributes=True)

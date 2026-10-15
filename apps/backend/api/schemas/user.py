from pydantic import BaseModel, UUID4, ConfigDict
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    clerk_id: str
    email: str
    role: Optional[str] = "Marketing Manager"
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    
    model_config = ConfigDict(from_attributes=True)

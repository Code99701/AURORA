from pydantic import BaseModel, ConfigDict, EmailStr, Field
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    display_name: str = Field(..., min_length=1, max_length=100)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    system_role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

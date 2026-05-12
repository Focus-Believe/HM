from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_online: bool = False
    last_seen: Optional[datetime] = None

class Message(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    message: str
    is_read: bool = False
    created_at: datetime

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    members: List[str] = []

class GroupMessage(BaseModel):
    group_id: int
    message: str

class CallInitiate(BaseModel):
    receiver_name: str
    call_type: str  # voice or video

class StoryCreate(BaseModel):
    media_url: str
    media_type: str  # image or video
    caption: Optional[str] = None

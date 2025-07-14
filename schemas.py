from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from fastapi_users import schemas
import uuid

# class UserResponse(BaseModel):
#     id: int
#     username: str
#     email: str
#     created_at: datetime

class UserRead(schemas.BaseUser[int]):
    username: str
    created_at: datetime

class UserCreate(schemas.BaseUserCreate):
    username: str
    # email: str
    # password: str

class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[str] = None

class QuestionCreate(BaseModel):
    title: str
    content: str

class AnswerCreate(BaseModel):
    content: str
    question_id: int

class QuestionResponse(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime
    author: UserRead
    answers: List["AnswerResponse"] = []

class AnswerResponse(BaseModel):
    id: int
    content: str
    created_at: datetime
    votes: int
    author: UserRead

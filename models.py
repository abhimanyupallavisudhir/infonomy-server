from sqlmodel import SQLModel, Field, Relationship
# from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlmodel import SQLModelBaseUserDB
from typing import Optional, List
from pydantic import ConfigDict
import datetime

class User(SQLModelBaseUserDB, table=True):

    # <-- tell Pydantic to allow SQLAlchemy Mapped[...] types
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # override the id field to be int instead of UUID
    id: int = Field(default=None, primary_key=True)

    # id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    # email: str = Field(unique=True, index=True)
    # hashed_password: str
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    # Relationships
    questions: List["Question"] = Relationship(back_populates="author")
    answers: List["Answer"] = Relationship(back_populates="author")

class Question(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    # Foreign key
    author_id: Optional[int] = Field(default=None, foreign_key="user.id")

    # Relationships
    author: "User" = Relationship(back_populates="questions")
    answers: List["Answer"] = Relationship(back_populates="question")

class Answer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    votes: int = Field(default=0)

    # Foreign keys
    author_id: Optional[int] = Field(default=None, foreign_key="user.id")
    question_id: Optional[int] = Field(default=None, foreign_key="question.id")

    # Relationships
    author: "User" = Relationship(back_populates="answers")
    question: "Question" = Relationship(back_populates="answers")
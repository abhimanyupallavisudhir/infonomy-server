from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from fastapi_users import schemas
from sqlmodel import SQLModel, Field
import uuid
from models import LLMBuyerType

class UserRead(schemas.BaseUser[int]):
    username: str
    created_at: datetime

class UserCreate(schemas.BaseUserCreate):
    username: str
    # email: str
    # password: str

class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[str] = None

class HumanBuyerRead(SQLModel):
    user_id: int
    default_child_llm: LLMBuyerType
    default_max_budget: float
    num_queries: dict[int, int]
    num_inspected: dict[int, int]
    num_purchased: dict[int, int]
    inspection_rate: dict[int, float]
    purchase_rate: dict[int, float]

    class Config:
        orm_mode = True

class HumanBuyerCreate(SQLModel):
    default_child_llm:  LLMBuyerType
    default_max_budget: float

class HumanBuyerUpdate(SQLModel):
    default_child_llm:    Optional[LLMBuyerType] = None
    default_max_budget:   Optional[float]         = None

class SellerMatcherRead(SQLModel):
    id:                 int
    seller_id:          int
    keywords:           Optional[List[str]]
    context_pages:      Optional[List[str]]
    min_max_budget:     float
    min_inspection_rate: float
    min_purchase_rate:   float
    min_priority:        int
    buyer_type:          Optional[str]
    buyer_llm_model:     Optional[List[str]]
    buyer_system_prompt: Optional[List[str]]
    age_limit:           Optional[int]

    class Config:
        orm_mode = True

class SellerMatcherCreate(SQLModel):
    seller_id:          int
    keywords:           Optional[List[str]] = None
    context_pages:      Optional[List[str]] = None
    min_max_budget:     float
    min_inspection_rate: float
    min_purchase_rate:   float
    min_priority:        int
    buyer_type:          Optional[str] = None
    buyer_llm_model:     Optional[List[str]] = None
    buyer_system_prompt: Optional[List[str]] = None
    age_limit:           Optional[int] = None

class SellerMatcherUpdate(SQLModel):
    keywords:           Optional[List[str]] = None
    context_pages:      Optional[List[str]] = None
    min_max_budget:     Optional[float] = None
    min_inspection_rate: Optional[float] = None
    min_purchase_rate:   Optional[float] = None
    min_priority:        Optional[int] = None
    buyer_type:          Optional[str] = None
    buyer_llm_model:     Optional[List[str]] = None
    buyer_system_prompt: Optional[List[str]] = None
    age_limit:           Optional[int] = None

class SellerRead(SQLModel):
    id: int
    type: str
    matchers: List[SellerMatcherRead]

    class Config:
        orm_mode = True

# class SellerCreate(SQLModel):
#     # type: str # this will automatically be set depending on the endpoint used
#     matchers: List[SellerMatcherCreate]

# class SellerUpdate(SQLModel):
#     # type: Optional[str] = None # this will automatically be set depending on the endpoint used
#     matchers: Optional[List[SellerMatcherUpdate]] = None

class HumanSellerRead(SellerRead):
    user_id: int


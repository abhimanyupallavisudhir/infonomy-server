from datetime import datetime
from typing import Optional, List
from fastapi_users import schemas
from sqlmodel import SQLModel, Field
from infonomy_server.models import LLMBuyerType

class UserRead(schemas.BaseUser[int]):
    username: str
    created_at: datetime
    last_login_date: Optional[datetime]
    balance: float
    available_balance: float
    daily_bonus_amount: float
    purchased_info_offers: List[int]
    buyer_profile: Optional["HumanBuyerRead"]
    seller_profile: Optional["HumanSellerRead"]
    bot_sellers: Optional[List["BotSellerRead"]]

class UserReadPrivate(UserRead):
    api_keys: dict

class UserCreate(schemas.BaseUserCreate):
    username: str
    # email: str
    # password: str

class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[str] = None
    api_keys: Optional[dict] = None

class HumanBuyerRead(SQLModel):
    id: int
    default_child_llm: LLMBuyerType
    num_queries: dict[int, int]
    num_inspected: dict[int, int]
    num_purchased: dict[int, int]
    inspection_rate: dict[int, float]
    purchase_rate: dict[int, float]

    class Config:
        orm_mode = True

class HumanBuyerCreate(SQLModel):
    default_child_llm:  LLMBuyerType = LLMBuyerType()

class HumanBuyerUpdate(SQLModel):
    default_child_llm:    Optional[LLMBuyerType] = None

class SellerMatcherRead(SQLModel):
    id:                 int
    human_seller_id:    Optional[int]
    bot_seller_id:      Optional[int]
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
    keywords:           Optional[List[str]] = None
    context_pages:      Optional[List[str]] = None
    min_max_budget:     float = 0.0
    min_inspection_rate: float = 0.0
    min_purchase_rate:   float = 0.0
    min_priority:        int = 0
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
    matchers: List[SellerMatcherRead]
    type: str

    class Config:
        orm_mode = True

# none of these need models -- seller accounts can be created without any info, and then matchers can be added later

# class SellerCreate(SQLModel):
#     # type: str # this will automatically be set depending on the endpoint used
#     matchers: List[SellerMatcherCreate]

# class SellerUpdate(SQLModel):
#     # type: Optional[str] = None # this will automatically be set depending on the endpoint used
#     matchers: Optional[List[SellerMatcherUpdate]] = None

class HumanSellerRead(SQLModel):
    id: int
    matchers: List[SellerMatcherRead]
    info_offers: List["InfoOfferReadPublic"]

    class Config:
        orm_mode = True

# class HumanSellerCreate(SellerCreate):
#     pass

# class HumanSellerUpdate(SellerUpdate):
#     pass

# private to creating seller only!
class BotSellerRead(SellerRead):
    id: int
    user_id: int
    info: Optional[str]
    price: Optional[float]
    llm_model: Optional[str]
    llm_prompt: Optional[str]


# subclass SQLModel because we don't have a SellerCreate or SellerUpdate model
class BotSellerCreate(SQLModel):
    info: Optional[str] = None
    price: Optional[float] = None
    llm_model: Optional[str] = None
    llm_prompt: Optional[str] = None

class BotSellerUpdate(SQLModel):
    info: Optional[str] = None
    price: Optional[float] = None
    llm_model: Optional[str] = None
    llm_prompt: Optional[str] = None

class DecisionContextRead(SQLModel):
    id: int
    query: Optional[str]
    context_pages: Optional[List[str]]
    buyer_id: int
    max_budget: float
    human_seller_ids: Optional[List[int]]
    bot_seller_ids: Optional[List[int]]
    priority: int
    created_at: datetime
    # # for recursive
    # children: Optional[List["DecisionContextRead"]]
    parent: Optional["DecisionContextRead"]
    # info_offers_being_inspected: Optional[List["InfoOfferReadPrivate"]]
    # info_offers_already_purchased: Optional[List["InfoOfferReadPrivate"]]

    class Config:
        orm_mode = True

class DecisionContextCreateNonRecursive(SQLModel):
    query: Optional[str] = None
    context_pages: Optional[List[str]] = None
    max_budget: float
    human_seller_ids: Optional[List[int]] = None
    bot_seller_ids: Optional[List[int]] = None
    priority: int = 0

class DecisionContextUpdateNonRecursive(SQLModel):
    query: Optional[str] = None
    context_pages: Optional[List[str]] = None
    max_budget: Optional[float] = None
    human_seller_ids: Optional[List[int]] = None
    bot_seller_ids: Optional[List[int]] = None
    priority: Optional[int] = None

class InfoOfferReadPublic(SQLModel):
    id: int
    human_seller_id: Optional[int]
    bot_seller_id: Optional[int]
    seller_type: str
    context_id: int
    public_info: Optional[str]
    price: float
    created_at: datetime

    class Config:
        orm_mode = True

class InfoOfferReadPrivate(InfoOfferReadPublic):
    private_info: str
    
class InfoOfferCreate(SQLModel):
    private_info: str
    public_info: Optional[str] = None
    price: float = 0.0

class InfoOfferUpdate(SQLModel):
    private_info: Optional[str] = None
    public_info: Optional[str] = None
    price: Optional[float] = None

class InspectionRead(SQLModel):
    id: int
    decision_context_id: int
    buyer_id: int
    child_context_id: Optional[int]
    purchased: List[int]
    job_id: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True

class InspectionCreate(SQLModel):
    decision_context_id: int
    info_offer_ids: List[int] = Field(description="List of InfoOffer IDs to inspect")

class InspectionUpdate(SQLModel):
    purchased: Optional[List[int]] = None

DecisionContextRead.update_forward_refs()
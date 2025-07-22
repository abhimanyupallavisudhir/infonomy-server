from __future__ import annotations
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON, String, CheckConstraint #, Computed, Float, case

# from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlmodel import SQLModelBaseUserDB
from typing import Optional, List, Literal
from pydantic import ConfigDict, BaseModel, model_validator
import datetime

class User(SQLModelBaseUserDB, table=True):
    # <-- tell Pydantic to allow SQLAlchemy Mapped[...] types
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # override the id field to be int instead of UUID
    id: int = Field(default=None, primary_key=True)

    username: str = Field(unique=True, index=True)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    balance: float = Field(default=0.0)

    # Relationships
    buyer_profile: Optional["HumanBuyer"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"uselist": False}
    )
    seller_profile: Optional["HumanSeller"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"uselist": False}
    )
    bot_sellers: List["BotSeller"] = Relationship(back_populates="user")


class LLMBuyerType(BaseModel):
    # an AI agent, which can be instantiated into specific LLMBuyers
    name: Optional[str] = "gpt-4o_basic"
    description: Optional[str] = "basic GPT-4o LLM buyer"
    querier_model: str = "openrouter/openai/chatgpt-4o-latest"
    querier_system_prompt: str = "You are a helpful assistant."
    decider_model: str = "openrouter/openai/chatgpt-4o-latest"
    decider_system_prompt: str = "You are a helpful assistant."
    max_budget: float = 50.0

# class LLMContext(BaseModel):
#     history: list["DecisionContext"] = []
#     info_offers_being_inspected: list["InfoOffer"] = []
#     info_offers_already_purchased: list["InfoOffer"] = []

# class Buyer(SQLModel, table=True):
#     __tablename__ = "buyer"
#     id: Optional[int] = Field(default=None, primary_key=True)
#     type: str = Field(
#         sa_column=Column(String, nullable=False),
#         index=True,
#         description="Type of buyer ('human_buyer' or 'llm_buyer')",
#     )

#     # polymorphic config
#     __mapper_args__ = {
#         "polymorphic_identity": "buyer",
#         "polymorphic_on": type,
#     }

#     # Relationships
#     decision_contexts: List["DecisionContext"] = Relationship(
#         back_populates="buyer", sa_relationship_kwargs={"lazy": "selectin"}
#     )


class HumanBuyer(SQLModel, table=True):
    # __tablename__ = "human_buyer"

    # id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", primary_key=True)

    # Settings/defaults
    default_child_llm: LLMBuyerType = Field(
        default_factory=LLMBuyerType, sa_column=Column(JSON, nullable=False)
    )
    default_max_budget: float = Field(default=50.0)
    # autoinspect: bool = Field(default=True)
    # autoinspect_n: int = Field(default=3)

    # Collectable data
    num_queries: dict[int, int] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Number of queries made by the buyer, by priority",
    )  # maps priority to number of queries with that priority
    num_inspected: dict[int, int] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Number of queries where an inspection was done by the buyer, by priority",
    )
    num_purchased: dict[int, int] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Number of queries where a purchase was made by the buyer, by priority",
    )
    @property
    def inspection_rate(self) -> dict[int, float]:
        rates: dict[int, float] = {}
        for prio, qcount in self.num_queries.items():
            inspected = self.num_inspected.get(prio, 0)
            rates[prio] = inspected / qcount if qcount else 0.0
        return rates

    @property
    def purchase_rate(self) -> dict[int, float]:
        rates: dict[int, float] = {}
        for prio, qcount in self.num_queries.items():
            purchased = self.num_purchased.get(prio, 0)
            rates[prio] = purchased / qcount if qcount else 0.0
        return rates
    # inspection_rate: dict[int, float] = Field(
    #     sa_column=Column(
    #         Float,
    #         Computed(
    #             case(
    #                 (Column("num_queries") == 0, 0.0),
    #                 else_=Column("num_inspected") / Column("num_queries"),
    #             )
    #         ),
    #         nullable=False,
    #         default=0.0,
    #     ),
    #     description="Inspection rate for queries of each priority",
    # )
    # purchase_rate: dict[int, float] = Field(
    #     sa_column=Column(
    #         Float,
    #         Computed(
    #             case(
    #                 (Column("num_queries") == 0, 0.0),
    #                 else_=Column("num_purchased") / Column("num_queries"),
    #             )
    #         ),
    #         nullable=False,
    #         default=0.0,
    #     ),
    #     description="Purchase rate for queries of each priority",
    # )

    # Relationships
    user: User = Relationship(back_populates="buyer_profile")
    decision_contexts: List["DecisionContext"] = Relationship(back_populates="buyer")


# class LLMBuyer(Buyer, table=True):
#     __tablename__ = "llm_buyer"
#     id: Optional[int] = Field(foreign_key="buyer.id", primary_key=True)
#     llm: LLMBuyerType = Field(
#         default_factory=LLMBuyerType, sa_column=Column(JSON, nullable=False)
#     )
#     # polymorphic config
#     __mapper_args__ = {"polymorphic_identity": "llm_buyer"}


class Seller(SQLModel, table=True):
    __tablename__ = "seller"
    id: int = Field(primary_key=True)
    type: str = Field(
        sa_column=Column(String, nullable=False),
        index=True,
        description="Type of seller ('human_seller' or 'bot_seller')",
    )

    # polymorphic config
    __mapper_args__ = {
        "polymorphic_identity": "seller",
        "polymorphic_on": type,
    }

    # Relationships
    matchers: List["SellerMatcher"] = Relationship(back_populates="seller")
    info_offers: List["InfoOffer"] = Relationship(back_populates="seller")


class HumanSeller(Seller, table=True):
    __tablename__ = "human_seller"

    id: int = Field(foreign_key="seller.id", primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    __mapper_args__ = {
        "polymorphic_identity": "human_seller",
    }

    # Relationships
    user: User = Relationship(back_populates="seller_profile")

class BotSeller(Seller, table=True):
    __tablename__ = "bot_seller"
    __table_args__ = (
        CheckConstraint(
            "info IS NOT NULL OR (llm_model IS NOT NULL AND llm_prompt IS NOT NULL)",
            name="ck_bot_seller_info_or_llm"
        ),
    )
    id: int = Field(foreign_key="seller.id", primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    __mapper_args__ = {
        "polymorphic_identity": "bot_seller",
    }

    info: Optional[str] = Field(
        sa_column=Column(String, nullable=True),
        description="For bots that just regurgitate a piece of info"
    )

    llm_model: Optional[str] = Field(
        sa_column=Column(String, nullable=True),
        description="For bots that use an LLM to generate responses"
    )
    llm_prompt: Optional[str] = Field(
        sa_column=Column(String, nullable=True),
        description="For bots that use an LLM to generate responses"
    )

    # Relationships
    user: User = Relationship(back_populates="bot_sellers")

    # ensure Pydantic actually runs validators on assignment + init
    model_config = ConfigDict(validate_default=True, validate_assignment=True)

    @model_validator(mode="before")
    def check_info_or_llm(cls, values: dict):
        info = values.get("info")
        model = values.get("llm_model")
        prompt = values.get("llm_prompt")
        if info is None and not (model and prompt):
            raise ValueError(
                "Must set either `info` or both `llm_model` and `llm_prompt`."
            )
        return values

class SellerMatcher(SQLModel, table=True):
    id: int = Field(primary_key=True)
    seller_id: int = Field(foreign_key="seller.user_id", index=True)
    keywords: Optional[List[str]] = Field(
        sa_column=Column(JSON, index=True), default=None, description="Keywords to look out for: None to get everything"
    )
    context_pages: Optional[List[str]] = Field(
        sa_column=Column(JSON, index=True), default=None, description="Context pages to consider: None to get everything"
    )
    min_max_budget: float = Field(default=0.0, index=True, description="Minimum max_budget the buyer should have")
    min_inspection_rate: float = Field(default=0.0, index=True, description="Minimum inspection rate the buyer should have for that priority of query")
    min_purchase_rate: float = Field(default=0.0, index=True, description="Minimum purchase rate the buyer should have for that priority of query")
    min_priority: int = Field(default=0, index=True, description="Minimum priority query to match")
    buyer_type: Optional[str] = Field(
        sa_column=Column(String, nullable=False),
        index=True,
        description="Type of buyer ('human_buyer' or 'llm_buyer'); None to match both",
        default=None,
    )
    buyer_llm_model: Optional[List[str]] = Field(
        sa_column=Column(JSON, index=True), default=None, description="Decider models to match; None to match all models"
    )
    buyer_system_prompt: Optional[List[str]] = Field(
        sa_column=Column(JSON, index=True), default=None, description="Keywords in Decider system prompts to match; None to get everything"
    )
    age_limit: Optional[int] = Field(
        default=60 * 60 * 24 * 7,  # 1 week
        description="Maximum age of a decision context in seconds to be considered for matching; None to get everything",
        index=True,
    )

    # Relationships
    seller: Seller = Relationship(back_populates="matchers")
    inbox_items: List["MatcherInbox"] = Relationship(back_populates="matcher", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

class DecisionContext(SQLModel, table=True):
    id: int = Field(primary_key=True)
    query: Optional[str] = Field(index=True, default=None, description="Custom query for information")
    context_pages: Optional[List[str]] = Field(sa_column=Column(JSON, index=True), default=None, description="Context pages, e.g. https://metaculus.com/...")

    # for recursive decision contexts
    parent_id: Optional[int] = Field(default=None, foreign_key="decisioncontext.id", index=True)
    parent:  Optional[DecisionContext]      = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "DecisionContext.id"}
    )
    children: List[DecisionContext]         = Relationship(back_populates="parent")

    # history: Optional[List["DecisionContext"]] = Field(
    #     sa_column=Column(JSON, index=True),
    #     default=None,
    #     description="History of previous decision contexts",
    # )
    # info_offers_being_inspected: Optional[List["InfoOffer"]] = Field(
    #     sa_column=Column(JSON, index=True),
    #     default=None,
    #     description="Info offers currently being inspected",
    # )
    # info_offers_already_purchased: Optional[List["InfoOffer"]] = Field(
    #     sa_column=Column(JSON, index=True),
    #     default=None,
    #     description="Info offers already purchased in this decision context",
    # )
    buyer_id: int = Field(foreign_key="human_buyer.user_id", index=True)
    max_budget: float = Field(default=0.0, index=True)
    seller_ids: Optional[List[int]] = Field(
        sa_column=Column(JSON, index=True),
        default=None,
        description="Direct query to specific sellers only",
    )
    priority: int = Field(default=0, le=1, ge=0, index=True)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    # Relationships
    buyer: HumanBuyer = Relationship(back_populates="decision_contexts")
    info_offers: List["InfoOffer"] = Relationship(back_populates="context")

    @property
    def info_offers_being_inspected(self) -> list["InfoOffer"]:
        return [offer for offer in self.info_offers if offer.currently_being_inspected]
    
    @property
    def info_offers_already_inspected(self) -> list["InfoOffer"]:
        return [offer for offer in self.info_offers if offer.inspected]

    @property
    def info_offers_already_purchased(self) -> list["InfoOffer"]:
        return [offer for offer in self.info_offers if offer.purchased]


class InfoOffer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    seller_id: int = Field(foreign_key="human_seller.id", index=True)
    context_id: int = Field(foreign_key="decisioncontext.id", index=True)
    private_info: str = Field(
        sa_column=Column(String, nullable=False),
        description="Private information about the offer, not visible except during inspection and after purchase",
    )
    public_info: Optional[str] = Field(
        sa_column=Column(String, nullable=True),
        description="Public information about the offer, retrievable via public API",
    )
    price: float = Field(default=0.0, index=True)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    currently_being_inspected: bool = Field(
        default=False,
        description="Whether the info offer is currently being inspected by a buyer",
    )
    inspected: bool = Field(
        default=False,
        description="Whether the info offer has been inspected by a buyer",
    )
    purchased: bool = Field(
        default=False,
        description="Whether the info offer has been purchased by a buyer",
    )

    # Relationships
    seller: HumanSeller = Relationship(back_populates="info_offers")
    context: DecisionContext = Relationship(back_populates="info_offers")

class MatcherInbox(SQLModel, table=True):
    id: int = Field(primary_key=True)
    matcher_id: int = Field(foreign_key="sellermatcher.id", index=True)
    decision_context_id: int = Field(foreign_key="decisioncontext.id", index=True)
    status: Literal["new", "ignored", "responded"] = Field(
        default="new",
        description="Status of the inbox item",
        index=True,
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    expires_at: datetime = Field(index=True)

    # Relationships
    matcher: SellerMatcher = Relationship(back_populates="inbox_items")
    decision_context: DecisionContext = Relationship()
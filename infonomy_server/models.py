# from __future__ import annotations
from sqlmodel import SQLModel, Field, Relationship, Session, select
from sqlalchemy import Column, JSON, String, CheckConstraint, Table, ForeignKey #, Computed, Float, case
# from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlmodel import SQLModelBaseUserDB
from typing import Optional, List, Literal
from pydantic import ConfigDict, BaseModel, model_validator
import datetime

# Association table for the many-to-many relationship between DecisionContext and InfoOffer
decision_context_parent_offers = Table(
    'decision_context_parent_offers',
    SQLModel.metadata,
    Column('decision_context_id', ForeignKey('decisioncontext.id'), primary_key=True),
    Column('info_offer_id', ForeignKey('infooffer.id'), primary_key=True)
)

class User(SQLModelBaseUserDB, table=True):
    # <-- tell Pydantic to allow SQLAlchemy Mapped[...] types
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    # override the id field to be int instead of UUID
    id: int = Field(default=None, primary_key=True)

    username: str = Field(unique=True, index=True)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    balance: float = Field(default=0.0)
    available_balance: float = Field(default=0.0, description="Available balance for creating DecisionContexts")
    last_login_date: Optional[datetime.date] = Field(default=None, description="Last date the user logged in")
    daily_bonus_amount: float = Field(default=10.0, description="Amount of money given as daily login bonus")
    api_keys: dict = Field(default_factory=dict, sa_column=Column(JSON), description="User's API keys for LLM services")

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
    model: str = "openrouter/openai/chatgpt-4o-latest"
    custom_prompt: Optional[str] = None
    # chooser_model: str = "openrouter/openai/chatgpt-4o-latest"
    # chooser_system_prompt: str = "You are a helpful assistant."
    # decider_model: str = "openrouter/openai/chatgpt-4o-latest"
    # decider_system_prompt: str = "You are a helpful assistant."
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
#         "polymorphic_on": "type",
#     }

#     # Relationships
#     decision_contexts: List["DecisionContext"] = Relationship(
#         back_populates="buyer", sa_relationship_kwargs={"lazy": "selectin"}
#     )


class HumanBuyer(SQLModel, table=True):
    # __tablename__ = "human_buyer"

    # id: Optional[int] = Field(default=None, primary_key=True)
    id: int = Field(foreign_key="user.id", primary_key=True)

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
        description="Number of queries where at least one InfoOffer was inspected by the buyer, by priority",
    )
    num_purchased: dict[int, int] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Number of queries where at least one InfoOffer was purchased by the buyer, by priority",
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


class HumanSeller(SQLModel, table=True):
    __tablename__ = "human_seller"
    id: int = Field(foreign_key="user.id", primary_key=True)
    type: str = Field(default="human_seller")
    
    # Relationships
    user: User = Relationship(back_populates="seller_profile")
    matchers: List["SellerMatcher"] = Relationship(
        back_populates="human_seller",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    info_offers: List["InfoOffer"] = Relationship(
        back_populates="human_seller",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

class BotSeller(SQLModel, table=True):
    __tablename__ = "bot_seller"
    __table_args__ = (
        CheckConstraint(
            "(info IS NOT NULL AND price IS NOT NULL) OR (llm_model IS NOT NULL AND llm_prompt IS NOT NULL)",
            name="ck_bot_seller_info_price_or_llm"
        ),
    )
    id: int = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    type: str = Field(default="bot_seller")
    info: Optional[str] = Field(
        sa_column=Column(String, nullable=True),
        description="For bots that just regurgitate a piece of info"
    )

    price: Optional[float] = Field(
        default=None,
        description="Price for the information provided by this bot (required for fixed info bots)"
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
    matchers: List["SellerMatcher"] = Relationship(
        back_populates="bot_seller",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    info_offers: List["InfoOffer"] = Relationship(
        back_populates="bot_seller",
        sa_relationship_kwargs={"lazy": "selectin"}
    )



    # ensure Pydantic actually runs validators on assignment + init
    model_config = ConfigDict(validate_default=True, validate_assignment=True)

    # BUG validator doesn't work -- for whatever reason the info, price, model, and prompt are all None
    # This doesn't happen when we get rid of the validator (the BotSeller is created with the correct values),
    # but the validator gets it wrong. It might be because the validator is run before the fields are set.
    # But setting "after" doesn't work either.
    # @model_validator(mode="after")
    # def check_info_price_or_llm(self):
    #     # Debug: Print what the validator sees
    #     print(f"DEBUG VALIDATOR: self.info = {self.info}")
    #     print(f"DEBUG VALIDATOR: self.price = {self.price}")
    #     print(f"DEBUG VALIDATOR: self.llm_model = {self.llm_model}")
    #     print(f"DEBUG VALIDATOR: self.llm_prompt = {self.llm_prompt}")
    #     print(f"DEBUG VALIDATOR: self.user_id = {self.user_id}")
        
    #     # Must have either (info and price) or (llm_model and llm_prompt)
    #     has_fixed_info = self.info is not None and self.price is not None
    #     has_llm = self.llm_model is not None and self.llm_prompt is not None
        
    #     if not (has_fixed_info or has_llm):
    #         raise ValueError(
    #             "Must set either `info` and `price` or both `llm_model` and `llm_prompt`."
    #         )
    #     return self

class SellerMatcher(SQLModel, table=True):
    id: int = Field(primary_key=True)
    human_seller_id: Optional[int] = Field(foreign_key="human_seller.id", index=True, default=None)
    bot_seller_id: Optional[int] = Field(foreign_key="bot_seller.id", index=True, default=None)
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
        sa_column=Column(String, nullable=True, index=True),
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
    inbox_items: List["MatcherInbox"] = Relationship(back_populates="matcher", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    human_seller: Optional["HumanSeller"] = Relationship(back_populates="matchers")
    bot_seller: Optional["BotSeller"] = Relationship(back_populates="matchers")

    @property
    def seller(self) -> Optional["HumanSeller | BotSeller"]:
        """Get the seller based on which foreign key is populated"""
        if self.human_seller_id is not None:
            return self.human_seller
        elif self.bot_seller_id is not None:
            return self.bot_seller
        return None

    @property
    def seller_type(self) -> str:
        """Get the seller type based on which foreign key is populated"""
        if self.human_seller_id is not None:
            return "human_seller"
        elif self.bot_seller_id is not None:
            return "bot_seller"
        return "unknown"

class DecisionContext(SQLModel, table=True):
    id: int = Field(primary_key=True)
    query: Optional[str] = Field(index=True, default=None, description="Custom query for information")
    context_pages: Optional[List[str]] = Field(sa_column=Column(JSON, index=True), default=None, description="Context pages, e.g. https://metaculus.com/...")

    # for recursive decision contexts
    parent_id: Optional[int] = Field(default=None, foreign_key="decisioncontext.id", index=True)
    # parent_offer_ids: Optional[List[int]] = Field(
    #     sa_column=Column(JSON, index=True), 
    #     default=None, 
    #     description="List of InfoOffer IDs from the parent context that this recursive context is inspecting"
    # )
    parent:  Optional["DecisionContext"]      = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "DecisionContext.id"}
    )
    children: List["DecisionContext"] = Relationship(back_populates="parent")
    parent_offers: List["InfoOffer"] = Relationship(
        sa_relationship_kwargs={
            "secondary": decision_context_parent_offers,
            "lazy": "selectin",
            "overlaps": "parent_contexts",
        }
    )

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
    buyer_id: int = Field(foreign_key="humanbuyer.id", index=True)
    max_budget: float = Field(default=0.0, index=True)
    human_seller_ids: Optional[List[int]] = Field(
        sa_column=Column(JSON, index=True),
        default=None,
        description="Direct query to specific sellers only",
    )
    bot_seller_ids: Optional[List[int]] = Field(
        sa_column=Column(JSON, index=True),
        default=None,
        description="Direct query to specific sellers only",
    )
    priority: int = Field(default=0, le=1, ge=0, index=True)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    # Relationships
    buyer: HumanBuyer = Relationship(back_populates="decision_contexts")
    info_offers: List["InfoOffer"] = Relationship(back_populates="context")

    # @property
    # def info_offers_being_inspected(self) -> list["InfoOffer"]:
    #     return [offer for offer in self.info_offers if offer.currently_being_inspected]
    
    # @property
    # def info_offers_already_inspected(self) -> list["InfoOffer"]:
    #     return [offer for offer in self.info_offers if offer.inspected]

    # @property
    # def info_offers_already_purchased(self) -> list["InfoOffer"]:
    #     return [offer for offer in self.info_offers if offer.purchased]

    # NEW: Convenience methods for working with parent offers
    @property
    def parent_offer_ids(self) -> List[int]:
        """Get list of parent offer IDs (for backward compatibility)"""
        return [offer.id for offer in self.parent_offers if offer.id is not None]

    def add_parent_offer(self, offer: "InfoOffer") -> None:
        """Add a parent offer to this context"""
        if offer not in self.parent_offers:
            self.parent_offers.append(offer)

    def add_parent_offers_by_ids(self, session: Session, offer_ids: List[int]) -> None:
        """Add parent offers by their IDs"""
        offers = session.exec(
            select(InfoOffer).where(InfoOffer.id.in_(offer_ids))
        ).all()
        for offer in offers:
            self.add_parent_offer(offer)

    def remove_parent_offer(self, offer: "InfoOffer") -> None:
        """Remove a parent offer from this context"""
        if offer in self.parent_offers:
            self.parent_offers.remove(offer)

class InfoOffer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    human_seller_id: Optional[int] = Field(foreign_key="human_seller.id", index=True, default=None)
    bot_seller_id: Optional[int] = Field(foreign_key="bot_seller.id", index=True, default=None)
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
    # currently_being_inspected: bool = Field(
    #     default=False,
    #     description="Whether the info offer is currently being inspected by a buyer",
    # )
    inspected: bool = Field(
        default=False,
        description="Whether the info offer has been inspected by a buyer",
    )
    purchased: bool = Field(
        default=False,
        description="Whether the info offer has been purchased by a buyer",
    )

    # Relationships
    context: DecisionContext = Relationship(back_populates="info_offers")
    human_seller: Optional["HumanSeller"] = Relationship(back_populates="info_offers")
    bot_seller: Optional["BotSeller"] = Relationship(back_populates="info_offers")

    parent_contexts: List[DecisionContext] = Relationship(
        back_populates="parent_offers",
        sa_relationship_kwargs={
            "secondary": decision_context_parent_offers,
            "overlaps": "parent_offers"  # Resolve overlapping relationships
        }
    )

    @property
    def seller(self) -> Optional["HumanSeller | BotSeller"]:
        """Get the seller based on which foreign key is populated"""
        if self.human_seller_id is not None:
            return self.human_seller
        elif self.bot_seller_id is not None:
            return self.bot_seller
        return None

    @property
    def seller_type(self) -> str:
        """Get the seller type based on which foreign key is populated"""
        if self.human_seller_id is not None:
            return "human_seller"
        elif self.bot_seller_id is not None:
            return "bot_seller"
        return "unknown"

class MatcherInbox(SQLModel, table=True):
    id: int = Field(primary_key=True)
    matcher_id: int = Field(foreign_key="sellermatcher.id", index=True)
    decision_context_id: int = Field(foreign_key="decisioncontext.id", index=True)
    status: str = Field(
        default="new",
        description="Status of the inbox item (new, ignored, responded)",
        index=True,
    )
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow, index=True)
    expires_at: datetime.datetime = Field(index=True)

    # Relationships
    matcher: SellerMatcher = Relationship(back_populates="inbox_items")
    decision_context: DecisionContext = Relationship()
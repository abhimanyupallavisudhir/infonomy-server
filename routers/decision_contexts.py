from typing import Union, List
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from sqlmodel import Session, select
from database import get_db
from models import User, HumanBuyer, DecisionContext, InfoOffer, SellerMatcher
from schemas import (
    UserRead,
    DecisionContextCreateNonRecursive,
    DecisionContextRead,
    DecisionContextUpdateNonRecursive,
    DecisionContextUpdateRecursive,
    DecisionContextCreateRecursive,
    HumanBuyerRead,
    HumanBuyerCreate,
    InfoOfferReadPrivate,
    InfoOfferReadPublic,
    InfoOfferCreate,
    InfoOfferUpdate,
)
from auth import current_active_user

router = APIRouter(tags=["decision_contexts"])


@router.post("/buyers", response_model=HumanBuyerRead)
def create_human_buyer(
    human_buyer: HumanBuyerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    db_human_buyer = HumanBuyer(**human_buyer.dict(), user_id=current_user.id)
    db.add(db_human_buyer)
    db.commit()
    db.refresh(db_human_buyer)
    return db_human_buyer


@router.post("/questions", response_model=DecisionContextCreateNonRecursive)
def create_decision_context(
    decision_context: DecisionContextCreateNonRecursive,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    db_decision_context = DecisionContext(
        **decision_context.dict(), buyer_id=current_user.id
    )
    db.add(db_decision_context)
    db.commit()
    db.refresh(db_decision_context)
    return db_decision_context


@router.patch(
    "/questions/{context_id}", response_model=DecisionContextUpdateNonRecursive
)
def update_decision_context(
    context_id: int,
    decision_context: DecisionContextUpdateNonRecursive,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    db_context = db.get(DecisionContext, context_id)
    if not db_context:
        raise HTTPException(status_code=404, detail="Decision context not found")

    for key, value in decision_context.dict(exclude_unset=True).items():
        setattr(db_context, key, value)

    db.add(db_context)
    db.commit()
    db.refresh(db_context)
    return db_context


@router.get("/questions/{context_id}", response_model=DecisionContextRead)
def read_decision_context(
    context_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    db_context = db.get(DecisionContext, context_id)
    if not db_context:
        raise HTTPException(status_code=404, detail="Decision context not found")
    return db_context


@router.get(
    "/matchers/{matcher_id}/questions_for",
    response_model=List[DecisionContextRead],
    status_code=status.HTTP_200_OK,
)
def read_decision_contexts_for_matcher(
    matcher_id: int,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
):
    # 1) Load and authorize
    matcher = db.get(SellerMatcher, matcher_id)
    if not matcher:
        raise HTTPException(status_code=404, detail="Matcher not found")
    # ensure this matcher belongs to the logged‑in seller
    if matcher.seller.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to view this matcher")

    # 2) Base SQL filters: budget, priority, age
    stmt = (
        select(DecisionContext)
        .where(DecisionContext.max_budget >= matcher.min_max_budget)
        .where(DecisionContext.priority >= matcher.min_priority)
    )
    if matcher.age_limit is not None:
        cutoff = datetime.utcnow() - timedelta(seconds=matcher.age_limit)
        stmt = stmt.where(DecisionContext.created_at >= cutoff)

    candidates = db.exec(stmt).all()

    # 3) In‑Python filters for JSON/text criteria
    matches: List[DecisionContext] = []
    for ctx in candidates:
        # — buyer_type (only human buyers exist today) —
        if matcher.buyer_type and matcher.buyer_type != "human_buyer":
            continue

        # — keywords in prompt —
        if matcher.keywords is not None:
            prompt = (ctx.query or "").lower()
            if not any(kw.lower() in prompt for kw in matcher.keywords):
                continue

        # — context_pages overlap —
        if matcher.context_pages is not None:
            pages = ctx.context_pages or []
            if not set(matcher.context_pages).intersection(pages):
                continue

        # (skip the LLM‐model / system‐prompt criteria here unless you
        #  add those fields to DecisionContext)

        matches.append(ctx)

    return matches

# PostgreSQL 
# from sqlalchemy import or_, and_, func
# @router.get(
#     "/matchers/{matcher_id}/questions_for",
#     response_model=List[DecisionContextRead],
# )
# def read_decision_contexts_for_matcher(
#     matcher_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(current_active_user),
# ):
#     matcher = db.get(SellerMatcher, matcher_id)
#     if not matcher or matcher.seller.user_id != current_user.id:
#         raise HTTPException(403)

#     # Build the base stmt with your numeric/date filters:
#     stmt = (
#         select(DecisionContext)
#         .where(DecisionContext.max_budget >= matcher.min_max_budget)
#         .where(DecisionContext.priority >= matcher.min_priority)
#     )
#     if matcher.age_limit is not None:
#         cutoff = datetime.utcnow() - timedelta(seconds=matcher.age_limit)
#         stmt = stmt.where(DecisionContext.created_at >= cutoff)

#     # 1) KEYWORD MATCH: require any of the keywords appear
#     if matcher.keywords:
#         # Postgres full‑text:
#         ts_query = " & ".join(func.plainto_tsquery("english", kw) for kw in matcher.keywords)
#         stmt = stmt.where(
#             func.to_tsvector("english", DecisionContext.query).op("@@")(func.to_tsquery("english", ts_query))
#         )
#         # └—or for simple ILIKE:
#         # stmt = stmt.where(
#         #     or_(*[DecisionContext.query.ilike(f"%{kw}%") for kw in matcher.keywords])
#         # )
#     # 2) CONTEXT_PAGES ARRAY OVERLAP
#     if matcher.context_pages:
#         # if using Postgres ARRAY:
#         # stmt = stmt.where(DecisionContext.context_pages.overlap(matcher.context_pages))
#         # if stored as JSONB array:
#         stmt = stmt.where(
#             DecisionContext.context_pages.cast("jsonb").op("?|")(matcher.context_pages)
#         )

#     # 3) (Other JSONB list fields you can treat similarly…)
#     # e.g. buyer_llm_model overlap etc.

#     results = db.exec(stmt).all()
#     return results


@router.get("/buyers/me/questions", response_model=list[DecisionContextRead])
def read_decision_contexts_for_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    db_contexts = db.exec(
        select(DecisionContext).where(
            DecisionContext.buyer_id == current_user.id
            and DecisionContext.parent_id is None
        )
    ).all()
    return db_contexts


@router.post("/questions/{context_id}/answers", response_model=InfoOfferReadPrivate)
def create_info_offer(
    context_id: int,
    info_offer: InfoOfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    db_context = db.get(DecisionContext, context_id)
    if not db_context:
        raise HTTPException(status_code=404, detail="Decision context not found")
    db_info_offer = InfoOffer(
        **info_offer.dict(exclude_unset=True), context_id=context_id
    )
    db.add(db_info_offer)
    db.commit()
    db.refresh(db_info_offer)
    return db_info_offer


@router.patch(
    "/questions/{context_id}/answers/{info_offer_id}",
    response_model=InfoOfferReadPrivate,
)
def update_info_offer(
    context_id: int,
    info_offer_id: int,
    info_offer: InfoOfferUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    db_info_offer = db.get(InfoOffer, info_offer_id)
    if not db_info_offer:
        raise HTTPException(status_code=404, detail="Info offer not found")

    for key, value in info_offer.dict(exclude_unset=True).items():
        setattr(db_info_offer, key, value)

    db.add(db_info_offer)
    db.commit()
    db.refresh(db_info_offer)
    return db_info_offer


@router.get(
    "/questions/{context_id}/answers/{info_offer_id}",
    response_model=Union[InfoOfferReadPrivate, InfoOfferReadPublic],
)
def read_info_offer(
    context_id: int,
    info_offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    # only read if user is seller, or has purchased the info offer
    db_info_offer = db.get(InfoOffer, info_offer_id)
    if not db_info_offer:
        raise HTTPException(status_code=404, detail="Info offer not found")
    make_public = db_info_offer.seller.user_id != current_user.id or (
        db_info_offer.purchased and db_info_offer.context.buyer_id == current_user.id
    )
    if not make_public:
        return InfoOfferReadPrivate.from_orm(db_info_offer)
    return InfoOfferReadPublic.from_orm(db_info_offer)


@router.get(
    "/questions/{context_id}/answers",
    response_model=list[Union[InfoOfferReadPrivate, InfoOfferReadPublic]],
)
def read_info_offers_for_decision_context(
    context_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    db_context = db.get(DecisionContext, context_id)
    if not db_context:
        raise HTTPException(status_code=404, detail="Decision context not found")

    db_info_offers = db.exec(
        select(InfoOffer).where(InfoOffer.context_id == context_id)
    ).all()
    return db_info_offers

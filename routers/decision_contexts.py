from typing import Union, List
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from sqlmodel import Session, select
from database import get_db
from models import User, HumanBuyer, DecisionContext, InfoOffer, SellerMatcher, Seller, HumanSeller, BotSeller, MatcherInbox
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

def get_context_for_buyer(
    context_id: int,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
) -> DecisionContext:
    """
    Dependency that loads a DecisionContext, 404s if missing,
    403s if the current user doesn’t own it.
    """
    ctx = db.get(DecisionContext, context_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Decision context not found")
    if ctx.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return ctx

def recompute_inbox_for_context(ctx: DecisionContext, db: Session):
    """
    Delete any existing inbox items for this context,
    re‑run the matcher logic, and insert fresh MatcherInbox rows.
    """
    # 1) clear old items
    db.query(MatcherInbox).filter(
        MatcherInbox.decision_context_id == ctx.id
    ).delete()
    db.commit()

    # 2) find candidate matchers by numeric filters
    stmt = (
        select(SellerMatcher)
        .where(ctx.max_budget >= SellerMatcher.min_max_budget)
        .where(ctx.priority   >= SellerMatcher.min_priority)
    )
    all_matchers: List[SellerMatcher] = db.exec(stmt).all()

    # 3) full Python matching (rates, keywords, contexts, buyer_type)
    buyer: HumanBuyer = ctx.buyer
    new_items: List[MatcherInbox] = []
    for m in all_matchers:
        # buyer_type
        if m.buyer_type and m.buyer_type != "human_buyer":
            continue

        # rates
        irate = buyer.inspection_rate.get(ctx.priority, 0.0)
        prate = buyer.purchase_rate.get(ctx.priority,   0.0)
        if irate < m.min_inspection_rate or prate < m.min_purchase_rate:
            continue

        # keywords
        if m.keywords is not None:
            text = (ctx.query or "").lower()
            if not any(kw.lower() in text for kw in m.keywords):
                continue

        # contexts
        if m.context_pages is not None:
            pages = ctx.context_pages or []
            if not any(p in pages for p in m.context_pages):
                continue
        now = datetime.utcnow()
        new_items.append(
            MatcherInbox(
                matcher_id=m.id,
                decision_context_id=ctx.id,
                status="new",
                created_at=now,
                expires_at=now + timedelta(seconds=m.age_limit)

            )
        )

    # 4) bulk‐insert fresh inbox items
    if new_items:
        db.add_all(new_items)
        db.commit()

@router.post(
    "/questions",
    response_model=DecisionContextRead,
    status_code=status.HTTP_201_CREATED,
)
def create_decision_context(
    decision_context: DecisionContextCreateNonRecursive,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
):
    if current_user.buyer_profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a buyer profile",
        )
    ctx = DecisionContext(
        **decision_context.dict(),
        buyer_id=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(ctx)
    db.commit()
    db.refresh(ctx)

    # populate inbox for this new context
    recompute_inbox_for_context(ctx, db)
    return ctx


@router.patch(
    "/questions/{context_id}",
    response_model=DecisionContextRead,
)
def update_decision_context(
    context_updates: DecisionContextUpdateNonRecursive,
    db_context: DecisionContext = Depends(get_context_for_buyer),
    db: Session = Depends(get_db),
):
    # apply only the fields the client sent
    for k, v in context_updates.dict(exclude_unset=True).items():
        setattr(db_context, k, v)
    db.add(db_context); db.commit(); db.refresh(db_context)

    # re‐sync the inbox: matchers may have gained/lost this context
    recompute_inbox_for_context(db_context, db)
    return db_context


@router.delete(
    "/questions/{context_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_decision_context(
    db_context: DecisionContext = Depends(get_context_for_buyer),
    db: Session = Depends(get_db),
):
    # clear out any inbox items first
    db.query(MatcherInbox).filter(
        MatcherInbox.decision_context_id == db_context.id
    ).delete()
    # then delete the context itself
    db.delete(db_context)
    db.commit()

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
    "/matchers/{matcher_id}/inbox",
    response_model=List[DecisionContextRead],
)
def read_decision_contexts_for_matcher(
    matcher_id: int,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
):
    # authorize…
    matcher = db.get(SellerMatcher, matcher_id)
    if not matcher or matcher.seller.user_id != current_user.id:
        raise HTTPException(status_code=404)

    # fetch all unread contexts
    stmt = (
        select(DecisionContext)
        .join(MatcherInbox, MatcherInbox.decision_context_id == DecisionContext.id)
        .where(MatcherInbox.matcher_id == matcher_id)
        .where(MatcherInbox.status == "new")
        .where(MatcherInbox.expires_at >= datetime.utcnow())
    )
    return db.exec(stmt).all()

@router.get(
    "/sellers/{seller_id}/inbox",
    response_model=List[DecisionContextRead],
    status_code=status.HTTP_200_OK,
)
def read_decision_contexts_for_seller(
    seller_id: int,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
):
    # 1) Load the seller (must be a HumanSeller)
    seller = db.get(Seller, seller_id)
    if not seller or not isinstance(seller, HumanSeller):
        raise HTTPException(status_code=404, detail="Seller not found")
    if seller.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not allowed to view this seller’s inbox"
        )

    # 2) Collect all matcher IDs for this seller
    matcher_ids = [m.id for m in seller.matchers]
    if not matcher_ids:
        return []

    # 3) Fetch all NEW DecisionContexts via the inbox table
    stmt = (
        select(DecisionContext)
        .join(MatcherInbox, MatcherInbox.decision_context_id == DecisionContext.id)
        .where(MatcherInbox.matcher_id.in_(matcher_ids))
        .where(MatcherInbox.status == "new")
    )
    results = db.exec(stmt).all()
    return results



@router.post(
    "/questions/{context_id}/answers",
    response_model=InfoOfferReadPrivate,
    status_code=status.HTTP_201_CREATED,
)
def create_info_offer(
    context_id: int,
    info_offer: InfoOfferCreate,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
):
    # 1) Ensure the context exists
    ctx = db.get(DecisionContext, context_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Decision context not found")

    # 2) Ensure the user is a seller with a profile
    human_seller = current_user.seller_profile
    if not human_seller:
        raise HTTPException(status_code=400, detail="User is not a seller")

    # 3) Create the InfoOffer
    offer = InfoOffer(
        **info_offer.dict(exclude_unset=True),
        context_id=context_id,
        seller_id=human_seller.user_id,
        created_at=datetime.utcnow(),
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)

    # 4) Mark any matching inbox items as “responded”
    matcher_ids = [m.id for m in human_seller.matchers]
    inbox_items = db.exec(
        select(MatcherInbox)
        .where(MatcherInbox.decision_context_id == context_id)
        .where(MatcherInbox.matcher_id.in_(matcher_ids))
    ).all()
    for item in inbox_items:
        item.status = "responded"
        db.add(item)
    db.commit()

    return offer


@router.patch(
    "/questions/{context_id}/answers/{info_offer_id}",
    response_model=InfoOfferReadPrivate,
)
def update_info_offer(
    context_id: int,
    info_offer_id: int,
    info_offer: InfoOfferUpdate,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
):
    # 1) Load the offer
    offer = db.get(InfoOffer, info_offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Info offer not found")

    # 2) Authorize
    human_seller = current_user.seller_profile
    if not human_seller or offer.seller_id != human_seller.user_id:
        raise HTTPException(status_code=403, detail="Not allowed to update this info offer")

    # 3) Apply updates
    for k, v in info_offer.dict(exclude_unset=True).items():
        setattr(offer, k, v)
    db.add(offer)
    db.commit()
    db.refresh(offer)

    # 4) Ensure the inbox remains “responded”
    matcher_ids = [m.id for m in human_seller.matchers]
    inbox_items = db.exec(
        select(MatcherInbox)
        .where(MatcherInbox.decision_context_id == context_id)
        .where(MatcherInbox.matcher_id.in_(matcher_ids))
    ).all()
    for item in inbox_items:
        item.status = "responded"
        db.add(item)
    db.commit()

    return offer


@router.delete(
    "/questions/{context_id}/answers/{info_offer_id}",
    response_model=InfoOfferReadPrivate,
)
def delete_info_offer(
    context_id: int,
    info_offer_id: int,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
):
    # 1) Load the offer
    offer = db.get(InfoOffer, info_offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Info offer not found")

    # 2) Authorize
    human_seller = current_user.seller_profile
    if not human_seller or offer.seller_id != human_seller.user_id:
        raise HTTPException(status_code=403, detail="Not allowed to delete this info offer")

    # 3) Delete it
    db.delete(offer)
    db.commit()

    # 4) Mark the context back to “new” in the inbox so the seller can reconsider
    matcher_ids = [m.id for m in human_seller.matchers]
    inbox_items = db.exec(
        select(MatcherInbox)
        .where(MatcherInbox.decision_context_id == context_id)
        .where(MatcherInbox.matcher_id.in_(matcher_ids))
    ).all()
    for item in inbox_items:
        item.status = "new"
        db.add(item)
    db.commit()

    return offer

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


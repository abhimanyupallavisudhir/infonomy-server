from typing import Union, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from sqlmodel import Session, select
from infonomy_server.database import get_db
from infonomy_server.models import (
    User,
    DecisionContext,
    InfoOffer,
    MatcherInbox,
)
from infonomy_server.schemas import (
    InfoOfferReadPrivate,
    InfoOfferReadPublic,
    InfoOfferCreate,
    InfoOfferUpdate,
)
from infonomy_server.auth import current_active_user

router = APIRouter(tags=["decision_contexts"])


@router.post(
    "/questions/{context_id}/answers",
    response_model=InfoOfferReadPrivate,
    status_code=status.HTTP_201_CREATED,
)
def create_info_offer(
    context_id: int,
    info_offer: InfoOfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
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
    current_user: User = Depends(current_active_user),
):
    # 1) Load the offer
    offer = db.get(InfoOffer, info_offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Info offer not found")

    # 2) Authorize
    human_seller = current_user.seller_profile
    if not human_seller or offer.seller_id != human_seller.user_id:
        raise HTTPException(
            status_code=403, detail="Not allowed to update this info offer"
        )

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
    current_user: User = Depends(current_active_user),
):
    # 1) Load the offer
    offer = db.get(InfoOffer, info_offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Info offer not found")

    # 2) Authorize
    human_seller = current_user.seller_profile
    if not human_seller or offer.seller_id != human_seller.user_id:
        raise HTTPException(
            status_code=403, detail="Not allowed to delete this info offer"
        )

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

    is_seller = db_info_offer.seller.user_id == current_user.id
    is_buyer_who_purchased = (
        db_info_offer.purchased and db_info_offer.context.buyer_id == current_user.id
    )

    if is_seller or is_buyer_who_purchased:
        return InfoOfferReadPrivate.from_orm(db_info_offer)
    else:
        return InfoOfferReadPublic.from_orm(db_info_offer)


@router.get(
    "/questions/{context_id}/answers",
    response_model=List[Union[InfoOfferReadPrivate, InfoOfferReadPublic]],
    status_code=status.HTTP_200_OK,
)
def read_info_offers_for_decision_context(
    context_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    # 1) Verify context exists
    ctx = db.get(DecisionContext, context_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Decision context not found")

    # 2) Load all offers for that context
    offers = db.exec(select(InfoOffer).where(InfoOffer.context_id == context_id)).all()

    # 3) For each offer, decide which schema to use
    result: List[Union[InfoOfferReadPrivate, InfoOfferReadPublic]] = []
    for offer in offers:
        is_seller = offer.seller.user_id == current_user.id
        is_buyer_who_purchased = offer.purchased and ctx.buyer_id == current_user.id

        if is_seller:
            # seller sees the full private schema
            result.append(InfoOfferReadPrivate.from_orm(offer))
        elif is_buyer_who_purchased:
            # buyer after purchase sees the public schema
            result.append(InfoOfferReadPublic.from_orm(offer))
        else:
            # everyone else: public view
            result.append(InfoOfferReadPublic.from_orm(offer))

    return result

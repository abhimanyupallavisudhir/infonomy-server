from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from sqlmodel import Session, select
from database import get_db
from models import (
    User,
    DecisionContext,
    SellerMatcher,
    Seller,
    HumanSeller,
    MatcherInbox,
)
from schemas import DecisionContextRead
from auth import current_active_user

router = APIRouter(tags=["inbox"])


@router.get(
    "/matchers/{matcher_id}/inbox",
    response_model=List[DecisionContextRead],
)
def read_decision_contexts_for_matcher(
    matcher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
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
    current_user: User = Depends(current_active_user),
):
    # 1) Load the seller (must be a HumanSeller)
    seller = db.get(Seller, seller_id)
    if not seller or not isinstance(seller, HumanSeller):
        raise HTTPException(status_code=404, detail="Seller not found")
    if seller.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not allowed to view this seller’s inbox"
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

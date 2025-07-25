from typing import List
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from sqlmodel import Session, select
from database import get_db
from models import (
    User,
    HumanBuyer,
    DecisionContext,
    SellerMatcher,
    MatcherInbox,
)
from schemas import (
    DecisionContextCreateNonRecursive,
    DecisionContextRead,
    DecisionContextUpdateNonRecursive,
)
from auth import current_active_user

router = APIRouter(tags=["decision_contexts"])

def get_context_for_buyer(
    context_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
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
    db.query(MatcherInbox).filter(MatcherInbox.decision_context_id == ctx.id).delete()
    db.commit()

    # 2) find candidate matchers by numeric filters
    stmt = (
        select(SellerMatcher)
        .where(ctx.max_budget >= SellerMatcher.min_max_budget)
        .where(ctx.priority >= SellerMatcher.min_priority)
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
        prate = buyer.purchase_rate.get(ctx.priority, 0.0)
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
                expires_at=now + timedelta(seconds=m.age_limit),
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
    current_user: User = Depends(current_active_user),
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
    db.add(db_context)
    db.commit()
    db.refresh(db_context)

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
    # TODO: add check to make sure recursive contexts are only visible to bot sellers, follow-up sellers and buyers who have already purchased
    db_context = db.get(DecisionContext, context_id)
    if not db_context:
        raise HTTPException(status_code=404, detail="Decision context not found")
    return db_context





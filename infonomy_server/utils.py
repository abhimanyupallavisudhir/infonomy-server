from typing import List
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends
from sqlmodel import Session, select
from infonomy_server.database import get_db
from infonomy_server.models import (
    User,
    HumanBuyer,
    DecisionContext,
    SellerMatcher,
    MatcherInbox,
)
from infonomy_server.auth import current_active_user

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


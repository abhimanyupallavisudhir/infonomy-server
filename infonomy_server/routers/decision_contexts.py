from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlmodel import Session, select
from infonomy_server.database import get_db
from infonomy_server.models import (
    User,
    DecisionContext,
    MatcherInbox,
)
from infonomy_server.schemas import (
    DecisionContextCreateNonRecursive,
    DecisionContextRead,
    DecisionContextUpdateNonRecursive,
)
from infonomy_server.auth import current_active_user
from infonomy_server.utils import (
    get_context_for_buyer,
    recompute_inbox_for_context,
    increment_buyer_query_counter
)
from typing import List, Optional

router = APIRouter(tags=["decision_contexts"])

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
    
    # Validate max_budget against available_balance
    if decision_context.max_budget > current_user.available_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Max budget ({decision_context.max_budget}) exceeds available balance ({current_user.available_balance})",
        )
    
    # Deduct max_budget from available_balance
    current_user.available_balance -= decision_context.max_budget
    db.add(current_user)
    
    ctx = DecisionContext(
        **decision_context.dict(),
        buyer_id=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(ctx)
    db.commit()
    db.refresh(ctx)

    # Increment the buyer's query counter for this priority level
    increment_buyer_query_counter(current_user.buyer_profile, ctx.priority, db)

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
):
    db_context = db.get(DecisionContext, context_id)
    if not db_context:
        raise HTTPException(status_code=404, detail="Decision context not found")
    if db_context.parent_id is not None:
        raise HTTPException(status_code=403, detail="Recursive contexts are not made public")
    return db_context


@router.get("/questions", response_model=List[DecisionContextRead])
def list_decision_contexts(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_db),
):
    """List all public decision contexts (excluding recursive ones)"""
    stmt = (
        select(DecisionContext)
        .where(DecisionContext.parent_id.is_(None))  # Exclude recursive contexts
        .order_by(DecisionContext.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    contexts = db.exec(stmt).all()
    return contexts


@router.get("/users/me/questions", response_model=List[DecisionContextRead])
def list_current_user_decision_contexts(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """List current user's decision contexts (including recursive ones)"""
    if current_user.buyer_profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a buyer profile",
        )
    
    stmt = (
        select(DecisionContext)
        .where(DecisionContext.buyer_id == current_user.id)
        .order_by(DecisionContext.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    contexts = db.exec(stmt).all()
    return contexts


@router.get("/users/{user_id}/questions", response_model=List[DecisionContextRead])
def list_user_decision_contexts(
    user_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_db),
    # current_user: User = Depends(current_active_user),
):
    """List decision contexts by specific user (excluding recursive ones)"""
    stmt = (
        select(DecisionContext)
        .where(DecisionContext.buyer_id == user_id)
        .where(DecisionContext.parent_id.is_(None))  # Exclude recursive contexts
        .order_by(DecisionContext.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    contexts = db.exec(stmt).all()
    return contexts






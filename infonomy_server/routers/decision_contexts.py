from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
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
from infonomy_server.utils import get_context_for_buyer, recompute_inbox_for_context

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
    db_context = db.get(DecisionContext, context_id)
    if not db_context:
        raise HTTPException(status_code=404, detail="Decision context not found")
    if db_context.parent_id is not None:
        raise HTTPException(status_code=403, detail="Recursive contexts are not made public")
    return db_context






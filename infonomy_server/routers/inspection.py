# routers/inspection.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from celery.result import AsyncResult

from infonomy_server.database import get_db
from infonomy_server.auth import current_active_user
from celery_app import celery
from infonomy_server.tasks import inspect_task  # our Celery task
from infonomy_server.models import DecisionContext
from infonomy_server.schemas import UserRead

router = APIRouter()

@router.post(
    "/questions/{context_id}/inspect",
    status_code=status.HTTP_202_ACCEPTED,
)
def inspect_context(
    context_id: int,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
):
    # ensure context exists & belongs to buyer
    ctx = db.get(DecisionContext, context_id)
    if not ctx or ctx.buyer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Context not found")

    # enqueue the background job
    # you can pass countdown= or other options to apply_async
    async_result = inspect_task.apply_async(
        args=[context_id, current_user.id],
    )

    return {"job_id": async_result.id}


@router.get("/jobs/{job_id}/status")
def get_job_status(
    job_id: str,
    current_user: UserRead = Depends(current_active_user),
):
    """
    Returns the Celery task state and, if ready, the result (list of purchased IDs).
    """
    result = AsyncResult(job_id, app=celery)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "state":  result.state,      # PENDING, STARTED, SUCCESS, FAILURE, ...
        "result": result.result,     # None until SUCCESS, then your List[int]
        "traceback": result.traceback if result.failed() else None,
    }

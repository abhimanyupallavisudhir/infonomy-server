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
from infonomy_server.logging_config import inspection_logger, log_business_event

router = APIRouter(tags=["inspection"])

@router.post(
    "/questions/{context_id}/inspect",
    status_code=status.HTTP_202_ACCEPTED,
)
def inspect_context(
    context_id: int,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
):
    # Log inspection start
    log_business_event(inspection_logger, "inspection_requested", user_id=current_user.id, parameters={
        "context_id": context_id,
        "user_id": current_user.id
    })
    
    # ensure context exists & belongs to buyer
    ctx = db.get(DecisionContext, context_id)
    if not ctx or ctx.buyer_id != current_user.id:
        log_business_event(inspection_logger, "inspection_failed", user_id=current_user.id, parameters={
            "context_id": context_id,
            "error": "context_not_found_or_unauthorized"
        })
        raise HTTPException(status_code=404, detail="Context not found")

    # enqueue the background job
    # you can pass countdown= or other options to apply_async
    async_result = inspect_task.apply_async(
        args=[context_id, current_user.id],
    )
    
    # Log successful job creation
    log_business_event(inspection_logger, "inspection_job_created", user_id=current_user.id, parameters={
        "context_id": context_id,
        "job_id": async_result.id,
        "max_budget": ctx.max_budget
    })

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
        log_business_event(inspection_logger, "job_status_failed", user_id=current_user.id, parameters={
            "job_id": job_id,
            "error": "job_not_found"
        })
        raise HTTPException(status_code=404, detail="Job not found")

    # Log job status check
    log_business_event(inspection_logger, "job_status_checked", user_id=current_user.id, parameters={
        "job_id": job_id,
        "state": result.state,
        "has_result": result.result is not None,
        "failed": result.failed()
    })

    return {
        "state":  result.state,      # PENDING, STARTED, SUCCESS, FAILURE, ...
        "result": result.result,     # None until SUCCESS, then your List[int]
        "traceback": result.traceback if result.failed() else None,
    }

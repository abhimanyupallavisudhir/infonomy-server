# routers/inspection.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from celery.result import AsyncResult
from datetime import datetime

from infonomy_server.database import get_db
from infonomy_server.auth import current_active_user
from celery_app import celery
from infonomy_server.tasks import inspect_task  # our Celery task
from infonomy_server.models import DecisionContext, InfoOffer, Inspection
from infonomy_server.schemas import UserRead, InspectionCreate, InspectionRead
from infonomy_server.logging_config import inspection_logger, log_business_event

router = APIRouter(tags=["inspection"])

@router.post(
    "/questions/{context_id}/inspect",
    response_model=InspectionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_inspection(
    context_id: int,
    inspection_data: InspectionCreate,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
):
    # Log inspection start
    log_business_event(inspection_logger, "inspection_requested", user_id=current_user.id, parameters={
        "context_id": context_id,
        "user_id": current_user.id,
        "info_offer_ids": inspection_data.info_offer_ids
    })
    
    # Validate that context_id matches inspection_data.decision_context_id
    if context_id != inspection_data.decision_context_id:
        raise HTTPException(status_code=400, detail="context_id in URL must match decision_context_id in request body")
    
    # ensure context exists (no longer restricted to owner)
    ctx = db.get(DecisionContext, context_id)
    if not ctx:
        log_business_event(inspection_logger, "inspection_failed", user_id=current_user.id, parameters={
            "context_id": context_id,
            "error": "context_not_found"
        })
        raise HTTPException(status_code=404, detail="Context not found")

    # Validate that the specified InfoOffers exist and belong to this context
    if inspection_data.info_offer_ids:
        offers = db.exec(
            select(InfoOffer)
            .where(InfoOffer.id.in_(inspection_data.info_offer_ids))
            .where(InfoOffer.context_id == context_id)
        ).all()
        
        if len(offers) != len(inspection_data.info_offer_ids):
            log_business_event(inspection_logger, "inspection_failed", user_id=current_user.id, parameters={
                "context_id": context_id,
                "error": "invalid_info_offer_ids"
            })
            raise HTTPException(status_code=400, detail="Some InfoOffers not found or don't belong to this context")
    else:
        # If no specific offers provided, inspect all offers for this context
        offers = db.exec(
            select(InfoOffer).where(InfoOffer.context_id == context_id)
        ).all()
        inspection_data.info_offer_ids = [offer.id for offer in offers]

    # Create the inspection
    inspection = Inspection(
        decision_context_id=context_id,
        buyer_id=current_user.id,
        known_offers=current_user.purchased_info_offers.copy(),  # Initialize with user's purchased offers
        created_at=datetime.utcnow()
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    # Associate the InfoOffers with this inspection
    for offer_id in inspection_data.info_offer_ids:
        offer = db.get(InfoOffer, offer_id)
        if offer:
            inspection.info_offers.append(offer)
    
    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    # enqueue the background job
    async_result = inspect_task.apply_async(
        args=[inspection.id],
    )
    
    # Set the job_id on the inspection object
    inspection.job_id = async_result.id
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    
    # Log successful job creation
    log_business_event(inspection_logger, "inspection_job_created", user_id=current_user.id, parameters={
        "inspection_id": inspection.id,
        "context_id": context_id,
        "job_id": async_result.id,
        "max_budget": ctx.max_budget
    })

    return inspection


@router.get("/inspections/{inspection_id}", response_model=InspectionRead)
def get_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
):
    """Get inspection details"""
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    # Only the buyer who created the inspection can view it
    if inspection.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this inspection")
    
    return inspection


@router.get("/questions/{context_id}/inspections", response_model=list[InspectionRead])
def list_inspections_for_context(
    context_id: int,
    db: Session = Depends(get_db),
    current_user: UserRead = Depends(current_active_user),
):
    """List all inspections for a specific context (only user's own inspections)"""
    inspections = db.exec(
        select(Inspection)
        .where(Inspection.decision_context_id == context_id)
        .where(Inspection.buyer_id == current_user.id)
        .order_by(Inspection.created_at.desc())
    ).all()
    
    return inspections


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

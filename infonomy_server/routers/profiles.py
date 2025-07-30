from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from infonomy_server.database import get_db
from infonomy_server.models import (
    User,
    HumanBuyer,
    HumanSeller,
)
from infonomy_server.schemas import (

    HumanBuyerRead,
    HumanBuyerCreate,
    HumanBuyerUpdate,
)
from infonomy_server.auth import current_active_user

router = APIRouter(tags=["profiles"])

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


@router.get("/buyers/me", response_model=HumanBuyerRead)
def read_current_human_buyer(
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    db_human_buyer = db.exec(
        select(HumanBuyer).where(HumanBuyer.user_id == current_user.id)
    ).first()
    if not db_human_buyer:
        raise HTTPException(status_code=404, detail="Human buyer profile not found")
    return db_human_buyer


@router.update("/buyers/me", response_model=HumanBuyerRead)
def update_current_human_buyer(
    human_buyer_updates: HumanBuyerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    db_human_buyer = db.exec(
        select(HumanBuyer).where(HumanBuyer.user_id == current_user.id)
    ).first()
    if not db_human_buyer:
        raise HTTPException(status_code=404, detail="Human buyer profile not found")
    for k, v in human_buyer_updates.dict(exclude_unset=True).items():
        setattr(db_human_buyer, k, v)
    db.add(db_human_buyer)
    db.commit()
    db.refresh(db_human_buyer)
    return db_human_buyer


@router.post("/sellers", response_model=HumanSeller)
def create_human_seller(
    db: Session = Depends(get_db), current_user: User = Depends(current_active_user)
):
    # Ensure the user does not already have a seller profile
    existing_seller = db.exec(
        select(HumanSeller).where(HumanSeller.user_id == current_user.id)
    ).first()
    if existing_seller:
        raise HTTPException(status_code=400, detail="User already has a seller profile")

    # Create the new HumanSeller profile
    human_seller = HumanSeller(user_id=current_user.id)
    db.add(human_seller)
    db.commit()
    db.refresh(human_seller)
    return human_seller

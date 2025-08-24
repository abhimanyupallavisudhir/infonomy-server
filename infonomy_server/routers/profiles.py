from fastapi import APIRouter, HTTPException, Depends, status
from sqlmodel import Session, select
from infonomy_server.database import get_db
from infonomy_server.models import (
    User,
    HumanBuyer,
    HumanSeller,
    SellerMatcher,
)
from infonomy_server.schemas import (
    HumanBuyerRead,
    HumanBuyerCreate,
    HumanBuyerUpdate,
    SellerMatcherRead,
    SellerMatcherCreate,
    SellerMatcherUpdate,
)
from infonomy_server.auth import current_active_user
from typing import List
from infonomy_server.utils import (
    get_context_for_buyer, 
    recompute_inbox_for_matcher, 
    remove_matcher_from_inboxes,
    get_buyer_stats_summary
)

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


@router.put("/buyers/me", response_model=HumanBuyerRead)
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


@router.get("/sellers/me", response_model=HumanSeller)
def read_current_human_seller(
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Get current user's seller profile"""
    db_human_seller = db.exec(
        select(HumanSeller).where(HumanSeller.user_id == current_user.id)
    ).first()
    if not db_human_seller:
        raise HTTPException(status_code=404, detail="Human seller profile not found")
    return db_human_seller


# HumanSeller Matcher CRUD operations
@router.post("/sellers/me/matchers", response_model=SellerMatcherRead)
def create_human_seller_matcher(
    matcher: SellerMatcherCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Create a new matcher for the current user's HumanSeller profile"""
    human_seller = db.exec(
        select(HumanSeller).where(HumanSeller.user_id == current_user.id)
    ).first()
    if not human_seller:
        raise HTTPException(status_code=404, detail="Human seller profile not found")
    
    db_matcher = SellerMatcher(
        **matcher.dict(),
        seller_id=human_seller.id,
        seller_type="human_seller"
    )
    db.add(db_matcher)
    db.commit()
    db.refresh(db_matcher)
    
    # Recompute inbox for this new matcher
    recompute_inbox_for_matcher(db_matcher, db)
    
    return db_matcher


@router.get("/sellers/me/matchers", response_model=List[SellerMatcherRead])
def list_human_seller_matchers(
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """List all matchers for the current user's HumanSeller profile"""
    human_seller = db.exec(
        select(HumanSeller).where(HumanSeller.user_id == current_user.id)
    ).first()
    if not human_seller:
        raise HTTPException(status_code=404, detail="Human seller profile not found")
    
    matchers = db.exec(
        select(SellerMatcher)
        .where(SellerMatcher.seller_id == human_seller.id)
        .where(SellerMatcher.seller_type == "human_seller")
    ).all()
    return matchers


@router.put("/sellers/me/matchers/{matcher_id}", response_model=SellerMatcherRead)
def update_human_seller_matcher(
    matcher_id: int,
    matcher_updates: SellerMatcherUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Update a matcher for the current user's HumanSeller profile"""
    human_seller = db.exec(
        select(HumanSeller).where(HumanSeller.user_id == current_user.id)
    ).first()
    if not human_seller:
        raise HTTPException(status_code=404, detail="Human seller profile not found")
    
    db_matcher = db.get(SellerMatcher, matcher_id)
    if not db_matcher:
        raise HTTPException(status_code=404, detail="Matcher not found")
    if db_matcher.seller_id != human_seller.id or db_matcher.seller_type != "human_seller":
        raise HTTPException(status_code=404, detail="Matcher not found for this HumanSeller")
    
    for k, v in matcher_updates.dict(exclude_unset=True).items():
        setattr(db_matcher, k, v)
    
    db.add(db_matcher)
    db.commit()
    db.refresh(db_matcher)
    
    # Recompute inbox for this updated matcher
    recompute_inbox_for_matcher(db_matcher, db)
    
    return db_matcher


@router.delete("/sellers/me/matchers/{matcher_id}")
def delete_human_seller_matcher(
    matcher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Delete a matcher for the current user's HumanSeller profile"""
    human_seller = db.exec(
        select(HumanSeller).where(HumanSeller.user_id == current_user.id)
    ).first()
    if not human_seller:
        raise HTTPException(status_code=404, detail="Human seller profile not found")
    
    db_matcher = db.get(SellerMatcher, matcher_id)
    if not db_matcher:
        raise HTTPException(status_code=404, detail="Matcher not found")
    if db_matcher.seller_id != human_seller.id or db_matcher.seller_type != "human_seller":
        raise HTTPException(status_code=404, detail="Matcher not found for this HumanSeller")
    
    # Remove all inbox items for this matcher before deleting it
    remove_matcher_from_inboxes(matcher_id, db)
    
    db.delete(db_matcher)
    db.commit()
    return {"message": "Matcher deleted successfully"}


@router.get("/buyers/me/stats")
def get_current_buyer_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Get current user's buyer statistics"""
    if current_user.buyer_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not have a buyer profile",
        )
    
    stats = get_buyer_stats_summary(current_user.buyer_profile)
    return stats


@router.get("/buyers/{user_id}/stats")
def get_buyer_stats_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Get buyer statistics for a specific user (admin access)"""
    # Check if current user is requesting their own stats or has admin access
    if user_id != current_user.id:
        # In a real application, you might want to check admin permissions here
        # For now, we'll allow users to see their own stats only
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own statistics",
        )
    
    user = db.get(User, user_id)
    if not user or user.buyer_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User or buyer profile not found",
        )
    
    stats = get_buyer_stats_summary(user.buyer_profile)
    return stats


from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from infonomy_server.database import get_db
from infonomy_server.models import (
    User,
    BotSeller,
    SellerMatcher,
)
from infonomy_server.schemas import (
    BotSellerRead,
    BotSellerCreate,
    BotSellerUpdate,
    SellerMatcherRead,
    SellerMatcherCreate,
    SellerMatcherUpdate,
)
from infonomy_server.auth import current_active_user
from typing import List
from infonomy_server.utils import (
    recompute_inbox_for_matcher, 
    remove_matcher_from_inboxes
)

router = APIRouter(prefix="/bot-sellers", tags=["bot-sellers"])

@router.post("/", response_model=BotSellerRead)
def create_bot_seller(
    bot_seller: BotSellerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Create a new BotSeller for the current user"""
    # Check if user has a seller profile (either HumanSeller or existing BotSellers)
    # First check for HumanSeller
    from infonomy_server.models import HumanSeller
    existing_human_seller = db.exec(
        select(HumanSeller).where(HumanSeller.user_id == current_user.id)
    ).first()
    
    # If no HumanSeller, check if they have any existing BotSellers
    if not existing_human_seller:
        existing_bot_seller = db.exec(
            select(BotSeller).where(BotSeller.user_id == current_user.id)
        ).first()
        
        if not existing_bot_seller:
            raise HTTPException(
                status_code=400, 
                detail="User must have a seller profile to create BotSellers"
            )
    
    db_bot_seller = BotSeller(**bot_seller.dict(), user_id=current_user.id)
    db.add(db_bot_seller)
    db.commit()
    db.refresh(db_bot_seller)
    return db_bot_seller

@router.get("/", response_model=List[BotSellerRead])
def list_bot_sellers(
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """List all BotSellers for the current user"""
    bot_sellers = db.exec(
        select(BotSeller).where(BotSeller.user_id == current_user.id)
    ).all()
    return bot_sellers

@router.get("/{bot_seller_id}", response_model=BotSellerRead)
def get_bot_seller(
    bot_seller_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Get a specific BotSeller by ID"""
    bot_seller = db.get(BotSeller, bot_seller_id)
    if not bot_seller:
        raise HTTPException(status_code=404, detail="BotSeller not found")
    if bot_seller.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this BotSeller")
    return bot_seller

@router.put("/{bot_seller_id}", response_model=BotSellerRead)
def update_bot_seller(
    bot_seller_id: int,
    bot_seller_updates: BotSellerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Update a BotSeller"""
    db_bot_seller = db.get(BotSeller, bot_seller_id)
    if not db_bot_seller:
        raise HTTPException(status_code=404, detail="BotSeller not found")
    if db_bot_seller.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this BotSeller")
    
    for k, v in bot_seller_updates.dict(exclude_unset=True).items():
        setattr(db_bot_seller, k, v)
    
    db.add(db_bot_seller)
    db.commit()
    db.refresh(db_bot_seller)
    return db_bot_seller

@router.delete("/{bot_seller_id}")
def delete_bot_seller(
    bot_seller_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Delete a BotSeller"""
    db_bot_seller = db.get(BotSeller, bot_seller_id)
    if not db_bot_seller:
        raise HTTPException(status_code=404, detail="BotSeller not found")
    if db_bot_seller.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this BotSeller")
    
    db.delete(db_bot_seller)
    db.commit()
    return {"message": "BotSeller deleted successfully"}

# Matcher management for BotSellers
@router.post("/{bot_seller_id}/matchers", response_model=SellerMatcherRead)
def create_bot_seller_matcher(
    bot_seller_id: int,
    matcher: SellerMatcherCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Create a new matcher for a BotSeller"""
    bot_seller = db.get(BotSeller, bot_seller_id)
    if not bot_seller:
        raise HTTPException(status_code=404, detail="BotSeller not found")
    if bot_seller.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this BotSeller")
    
    db_matcher = SellerMatcher(
        **matcher.dict(),
        seller_id=bot_seller_id,
        seller_type="bot_seller"
    )
    db.add(db_matcher)
    db.commit()
    db.refresh(db_matcher)
    
    # Recompute inbox for this new matcher
    recompute_inbox_for_matcher(db_matcher, db)
    
    return db_matcher

@router.get("/{bot_seller_id}/matchers", response_model=List[SellerMatcherRead])
def list_bot_seller_matchers(
    bot_seller_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """List all matchers for a BotSeller"""
    bot_seller = db.get(BotSeller, bot_seller_id)
    if not bot_seller:
        raise HTTPException(status_code=404, detail="BotSeller not found")
    if bot_seller.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this BotSeller")
    
    matchers = db.exec(
        select(SellerMatcher)
        .where(SellerMatcher.seller_id == bot_seller_id)
        .where(SellerMatcher.seller_type == "bot_seller")
    ).all()
    return matchers

@router.put("/{bot_seller_id}/matchers/{matcher_id}", response_model=SellerMatcherRead)
def update_bot_seller_matcher(
    bot_seller_id: int,
    matcher_id: int,
    matcher_updates: SellerMatcherUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Update a matcher for a BotSeller"""
    bot_seller = db.get(BotSeller, bot_seller_id)
    if not bot_seller:
        raise HTTPException(status_code=404, detail="BotSeller not found")
    if bot_seller.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this BotSeller")
    
    db_matcher = db.get(SellerMatcher, matcher_id)
    if not db_matcher:
        raise HTTPException(status_code=404, detail="Matcher not found")
    if db_matcher.seller_id != bot_seller_id or db_matcher.seller_type != "bot_seller":
        raise HTTPException(status_code=404, detail="Matcher not found for this BotSeller")
    
    for k, v in matcher_updates.dict(exclude_unset=True).items():
        setattr(db_matcher, k, v)
    
    db.add(db_matcher)
    db.commit()
    db.refresh(db_matcher)
    
    # Recompute inbox for this updated matcher
    recompute_inbox_for_matcher(db_matcher, db)
    
    return db_matcher

@router.delete("/{bot_seller_id}/matchers/{matcher_id}")
def delete_bot_seller_matcher(
    bot_seller_id: int,
    matcher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Delete a matcher for a BotSeller"""
    bot_seller = db.get(BotSeller, bot_seller_id)
    if not bot_seller:
        raise HTTPException(status_code=404, detail="BotSeller not found")
    if bot_seller.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this BotSeller")
    
    db_matcher = db.get(SellerMatcher, matcher_id)
    if not db_matcher:
        raise HTTPException(status_code=404, detail="Matcher not found")
    if db_matcher.seller_id != bot_seller_id or db_matcher.seller_type != "bot_seller":
        raise HTTPException(status_code=404, detail="Matcher not found for this BotSeller")
    
    # Remove all inbox items for this matcher before deleting it
    remove_matcher_from_inboxes(matcher_id, db)
    
    db.delete(db_matcher)
    db.commit()
    return {"message": "Matcher deleted successfully"} 
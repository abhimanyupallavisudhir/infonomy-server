from fastapi import FastAPI, HTTPException, Depends, Query
from sqlmodel import Session, select
from infonomy_server.database import create_db_and_tables, get_db
from infonomy_server.models import User, InfoOffer, DecisionContext
from infonomy_server.schemas import UserRead, UserCreate, UserUpdate
from infonomy_server.auth import current_active_user, auth_backend, fastapi_users
from infonomy_server.routers import decision_contexts, info_offers, inspection, inbox, bot_sellers, profiles
from typing import List

app = FastAPI(title="Q&A Platform API", version="1.0.0")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
def root():
    return {"message": "Welcome to the Q&A Platform API"}

# Include FastAPI Users routes
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

# Include our custom routes
app.include_router(decision_contexts.router)
app.include_router(info_offers.router)
app.include_router(inspection.router)
app.include_router(inbox.router)
app.include_router(bot_sellers.router)
app.include_router(profiles.router)

# User Endpoints

@app.get("/users/", response_model=list[UserRead], tags=["users"])
def get_users(db: Session = Depends(get_db)):
    db_users = db.exec(select(User)).all()
    return db_users


@app.get("/users/me", response_model=UserRead, tags=["users"])
def get_current_user(
    current_user: User = Depends(current_active_user),
):
    """Get current user profile"""
    return current_user


@app.put("/users/me", response_model=UserRead, tags=["users"])
def update_current_user(
    user_updates: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Update current user profile"""
    for k, v in user_updates.dict(exclude_unset=True).items():
        setattr(current_user, k, v)
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@app.get("/users/{user_id}", response_model=UserRead, tags=["users"])
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Get public user profile by ID"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/users/me/purchases", tags=["users"])
def get_current_user_purchases(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Get current user's purchase history"""
    if not current_user.buyer_profile:
        raise HTTPException(
            status_code=400, 
            detail="User does not have a buyer profile"
        )
    
    # Get all purchased info offers for the current user
    purchased_offers = db.exec(
        select(InfoOffer)
        .join(DecisionContext, InfoOffer.context_id == DecisionContext.id)
        .where(DecisionContext.buyer_id == current_user.id)
        .where(InfoOffer.purchased == True)
        .order_by(InfoOffer.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    
    return {
        "purchases": [
            {
                "offer_id": offer.id,
                "context_id": offer.context_id,
                "seller_id": offer.seller_id,
                "seller_type": offer.seller_type,
                "price": offer.price,
                "purchased_at": offer.created_at,  # Using created_at as proxy for purchase time
                "context_query": offer.context.query if offer.context else None,
            }
            for offer in purchased_offers
        ],
        "total": len(purchased_offers),
        "skip": skip,
        "limit": limit
    }


@app.get("/users/me/sales", tags=["users"])
def get_current_user_sales(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Get current user's sales history"""
    # Check if user has any seller profiles
    human_seller = current_user.seller_profile
    bot_sellers = current_user.bot_sellers
    
    if not human_seller and not bot_sellers:
        raise HTTPException(
            status_code=400, 
            detail="User does not have a seller profile"
        )
    
    # Collect all sold offers from both HumanSeller and BotSellers
    sold_offers = []
    
    if human_seller:
        human_sales = db.exec(
            select(InfoOffer)
            .where(InfoOffer.seller_id == human_seller.user_id)
            .where(InfoOffer.seller_type == "human_seller")
            .where(InfoOffer.purchased == True)
            .order_by(InfoOffer.created_at.desc())
        ).all()
        sold_offers.extend(human_sales)
    
    if bot_sellers:
        bot_seller_ids = [bs.id for bs in bot_sellers]
        bot_sales = db.exec(
            select(InfoOffer)
            .where(InfoOffer.seller_id.in_(bot_seller_ids))
            .where(InfoOffer.seller_type == "bot_seller")
            .where(InfoOffer.purchased == True)
            .order_by(InfoOffer.created_at.desc())
        ).all()
        sold_offers.extend(bot_sales)
    
    # Sort by creation date and apply pagination
    sold_offers.sort(key=lambda x: x.created_at, reverse=True)
    paginated_sales = sold_offers[skip:skip + limit]
    
    return {
        "sales": [
            {
                "offer_id": offer.id,
                "context_id": offer.context_id,
                "seller_id": offer.seller_id,
                "seller_type": offer.seller_type,
                "price": offer.price,
                "sold_at": offer.created_at,  # Using created_at as proxy for sale time
                "context_query": offer.context.query if offer.context else None,
            }
            for offer in paginated_sales
        ],
        "total": len(sold_offers),
        "skip": skip,
        "limit": limit
    }


@app.get("/transactions", tags=["users"])
def get_transactions(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Get all transactions (purchases and sales) for the current user"""
    if not current_user.buyer_profile and not current_user.seller_profile and not current_user.bot_sellers:
        raise HTTPException(
            status_code=400, 
            detail="User does not have any profiles"
        )
    
    # Get purchases
    purchases = []
    if current_user.buyer_profile:
        purchased_offers = db.exec(
            select(InfoOffer)
            .join(DecisionContext, InfoOffer.context_id == DecisionContext.id)
            .where(DecisionContext.buyer_id == current_user.id)
            .where(InfoOffer.purchased == True)
            .order_by(InfoOffer.created_at.desc())
        ).all()
        
        purchases = [
            {
                "type": "purchase",
                "offer_id": offer.id,
                "context_id": offer.context_id,
                "seller_id": offer.seller_id,
                "seller_type": offer.seller_type,
                "amount": -offer.price,  # Negative for purchases
                "timestamp": offer.created_at,
                "context_query": offer.context.query if offer.context else None,
            }
            for offer in purchased_offers
        ]
    
    # Get sales
    sales = []
    if current_user.seller_profile or current_user.bot_sellers:
        sold_offers = []
        
        if current_user.seller_profile:
            human_sales = db.exec(
                select(InfoOffer)
                .where(InfoOffer.seller_id == current_user.seller_profile.user_id)
                .where(InfoOffer.seller_type == "human_seller")
                .where(InfoOffer.purchased == True)
                .order_by(InfoOffer.created_at.desc())
            ).all()
            sold_offers.extend(human_sales)
        
        if current_user.bot_sellers:
            bot_seller_ids = [bs.id for bs in current_user.bot_sellers]
            bot_sales = db.exec(
                select(InfoOffer)
                .where(InfoOffer.seller_id.in_(bot_seller_ids))
                .where(InfoOffer.seller_type == "bot_seller")
                .where(InfoOffer.purchased == True)
                .order_by(InfoOffer.created_at.desc())
            ).all()
            sold_offers.extend(bot_sales)
        
        sales = [
            {
                "type": "sale",
                "offer_id": offer.id,
                "context_id": offer.context_id,
                "buyer_id": offer.context.buyer_id if offer.context else None,
                "amount": offer.price,  # Positive for sales
                "timestamp": offer.created_at,
                "context_query": offer.context.query if offer.context else None,
            }
            for offer in sold_offers
        ]
    
    # Combine and sort all transactions
    all_transactions = purchases + sales
    all_transactions.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # Apply pagination
    paginated_transactions = all_transactions[skip:skip + limit]
    
    return {
        "transactions": paginated_transactions,
        "total": len(all_transactions),
        "skip": skip,
        "limit": limit,
        "summary": {
            "total_purchases": len(purchases),
            "total_sales": len(sales),
            "net_amount": sum(t["amount"] for t in all_transactions)
        }
    }


@app.get("/users/me/daily-bonus", tags=["users"])
def get_daily_bonus_status(
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    """Get current user's daily bonus status"""
    from infonomy_server.utils import process_daily_login_bonus
    import datetime
    
    today = datetime.date.today()
    
    # Check if user has already received a bonus today
    if current_user.last_login_date == today:
        return {
            "bonus_available": False,
            "message": "Daily bonus already received today",
            "last_bonus_date": current_user.last_login_date,
            "next_bonus_date": today + datetime.timedelta(days=1),
            "daily_bonus_amount": current_user.daily_bonus_amount,
            "current_balance": current_user.balance,
            "current_available_balance": current_user.available_balance
        }
    else:
        return {
            "bonus_available": True,
            "message": "Daily bonus available",
            "last_bonus_date": current_user.last_login_date,
            "next_bonus_date": today,
            "daily_bonus_amount": current_user.daily_bonus_amount,
            "current_balance": current_user.balance,
            "current_available_balance": current_user.available_balance
        }


@app.post("/users/me/daily-bonus", tags=["users"])
def claim_daily_bonus(
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    """Manually claim daily bonus (useful if automatic login bonus didn't work)"""
    from infonomy_server.utils import process_daily_login_bonus
    
    bonus_result = process_daily_login_bonus(current_user, db)
    
    return {
        "success": True,
        "result": bonus_result
    }


@app.put("/users/me/api-keys", tags=["users"])
def update_api_keys(
    api_keys: dict,
    current_user: User = Depends(current_active_user),
    db: Session = Depends(get_db),
):
    """Update current user's API keys for LLM services"""
    
    # Update user's API keys (no validation - users can provide any dict)
    current_user.api_keys = api_keys
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    return {
        "success": True,
        "message": "API keys updated successfully",
        "api_keys": current_user.api_keys
    }


@app.get("/users/me/api-keys", tags=["users"])
def get_api_keys(
    current_user: User = Depends(current_active_user),
):
    """Get current user's API keys (only key names, not values for security)"""
    
    # Return only the names of configured API keys, not the actual values
    configured_keys = list(current_user.api_keys.keys()) if current_user.api_keys else []
    
    return {
        "configured_api_keys": configured_keys,
        "total_keys": len(configured_keys)
    }

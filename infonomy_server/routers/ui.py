from fastapi import APIRouter, Request, Depends, HTTPException, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional, List
from infonomy_server.database import get_db
from infonomy_server.models import User, DecisionContext, InfoOffer, HumanBuyer, HumanSeller, BotSeller, SellerMatcher, MatcherInbox
from infonomy_server.schemas import DecisionContextCreateNonRecursive, InfoOfferCreate, HumanBuyerCreate, HumanBuyerUpdate, BotSellerCreate, BotSellerUpdate, SellerMatcherCreate, SellerMatcherUpdate
from infonomy_server.auth import current_active_user
from infonomy_server.auth_helpers import get_current_user_optional
from infonomy_server.utils import get_context_for_buyer, recompute_inbox_for_context, increment_buyer_query_counter
from datetime import datetime
import json

router = APIRouter(tags=["ui"])

# Templates setup
templates = Jinja2Templates(directory="infonomy_server/templates")

# Helper function to get user context
async def get_user_context(request: Request, db: Session):
    print(f"Headers: {dict(request.headers)}")
    user = await get_current_user_optional(request, db)
    print(f"User from token: {user.username if user else 'None'}")
    return {
        "request": request,
        "user": user,
        "is_authenticated": user is not None
    }

@router.get("/debug/auth", response_class=HTMLResponse)
async def debug_auth(request: Request, db: Session = Depends(get_db)):
    """Debug endpoint to test authentication"""
    print("=== DEBUG AUTH ===")
    print(f"Headers: {dict(request.headers)}")
    
    # Check cookies for auth_token
    cookie_header = request.headers.get("cookie")
    auth_token_from_cookie = None
    if cookie_header:
        for cookie in cookie_header.split(";"):
            if "auth_token=" in cookie:
                auth_token_from_cookie = cookie.split("auth_token=")[1].split(";")[0].strip()
                print(f"Auth token from cookie: {auth_token_from_cookie[:20] if auth_token_from_cookie else 'None'}...")
                break
    
    # Try to get user from token
    user = await get_current_user_optional(request, db)
    print(f"User from token: {user.username if user else 'None'}")
    
    # Check form data for auth_token
    try:
        form_data = await request.form()
        auth_token = form_data.get("auth_token")
        print(f"Auth token from form: {auth_token[:20] if auth_token else 'None'}...")
    except:
        print("No form data")
    
    return f"""
    <html>
        <body>
            <h1>Auth Debug</h1>
            <p>User: {user.username if user else 'None'}</p>
            <p>Headers: {dict(request.headers)}</p>
            <p>Token in cookie: {auth_token_from_cookie[:20] if auth_token_from_cookie else 'None'}...</p>
            <p>Token in localStorage: <span id="token-display">Loading...</span></p>
            <script>
                const token = localStorage.getItem('auth_token');
                document.getElementById('token-display').textContent = token ? token.substring(0, 20) + '...' : 'None';
            </script>
        </body>
    </html>
    """

@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request, db: Session = Depends(get_db)):
    """Home page with questions list and new question form"""
    context = await get_user_context(request, db)
    
    # Get recent questions with buyer information
    questions = db.exec(
        select(DecisionContext, User)
        .join(User, DecisionContext.buyer_id == User.id)
        .order_by(DecisionContext.created_at.desc())
        .limit(50)
    ).all()
    
    # Extract questions and buyers from the joined results
    questions_with_buyers = []
    for question, buyer in questions:
        questions_with_buyers.append({
            "question": question,
            "buyer": buyer
        })
    
    context["questions_with_buyers"] = questions_with_buyers
    return templates.TemplateResponse("home.html", context)

@router.get("/questions", response_class=HTMLResponse)
async def questions_page(request: Request, db: Session = Depends(get_db)):
    """Questions listing page"""
    context = await get_user_context(request, db)
    
    # Get recent questions with buyer information
    questions = db.exec(
        select(DecisionContext, User)
        .join(User, DecisionContext.buyer_id == User.id)
        .order_by(DecisionContext.created_at.desc())
        .limit(100)
    ).all()
    
    # Extract questions and buyers from the joined results
    questions_with_buyers = []
    for question, buyer in questions:
        questions_with_buyers.append({
            "question": question,
            "buyer": buyer
        })
    
    context["questions_with_buyers"] = questions_with_buyers
    return templates.TemplateResponse("questions.html", context)

@router.get("/questions/{question_id}", response_class=HTMLResponse)
async def question_detail_page(
    request: Request, 
    question_id: int, 
    db: Session = Depends(get_db)
):
    """Individual question page with answers"""
    context = await get_user_context(request, db)
    
    # Get the question
    question = db.get(DecisionContext, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Get all info offers for this question with seller information
    info_offers_with_sellers = db.exec(
        select(InfoOffer, User, BotSeller)
        .outerjoin(User, InfoOffer.human_seller_id == User.id)
        .outerjoin(BotSeller, InfoOffer.bot_seller_id == BotSeller.id)
        .where(InfoOffer.context_id == question_id)
        .order_by(InfoOffer.created_at.asc())
    ).all()
    
    # Extract info offers and seller info
    info_offers_data = []
    for result in info_offers_with_sellers:
        info_offer, human_seller, bot_seller = result
        
        # Get bot seller owner info if it's a bot seller
        bot_seller_owner = None
        if bot_seller:
            bot_seller_owner = db.get(User, bot_seller.user_id)
        
        info_offers_data.append({
            "info_offer": info_offer,
            "human_seller": human_seller,
            "bot_seller": bot_seller,
            "bot_seller_owner": bot_seller_owner
        })
    
    # Get buyer info to check if current user is the question poster
    buyer = db.get(User, question.buyer_id)
    
    context.update({
        "question": question,
        "info_offers_data": info_offers_data,
        "buyer": buyer,
        "is_question_owner": context["user"] and context["user"].id == question.buyer_id
    })
    
    return templates.TemplateResponse("question_detail.html", context)

@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, db: Session = Depends(get_db)):
    """Users listing page"""
    context = await get_user_context(request, db)
    
    # Get all users
    users = db.exec(select(User)).all()
    
    context["users"] = users
    return templates.TemplateResponse("users.html", context)

@router.get("/api/users/me")
async def get_current_user_api(
    request: Request, 
    db: Session = Depends(get_db)
):
    """Get current user info for API calls"""
    context = await get_user_context(request, db)
    
    if not context["user"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return {
        "id": context["user"].id,
        "username": context["user"].username,
        "email": context["user"].email,
        "buyer_profile": context["user"].buyer_profile is not None,
        "seller_profile": context["user"].seller_profile is not None
    }



@router.get("/users/me", response_class=HTMLResponse)
async def current_user_profile_page(
    request: Request, 
    db: Session = Depends(get_db)
):
    """Current user's own profile page"""
    context = await get_user_context(request, db)
    
    if not context["user"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    current_user = context["user"]
    
    # Get user's questions and answers
    questions = db.exec(
        select(DecisionContext)
        .where(DecisionContext.buyer_id == current_user.id)
        .order_by(DecisionContext.created_at.desc())
    ).all()
    
    answers = []
    if current_user.seller_profile:
        answers = db.exec(
            select(InfoOffer)
            .where(InfoOffer.human_seller_id == current_user.seller_profile.id)
            .order_by(InfoOffer.created_at.desc())
        ).all()
    
    context.update({
        "profile_user": current_user,
        "questions": questions,
        "answers": answers,
        "is_own_profile": True
    })
    
    return templates.TemplateResponse("user_profile.html", context)

@router.get("/users/{user_id}", response_class=HTMLResponse)
async def user_profile_page(
    request: Request, 
    user_id: int, 
    db: Session = Depends(get_db)
):
    """Individual user profile page"""
    context = await get_user_context(request, db)
    
    # Get the user
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's questions and answers
    questions = db.exec(
        select(DecisionContext)
        .where(DecisionContext.buyer_id == user_id)
        .order_by(DecisionContext.created_at.desc())
    ).all()
    
    answers = []
    if user.seller_profile:
        answers = db.exec(
            select(InfoOffer)
            .where(InfoOffer.human_seller_id == user.seller_profile.id)
            .order_by(InfoOffer.created_at.desc())
        ).all()
    
    context.update({
        "profile_user": user,
        "questions": questions,
        "answers": answers,
        "is_own_profile": context["user"] and context["user"].id == user_id
    })
    
    return templates.TemplateResponse("user_profile.html", context)

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """User registration page"""
    context = await get_user_context(request, None)
    return templates.TemplateResponse("register.html", context)



# Form handlers
@router.post("/questions", response_class=HTMLResponse)
async def create_question(
    request: Request,
    query: str = Form(...),
    context_pages: str = Form(""),
    max_budget: float = Form(...),
    priority: int = Form(0),
    db: Session = Depends(get_db)
):
    """Handle new question creation"""
    context = await get_user_context(request, db)
    
    if not context["user"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    current_user = context["user"]
    
    # Parse context_pages from comma-separated string
    context_pages_list = [p.strip() for p in context_pages.split(",") if p.strip()] if context_pages else None
    
    question_data = DecisionContextCreateNonRecursive(
        query=query,
        context_pages=context_pages_list,
        max_budget=max_budget,
        priority=priority
    )
    
    # Create the question using existing logic
    if not current_user.buyer_profile:
        raise HTTPException(status_code=400, detail="User does not have a buyer profile")
    
    if question_data.max_budget > current_user.available_balance:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Deduct max_budget from available_balance
    current_user.available_balance -= question_data.max_budget
    db.add(current_user)
    
    ctx = DecisionContext(
        **question_data.dict(),
        buyer_id=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(ctx)
    db.commit()
    db.refresh(ctx)
    
    # Increment the buyer's query counter
    increment_buyer_query_counter(current_user.buyer_profile, ctx.priority, db)
    
    # Populate inbox for this new context
    recompute_inbox_for_context(ctx, db)
    
    return RedirectResponse(url=f"/questions/{ctx.id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/questions/{question_id}/answers", response_class=HTMLResponse)
async def create_answer(
    request: Request,
    question_id: int,
    private_info: str = Form(...),
    public_info: str = Form(""),
    price: float = Form(0.0),
    db: Session = Depends(get_db)
):
    """Handle new answer creation"""
    context = await get_user_context(request, db)
    
    if not context["user"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    current_user = context["user"]
    
    # Get the context
    ctx = db.get(DecisionContext, question_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Decision context not found")
    
    # Ensure user is a seller
    if not current_user.seller_profile:
        raise HTTPException(status_code=400, detail="User is not a seller")
    
    # Create the info offer
    offer = InfoOffer(
        private_info=private_info,
        public_info=public_info if public_info else None,
        price=price,
        context_id=question_id,
        human_seller_id=current_user.seller_profile.id,
        created_at=datetime.utcnow(),
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    
    # Mark matching inbox items as responded
    matcher_ids = [m.id for m in current_user.seller_profile.matchers]
    inbox_items = db.exec(
        select(MatcherInbox)
        .where(MatcherInbox.decision_context_id == question_id)
        .where(MatcherInbox.matcher_id.in_(matcher_ids))
    ).all()
    for item in inbox_items:
        item.status = "responded"
        db.add(item)
    db.commit()
    
    return RedirectResponse(url=f"/questions/{question_id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/inspect/{question_id}/{answer_id}", response_class=HTMLResponse)
async def inspect_answer(
    request: Request,
    question_id: int,
    answer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user)
):
    """Handle answer inspection"""
    # This would integrate with your existing inspection logic
    # For now, just redirect back to the question
    return RedirectResponse(url=f"/questions/{question_id}", status_code=status.HTTP_303_SEE_OTHER)

# Profile management endpoints
@router.post("/profile/buyer", response_class=HTMLResponse)
async def create_buyer_profile(
    request: Request,
    default_child_llm: str = Form(...),
    db: Session = Depends(get_db)
):
    """Create or update buyer profile"""
    context = await get_user_context(request, db)
    
    if not context["user"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    current_user = context["user"]
    
    from infonomy_server.models import LLMBuyerType
    
    # Create LLMBuyerType instance and convert to dict for JSON storage
    llm_buyer = LLMBuyerType(name=default_child_llm)
    llm_buyer_dict = llm_buyer.dict()
    
    buyer_data = HumanBuyerCreate(
        default_child_llm=llm_buyer_dict
    )
    
    if current_user.buyer_profile:
        # Update existing profile
        current_user.buyer_profile.default_child_llm = llm_buyer_dict
        db.add(current_user.buyer_profile)
    else:
        # Create new profile
        buyer = HumanBuyer(
            default_child_llm=llm_buyer_dict,
            user_id=current_user.id
        )
        db.add(buyer)
        current_user.buyer_profile = buyer
    
    db.commit()
    db.refresh(current_user)
    
    return RedirectResponse(url=f"/users/{current_user.id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/profile/seller", response_class=HTMLResponse)
async def create_seller_profile(
    request: Request,
    db: Session = Depends(get_db)
):
    """Create seller profile"""
    context = await get_user_context(request, db)
    
    if not context["user"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    current_user = context["user"]
    
    # Check if user already has a seller profile
    if current_user.seller_profile:
        raise HTTPException(status_code=400, detail="User already has a seller profile")
    
    # Create the seller profile
    seller = HumanSeller(id=current_user.id)
    db.add(seller)
    db.commit()
    db.refresh(seller)
    
    return RedirectResponse(url=f"/users/{current_user.id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/profile/bot-seller", response_class=HTMLResponse)
async def create_bot_seller(
    request: Request,
    info: str = Form(""),
    price: float = Form(0.0),
    llm_model: str = Form(""),
    llm_prompt: str = Form(""),
    db: Session = Depends(get_db)
):
    """Create bot seller"""
    context = await get_user_context(request, db)
    
    if not context["user"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    current_user = context["user"]
    
    bot_data = BotSellerCreate(
        info=info if info else None,
        price=price if price > 0 else None,
        llm_model=llm_model if llm_model else None,
        llm_prompt=llm_prompt if llm_prompt else None
    )
    
    bot = BotSeller(
        **bot_data.dict(),
        user_id=current_user.id
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    
    return RedirectResponse(url=f"/users/{current_user.id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/profile/matcher", response_class=HTMLResponse)
async def create_matcher(
    request: Request,
    keywords: str = Form(""),
    context_pages: str = Form(""),
    min_max_budget: float = Form(0.0),
    min_inspection_rate: float = Form(0.0),
    min_purchase_rate: float = Form(0.0),
    min_priority: int = Form(0),
    buyer_type: str = Form(""),
    buyer_llm_model: str = Form(""),
    buyer_system_prompt: str = Form(""),
    age_limit: int = Form(0),
    db: Session = Depends(get_db)
):
    """Create matcher for current user's seller profile"""
    context = await get_user_context(request, db)
    
    if not context["user"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    current_user = context["user"]
    
    # Parse comma-separated strings
    keywords_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else None
    context_pages_list = [p.strip() for p in context_pages.split(",") if p.strip()] if context_pages else None
    buyer_llm_model_list = [m.strip() for m in buyer_llm_model.split(",") if m.strip()] if buyer_llm_model else None
    buyer_system_prompt_list = [p.strip() for p in buyer_system_prompt.split(",") if p.strip()] if buyer_system_prompt else None
    
    matcher_data = SellerMatcherCreate(
        keywords=keywords_list,
        context_pages=context_pages_list,
        min_max_budget=min_max_budget,
        min_inspection_rate=min_inspection_rate,
        min_purchase_rate=min_purchase_rate,
        min_priority=min_priority,
        buyer_type=buyer_type if buyer_type else None,
        buyer_llm_model=buyer_llm_model_list,
        buyer_system_prompt=buyer_system_prompt_list,
        age_limit=age_limit if age_limit > 0 else None
    )
    
    if not current_user.seller_profile:
        raise HTTPException(status_code=400, detail="User does not have a seller profile")
    
    matcher = SellerMatcher(
        **matcher_data.dict(),
        human_seller_id=current_user.seller_profile.id
    )
    db.add(matcher)
    db.commit()
    db.refresh(matcher)
    
    # Recompute inbox for this new matcher
    from infonomy_server.utils import recompute_inbox_for_matcher
    recompute_inbox_for_matcher(matcher, db)
    
    return RedirectResponse(url=f"/users/{current_user.id}", status_code=status.HTTP_303_SEE_OTHER) 

@router.post("/profile/bot-matcher", response_class=HTMLResponse)
async def create_bot_matcher(
    request: Request,
    bot_seller_id: int = Form(...),
    keywords: str = Form(""),
    min_max_budget: float = Form(0.0),
    db: Session = Depends(get_db)
):
    """Create matcher for a bot seller"""
    context = await get_user_context(request, db)
    
    if not context["user"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    current_user = context["user"]
    
    # Parse comma-separated keywords
    keywords_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else None
    
    # Verify the bot seller belongs to the current user
    bot_seller = db.get(BotSeller, bot_seller_id)
    if not bot_seller or bot_seller.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Bot seller not found")
    
    matcher_data = SellerMatcherCreate(
        keywords=keywords_list,
        min_max_budget=min_max_budget
    )
    
    matcher = SellerMatcher(
        **matcher_data.dict(),
        bot_seller_id=bot_seller_id
    )
    db.add(matcher)
    db.commit()
    
    return RedirectResponse(url=f"/users/{current_user.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/matcher/{matcher_id}/update", response_class=HTMLResponse)
async def update_matcher(
    matcher_id: int,
    request: Request,
    keywords: str = Form(""),
    context_pages: str = Form(""),
    min_max_budget: float = Form(0.0),
    min_inspection_rate: float = Form(0.0),
    min_purchase_rate: float = Form(0.0),
    min_priority: int = Form(0),
    buyer_type: str = Form(""),
    buyer_llm_model: str = Form(""),
    buyer_system_prompt: str = Form(""),
    age_limit: int = Form(0),
    db: Session = Depends(get_db)
):
    """Update an existing matcher"""
    context = await get_user_context(request, db)
    
    if not context["user"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    current_user = context["user"]
    
    # Get the matcher and verify ownership
    matcher = db.get(SellerMatcher, matcher_id)
    if not matcher or matcher.human_seller_id != current_user.seller_profile.id:
        raise HTTPException(status_code=404, detail="Matcher not found")
    
    # Parse comma-separated strings
    keywords_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else None
    context_pages_list = [p.strip() for p in context_pages.split(",") if p.strip()] if context_pages else None
    buyer_llm_model_list = [m.strip() for m in buyer_llm_model.split(",") if m.strip()] if buyer_llm_model else None
    buyer_system_prompt_list = [p.strip() for p in buyer_system_prompt.split(",") if p.strip()] if buyer_system_prompt else None
    
    # Update matcher fields
    matcher.keywords = keywords_list
    matcher.context_pages = context_pages_list
    matcher.min_max_budget = min_max_budget
    matcher.min_inspection_rate = min_inspection_rate
    matcher.min_purchase_rate = min_purchase_rate
    matcher.min_priority = min_priority
    matcher.buyer_type = buyer_type if buyer_type else None
    matcher.buyer_llm_model = buyer_llm_model_list
    matcher.buyer_system_prompt = buyer_system_prompt_list
    matcher.age_limit = age_limit if age_limit > 0 else None
    
    db.add(matcher)
    db.commit()
    db.refresh(matcher)
    
    # Recompute inbox for this updated matcher
    from infonomy_server.utils import recompute_inbox_for_matcher
    recompute_inbox_for_matcher(matcher, db)
    
    return RedirectResponse(url=f"/users/{current_user.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/matcher/{matcher_id}/delete", response_class=HTMLResponse)
async def delete_matcher(
    matcher_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete a matcher"""
    context = await get_user_context(request, db)
    
    if not context["user"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    current_user = context["user"]
    
    # Get the matcher and verify ownership
    matcher = db.get(SellerMatcher, matcher_id)
    if not matcher or matcher.human_seller_id != current_user.seller_profile.id:
        raise HTTPException(status_code=404, detail="Matcher not found")
    
    # Remove all inbox items for this matcher before deleting it
    from infonomy_server.utils import remove_matcher_from_inboxes
    remove_matcher_from_inboxes(matcher_id, db)
    
    db.delete(matcher)
    db.commit()
    
    return RedirectResponse(url=f"/users/{current_user.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/api-keys", response_class=HTMLResponse)
async def update_api_keys(
    request: Request,
    key_names: List[str] = Form(...),
    key_values: List[str] = Form(...),
    db: Session = Depends(get_db)
):
    """Update user's API keys"""
    context = await get_user_context(request, db)
    
    if not context["user"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    current_user = context["user"]
    
    # Build API keys dictionary from form data
    api_keys = {}
    for i, key_name in enumerate(key_names):
        if key_name.strip() and i < len(key_values):
            key_value = key_values[i].strip()
            if key_value:  # Only add non-empty keys
                api_keys[key_name.strip()] = key_value
    
    # Update user's API keys
    current_user.api_keys = api_keys
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    return RedirectResponse(url=f"/users/{current_user.id}", status_code=status.HTTP_303_SEE_OTHER)
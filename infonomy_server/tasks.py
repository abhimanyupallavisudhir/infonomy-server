import time
from datetime import datetime
from typing import List, Optional
from sqlmodel import Session, select

# Import the Celery app to ensure correct configuration is used
from celery_app import celery

from infonomy_server.database import engine
from infonomy_server.utils import (
    recompute_inbox_for_context,
    increment_buyer_inspected_counter,
    increment_buyer_purchased_counter
)
from infonomy_server.llm import call_llm
from infonomy_server.models import (
    DecisionContext,
    InfoOffer,
    HumanBuyer,
    SellerMatcher,
    BotSeller,
    User,
    LLMBuyerType,
    Inspection,
)
from infonomy_server.logging_config import (
    celery_logger, bot_sellers_logger, 
    log_celery_task, log_business_event, 
    log_function_error
)


@celery.task(bind=True)
def process_bot_sellers_for_context(self, context_id: int):
    """
    Process all BotSellers that have matchers matching a DecisionContext.
    This task is called when a DecisionContext is submitted to seller inboxes.
    """
    
    # Log task start
    task_id = self.request.id if hasattr(self.request, 'id') else 'unknown'
    log_celery_task(celery_logger, "process_bot_sellers_for_context", task_id, {
        "context_id": context_id
    })
    
    session = Session(engine)
    
    try:
        # Get the decision context
        context = session.get(DecisionContext, context_id)
        if not context:
            log_business_event(celery_logger, "context_not_found", parameters={
                "context_id": context_id
            })
            return
        
        # Find all BotSeller matchers that match this context
        bot_matchers = session.exec(
            select(SellerMatcher)
            .where(SellerMatcher.bot_seller_id.isnot(None))
        ).all()
        
        # Process each matching BotSeller
        processed_count = 0
        for matcher in bot_matchers:
            try:
                # Check if this matcher actually matches the context
                if not _matcher_matches_context(matcher, context, session):
                    continue
                
                # Get the BotSeller
                bot_seller = session.get(BotSeller, matcher.bot_seller_id)
                if not bot_seller:
                    continue
                
                # Generate InfoOffer based on BotSeller type
                info_offer = _generate_bot_seller_offer(bot_seller, context, session)
                if info_offer:
                    session.add(info_offer)
                    processed_count += 1
                    
                    log_business_event(bot_sellers_logger, "bot_seller_offer_created", user_id=bot_seller.user_id, parameters={
                        "bot_seller_id": bot_seller.id,
                        "context_id": context_id,
                        "info_offer_id": info_offer.id,
                        "matcher_id": matcher.id,
                        "offer_price": info_offer.price,
                        "bot_seller_type": "fixed_text" if bot_seller.info else "llm"
                    })
            except Exception as e:
                # Log error but continue processing other bots
                log_function_error(bot_sellers_logger, "process_bot_seller_matcher", e, {
                    "matcher_id": matcher.id,
                    "context_id": context_id
                })
                continue
        
        if processed_count > 0:
            session.commit()
            log_business_event(celery_logger, "bot_sellers_processing_complete", parameters={
                "context_id": context_id,
                "processed_count": processed_count,
                "total_matchers": len(bot_matchers)
            })
        
    except Exception as e:
        session.rollback()
        log_function_error(celery_logger, "process_bot_sellers_for_context", e, {
            "context_id": context_id
        })
        raise e
    finally:
        session.close()


def _matcher_matches_context(matcher: SellerMatcher, context: DecisionContext, session: Session) -> bool:
    """Check if a matcher matches a decision context"""
    
    buyer = session.get(HumanBuyer, context.buyer_id)
    if not buyer:
        return False
    
    # Check numeric filters
    if context.max_budget < matcher.min_max_budget:
        return False
    if context.priority < matcher.min_priority:
        return False
    
    # Check buyer type
    if matcher.buyer_type and matcher.buyer_type != "human_buyer":
        return False
    
    # Check rates
    irate = buyer.inspection_rate.get(context.priority, 0.0)
    prate = buyer.purchase_rate.get(context.priority, 0.0)
    if irate < matcher.min_inspection_rate or prate < matcher.min_purchase_rate:
        return False
    
    # Check keywords
    if matcher.keywords is not None:
        text = (context.query or "").lower()
        if not any(kw.lower() in text for kw in matcher.keywords):
            return False
    
    # Check context pages
    if matcher.context_pages is not None:
        pages = context.context_pages or []
        if not any(p in pages for p in matcher.context_pages):
            return False
    
    # Check age limit
    if matcher.age_limit is not None:
        age_seconds = (datetime.utcnow() - context.created_at).total_seconds()
        if age_seconds > matcher.age_limit:
            return False
    
    return True


def _generate_bot_seller_offer(bot_seller: BotSeller, context: DecisionContext, session: Session) -> Optional[InfoOffer]:
    """Generate an InfoOffer from a given context"""
    
    if bot_seller.info and bot_seller.price is not None:
        # Fixed info bot
        private_info = bot_seller.info
        public_info = f"Fixed information from BotSeller {bot_seller.id}"
        price = bot_seller.price  # Use the price set on the BotSeller
    elif bot_seller.llm_model and bot_seller.llm_prompt:
        # LLM bot - call the LLM to generate info
        try:
            private_info, public_info, llm_price = _call_bot_seller_llm(bot_seller, context)
            # Use the price returned by the LLM, but ensure it's within budget
            price = min(llm_price, context.max_budget)
        except Exception:
            # If LLM call fails, don't create an offer
            return None
    else:
        return None
    
    return InfoOffer(
        bot_seller_id=bot_seller.id,
        context_id=context.id,
        private_info=private_info,
        public_info=public_info,
        price=price,
        created_at=datetime.utcnow(),
        inspected=False,
        purchased=False
    )


def _call_bot_seller_llm(bot_seller: BotSeller, context: DecisionContext) -> tuple[str, str, float]:
    """Call the LLM for a BotSeller to generate information with structured response"""
    
    # Create a simple prompt for the bot seller
    prompt = f"""
You are a BotSeller in an information market. A buyer is looking for information related to:

Query: {context.query or 'No specific query'}
Context Pages: {context.context_pages or 'No specific context pages'}
Priority: {context.priority}
Max Budget: {context.max_budget}

Please provide helpful, relevant information based on your knowledge and the context provided.

{bot_seller.llm_prompt}

You must respond with:
1. private_info: The actual information the buyer will receive after purchase
2. public_info: A brief, public description of what you're offering (visible before purchase)
3. price: A reasonable price for this information (consider the value and buyer's budget)

Make sure the price is reasonable and within the buyer's budget of {context.max_budget}.
"""
    
    try:
        # Get configuration values
        try:
            from infonomy_server.config import DEFAULT_LLM_MAX_TOKENS, DEFAULT_LLM_TEMPERATURE
        except ImportError:
            DEFAULT_LLM_MAX_TOKENS = 500
            DEFAULT_LLM_TEMPERATURE = 0.7
        
        # Create a response model for structured output
        from pydantic import BaseModel
        
        class BotSellerResponse(BaseModel):
            private_info: str
            public_info: str
            price: float
        
        # Get the user to use their API keys
        from infonomy_server.database import engine
        from sqlmodel import Session
        from infonomy_server.models import User
        
        session = Session(engine)
        try:
            user = session.get(User, bot_seller.user_id)
        finally:
            session.close()
        
        # Use user's API keys if available, otherwise fall back to server defaults
        api_keys = user.api_keys if user and user.api_keys else {}
        
        # Import the context manager and use it
        from infonomy_server.utils import temporary_api_keys
        from infonomy_server.llm import CLIENT
        
        with temporary_api_keys(api_keys):
            import os
            start_time = time.time()
            
            # Get all environment variables (within the context manager)
            env_vars = {}
            for key_name, key_value in os.environ.items():
                if key_value and len(key_value) > 12:
                    # Truncate long values for security (show first 8 and last 4 characters)
                    env_vars[key_name] = f"{key_value[:8]}...{key_value[-4:]}"
                else:
                    env_vars[key_name] = key_value
            
            # Prepare messages for logging (truncate content for readability)
            def truncate_content(content, max_length=200):
                if isinstance(content, str) and len(content) > max_length:
                    return content[:max_length] + "..."
                return content
            
            messages = [{"role": "user", "content": prompt}]
            logged_messages = []
            for msg in messages:
                logged_msg = {
                    "role": msg.get("role", "unknown"),
                    "content": truncate_content(msg.get("content", ""))
                }
                logged_messages.append(logged_msg)
            
            try:
                response = CLIENT.chat.completions.create(
                    model=bot_seller.llm_model,
                    response_model=BotSellerResponse,
                    messages=messages,
                    max_tokens=DEFAULT_LLM_MAX_TOKENS,
                    temperature=DEFAULT_LLM_TEMPERATURE
                )
                end_time = time.time()
                
                # Log successful LLM call
                from infonomy_server.logging_config import log_llm_call
                log_llm_call(bot_sellers_logger, bot_seller.llm_model, len(prompt), 
                            len(str(response)), end_time - start_time, {
                                "bot_seller_id": bot_seller.id,
                                "context_id": context.id,
                                "user_id": bot_seller.user_id,
                                "status": "success",
                                "messages": logged_messages,
                                "env_vars": env_vars
                            })
            except Exception as e:
                end_time = time.time()
                
                # Log failed LLM call
                from infonomy_server.logging_config import log_llm_call
                log_llm_call(bot_sellers_logger, bot_seller.llm_model, len(prompt), 
                            0, end_time - start_time, {
                                "bot_seller_id": bot_seller.id,
                                "context_id": context.id,
                                "user_id": bot_seller.user_id,
                                "status": "failed",
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "messages": logged_messages,
                                "env_vars": env_vars
                            })
                # Re-raise the exception
                raise
        
        return response.private_info, response.public_info, response.price
        
    except Exception as e:
        # Log the error
        log_function_error(bot_sellers_logger, "_generate_bot_seller_offer", e, {
            "bot_seller_id": bot_seller.id,
            "context_id": context.id,
            "user_id": bot_seller.user_id
        })
        # Return fallback values if LLM call fails
        fallback_info = f"Error generating information: {str(e)}"
        return fallback_info, "Information temporarily unavailable", 0.0


@celery.task(bind=True)
def inspect_task(
    self,
    inspection_id: int,
    depth=0,
    breadth=0,
    max_depth=3,
    max_breadth=3,
) -> List[int]:
    """
    Inspection system with child/brother inspection pattern:
    1) Load inspection and its InfoOffers
    2) Call LLM with inspection attributes and known_info=[]
    3) If LLM chooses offers: return them and update inspection.purchased and user.purchased_info_offers
    4) If LLM creates child context: create child inspection, wait for offers, recurse
    5) Create younger brother inspection with expanded known_offers and breadth+1
    6) Return whatever the brother inspection returns
    """
    
    # Log task start
    task_id = self.request.id if hasattr(self.request, 'id') else 'unknown'
    log_celery_task(celery_logger, "inspect_task", task_id, {
        "inspection_id": inspection_id,
        "depth": depth,
        "breadth": breadth,
        "max_depth": max_depth,
        "max_breadth": max_breadth,
    })
    
    session = Session(engine)
    
    try:
        if depth >= max_depth or breadth >= max_breadth:
            # If this is a top-level inspection and we're hitting limits, restore the max_budget to available_balance
            if depth == 0:
                inspection = session.get(Inspection, inspection_id)
                if inspection:
                    ctx = inspection.decision_context
                    user = session.get(User, inspection.buyer_id)
                    if ctx and user:
                        # Restore the max_budget to available_balance since no purchases were made
                        user.available_balance += ctx.max_budget
                        session.add(user)
                        session.commit()
                    return inspection.purchased
            return []

        # Load inspection and related data
        inspection = session.get(Inspection, inspection_id)
        if not inspection:
            log_business_event(celery_logger, "inspection_not_found", parameters={
                "inspection_id": inspection_id
            })
            return []

        ctx = inspection.decision_context
        buyer = session.get(HumanBuyer, inspection.buyer_id)
        user = session.get(User, inspection.buyer_id)
        
        if not ctx or not buyer or not user:
            return inspection.purchased

        # 1) Fetch InfoOffers associated with this inspection
        offers: List[InfoOffer] = inspection.info_offers

        if not offers:
            # no offers to inspect → finish
            # If this is a top-level inspection and we're done, restore the max_budget to available_balance
            if depth == 0:
                # Restore the max_budget to available_balance since no purchases were made
                user.available_balance += ctx.max_budget
                session.add(user)
                session.commit()
            
            return inspection.purchased

        # 2) Call LLM with inspection attributes and known_info=[]
        chosen_ids, child_ctx = call_llm(
            context=ctx, 
            offers=offers, 
            known_info=[],  # Always empty as per specification
            buyer=LLMBuyerType(**buyer.default_child_llm),
            user=user
        )

        # Increment the buyer's inspected counter for this priority level
        # Only increment once per context, not per offer
        # AND only for the original context (depth=0), not recursive child contexts
        if depth == 0:
            increment_buyer_inspected_counter(buyer, ctx.priority, session)

        # 3a) If LLM picked any offers → "buy" them
        if chosen_ids:
            # Update inspection.purchased
            inspection.purchased.extend(chosen_ids)
            
            # Update user.purchased_info_offers
            for offer_id in chosen_ids:
                if offer_id not in user.purchased_info_offers:
                    user.purchased_info_offers.append(offer_id)
            
            # Increment the buyer's purchased counter for this priority level
            # Only increment once per context, not per offer
            # AND only for the original context (depth=0), not recursive child contexts
            if depth == 0:
                increment_buyer_purchased_counter(buyer, ctx.priority, session)
                
                # Handle balance logic for top-level contexts only
                # Calculate total cost of purchased offers
                total_cost = sum(off.price for off in offers if off.id in chosen_ids)
                # Deduct from actual balance
                user.balance -= total_cost
                # Restore the max_budget to available_balance
                user.available_balance += ctx.max_budget
                session.add(user)
            
            session.add(inspection)
            session.commit()
            
            # Return the chosen offers
            return chosen_ids

        # 3b) If LLM returned an empty list *but* wants more info
        if child_ctx:
            # create a new DecisionContext row
            session.add(child_ctx)
            session.commit()
            session.refresh(child_ctx)

            # Update the current inspection to reference the child context
            inspection.child_context_id = child_ctx.id
            session.add(inspection)

            # notify sellers via your inbox‑recompute helper
            recompute_inbox_for_context(child_ctx, session)

            # Process BotSellers immediately
            try:
                process_bot_sellers_for_context.delay(child_ctx.id)
            except Exception as e:
                print(f"Warning: Failed to trigger BotSeller processing: {str(e)}")
                # Continue with the inspection process even if BotSeller processing fails

            # wait (poll) until InfoOffers appear with a time limit instead of count
            start_time = time.time()
            
            try:
                from infonomy_server.config import (
                    BOTSELLER_TIMEOUT_SECONDS,
                    BOTSELLER_MAX_WAIT_TIME,
                    BOTSELLER_POLL_INTERVAL_FAST,
                    BOTSELLER_POLL_INTERVAL_SLOW
                )
            except ImportError:
                # Fallback to default values if config is not available
                BOTSELLER_TIMEOUT_SECONDS = 30
                BOTSELLER_MAX_WAIT_TIME = 60
                BOTSELLER_POLL_INTERVAL_FAST = 1
                BOTSELLER_POLL_INTERVAL_SLOW = 3
            
            while True:
                count = session.exec(
                    select(InfoOffer)
                    .where(InfoOffer.context_id == child_ctx.id)
                ).count()
                
                elapsed_time = time.time() - start_time
                
                # Stop waiting if we have offers or if timeout is reached
                if count > 0 or elapsed_time > BOTSELLER_MAX_WAIT_TIME:
                    break
                
                # For BotSellers, we expect faster response, so check more frequently early on
                if elapsed_time < BOTSELLER_TIMEOUT_SECONDS:
                    time.sleep(BOTSELLER_POLL_INTERVAL_FAST)  # Check every 1 second for BotSellers
                else:
                    time.sleep(BOTSELLER_POLL_INTERVAL_SLOW)  # Check every 3 seconds for human sellers
            
            # Create a child inspection for the child context
            child_inspection = Inspection(
                decision_context_id=child_ctx.id,
                buyer_id=inspection.buyer_id,
                known_offers=inspection.known_offers.copy(),  # Inherit known_offers
                created_at=datetime.utcnow()
            )
            session.add(child_inspection)
            session.commit()
            session.refresh(child_inspection)

            # Associate all InfoOffers from the child context with the child inspection
            child_offers = session.exec(
                select(InfoOffer).where(InfoOffer.context_id == child_ctx.id)
            ).all()
            for offer in child_offers:
                child_inspection.info_offers.append(offer)
            session.add(child_inspection)
            session.commit()
            
            # Recurse into the child inspection with depth+1
            child_purchased = inspect_task(
                inspection_id=child_inspection.id,
                depth=depth + 1,
                breadth=breadth,
                max_depth=max_depth,
                max_breadth=max_breadth
            )
            
            # Append child purchases to current purchased list (but don't process them)
            current_purchased = inspection.purchased + child_purchased
            
            # Create younger brother inspection with expanded known_offers and breadth+1
            brother_inspection = Inspection(
                decision_context_id=ctx.id,
                buyer_id=inspection.buyer_id,
                known_offers=inspection.known_offers + current_purchased,  # Expand known_offers
                elder_brother_id=inspection.id,
                created_at=datetime.utcnow()
            )
            session.add(brother_inspection)
            session.commit()
            session.refresh(brother_inspection)

            # Associate the same InfoOffers with the brother inspection
            for offer in offers:
                brother_inspection.info_offers.append(offer)
            session.add(brother_inspection)
            session.commit()

            # Update the current inspection to reference its younger brother
            inspection.younger_brother_id = brother_inspection.id
            session.add(inspection)
            session.commit()
            
            # Recurse into the brother inspection with breadth+1
            return inspect_task(
                inspection_id=brother_inspection.id,
                depth=depth,
                breadth=breadth + 1,
                max_depth=max_depth,
                max_breadth=max_breadth
            )

        # 4) Nothing to buy and no child → we're done
        # If this is a top-level inspection and we're done, restore the max_budget to available_balance
        if depth == 0:
            # Restore the max_budget to available_balance since no purchases were made
            user.available_balance += ctx.max_budget
            session.add(user)
            session.commit()
        
        return inspection.purchased
        
    except Exception as e:
        # Log the error
        log_function_error(celery_logger, "inspect_task", e, {
            "inspection_id": inspection_id,
            "depth": depth,
            "breadth": breadth,
            "task_id": self.request.id if hasattr(self.request, 'id') else 'unknown'
        })
        # Re-raise the exception so Celery can handle it
        raise
    finally:
        session.close()

import time
from datetime import datetime, timedelta
from typing import List, Optional
from celery import shared_task
from sqlmodel import Session, select

from infonomy_server.database import engine
from infonomy_server.utils import (
    recompute_inbox_for_context,
    increment_buyer_inspected_counter,
    increment_buyer_purchased_counter
)
from infonomy_server.llm import call_llm, completion  # your wrapper around the child‐LLM
from infonomy_server.models import (
    DecisionContext,
    InfoOffer,
    HumanBuyer,
    SellerMatcher,
    MatcherInbox,
    BotSeller,
    User,
)


@shared_task
def process_bot_sellers_for_context(context_id: int):
    """
    Process all BotSellers that have matchers matching a DecisionContext.
    This task is called when a DecisionContext is submitted to seller inboxes.
    """
    
    session = Session(engine)
    
    try:
        # Get the decision context
        context = session.get(DecisionContext, context_id)
        if not context:
            return
        
        # Find all BotSeller matchers that match this context
        bot_matchers = session.exec(
            select(SellerMatcher)
            .where(SellerMatcher.seller_type == "bot_seller")
        ).all()
        
        # Process each matching BotSeller
        processed_count = 0
        for matcher in bot_matchers:
            try:
                # Check if this matcher actually matches the context
                if not _matcher_matches_context(matcher, context, session):
                    continue
                
                # Get the BotSeller
                bot_seller = session.get(BotSeller, matcher.seller_id)
                if not bot_seller:
                    continue
                
                # Generate InfoOffer based on BotSeller type
                info_offer = _generate_bot_seller_offer(bot_seller, context, session)
                if info_offer:
                    session.add(info_offer)
                    processed_count += 1
            except Exception as e:
                # Log error but continue processing other bots
                print(f"Error processing BotSeller matcher {matcher.id}: {str(e)}")
                continue
        
        if processed_count > 0:
            session.commit()
            print(f"Processed {processed_count} BotSellers for context {context_id}")
        
    except Exception as e:
        session.rollback()
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
        except Exception as e:
            # If LLM call fails, don't create an offer
            return None
    else:
        return None
    
    return InfoOffer(
        seller_id=bot_seller.id,
        seller_type="bot_seller",
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
            response = CLIENT.chat.completions.create(
                model=bot_seller.llm_model,
                response_model=BotSellerResponse,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=DEFAULT_LLM_MAX_TOKENS,
                temperature=DEFAULT_LLM_TEMPERATURE
            )
        
        return response.private_info, response.public_info, response.price
        
    except Exception as e:
        print(f"Error calling LLM for BotSeller {bot_seller.id}: {str(e)}")
        # Return fallback values if LLM call fails
        fallback_info = f"Error generating information: {str(e)}"
        return fallback_info, "Information temporarily unavailable", 0.0


@shared_task(bind=True)
def inspect_task(
    self,
    context_id: int,
    buyer_id: int,
    purchased: Optional[List[int]] = None,
    depth=0,
    breadth=0,
    max_depth=3,
    max_breadth=3,
) -> List[int]:
    """
    1) Load the context & all current InfoOffers
    2) Call LLM to choose offers or ask for a child context
    3) If offers chosen: record them, remove from available, recurse
    4) If child context requested: create it, recompute inbox, wait for offers, recurse
    5) When done: return full list of purchased offer IDs
    TODO: Right now this inspects *all* info offers, we might want to customize that later.
    """
    if purchased is None:
        purchased = []
    
    session = Session(engine)
    
    try:
        if depth >= max_depth or breadth >= max_breadth:
            # If this is a top-level context and we're hitting limits, restore the max_budget to available_balance
            if depth == 0:
                # Load context & buyer to get the max_budget
                ctx = session.get(DecisionContext, context_id)
                buyer = session.get(HumanBuyer, buyer_id)
                if ctx and buyer:
                    user = session.get(User, buyer.user_id)
                    if user:
                        # Restore the max_budget to available_balance since no purchases were made
                        user.available_balance += ctx.max_budget
                        session.add(user)
                        session.commit()
            
            return purchased

        # Load context & buyer
        ctx = session.get(DecisionContext, context_id)
        buyer = session.get(HumanBuyer, buyer_id)
        if not ctx or not buyer:
            return purchased or []

        # 1) Fetch all available InfoOffers for this ctx
        # not sure about whether we should let them re-inspect inspected offers
        # but for now we do not TODO
        offers: List[InfoOffer] = session.exec(
            select(InfoOffer)
            .where(InfoOffer.context_id == context_id)
            .where(InfoOffer.purchased == False)
            .where(InfoOffer.inspected == False)
        ).all()

        if not offers:
            # no more offers to inspect → finish
            # If this is a top-level context and we're done, restore the max_budget to available_balance
            if depth == 0:
                user = session.get(User, buyer.user_id)
                if user:
                    # Restore the max_budget to available_balance since no purchases were made
                    user.available_balance += ctx.max_budget
                    session.add(user)
                    session.commit()
            
            return purchased

        # just for the LLM
        known_info: List[InfoOffer] = []
        for p in purchased:
            off = session.get(InfoOffer, p)
            if off:
                known_info.append(off)

        # 2) Invoke your LLM with full, private offer data
        #    Here we assume `call_llm` returns (chosen_offer_ids, child_ctx)
        
        # Get the user to pass their API keys to the LLM
        user = session.get(User, buyer.user_id)
        
        chosen_ids, child_ctx = call_llm(
            context=ctx, 
            offers=offers, 
            known_info=known_info, 
            buyer=buyer.default_child_llm,
            user=user
        )

        for offer in offers:
            offer.inspected = True

        # Increment the buyer's inspected counter for this priority level
        # Only increment once per context, not per offer
        # AND only for the original context (depth=0), not recursive child contexts
        if depth == 0:
            increment_buyer_inspected_counter(buyer, ctx.priority, session)

        # 3a) If LLM picked any offers → "buy" them
        if chosen_ids:
            for oid in chosen_ids:
                off = session.get(InfoOffer, oid)
                off.purchased = True
            purchased.extend(chosen_ids)
            
            # Increment the buyer's purchased counter for this priority level
            # Only increment once per context, not per offer
            # AND only for the original context (depth=0), not recursive child contexts
            if depth == 0:
                increment_buyer_purchased_counter(buyer, ctx.priority, session)
                
                # Handle balance logic for top-level contexts only
                # Get the user to update their balance
                user = session.get(User, buyer.user_id)
                if user:
                    # Calculate total cost of purchased offers
                    total_cost = sum(off.price for off in offers if off.id in chosen_ids)
                    # Deduct from actual balance
                    user.balance -= total_cost
                    # Restore the max_budget to available_balance
                    user.available_balance += ctx.max_budget
                    session.add(user)
            
            # # remove those offers from future consideration
            # session.exec(
            #     select(InfoOffer).where(InfoOffer.id.in_(chosen_ids))
            # ).scalars().delete(synchronize_session="fetch")
            session.commit()
            # recurse on the same context
            return inspect_task(
                context_id=context_id,
                buyer_id=buyer_id,
                purchased=purchased,
                depth=depth,
                breadth=breadth + 1,
                max_depth=max_depth,
                max_breadth=max_breadth,
            )

        # 3b) If LLM returned an empty list *but* wants more info
        if child_ctx:
            # create a new DecisionContext row
            session.add(child_ctx)
            session.commit()
            session.refresh(child_ctx)

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
                    .where(InfoOffer.purchased == False)
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
            
            # recurse into the child context
            # don't need to include a selection of the offers here,
            # because again we are inspecting all offers
            return inspect_task(
                context_id=child_ctx.id,
                buyer_id=buyer_id,
                purchased=purchased,
                depth=depth + 1,
                breadth=breadth,
                max_depth=max_depth,
                max_breadth=max_breadth,
            )

        # 4) Nothing to buy and no child → we're done
        # If this is a top-level context and we're done, restore the max_budget to available_balance
        if depth == 0:
            user = session.get(User, buyer.user_id)
            if user:
                # Restore the max_budget to available_balance since no purchases were made
                user.available_balance += ctx.max_budget
                session.add(user)
                session.commit()
        
        return purchased
        
    finally:
        session.close()

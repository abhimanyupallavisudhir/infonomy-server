from typing import List
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends
from sqlmodel import Session, select
from infonomy_server.database import get_db
from infonomy_server.models import (
    User,
    HumanBuyer,
    DecisionContext,
    SellerMatcher,
    MatcherInbox,
    BotSeller,
)
from infonomy_server.auth import current_active_user
import os
from contextlib import contextmanager


def get_context_for_buyer(
    context_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_active_user),
) -> DecisionContext:
    """
    Dependency that loads a DecisionContext, 404s if missing,
    403s if the current user doesn’t own it.
    """
    ctx = db.get(DecisionContext, context_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Decision context not found")
    if ctx.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return ctx


def recompute_inbox_for_context(ctx: DecisionContext, db: Session):
    """
    Delete any existing inbox items for this context,
    re‑run the matcher logic, and insert fresh MatcherInbox rows.
    """
    # 1) clear old items
    db.query(MatcherInbox).filter(MatcherInbox.decision_context_id == ctx.id).delete()
    db.commit()

    # 2) find candidate matchers by numeric filters
    stmt = (
        select(SellerMatcher)
        .where(ctx.max_budget >= SellerMatcher.min_max_budget)
        .where(ctx.priority >= SellerMatcher.min_priority)
    )
    all_matchers: List[SellerMatcher] = db.exec(stmt).all()

    # 3) full Python matching (rates, keywords, contexts, buyer_type)
    buyer: HumanBuyer = ctx.buyer
    new_items: List[MatcherInbox] = []
    for m in all_matchers:
        # buyer_type
        if m.buyer_type and m.buyer_type != "human_buyer":
            continue

        # rates
        irate = buyer.inspection_rate.get(ctx.priority, 0.0)
        prate = buyer.purchase_rate.get(ctx.priority, 0.0)
        if irate < m.min_inspection_rate or prate < m.min_purchase_rate:
            continue

        # keywords
        if m.keywords is not None:
            text = (ctx.query or "").lower()
            if not any(kw.lower() in text for kw in m.keywords):
                continue

        # contexts
        if m.context_pages is not None:
            pages = ctx.context_pages or []
            if not any(p in pages for p in m.context_pages):
                continue
        now = datetime.utcnow()
        new_items.append(
            MatcherInbox(
                matcher_id=m.id,
                decision_context_id=ctx.id,
                status="new",
                created_at=now,
                expires_at=now + timedelta(seconds=m.age_limit),
            )
        )

    # 4) bulk‐insert fresh inbox items
    if new_items:
        db.add_all(new_items)
        db.commit()
    
    # 5) Trigger BotSeller processing for this context
    from infonomy_server.tasks import process_bot_sellers_for_context
    process_bot_sellers_for_context.delay(ctx.id)


def recompute_inbox_for_matcher(matcher: SellerMatcher, db: Session):
    """
    Efficiently recompute inbox items for a specific matcher.
    This is called when a matcher is created, updated, or deleted.
    """
    # 1) Clear existing inbox items for this matcher
    db.query(MatcherInbox).filter(MatcherInbox.matcher_id == matcher.id).delete()
    
    # 2) Find all decision contexts that this matcher should match against
    stmt = (
        select(DecisionContext)
        .where(DecisionContext.max_budget >= matcher.min_max_budget)
        .where(DecisionContext.priority >= matcher.min_priority)
    )
    candidate_contexts = db.exec(stmt).all()
    
    # 3) Apply full matching logic to each candidate context
    new_items = []
    for ctx in candidate_contexts:
        # Skip if this is a recursive context (should be handled by parent context)
        if ctx.parent_id is not None:
            continue
            
        buyer = ctx.buyer
        
        # buyer_type check
        if matcher.buyer_type and matcher.buyer_type != "human_buyer":
            continue
            
        # rates check
        irate = buyer.inspection_rate.get(ctx.priority, 0.0)
        prate = buyer.purchase_rate.get(ctx.priority, 0.0)
        if irate < matcher.min_inspection_rate or prate < matcher.min_purchase_rate:
            continue
            
        # keywords check
        if matcher.keywords is not None:
            text = (ctx.query or "").lower()
            if not any(kw.lower() in text for kw in matcher.keywords):
                continue
                
        # contexts check
        if matcher.context_pages is not None:
            pages = ctx.context_pages or []
            if not any(p in pages for p in matcher.context_pages):
                continue
                
        # age limit check (CRITICAL: was missing!)
        if matcher.age_limit is not None:
            age_seconds = (datetime.utcnow() - ctx.created_at).total_seconds()
            if age_seconds > matcher.age_limit:
                continue
                
        # Create inbox item
        now = datetime.utcnow()
        new_items.append(
            MatcherInbox(
                matcher_id=matcher.id,
                decision_context_id=ctx.id,
                status="new",
                created_at=now,
                expires_at=now + timedelta(seconds=matcher.age_limit),
            )
        )
    
    # 4) Bulk insert new inbox items
    if new_items:
        db.add_all(new_items)
        db.commit()
    
    # 5) Trigger BotSeller processing for affected contexts if this is a bot seller matcher
    if matcher.seller_type == "bot_seller":
        from infonomy_server.tasks import process_bot_sellers_for_context
        for ctx in candidate_contexts:
            if ctx.parent_id is None:  # Only process non-recursive contexts
                process_bot_sellers_for_context.delay(ctx.id)


def recompute_all_inboxes(db: Session):
    """
    Recompute all inboxes for all decision contexts.
    This is useful for bulk operations or when the system needs to be resynchronized.
    Use sparingly as it can be expensive.
    """
    # Get all non-recursive decision contexts
    stmt = select(DecisionContext).where(DecisionContext.parent_id.is_(None))
    contexts = db.exec(stmt).all()
    
    # Clear all existing inbox items
    db.query(MatcherInbox).delete()
    db.commit()
    
    # Recompute inbox for each context
    for ctx in contexts:
        recompute_inbox_for_context(ctx, db)


def remove_matcher_from_inboxes(matcher_id: int, db: Session):
    """
    Remove all inbox items for a specific matcher.
    This is called when a matcher is deleted.
    """
    db.query(MatcherInbox).filter(MatcherInbox.matcher_id == matcher_id).delete()
    db.commit()


def get_affected_decision_contexts_for_matcher(matcher: SellerMatcher, db: Session) -> List[DecisionContext]:
    """
    Get all decision contexts that would be affected by a change to this matcher.
    This is useful for understanding the scope of impact before making changes.
    """
    stmt = (
        select(DecisionContext)
        .where(DecisionContext.max_budget >= matcher.min_max_budget)
        .where(DecisionContext.priority >= matcher.min_priority)
        .where(DecisionContext.parent_id.is_(None))  # Only non-recursive contexts
    )
    return db.exec(stmt).all()


def bulk_update_matcher_inboxes(matcher_ids: List[int], db: Session):
    """
    Efficiently update inboxes for multiple matchers at once.
    This is useful when multiple matchers are updated simultaneously.
    """
    # Get all the matchers
    stmt = select(SellerMatcher).where(SellerMatcher.id.in_(matcher_ids))
    matchers = db.exec(stmt).all()
    
    # Clear inbox items for all affected matchers
    db.query(MatcherInbox).filter(MatcherInbox.matcher_id.in_(matcher_ids)).delete()
    db.commit()
    
    # Recompute inbox for each matcher
    for matcher in matchers:
        recompute_inbox_for_matcher(matcher, db)


def get_matcher_impact_summary(matcher: SellerMatcher, db: Session) -> dict:
    """
    Get a summary of the impact of a matcher change.
    This helps users understand how many decision contexts will be affected.
    """
    affected_contexts = get_affected_decision_contexts_for_matcher(matcher, db)
    
    # Count contexts by priority
    priority_counts = {}
    for ctx in affected_contexts:
        priority = ctx.priority
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
    
    # Count contexts by budget range
    budget_ranges = {
        "low": 0,      # 0-10
        "medium": 0,   # 10-50  
        "high": 0      # 50+
    }
    
    for ctx in affected_contexts:
        if ctx.max_budget <= 10:
            budget_ranges["low"] += 1
        elif ctx.max_budget <= 50:
            budget_ranges["medium"] += 1
        else:
            budget_ranges["high"] += 1
    
    return {
        "total_affected_contexts": len(affected_contexts),
        "priority_distribution": priority_counts,
        "budget_distribution": budget_ranges,
        "matcher_criteria": {
            "min_budget": matcher.min_max_budget,
            "min_priority": matcher.min_priority,
            "keywords": matcher.keywords,
            "context_pages": matcher.context_pages,
            "buyer_type": matcher.buyer_type
        }
    }


def cleanup_expired_inbox_items(db: Session):
    """
    Remove expired inbox items to keep the database clean.
    This should be run periodically (e.g., via a cron job).
    """
    now = datetime.utcnow()
    expired_count = db.query(MatcherInbox).filter(MatcherInbox.expires_at < now).delete()
    db.commit()
    return expired_count


def get_inbox_statistics(db: Session) -> dict:
    """
    Get statistics about the current inbox state.
    Useful for monitoring and debugging.
    """
    total_inbox_items = db.query(MatcherInbox).count()
    new_items = db.query(MatcherInbox).filter(MatcherInbox.status == "new").count()
    ignored_items = db.query(MatcherInbox).filter(MatcherInbox.status == "ignored").count()
    responded_items = db.query(MatcherInbox).filter(MatcherInbox.status == "responded").count()
    
    # Count by matcher type
    human_matcher_items = db.query(MatcherInbox).join(SellerMatcher).filter(
        SellerMatcher.human_seller_id.isnot(None)
    ).count()
    bot_matcher_items = db.query(MatcherInbox).join(SellerMatcher).filter(
        SellerMatcher.bot_seller_id.isnot(None)
    ).count()
    
    return {
        "total_inbox_items": total_inbox_items,
        "by_status": {
            "new": new_items,
            "ignored": ignored_items,
            "responded": responded_items
        },
        "by_seller_type": {
            "human_seller": human_matcher_items,
            "bot_seller": bot_matcher_items
        }
    }


def validate_matcher_configuration(matcher: SellerMatcher, db: Session) -> dict:
    """
    Validate a matcher configuration and provide warnings about potential issues.
    """
    warnings = []
    errors = []
    
    # Check if the matcher will match any existing contexts
    affected_contexts = get_affected_decision_contexts_for_matcher(matcher, db)
    
    if not affected_contexts:
        warnings.append("This matcher will not match any existing decision contexts")
    
    # Check for very restrictive settings that might limit matches
    if matcher.keywords and len(matcher.keywords) > 5:
        warnings.append("Many keywords may make matching too restrictive")
    
    if matcher.context_pages and len(matcher.context_pages) > 10:
        warnings.append("Many context pages may make matching too restrictive")
    
    # Check for reasonable rate thresholds
    if matcher.min_inspection_rate > 0.8:
        warnings.append("High minimum inspection rate may limit matches")
    
    if matcher.min_purchase_rate > 0.8:
        warnings.append("High minimum purchase rate may limit matches")
    
    # Check age limit
    if matcher.age_limit and matcher.age_limit < 3600:  # Less than 1 hour
        warnings.append("Very short age limit may cause inbox items to expire quickly")
    
    return {
        "is_valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
        "estimated_impact": len(affected_contexts)
    }


def optimize_matcher_performance(db: Session):
    """
    Perform database maintenance to optimize matcher performance.
    This should be run periodically during low-traffic periods.
    """
    # Analyze table statistics
    db.execute("ANALYZE matcherinbox")
    db.execute("ANALYZE sellermatcher") 
    db.execute("ANALYZE decisioncontext")
    
    # Clean up any orphaned inbox items
    orphaned_count = db.query(MatcherInbox).outerjoin(SellerMatcher).filter(
        SellerMatcher.id.is_(None)
    ).delete()
    
    orphaned_context_count = db.query(MatcherInbox).outerjoin(DecisionContext).filter(
        DecisionContext.id.is_(None)
    ).delete()
    
    db.commit()
    
    return {
        "orphaned_matcher_items_removed": orphaned_count,
        "orphaned_context_items_removed": orphaned_context_count
    }


def increment_buyer_query_counter(buyer: HumanBuyer, priority: int, db: Session):
    """
    Increment the num_queries counter for a specific priority level.
    This is called when a buyer creates a new DecisionContext.
    """
    if buyer.num_queries is None:
        buyer.num_queries = {}
    
    buyer.num_queries[priority] = buyer.num_queries.get(priority, 0) + 1
    db.add(buyer)
    db.commit()


def increment_buyer_inspected_counter(buyer: HumanBuyer, priority: int, db: Session):
    """
    Increment the num_inspected counter for a specific priority level.
    This is called when a buyer inspects InfoOffers for a DecisionContext.
    
    IMPORTANT: This should only be called for the ORIGINAL DecisionContext (depth=0),
    not for recursive child contexts. The inspection task handles this automatically.
    """
    if buyer.num_inspected is None:
        buyer.num_inspected = {}
    
    buyer.num_inspected[priority] = buyer.num_inspected.get(priority, 0) + 1
    db.add(buyer)
    db.commit()


def increment_buyer_purchased_counter(buyer: HumanBuyer, priority: int, db: Session):
    """
    Increment the num_purchased counter for a specific priority level.
    This is called when a buyer purchases InfoOffers for a DecisionContext.
    
    IMPORTANT: This should only be called for the ORIGINAL DecisionContext (depth=0),
    not for recursive child contexts. The inspection task handles this automatically.
    """
    if buyer.num_purchased is None:
        buyer.num_purchased = {}
    
    buyer.num_purchased[priority] = buyer.num_purchased.get(priority, 0) + 1
    db.add(buyer)
    db.commit()


def get_buyer_stats_summary(buyer: HumanBuyer) -> dict:
    """
    Get a summary of the buyer's statistics across all priority levels.
    """
    if not buyer.num_queries:
        return {
            "total_queries": 0,
            "total_inspected": 0,
            "total_purchased": 0,
            "overall_inspection_rate": 0.0,
            "overall_purchase_rate": 0.0,
            "by_priority": {}
        }
    
    total_queries = sum(buyer.num_queries.values())
    total_inspected = sum(buyer.num_inspected.values()) if buyer.num_inspected else 0
    total_purchased = sum(buyer.num_purchased.values()) if buyer.num_purchased else 0
    
    overall_inspection_rate = total_inspected / total_queries if total_queries > 0 else 0.0
    overall_purchase_rate = total_purchased / total_queries if total_queries > 0 else 0.0
    
    by_priority = {}
    for priority in buyer.num_queries.keys():
        queries = buyer.num_queries.get(priority, 0)
        inspected = buyer.num_inspected.get(priority, 0) if buyer.num_inspected else 0
        purchased = buyer.num_purchased.get(priority, 0) if buyer.num_purchased else 0
        
        by_priority[priority] = {
            "queries": queries,
            "inspected": inspected,
            "purchased": purchased,
            "inspection_rate": inspected / queries if queries > 0 else 0.0,
            "purchase_rate": purchased / queries if queries > 0 else 0.0
        }
    
    return {
        "total_queries": total_queries,
        "total_inspected": total_inspected,
        "total_purchased": total_purchased,
        "overall_inspection_rate": overall_inspection_rate,
        "overall_purchase_rate": overall_purchase_rate,
        "by_priority": by_priority
    }


def process_daily_login_bonus(user: User, db: Session) -> dict:
    """
    Process daily login bonus for a user.
    
    Args:
        user: The user to process the bonus for
        db: Database session
        
    Returns:
        dict: Information about the bonus processing
    """
    import datetime
    
    today = datetime.date.today()
    
    # Check if user has already received a bonus today
    if user.last_login_date == today:
        return {
            "bonus_awarded": False,
            "message": "Daily bonus already received today",
            "next_bonus_date": today + datetime.timedelta(days=1)
        }
    
    # Award the daily bonus
    bonus_amount = user.daily_bonus_amount
    
    # Update user's balances
    user.balance += bonus_amount
    user.available_balance += bonus_amount
    user.last_login_date = today
    
    db.add(user)
    db.commit()
    
    return {
        "bonus_awarded": True,
        "bonus_amount": bonus_amount,
        "message": f"Daily bonus of {bonus_amount} awarded",
        "new_balance": user.balance,
        "new_available_balance": user.available_balance,
        "next_bonus_date": today + datetime.timedelta(days=1)
    }


@contextmanager
def temporary_api_keys(api_keys: dict):
    """
    Context manager to temporarily set API keys in environment variables.
    
    Args:
        api_keys: Dictionary of API key names and values
        
    Yields:
        None
        
    Example:
        with temporary_api_keys({"OPENAI_API_KEY": "sk-..."}):
            # API keys are set in environment
            make_llm_call()
        # API keys are automatically cleared
    """
    # Store original values
    original_values = {}
    
    try:
        # Set new API keys
        for key_name, key_value in api_keys.items():
            if key_value:  # Only set non-empty values
                original_values[key_name] = os.environ.get(key_name)
                os.environ[key_name] = key_value
        
        yield
        
    finally:
        # Restore original values
        for key_name in api_keys.keys():
            if key_name in original_values:
                if original_values[key_name] is None:
                    # Remove the key if it wasn't set originally
                    os.environ.pop(key_name, None)
                else:
                    # Restore the original value
                    os.environ[key_name] = original_values[key_name]


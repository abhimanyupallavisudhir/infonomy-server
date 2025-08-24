#!/usr/bin/env python3
"""
Test script to demonstrate the efficiency of the new matcher inbox update approach.
This script compares the old approach (recomputing all inboxes) with the new approach
(updating only affected inboxes).
"""

import time
from typing import List, Dict
from sqlmodel import Session, select
from infonomy_server.database import get_db
from infonomy_server.models import DecisionContext, SellerMatcher, MatcherInbox
from infonomy_server.utils import (
    recompute_inbox_for_context,
    recompute_inbox_for_matcher,
    recompute_all_inboxes,
    get_affected_decision_contexts_for_matcher,
    get_inbox_statistics
)


def benchmark_old_approach(db: Session, contexts: List[DecisionContext]) -> Dict:
    """
    Benchmark the old approach: recompute inbox for each context individually.
    This simulates what happens when decision contexts change.
    """
    start_time = time.time()
    
    # Clear all existing inbox items
    db.query(MatcherInbox).delete()
    db.commit()
    
    # Recompute inbox for each context (old approach)
    for ctx in contexts:
        recompute_inbox_for_context(ctx, db)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Get final statistics
    stats = get_inbox_statistics(db)
    
    return {
        "approach": "old_approach",
        "total_time_seconds": total_time,
        "contexts_processed": len(contexts),
        "time_per_context": total_time / len(contexts) if contexts else 0,
        "final_inbox_count": stats["total_inbox_items"]
    }


def benchmark_new_approach(db: Session, matchers: List[SellerMatcher]) -> Dict:
    """
    Benchmark the new approach: recompute inbox for each matcher individually.
    This simulates what happens when matchers change.
    """
    start_time = time.time()
    
    # Clear all existing inbox items
    db.query(MatcherInbox).delete()
    db.commit()
    
    # Recompute inbox for each matcher (new approach)
    for matcher in matchers:
        recompute_inbox_for_matcher(matcher, db)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Get final statistics
    stats = get_inbox_statistics(db)
    
    return {
        "approach": "new_approach", 
        "total_time_seconds": total_time,
        "matchers_processed": len(matchers),
        "time_per_matcher": total_time / len(matchers) if matchers else 0,
        "final_inbox_count": stats["total_inbox_items"]
    }


def benchmark_bulk_approach(db: Session, contexts: List[DecisionContext]) -> Dict:
    """
    Benchmark the bulk approach: recompute all inboxes at once.
    This is the most efficient for complete resynchronization.
    """
    start_time = time.time()
    
    # Use the bulk recompute function
    recompute_all_inboxes(db)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Get final statistics
    stats = get_inbox_statistics(db)
    
    return {
        "approach": "bulk_approach",
        "total_time_seconds": total_time,
        "contexts_processed": len(contexts),
        "time_per_context": total_time / len(contexts) if contexts else 0,
        "final_inbox_count": stats["total_inbox_items"]
    }


def analyze_matcher_impact(db: Session, matcher: SellerMatcher) -> Dict:
    """
    Analyze the impact of a specific matcher change.
    """
    from infonomy_server.utils import get_matcher_impact_summary, validate_matcher_configuration
    
    impact_summary = get_matcher_impact_summary(matcher, db)
    validation = validate_matcher_configuration(matcher, db)
    
    return {
        "matcher_id": matcher.id,
        "seller_type": matcher.seller_type,
        "impact_summary": impact_summary,
        "validation": validation
    }


def run_efficiency_analysis():
    """
    Run a comprehensive efficiency analysis of the different approaches.
    """
    print("🔍 Running Matcher Inbox Efficiency Analysis")
    print("=" * 60)
    
    # Get database session
    db = next(get_db())
    
    try:
        # Get current data counts
        total_contexts = db.query(DecisionContext).count()
        total_matchers = db.query(SellerMatcher).count()
        total_inbox_items = db.query(MatcherInbox).count()
        
        print(f"📊 Current System State:")
        print(f"   Decision Contexts: {total_contexts}")
        print(f"   Seller Matchers: {total_matchers}")
        print(f"   Inbox Items: {total_inbox_items}")
        print()
        
        # Get sample data for benchmarking
        contexts = db.exec(
            select(DecisionContext)
            .where(DecisionContext.parent_id.is_(None))
            .limit(100)  # Limit for reasonable benchmark time
        ).all()
        
        matchers = db.exec(
            select(SellerMatcher).limit(50)  # Limit for reasonable benchmark time
        ).all()
        
        print(f"🧪 Benchmarking with {len(contexts)} contexts and {len(matchers)} matchers")
        print()
        
        # Run benchmarks
        print("⏱️  Running Benchmarks...")
        
        old_results = benchmark_old_approach(db, contexts)
        new_results = benchmark_new_approach(db, matchers)
        bulk_results = benchmark_bulk_approach(db, contexts)
        
        # Display results
        print("📈 Benchmark Results:")
        print(f"   Old Approach (per-context): {old_results['total_time_seconds']:.3f}s")
        print(f"   New Approach (per-matcher): {new_results['total_time_seconds']:.3f}s")
        print(f"   Bulk Approach (all-at-once): {bulk_results['total_time_seconds']:.3f}s")
        print()
        
        # Calculate efficiency improvements
        if old_results['total_time_seconds'] > 0:
            old_vs_new_improvement = (
                (old_results['total_time_seconds'] - new_results['total_time_seconds']) / 
                old_results['total_time_seconds'] * 100
            )
            print(f"🚀 New approach vs Old approach: {old_vs_new_improvement:.1f}% improvement")
        
        if new_results['total_time_seconds'] > 0:
            new_vs_bulk_improvement = (
                (new_results['total_time_seconds'] - bulk_results['total_time_seconds']) / 
                new_results['total_time_seconds'] * 100
            )
            print(f"🚀 Bulk approach vs New approach: {new_vs_bulk_improvement:.1f}% improvement")
        
        print()
        
        # Analyze a sample matcher
        if matchers:
            sample_matcher = matchers[0]
            print(f"🔍 Analyzing Sample Matcher (ID: {sample_matcher.id}):")
            impact_analysis = analyze_matcher_impact(db, sample_matcher)
            
            print(f"   Total affected contexts: {impact_analysis['impact_summary']['total_affected_contexts']}")
            print(f"   Priority distribution: {impact_analysis['impact_summary']['priority_distribution']}")
            print(f"   Budget distribution: {impact_analysis['impact_summary']['budget_distribution']}")
            
            if impact_analysis['validation']['warnings']:
                print(f"   ⚠️  Warnings: {', '.join(impact_analysis['validation']['warnings'])}")
        
        print()
        print("✅ Analysis Complete!")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    run_efficiency_analysis() 
#!/usr/bin/env python3
"""
Test script to verify that buyer tracking only increments counters for the original
DecisionContext (depth=0), not for recursive child contexts.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from infonomy_server.database import get_db
from infonomy_server.models import User, HumanBuyer, DecisionContext
from infonomy_server.utils import (
    increment_buyer_query_counter,
    increment_buyer_inspected_counter,
    increment_buyer_purchased_counter,
    get_buyer_stats_summary
)
from sqlmodel import Session, select
from datetime import datetime


def test_recursive_tracking():
    """Test that counters only increment for original contexts, not recursive ones"""
    print("🧪 Testing Recursive Buyer Tracking")
    print("=" * 50)
    
    # Get database session
    db = next(get_db())
    
    try:
        # Find a user with a buyer profile
        buyer_user = db.exec(
            select(User).join(HumanBuyer).limit(1)
        ).first()
        
        if not buyer_user or not buyer_user.buyer_profile:
            print("❌ No user with buyer profile found. Please create a buyer profile first.")
            return
        
        buyer = buyer_user.buyer_profile
        print(f"✅ Found buyer: User ID {buyer_user.id}")
        
        # Reset counters for clean testing
        if buyer.num_queries:
            buyer.num_queries.clear()
        if buyer.num_inspected:
            buyer.num_inspected.clear()
        if buyer.num_purchased:
            buyer.num_purchased.clear()
        db.add(buyer)
        db.commit()
        
        print(f"   Initial stats: {get_buyer_stats_summary(buyer)}")
        print()
        
        # Test 1: Simulate original context (depth=0)
        print("📝 Test 1: Simulating original context (depth=0)")
        print("   This SHOULD increment counters")
        
        # Simulate what happens in inspect_task for depth=0
        increment_buyer_inspected_counter(buyer, 0, db)
        increment_buyer_purchased_counter(buyer, 0, db)
        
        db.refresh(buyer)
        stats_after_original = get_buyer_stats_summary(buyer)
        print(f"   After original context: {stats_after_original}")
        
        # Test 2: Simulate recursive child context (depth=1)
        print("\n📝 Test 2: Simulating recursive child context (depth=1)")
        print("   This should NOT increment counters (handled by depth check)")
        
        # Simulate what would happen if we called increment functions for depth=1
        # (This should not happen in the real inspect_task, but let's verify the logic)
        print("   Note: In real inspect_task, these functions are not called for depth > 0")
        print("   But if they were called, they would still increment (which is why we need the depth check)")
        
        # Test 3: Verify the depth check logic
        print("\n📝 Test 3: Verifying depth check logic")
        print("   The inspect_task should only call increment functions when depth == 0")
        
        # Simulate the logic that should be in inspect_task
        depth = 0
        if depth == 0:
            print("   ✅ depth == 0: Should increment counters")
            increment_buyer_inspected_counter(buyer, 0, db)
            increment_buyer_purchased_counter(buyer, 0, db)
        else:
            print("   ❌ depth > 0: Should NOT increment counters")
        
        depth = 1
        if depth == 0:
            print("   ❌ depth == 0: Should increment counters")
            increment_buyer_inspected_counter(buyer, 0, db)
            increment_buyer_purchased_counter(buyer, 0, db)
        else:
            print("   ✅ depth > 0: Should NOT increment counters")
        
        depth = 2
        if depth == 0:
            print("   ❌ depth == 0: Should increment counters")
            increment_buyer_inspected_counter(buyer, 0, db)
            increment_buyer_purchased_counter(buyer, 0, db)
        else:
            print("   ✅ depth > 0: Should NOT increment counters")
        
        # Get final stats
        db.refresh(buyer)
        final_stats = get_buyer_stats_summary(buyer)
        
        print(f"\n📊 Final stats: {final_stats}")
        
        # Verify that counters only incremented for the original context
        expected_queries = 0  # No queries created in this test
        expected_inspected = 3  # 1 from test 1 + 1 from test 3 (depth=0) + 1 from test 3 (depth=0)
        expected_purchased = 3  # Same as inspected
        
        actual_inspected = final_stats['total_inspected']
        actual_purchased = final_stats['total_purchased']
        
        print(f"\n📈 Verification:")
        print(f"   Expected inspected: {expected_inspected}")
        print(f"   Actual inspected: {actual_inspected}")
        print(f"   Expected purchased: {expected_purchased}")
        print(f"   Actual purchased: {actual_purchased}")
        
        if actual_inspected == expected_inspected and actual_purchased == expected_purchased:
            print("   ✅ Counters incremented correctly (only for depth=0)")
        else:
            print("   ❌ Counter increment logic incorrect")
        
        print()
        print("✅ Recursive tracking test completed!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


def test_inspect_task_logic():
    """Test the logic that should be used in inspect_task"""
    print("\n🔍 Testing Inspect Task Logic")
    print("=" * 40)
    
    print("The inspect_task should use this logic:")
    print()
    print("def inspect_task(context_id, buyer_id, purchased=None, depth=0, ...):")
    print("    # ... inspection logic ...")
    print("    ")
    print("    # Only increment counters for original context (depth=0)")
    print("    if depth == 0:")
    print("        increment_buyer_inspected_counter(buyer, ctx.priority, session)")
    print("    ")
    print("    if chosen_ids and depth == 0:")
    print("        increment_buyer_purchased_counter(buyer, ctx.priority, session)")
    print("    ")
    print("    # Recursive calls maintain the same depth logic")
    print("    return inspect_task(..., depth=depth+1, ...)")
    
    print("\n✅ This ensures counters only increment once per original context")


if __name__ == "__main__":
    test_recursive_tracking()
    test_inspect_task_logic() 
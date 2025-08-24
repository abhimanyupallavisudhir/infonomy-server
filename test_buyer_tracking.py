#!/usr/bin/env python3
"""
Test script to verify that the buyer tracking functionality is working correctly.
This script tests the increment functions and statistics generation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from infonomy_server.database import get_db
from infonomy_server.models import User, HumanBuyer, DecisionContext, InfoOffer
from infonomy_server.utils import (
    increment_buyer_query_counter,
    increment_buyer_inspected_counter,
    increment_buyer_purchased_counter,
    get_buyer_stats_summary
)
from sqlmodel import Session, select
from datetime import datetime


def test_buyer_tracking():
    """Test the buyer tracking functionality"""
    print("🧪 Testing Buyer Tracking Functionality")
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
        print(f"   Current stats: {get_buyer_stats_summary(buyer)}")
        print()
        
        # Test 1: Increment query counter
        print("📝 Test 1: Incrementing query counter for priority 0")
        initial_queries = buyer.num_queries.get(0, 0) if buyer.num_queries else 0
        increment_buyer_query_counter(buyer, 0, db)
        
        # Refresh the buyer object
        db.refresh(buyer)
        new_queries = buyer.num_queries.get(0, 0) if buyer.num_queries else 0
        
        if new_queries == initial_queries + 1:
            print(f"   ✅ Query counter incremented: {initial_queries} → {new_queries}")
        else:
            print(f"   ❌ Query counter failed: {initial_queries} → {new_queries}")
        
        print()
        
        # Test 2: Increment inspected counter
        print("🔍 Test 2: Incrementing inspected counter for priority 0")
        initial_inspected = buyer.num_inspected.get(0, 0) if buyer.num_inspected else 0
        increment_buyer_inspected_counter(buyer, 0, db)
        
        # Refresh the buyer object
        db.refresh(buyer)
        new_inspected = buyer.num_inspected.get(0, 0) if buyer.num_inspected else 0
        
        if new_inspected == initial_inspected + 1:
            print(f"   ✅ Inspected counter incremented: {initial_inspected} → {new_inspected}")
        else:
            print(f"   ❌ Inspected counter failed: {initial_inspected} → {new_inspected}")
        
        print()
        
        # Test 3: Increment purchased counter
        print("💰 Test 3: Incrementing purchased counter for priority 0")
        initial_purchased = buyer.num_purchased.get(0, 0) if buyer.num_purchased else 0
        increment_buyer_purchased_counter(buyer, 0, db)
        
        # Refresh the buyer object
        db.refresh(buyer)
        new_purchased = buyer.num_purchased.get(0, 0) if buyer.num_purchased else 0
        
        if new_purchased == initial_purchased + 1:
            print(f"   ✅ Purchased counter incremented: {initial_purchased} → {new_purchased}")
        else:
            print(f"   ❌ Purchased counter failed: {initial_purchased} → {new_purchased}")
        
        print()
        
        # Test 4: Test different priority levels
        print("📊 Test 4: Testing different priority levels")
        increment_buyer_query_counter(buyer, 1, db)
        increment_buyer_inspected_counter(buyer, 1, db)
        increment_buyer_purchased_counter(buyer, 1, db)
        
        # Refresh and get final stats
        db.refresh(buyer)
        final_stats = get_buyer_stats_summary(buyer)
        
        print(f"   Final stats: {final_stats}")
        print()
        
        # Test 5: Verify inspection and purchase rates
        print("📈 Test 5: Verifying calculated rates")
        if final_stats['by_priority'].get(0):
            priority_0_stats = final_stats['by_priority'][0]
            expected_inspection_rate = priority_0_stats['inspected'] / priority_0_stats['queries']
            expected_purchase_rate = priority_0_stats['purchased'] / priority_0_stats['queries']
            
            print(f"   Priority 0 - Queries: {priority_0_stats['queries']}")
            print(f"   Priority 0 - Inspected: {priority_0_stats['inspected']}")
            print(f"   Priority 0 - Purchased: {priority_0_stats['purchased']}")
            print(f"   Priority 0 - Inspection Rate: {priority_0_stats['inspection_rate']:.3f}")
            print(f"   Priority 0 - Purchase Rate: {priority_0_stats['purchase_rate']:.3f}")
            
            # Verify the rates match the expected calculations
            if abs(priority_0_stats['inspection_rate'] - expected_inspection_rate) < 0.001:
                print("   ✅ Inspection rate calculation correct")
            else:
                print("   ❌ Inspection rate calculation incorrect")
                
            if abs(priority_0_stats['purchase_rate'] - expected_purchase_rate) < 0.001:
                print("   ✅ Purchase rate calculation correct")
            else:
                print("   ❌ Purchase rate calculation incorrect")
        
        print()
        print("✅ All tests completed!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


def test_edge_cases():
    """Test edge cases and error handling"""
    print("\n🔍 Testing Edge Cases")
    print("=" * 30)
    
    # Get database session
    db = next(get_db())
    
    try:
        # Test with None values
        print("🧪 Test: Handling None values in counters")
        
        # Create a temporary buyer profile for testing
        test_user = db.exec(select(User).limit(1)).first()
        if test_user:
            # Test with None counters
            buyer = HumanBuyer(
                user_id=test_user.id,
                num_queries=None,
                num_inspected=None,
                num_purchased=None
            )
            
            # Test increment functions with None values
            increment_buyer_query_counter(buyer, 0, db)
            increment_buyer_inspected_counter(buyer, 0, db)
            increment_buyer_purchased_counter(buyer, 0, db)
            
            print("   ✅ Successfully handled None values")
            print(f"   Final counters: {buyer.num_queries}, {buyer.num_inspected}, {buyer.num_purchased}")
        
        print("✅ Edge case tests completed!")
        
    except Exception as e:
        print(f"❌ Error during edge case testing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    test_buyer_tracking()
    test_edge_cases() 
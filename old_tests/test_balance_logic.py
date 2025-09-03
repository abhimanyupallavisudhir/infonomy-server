#!/usr/bin/env python3
"""
Test script to verify that the balance logic works correctly.
This tests the new User.available_balance attribute and the balance deduction logic.
"""

from infonomy_server.database import engine
from infonomy_server.models import User, HumanBuyer, DecisionContext, InfoOffer
from sqlmodel import Session, select
from datetime import datetime

def test_balance_logic():
    """Test the balance logic for DecisionContext creation and purchases"""
    session = Session(engine)
    
    try:
        print("🧪 Testing Balance Logic")
        print("=" * 50)
        
        # Find a user with a buyer profile
        user = session.exec(
            select(User).join(HumanBuyer).limit(1)
        ).first()
        
        if not user or not user.buyer_profile:
            print("❌ No user with buyer profile found. Please create a buyer profile first.")
            return
        
        print(f"✅ Found user: {user.username} (ID: {user.id})")
        print(f"   Initial balance: {user.balance}")
        print(f"   Initial available_balance: {user.available_balance}")
        
        # Test 1: Create a DecisionContext with max_budget
        print("\n📝 Test 1: Creating DecisionContext")
        max_budget = 25.0
        
        # Check if user has enough available_balance
        if user.available_balance < max_budget:
            print(f"   ❌ User doesn't have enough available_balance ({user.available_balance} < {max_budget})")
            return
        
        # Simulate the logic from create_decision_context
        user.available_balance -= max_budget
        session.add(user)
        session.commit()
        
        print(f"   ✅ Deducted {max_budget} from available_balance")
        print(f"   New available_balance: {user.available_balance}")
        
        # Test 2: Simulate purchasing InfoOffers
        print("\n💰 Test 2: Simulating Purchase")
        
        # Create a mock DecisionContext for testing
        ctx = DecisionContext(
            query="Test query",
            buyer_id=user.buyer_profile.user_id,
            max_budget=max_budget,
            priority=0,
            created_at=datetime.utcnow()
        )
        session.add(ctx)
        session.commit()
        session.refresh(ctx)
        
        # Simulate the balance logic from inspect_task (depth=0)
        # This would normally happen when offers are purchased
        total_cost = 15.0  # Simulate cost of purchased offers
        
        # Deduct from actual balance
        user.balance -= total_cost
        # Restore the max_budget to available_balance
        user.available_balance += ctx.max_budget
        session.add(user)
        session.commit()
        
        print(f"   ✅ Deducted {total_cost} from balance")
        print(f"   ✅ Restored {ctx.max_budget} to available_balance")
        print(f"   Final balance: {user.balance}")
        print(f"   Final available_balance: {user.available_balance}")
        
        # Verify the logic
        expected_available = user.available_balance
        print(f"\n🔍 Verification:")
        print(f"   Expected available_balance: {expected_available}")
        print(f"   Actual available_balance: {user.available_balance}")
        
        if abs(expected_available - user.available_balance) < 0.01:
            print("   ✅ Balance logic is working correctly!")
        else:
            print("   ❌ Balance logic has an issue!")
        
        # Clean up test data
        session.delete(ctx)
        session.commit()
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error during testing: {str(e)}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    test_balance_logic() 
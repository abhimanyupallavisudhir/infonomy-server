#!/usr/bin/env python3
"""
Test script to verify that the daily bonus system works correctly.
This tests the daily login bonus functionality.
"""

from infonomy_server.database import engine
from infonomy_server.models import User, HumanBuyer
from sqlmodel import Session, select
import datetime

def test_daily_bonus():
    """Test the daily bonus system"""
    session = Session(engine)
    
    try:
        print("🧪 Testing Daily Bonus System")
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
        print(f"   Daily bonus amount: {user.daily_bonus_amount}")
        print(f"   Last login date: {user.last_login_date}")
        
        # Test 1: Check bonus status
        print("\n📊 Test 1: Checking Bonus Status")
        from infonomy_server.utils import process_daily_login_bonus
        
        today = datetime.date.today()
        if user.last_login_date == today:
            print("   Status: Bonus already received today")
            bonus_available = False
        else:
            print("   Status: Bonus available")
            bonus_available = True
        
        # Test 2: Process daily bonus
        print("\n💰 Test 2: Processing Daily Bonus")
        
        initial_balance = user.balance
        initial_available_balance = user.available_balance
        
        bonus_result = process_daily_login_bonus(user, session)
        
        print(f"   Bonus awarded: {bonus_result['bonus_awarded']}")
        print(f"   Message: {bonus_result['message']}")
        
        if bonus_result['bonus_awarded']:
            print(f"   Bonus amount: {bonus_result['bonus_amount']}")
            print(f"   New balance: {bonus_result['new_balance']}")
            print(f"   New available_balance: {bonus_result['new_available_balance']}")
            
            # Verify the balance changes
            expected_balance = initial_balance + user.daily_bonus_amount
            expected_available_balance = initial_available_balance + user.daily_bonus_amount
            
            if abs(user.balance - expected_balance) < 0.01:
                print("   ✅ Balance updated correctly!")
            else:
                print(f"   ❌ Balance mismatch! Expected: {expected_balance}, Got: {user.balance}")
            
            if abs(user.available_balance - expected_available_balance) < 0.01:
                print("   ✅ Available balance updated correctly!")
            else:
                print(f"   ❌ Available balance mismatch! Expected: {expected_available_balance}, Got: {user.available_balance}")
        else:
            print(f"   Next bonus date: {bonus_result['next_bonus_date']}")
        
        # Test 3: Try to get bonus again (should fail)
        print("\n🔄 Test 3: Trying to Get Bonus Again")
        
        bonus_result2 = process_daily_login_bonus(user, session)
        
        print(f"   Bonus awarded: {bonus_result2['bonus_awarded']}")
        print(f"   Message: {bonus_result2['message']}")
        
        if not bonus_result2['bonus_awarded']:
            print("   ✅ Correctly prevented duplicate bonus!")
        else:
            print("   ❌ Should not have awarded bonus again!")
        
        # Test 4: Simulate next day
        print("\n📅 Test 4: Simulating Next Day")
        
        # Temporarily set last_login_date to yesterday
        original_last_login = user.last_login_date
        user.last_login_date = today - datetime.timedelta(days=1)
        session.add(user)
        session.commit()
        
        bonus_result3 = process_daily_login_bonus(user, session)
        
        print(f"   Bonus awarded: {bonus_result3['bonus_awarded']}")
        print(f"   Message: {bonus_result3['message']}")
        
        if bonus_result3['bonus_awarded']:
            print("   ✅ Correctly awarded bonus on next day!")
        else:
            print("   ❌ Should have awarded bonus on next day!")
        
        # Restore original last_login_date
        user.last_login_date = original_last_login
        session.add(user)
        session.commit()
        
        print("\n🎉 Daily bonus system test completed!")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error during testing: {str(e)}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    test_daily_bonus() 
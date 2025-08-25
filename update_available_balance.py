#!/usr/bin/env python3
"""
Script to update existing users' available_balance to match their current balance.
This ensures that existing users can continue to use the system after the new balance logic is implemented.
"""

from infonomy_server.database import engine
from infonomy_server.models import User
from sqlmodel import Session, select

def update_available_balance():
    """Update all existing users' available_balance to match their current balance"""
    session = Session(engine)
    
    try:
        # Get all users
        users = session.exec(select(User)).all()
        
        updated_count = 0
        for user in users:
            if user.available_balance == 0.0:  # Only update if not already set
                user.available_balance = user.balance
                session.add(user)
                updated_count += 1
                print(f"Updated user {user.id} ({user.username}): available_balance = {user.available_balance}")
        
        if updated_count > 0:
            session.commit()
            print(f"\n✅ Successfully updated {updated_count} users")
        else:
            print("\n✅ No users needed updating")
            
    except Exception as e:
        session.rollback()
        print(f"❌ Error updating users: {str(e)}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    print("🔄 Updating users' available_balance...")
    update_available_balance()
    print("✅ Done!") 
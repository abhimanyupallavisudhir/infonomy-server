#!/usr/bin/env python3
"""
Script to set up daily bonus settings for existing users.
This ensures that existing users have proper daily bonus configuration.
"""

from infonomy_server.database import engine
from infonomy_server.models import User
from sqlmodel import Session, select
import datetime

def setup_daily_bonus():
    """Set up daily bonus settings for all existing users"""
    session = Session(engine)
    
    try:
        # Get all users
        users = session.exec(select(User)).all()
        
        updated_count = 0
        for user in users:
            needs_update = False
            
            # Set default daily bonus amount if not set
            if not hasattr(user, 'daily_bonus_amount') or user.daily_bonus_amount == 0.0:
                user.daily_bonus_amount = 10.0
                needs_update = True
                print(f"Set daily bonus amount for user {user.id} ({user.username}): {user.daily_bonus_amount}")
            
            # Set last_login_date to yesterday if not set (so they can get bonus on first login)
            if user.last_login_date is None:
                user.last_login_date = datetime.date.today() - datetime.timedelta(days=1)
                needs_update = True
                print(f"Set last_login_date for user {user.id} ({user.username}): {user.last_login_date}")
            
            if needs_update:
                session.add(user)
                updated_count += 1
        
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
    print("🔄 Setting up daily bonus for users...")
    setup_daily_bonus()
    print("✅ Done!") 
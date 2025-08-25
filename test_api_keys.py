#!/usr/bin/env python3
"""
Test script to verify that the API key system works correctly.
This tests the user-specific API key functionality.
"""

from infonomy_server.database import engine
from infonomy_server.models import User, HumanBuyer
from sqlmodel import Session, select
import os

def test_api_keys():
    """Test the API key system"""
    session = Session(engine)
    
    try:
        print("🧪 Testing API Key System")
        print("=" * 50)
        
        # Find a user with a buyer profile
        user = session.exec(
            select(User).join(HumanBuyer).limit(1)
        ).first()
        
        if not user or not user.buyer_profile:
            print("❌ No user with buyer profile found. Please create a buyer profile first.")
            return
        
        print(f"✅ Found user: {user.username} (ID: {user.id})")
        print(f"   Current API keys: {list(user.api_keys.keys()) if user.api_keys else 'None'}")
        
        # Test 1: Check current environment
        print("\n🔍 Test 1: Checking Current Environment")
        current_openai_key = os.environ.get("OPENAI_API_KEY", "Not set")
        print(f"   Current OPENAI_API_KEY in env: {'Set' if current_openai_key != 'Not set' else 'Not set'}")
        
        # Test 2: Test temporary API keys context manager
        print("\n🔑 Test 2: Testing Temporary API Keys Context Manager")
        from infonomy_server.utils import temporary_api_keys
        
        test_api_keys = {
            "OPENAI_API_KEY": "sk-test123",
            "ANTHROPIC_API_KEY": "sk-ant-test123"
        }
        
        print(f"   Setting test API keys: {list(test_api_keys.keys())}")
        
        with temporary_api_keys(test_api_keys):
            # Check if keys are set in environment
            openai_key_in_env = os.environ.get("OPENAI_API_KEY")
            anthropic_key_in_env = os.environ.get("ANTHROPIC_API_KEY")
            
            print(f"   OPENAI_API_KEY in env during context: {'Set' if openai_key_in_env else 'Not set'}")
            print(f"   ANTHROPIC_API_KEY in env during context: {'Set' if anthropic_key_in_env else 'Not set'}")
            
            if openai_key_in_env == "sk-test123" and anthropic_key_in_env == "sk-ant-test123":
                print("   ✅ API keys correctly set in environment")
            else:
                print("   ❌ API keys not correctly set in environment")
        
        # Check if keys are cleared after context
        openai_key_after = os.environ.get("OPENAI_API_KEY")
        anthropic_key_after = os.environ.get("ANTHROPIC_API_KEY")
        
        print(f"   OPENAI_API_KEY in env after context: {'Set' if openai_key_after else 'Not set'}")
        print(f"   ANTHROPIC_API_KEY in env after context: {'Set' if anthropic_key_after else 'Not set'}")
        
        if openai_key_after == current_openai_key:
            print("   ✅ Environment correctly restored after context")
        else:
            print("   ❌ Environment not correctly restored after context")
        
        # Test 3: Test with empty API keys
        print("\n🚫 Test 3: Testing with Empty API Keys")
        
        empty_api_keys = {}
        
        with temporary_api_keys(empty_api_keys):
            # Should not change environment
            openai_key_empty = os.environ.get("OPENAI_API_KEY")
            if openai_key_empty == current_openai_key:
                print("   ✅ Environment unchanged with empty API keys")
            else:
                print("   ❌ Environment changed unexpectedly with empty API keys")
        
        # Test 4: Test with None API keys
        print("\n🚫 Test 4: Testing with None API Keys")
        
        with temporary_api_keys(None):
            # Should not change environment
            openai_key_none = os.environ.get("OPENAI_API_KEY")
            if openai_key_none == current_openai_key:
                print("   ✅ Environment unchanged with None API keys")
            else:
                print("   ❌ Environment changed unexpectedly with None API keys")
        
        print("\n🎉 API key system test completed!")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error during testing: {str(e)}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    test_api_keys() 
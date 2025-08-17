#!/usr/bin/env python3
"""
Simple test script to verify BotSeller functionality
"""

import asyncio
import httpx
import json
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
TEST_USER = {
    "username": "testuser",
    "password": "testpass123"
}

async def test_botseller_functionality():
    """Test the complete BotSeller workflow"""
    
    async with httpx.AsyncClient() as client:
        print("Testing BotSeller functionality...")
        
        # 1. Test user registration (if needed)
        print("\n1. Testing user registration...")
        try:
            register_response = await client.post(
                f"{BASE_URL}/auth/register",
                json=TEST_USER
            )
            if register_response.status_code == 201:
                print("✓ User registered successfully")
            elif register_response.status_code == 400:
                print("✓ User already exists")
            else:
                print(f"✗ Registration failed: {register_response.status_code}")
                return
        except Exception as e:
            print(f"✗ Registration error: {e}")
            return
        
        # 2. Test user login
        print("\n2. Testing user login...")
        try:
            login_response = await client.post(
                f"{BASE_URL}/auth/jwt/login",
                data={
                    "username": TEST_USER["username"],
                    "password": TEST_USER["password"]
                }
            )
            if login_response.status_code != 200:
                print(f"✗ Login failed: {login_response.status_code}")
                return
            
            token_data = login_response.json()
            access_token = token_data["access_token"]
            print("✓ User logged in successfully")
        except Exception as e:
            print(f"✗ Login error: {e}")
            return
        
        # Set up headers for authenticated requests
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # 3. Test creating a seller profile
        print("\n3. Testing seller profile creation...")
        try:
            seller_response = await client.post(
                f"{BASE_URL}/profiles/sellers",
                headers=headers
            )
            if seller_response.status_code == 200:
                seller_data = seller_response.json()
                seller_id = seller_data["id"]
                print(f"✓ Seller profile created with ID: {seller_id}")
            else:
                print(f"✗ Seller profile creation failed: {seller_response.status_code}")
                return
        except Exception as e:
            print(f"✗ Seller profile creation error: {e}")
            return
        
        # 4. Test creating a BotSeller
        print("\n4. Testing BotSeller creation...")
        try:
            botseller_data = {
                "info": "This is a test BotSeller that provides fixed information.",
                "llm_model": None,
                "llm_prompt": None
            }
            
            botseller_response = await client.post(
                f"{BASE_URL}/bot-sellers/",
                json=botseller_data,
                headers=headers
            )
            if botseller_response.status_code == 200:
                botseller_info = botseller_response.json()
                botseller_id = botseller_info["id"]
                print(f"✓ BotSeller created with ID: {botseller_id}")
            else:
                print(f"✗ BotSeller creation failed: {botseller_response.status_code}")
                print(f"Response: {botseller_response.text}")
                return
        except Exception as e:
            print(f"✗ BotSeller creation error: {e}")
            return
        
        # 5. Test creating a matcher for the BotSeller
        print("\n5. Testing matcher creation...")
        try:
            matcher_data = {
                "keywords": ["test", "information"],
                "context_pages": None,
                "min_max_budget": 0.0,
                "min_inspection_rate": 0.0,
                "min_purchase_rate": 0.0,
                "min_priority": 0,
                "buyer_type": "human_buyer",
                "buyer_llm_model": None,
                "buyer_system_prompt": None,
                "age_limit": 86400
            }
            
            matcher_response = await client.post(
                f"{BASE_URL}/bot-sellers/{botseller_id}/matchers",
                json=matcher_data,
                headers=headers
            )
            if matcher_response.status_code == 200:
                matcher_info = matcher_response.json()
                matcher_id = matcher_info["id"]
                print(f"✓ Matcher created with ID: {matcher_id}")
            else:
                print(f"✗ Matcher creation failed: {matcher_response.status_code}")
                print(f"Response: {matcher_response.text}")
                return
        except Exception as e:
            print(f"✗ Matcher creation error: {e}")
            return
        
        # 6. Test listing BotSellers
        print("\n6. Testing BotSeller listing...")
        try:
            list_response = await client.get(
                f"{BASE_URL}/bot-sellers/",
                headers=headers
            )
            if list_response.status_code == 200:
                botsellers = list_response.json()
                print(f"✓ Found {len(botsellers)} BotSellers")
                for bs in botsellers:
                    print(f"  - BotSeller {bs['id']}: {bs.get('info', 'LLM Bot')}")
            else:
                print(f"✗ BotSeller listing failed: {list_response.status_code}")
        except Exception as e:
            print(f"✗ BotSeller listing error: {e}")
        
        # 7. Test listing matchers
        print("\n7. Testing matcher listing...")
        try:
            matchers_response = await client.get(
                f"{BASE_URL}/bot-sellers/{botseller_id}/matchers",
                headers=headers
            )
            if matchers_response.status_code == 200:
                matchers = matchers_response.json()
                print(f"✓ Found {len(matchers)} matchers for BotSeller {botseller_id}")
                for m in matchers:
                    print(f"  - Matcher {m['id']}: keywords={m.get('keywords', [])}")
            else:
                print(f"✗ Matcher listing failed: {matchers_response.status_code}")
        except Exception as e:
            print(f"✗ Matcher listing error: {e}")
        
        print("\n✓ BotSeller functionality test completed successfully!")
        print(f"\nCreated BotSeller ID: {botseller_id}")
        print(f"Created Matcher ID: {matcher_id}")
        print("\nYou can now test the full workflow by:")
        print("1. Creating a DecisionContext that matches the matcher")
        print("2. Checking that the BotSeller automatically generates an InfoOffer")
        print("3. Verifying the inspection process works with the new timeout logic")

if __name__ == "__main__":
    asyncio.run(test_botseller_functionality()) 
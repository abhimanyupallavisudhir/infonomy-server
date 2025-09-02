from fastapi import Request, HTTPException, Depends
from fastapi_users import FastAPIUsers
from sqlmodel import Session
from infonomy_server.database import get_db
from infonomy_server.models import User
from infonomy_server.auth import fastapi_users
from typing import Optional
import jwt
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
SECRET = os.getenv("SECRET", "mybigsecret")  # Fallback to the value from .env

print(f"SECRET loaded: {SECRET[:10]}..." if SECRET else "SECRET is None!")

async def get_current_user_from_token(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user from JWT token in Authorization header, form data, or cookies"""
    # First try Authorization header
    auth_header = request.headers.get("Authorization")
    token = None
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        print(f"Got token from Authorization header: {token[:20]}...")
    else:
        # Fallback: check form data for auth_token
        try:
            form_data = await request.form()
            token = form_data.get("auth_token")
            if token:
                print(f"Got token from form data: {token[:20]}...")
        except:
            pass
        
        # Fallback: check cookies for auth_token
        if not token:
            cookie_header = request.headers.get("cookie")
            if cookie_header:
                for cookie in cookie_header.split(";"):
                    if "auth_token=" in cookie:
                        token = cookie.split("auth_token=")[1].split(";")[0].strip()
                        print(f"Got token from cookie: {token[:20]}...")
                        break
    
    if not token:
        print("No token found in headers, form data, or cookies")
        return None
    
    try:
        # FastAPI Users JWT structure
        payload = jwt.decode(token, SECRET, algorithms=["HS256"], audience="fastapi-users:auth")
        print(f"JWT payload: {payload}")
        user_id = payload.get("sub")
        if user_id:
            user = db.get(User, int(user_id))
            if user and user.is_active:
                print(f"Found user: {user.username}")
                return user
            else:
                print(f"User not found or not active: {user_id}")
        else:
            print("No user_id in JWT payload")
    except jwt.ExpiredSignatureError:
        print(f"JWT expired for token: {token[:20]}...")
        return None
    except jwt.InvalidTokenError as e:
        print(f"Invalid JWT token: {e}")
        return None
    except Exception as e:
        print(f"Error decoding JWT: {e}")
        return None
    
    return None

async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise"""
    return await get_current_user_from_token(request, db) 
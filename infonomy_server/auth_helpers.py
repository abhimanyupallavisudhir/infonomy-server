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

load_dotenv()
SECRET = os.getenv("SECRET")

async def get_current_user_from_token(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user from JWT token in Authorization header"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id:
            user = db.get(User, int(user_id))
            return user
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    
    return None

async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise"""
    return await get_current_user_from_token(request, db) 
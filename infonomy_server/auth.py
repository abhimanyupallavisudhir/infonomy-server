import uuid
from typing import Optional
import os
from dotenv import load_dotenv

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, IntegerIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    # JWTAuthentication,
    JWTStrategy,
)
# from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users_db_sqlmodel import SQLModelUserDatabase  # sync adapter
from sqlmodel import Session

from infonomy_server.database import get_db
from infonomy_server.models import User

# Load environment variables from .env file
load_dotenv()
SECRET = os.getenv("SECRET")

class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")

    async def on_after_login(
        self, user: User, request: Optional[Request] = None
    ):
        """Process daily login bonus when user logs in"""
        from infonomy_server.utils import process_daily_login_bonus
        from infonomy_server.database import engine
        from sqlmodel import Session
        
        # Create a new session for processing the bonus
        session = Session(engine)
        try:
            # Refresh user data from database
            db_user = session.get(User, user.id)
            if db_user:
                bonus_result = process_daily_login_bonus(db_user, session)
                if bonus_result["bonus_awarded"]:
                    print(f"User {user.id} received daily bonus: {bonus_result['bonus_amount']}")
                else:
                    print(f"User {user.id} already received daily bonus today")
        except Exception as e:
            print(f"Error processing daily bonus for user {user.id}: {str(e)}")
        finally:
            session.close()

async def get_user_db(session: Session = Depends(get_db)):
    yield SQLModelUserDatabase(session, User)

async def get_user_manager(user_db: SQLModelUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)

# Authentication backend
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
# jwt_authentication = JWTAuthentication(
#     secret=SECRET,
#     lifetime_seconds=3600,
#     tokenUrl="auth/jwt/login",
# )

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    # get_strategy=lambda: jwt_authentication,
    get_strategy=get_jwt_strategy,
)

# FastAPI Users instance
fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])

# Dependencies
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
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
from infonomy_server.logging_config import auth_logger, log_business_event

# Load environment variables from .env file
load_dotenv()
SECRET = os.getenv("SECRET")

class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        log_business_event(auth_logger, "user_registered", user_id=user.id, parameters={
            "email": user.email,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser
        })

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        log_business_event(auth_logger, "password_reset_requested", user_id=user.id, parameters={
            "email": user.email,
            "token_length": len(token)
        })

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        log_business_event(auth_logger, "verification_requested", user_id=user.id, parameters={
            "email": user.email,
            "token_length": len(token)
        })

    async def on_after_login(
        self, user: User, request: Optional[Request] = None, response=None
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
                    log_business_event(auth_logger, "daily_bonus_awarded", user_id=user.id, parameters={
                        "bonus_amount": bonus_result['bonus_amount'],
                        "new_balance": db_user.available_balance
                    })
                else:
                    log_business_event(auth_logger, "daily_bonus_already_received", user_id=user.id, parameters={
                        "last_bonus_date": bonus_result.get('last_bonus_date')
                    })
        except Exception as e:
            log_business_event(auth_logger, "daily_bonus_error", user_id=user.id, parameters={
                "error": str(e)
            })
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
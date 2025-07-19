from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import Session, select
from database import create_db_and_tables, get_db
from models import User, Question, Answer
from schemas import UserCreate, QuestionCreate, AnswerCreate, UserRead, UserUpdate, QuestionResponse, AnswerResponse
from auth import current_active_user, auth_backend, fastapi_users
from routers import decision_contexts, info_offers

app = FastAPI(title="Q&A Platform API", version="1.0.0")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
def root():
    return {"message": "Welcome to the Q&A Platform API"}

# Include FastAPI Users routes
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

# Include our custom routes
app.include_router(decision_contexts.router)
app.include_router(decision_contexts.router)

# # User Endpoints

@app.get("/users/", response_model=list[UserRead])
def get_users(db: Session = Depends(get_db)):
    db_users = db.exec(select(User)).all()
    return db_users

# @app.post("/users/", response_model=UserResponse)
# def create_user(user: UserCreate, db: Session = Depends(get_db)):
#     #check if user already exists
#     existing_user = db.exec(select(User).where(User.username == user.username)).first()
#     if existing_user:
#         raise HTTPException(status_code=400, detail="Username already exists")
    
#     db_user = User(
#         username = user.username,
#         email = user.email,
#         hashed_password = user.password,  # In a real application, hash the password
#     )
#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
#     return db_user


# @app.get("/users/{user_id}", response_model=UserResponse)
# def get_user(user_id: int, db: Session = Depends(get_db)):
#     user = db.get(User, user_id)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#     return user

from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import Session, select
from database import create_db_and_tables, get_db
from models import User, Question, Answer
from schemas import UserCreate, QuestionCreate, AnswerCreate, UserRead, UserUpdate, QuestionResponse, AnswerResponse
from auth import current_active_user, auth_backend, fastapi_users

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

# # User Endpoints
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

@app.get("/users/", response_model=list[UserRead])
def get_users(db: Session = Depends(get_db)):
    db_users = db.exec(select(User)).all()
    return db_users

# @app.get("/users/{user_id}", response_model=UserResponse)
# def get_user(user_id: int, db: Session = Depends(get_db)):
#     user = db.get(User, user_id)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#     return user

# Question Endpoints
@app.post("/questions/", response_model=QuestionResponse)
def create_question(question: QuestionCreate, db: Session = Depends(get_db), current_user: User = Depends(current_active_user)):
    db_question = Question(
        title=question.title,
        content=question.content,
        author_id=current_user.id  # Use the authenticated user's ID
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

@app.get("/questions/", response_model=list[QuestionResponse])
def get_questions(db: Session = Depends(get_db)):
    db_questions = db.exec(select(Question)).all()
    return db_questions

@app.get("/questions/{question_id}", response_model=QuestionResponse)
def get_question(question_id: int, db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question

@app.put("/questions/{question_id}", response_model=QuestionResponse)
def update_question(question_id: int, question_update: QuestionCreate, db: Session = Depends(get_db), current_user: User = Depends(current_active_user)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if question.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this question")
    
    question.title = question_update.title
    question.content = question_update.content
    db.add(question)
    db.commit()
    db.refresh(question)
    return question

@app.delete("/questions/{question_id}", response_model=QuestionResponse)
def delete_question(question_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_active_user)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if question.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this question")
    
    db.delete(question)
    db.commit()
    return {"message": "Question deleted successfully", "question_id": question_id}

# Answer Endpoints
@app.post("/answers/", response_model=AnswerResponse)
def create_answer(answer: AnswerCreate, db: Session = Depends(get_db), current_user: User = Depends(current_active_user)):
    question = db.get(Question, answer.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    db_answer = Answer(
        content=answer.content,
        question_id=answer.question_id,
        author_id=current_user.id # Use the authenticated user's ID
    )
    db.add(db_answer)
    db.commit()
    db.refresh(db_answer)
    return db_answer
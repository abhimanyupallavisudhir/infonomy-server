from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from database import get_db
from models import User, Question
from schemas import QuestionCreate, QuestionResponse
from auth import current_active_user

router = APIRouter(prefix="/questions", tags=["questions"])

@router.post("/", response_model=QuestionResponse)
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

@router.get("/", response_model=list[QuestionResponse])
def get_questions(db: Session = Depends(get_db)):
    db_questions = db.exec(select(Question)).all()
    return db_questions

@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(question_id: int, db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question

@router.put("/{question_id}", response_model=QuestionResponse)
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

@router.delete("/{question_id}", response_model=QuestionResponse)
def delete_question(question_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_active_user)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if question.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this question")
    
    db.delete(question)
    db.commit()
    return {"message": "Question deleted successfully", "question_id": question_id}

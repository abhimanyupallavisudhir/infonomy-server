from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from database import get_db
from models import User, 
from schemas import AnswerCreate, AnswerResponse
from auth import current_active_user

router = APIRouter(prefix="/answers", tags=["answers"])

@router.post("/", response_model=AnswerResponse)
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
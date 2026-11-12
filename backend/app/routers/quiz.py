from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.ratelimit import rate_limited
from app.db.session import SessionLocal, get_db
from app.graphs.learning_graph import run_learning_graph
from app.models import Document, Quiz, User
from app.schemas import QuizCreateRequest, QuizOut, QuizQuestionOut, QuizSubmitRequest, QuizSubmitResponse
from app.services.performance import current_difficulty, grade_and_update

router = APIRouter(prefix="/quiz", tags=["quiz"])

logger = logging.getLogger(__name__)


def _public_questions(questions: list[dict]) -> list[QuizQuestionOut]:
    out = []
    for idx, q in enumerate(questions):
        out.append(
            QuizQuestionOut(
                id=idx,
                type=q.get("type", "mcq"),
                prompt=q.get("prompt", ""),
                options=q.get("options"),
                topic=q.get("topic", "General"),
            )
        )
    return out


def _to_quiz_out(quiz: Quiz) -> QuizOut:
    return QuizOut(
        id=quiz.id,
        document_id=quiz.document_id,
        difficulty=quiz.difficulty or "beginner",
        status=quiz.status or "ready",
        error=quiz.error,
        questions=_public_questions(quiz.questions or []),
    )


def generate_quiz_task(quiz_id: int, user_id: int, document_id: int, focus_weak_areas: bool) -> None:
    """Background task: generate quiz questions via the LangGraph Quiz Agent.

    Running this outside the request/response cycle avoids long blocking HTTP calls
    (the local LLM can take several minutes), which previously surfaced in the UI as
    'Failed to fetch'.
    """
    db = SessionLocal()
    try:
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if quiz is None:
            return
        result = run_learning_graph(
            mode="quiz",
            user_id=user_id,
            document_id=document_id,
            db=db,
            focus_weak_areas=focus_weak_areas,
        )
        questions = result.get("quiz", {}).get("questions", [])
        quiz.questions = questions
        quiz.difficulty = result.get("difficulty", quiz.difficulty or "beginner")
        if questions:
            quiz.status = "ready"
            quiz.error = None
        else:
            quiz.status = "failed"
            quiz.error = (
                "The AI could not generate questions for this document. "
                "Make sure Ollama is running (`ollama serve`) and the document has enough content."
            )
        db.add(quiz)
        db.commit()
        logger.info("Generated quiz %s with %d questions", quiz_id, len(questions))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to generate quiz %s: %s", quiz_id, exc, exc_info=True)
        db.rollback()
        try:
            quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
            if quiz is not None:
                quiz.status = "failed"
                quiz.error = str(exc)
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()


@router.post("", response_model=QuizOut)
def create_quiz(
    body: QuizCreateRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rate: None = Depends(rate_limited("quiz", 10)),
):
    doc = db.query(Document).filter(Document.id == body.document_id, Document.user_id == user.id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "ready":
        raise HTTPException(status_code=409, detail="Document is not ready")

    quiz = Quiz(
        user_id=user.id,
        document_id=doc.id,
        difficulty=current_difficulty(db, user.id, doc.id),
        status="generating",
        questions=[],
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)

    background_tasks.add_task(generate_quiz_task, quiz.id, user.id, doc.id, body.focus_weak_areas)
    return _to_quiz_out(quiz)


@router.get("/{quiz_id}", response_model=QuizOut)
def get_quiz(quiz_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.user_id == user.id).first()
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return _to_quiz_out(quiz)


@router.post("/{quiz_id}/submit", response_model=QuizSubmitResponse)
def submit_quiz(
    quiz_id: int,
    body: QuizSubmitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.user_id == user.id).first()
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if (quiz.status or "ready") != "ready" or not quiz.questions:
        raise HTTPException(status_code=409, detail="Quiz is not ready yet")
    return grade_and_update(db, user, quiz, body.answers)

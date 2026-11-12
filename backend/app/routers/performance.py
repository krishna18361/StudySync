from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.graphs.learning_graph import run_learning_graph
from app.models import Document, User
from app.schemas import PerformanceOut
from app.services.performance import get_performance

router = APIRouter(tags=["performance"])


@router.get("/performance", response_model=PerformanceOut)
def performance(
    document_id: Optional[int] = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_performance(db, user.id, document_id)


@router.get("/performance/coach")
def get_adaptive_coach_advice(
    document_id: int = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user.id).first()
    if not doc:
        return {"adaptive_advice": "Upload a document to get personalized AI coaching."}

    result = run_learning_graph(
        mode="adaptive",
        user_id=user.id,
        document_id=doc.id,
        db=db,
    )
    return {
        "document_id": doc.id,
        "difficulty": result.get("difficulty", "beginner"),
        "weak_topics": result.get("weak_topics", []),
        "adaptive_advice": result.get("adaptive_advice", "Keep practicing! Take a quiz to identify areas for improvement."),
    }


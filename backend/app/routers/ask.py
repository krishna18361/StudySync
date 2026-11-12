from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.ratelimit import rate_limited
from app.db.session import get_db
from app.graphs.learning_graph import run_learning_graph
from app.models import Document, User
from app.schemas import AskResponse, QuestionRequest
from app.services.ingest import extract_text
from app.services.vectorstore import retrieve_text_context

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask_doubt(
    body: QuestionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rate: None = Depends(rate_limited("ask", 30)),
):
    doc = db.query(Document).filter(Document.id == body.document_id, Document.user_id == user.id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "ready":
        raise HTTPException(status_code=409, detail="Document is not ready")

    # Optimization: Remove redundant text extraction and manual retrieval.
    # The run_learning_graph retrieve_node already handles vector retrieval from ChromaDB,
    # which is significantly faster than re-parsing the PDF on every request.
    try:
        result = run_learning_graph(
            mode="answer",
            user_id=user.id,
            document_id=doc.id,
            question=body.question,
            history=body.history,
            context=None,  # Let the graph retrieve context from vectorstore
            db=db,
        )
        return AskResponse(
            answer=result.get("answer") or "Could not generate answer.",
            sources=result.get("sources") or [],
        )
    except Exception as exc:
        logger.exception("Doubt resolution failed for doc=%s question=%r", doc.id, body.question)
        # Return a graceful response instead of letting the server crash with a 500
        return AskResponse(
            answer=(
                "⚠️ The AI tutor encountered an error while processing your question.\n\n"
                f"**Error:** {exc}\n\n"
                "Please make sure Ollama is running (`ollama serve`) and try again."
            ),
            sources=[],
        )

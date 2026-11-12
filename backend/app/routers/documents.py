from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import SessionLocal, get_db
from app.graphs.learning_graph import run_learning_graph
from app.models import Attempt, Document, Performance, Quiz, SkillScore, Summary, TopicScore, User
from app.schemas import DocumentOut, SummaryOut
from app.services.ingest import chunk_text, extract_text
from app.services.vectorstore import delete_document_index, index_document

router = APIRouter(prefix="/documents", tags=["documents"])
upload_router = APIRouter(tags=["documents"])

import logging

logger = logging.getLogger(__name__)

ALLOWED = {".pdf", ".docx", ".pptx", ".txt", ".md", ".text"}


def generate_document_summary(user_id: int, document_id: int) -> None:
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
        if doc is None or doc.status != "ready":
            return
        
        full_text = ""
        filepath = Path(doc.filepath)
        if filepath.exists():
            try:
                full_text = extract_text(filepath)
            except Exception as e:
                logger.warning(f"Could not extract text from {filepath}: {e}")

        result = run_learning_graph(
            mode="summarize",
            user_id=user_id,
            document_id=document_id,
            db=db,
            context=full_text if full_text.strip() else None,
        )
        summary = doc.summary or Summary(document_id=document_id)
        summary_data = result.get("summary", {})
        summary.key_concepts = summary_data.get("key_concepts", [])
        summary.definitions = summary_data.get("definitions", [])
        summary.important_points = summary_data.get("important_points", [])
        summary.examples = summary_data.get("examples", [])
        summary.exam_notes = summary_data.get("exam_notes", "")
        summary.status = "ready"
        summary.error = None
        db.add(summary)
        db.commit()
        logger.info(f"Successfully generated summary for document {document_id}")
    except Exception as exc:
        logger.error(f"Failed to generate summary for document {document_id}: {exc}", exc_info=True)
        db.rollback()
        try:
            summary = db.query(Summary).filter(Summary.document_id == document_id).first()
            if summary is not None:
                summary.status = "failed"
                summary.error = str(exc)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()



@router.post("/upload", response_model=DocumentOut)
@upload_router.post("/upload", response_model=DocumentOut)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{suffix}'. Supported formats: PDF, DOCX, PPTX, TXT, MD",
        )

    upload_root = Path(settings.resolved(settings.upload_dir))
    upload_root.mkdir(parents=True, exist_ok=True)
    original_name = Path(file.filename or "document").name
    stored_name = f"{user.id}_{uuid4().hex}_{original_name}"
    dest = upload_root / stored_name

    # Stream the upload to disk in 1 MB chunks and enforce a size limit without
    # loading the whole file into memory (keeps large uploads fast and safe).
    max_bytes = max(settings.max_upload_mb, 1) * 1024 * 1024
    size = 0
    too_large = False
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                too_large = True
                break
            out.write(chunk)
    await file.close()
    if too_large:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Maximum allowed size is {settings.max_upload_mb} MB.",
        )

    doc = Document(
        user_id=user.id,
        filename=file.filename or stored_name,
        filepath=str(dest),
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    extracted_text = None
    chunks: list[str] = []
    chunks_stored = 0
    try:
        text = extract_text(dest)
        if not text.strip():
            raise ValueError("No text could be extracted from the file")
        extracted_text = text
        chunks = chunk_text(text)
        chunks_stored = index_document(user.id, doc.id, text)
        summary = Summary(
            document_id=doc.id,
            key_concepts=[],
            definitions=[],
            important_points=[],
            examples=[],
            exam_notes="Summary is being generated. You can already ask questions about this document.",
            status="generating",
        )
        db.add(summary)
        doc.status = "ready"
        db.commit()
        db.refresh(doc)
        background_tasks.add_task(generate_document_summary, user.id, doc.id)
    except Exception as exc:
        doc.status = "failed"
        doc.error = str(exc)
        db.commit()
        db.refresh(doc)

    response = DocumentOut.model_validate(doc)
    response.message = (
        "uploaded successfully"
        if doc.status == "ready"
        else "file uploaded, but processing failed"
    )
    response.extracted_text = extracted_text
    response.chunks = chunks
    response.chunks_stored = chunks_stored
    return response


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user.id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    filepath = Path(doc.filepath)
    try:
        delete_document_index(user.id, doc.id)
    except Exception:
        pass
    if filepath.exists():
        filepath.unlink()
    # Remove quiz-related data so no orphaned attempts/topic scores/performance remain.
    quiz_ids = [q.id for q in db.query(Quiz.id).filter(Quiz.document_id == doc.id).all()]
    if quiz_ids:
        db.query(Attempt).filter(Attempt.quiz_id.in_(quiz_ids)).delete(synchronize_session=False)
    db.query(Quiz).filter(Quiz.document_id == doc.id).delete(synchronize_session=False)
    db.query(TopicScore).filter(TopicScore.document_id == doc.id).delete(synchronize_session=False)
    db.query(SkillScore).filter(SkillScore.document_id == doc.id).delete(synchronize_session=False)
    db.query(Performance).filter(Performance.document_id == doc.id).delete(synchronize_session=False)
    if doc.summary:
        db.delete(doc.summary)
    db.delete(doc)
    db.commit()
    return {"message": "document deleted successfully", "document_id": document_id}



@router.get("", response_model=list[DocumentOut])
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Document)
        .filter(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
        .all()
    )


@router.get("/{document_id}/summary", response_model=SummaryOut)
def get_summary(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user.id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "ready" or doc.summary is None:
        raise HTTPException(status_code=409, detail="Summary is not ready yet")
    summary = doc.summary
    return SummaryOut(
        document_id=doc.id,
        key_concepts=summary.key_concepts or [],
        definitions=summary.definitions or [],
        important_points=summary.important_points or [],
        examples=summary.examples or [],
        exam_notes=summary.exam_notes or "",
        status=summary.status or "ready",
        error=summary.error,
    )


@router.post("/{document_id}/summarize", response_model=SummaryOut)
def trigger_summarize(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trigger or regenerate the AI structured summary for an uploaded document."""
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user.id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "ready":
        raise HTTPException(status_code=400, detail="Document is not ready for summarization")

    full_text = ""
    filepath = Path(doc.filepath)
    if filepath.exists():
        try:
            full_text = extract_text(filepath)
        except Exception as e:
            logger.warning(f"Could not extract text from {filepath}: {e}")

    summary = doc.summary or Summary(document_id=doc.id)
    try:
        result = run_learning_graph(
            mode="summarize",
            user_id=user.id,
            document_id=doc.id,
            db=db,
            context=full_text if full_text.strip() else None,
        )
        summary_data = result.get("summary", {})
        summary.key_concepts = summary_data.get("key_concepts", [])
        summary.definitions = summary_data.get("definitions", [])
        summary.important_points = summary_data.get("important_points", [])
        summary.examples = summary_data.get("examples", [])
        summary.exam_notes = summary_data.get("exam_notes", "")
        summary.status = "ready"
        summary.error = None
    except Exception as exc:
        logger.error(f"Regenerate summary failed for document {doc.id}: {exc}", exc_info=True)
        summary.status = "failed"
        summary.error = str(exc)
    db.add(summary)
    db.commit()
    db.refresh(summary)

    return SummaryOut(
        document_id=doc.id,
        key_concepts=summary.key_concepts or [],
        definitions=summary.definitions or [],
        important_points=summary.important_points or [],
        examples=summary.examples or [],
        exam_notes=summary.exam_notes or "",
        status=summary.status or "ready",
        error=summary.error,
    )


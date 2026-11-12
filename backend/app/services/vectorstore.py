from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document as LCDocument
from langchain_ollama import OllamaEmbeddings

from app.core.config import settings
from app.services.ingest import chunk_text

logger = logging.getLogger(__name__)


def _embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


def _store(user_id: int, document_id: int) -> Chroma:
    persist = Path(settings.resolved(settings.chroma_dir))
    persist.mkdir(parents=True, exist_ok=True)
    collection = f"user_{user_id}_doc_{document_id}"
    return Chroma(
        collection_name=collection,
        persist_directory=str(persist),
        embedding_function=_embeddings(),
    )


def index_document(user_id: int, document_id: int, text: str) -> int:
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("Document produced no chunks")
    store = _store(user_id, document_id)
    docs = [
        LCDocument(
            page_content=chunk,
            metadata={"user_id": user_id, "document_id": document_id, "chunk": i},
        )
        for i, chunk in enumerate(chunks)
    ]
    store.add_documents(docs)
    return len(docs)


def retrieve_context(user_id: int, document_id: int, query: str, k: int = 6) -> tuple[str, list[str]]:
    store = _store(user_id, document_id)
    docs = store.similarity_search(query, k=k)
    snippets = [doc.page_content.strip() for doc in docs if doc.page_content.strip()]
    return "\n\n---\n\n".join(snippets), snippets


def retrieve_text_context(text: str, query: str, k: int = 6) -> tuple[str, list[str]]:
    """Retrieve relevant chunks without embeddings when a vector index is unavailable."""
    chunks = chunk_text(text)
    if not chunks:
        return "", []

    stop_words = {
        "about", "and", "are", "can", "does", "example", "explain", "for",
        "give", "how", "into", "main", "please", "simple", "simply", "the",
        "this", "what", "with", "you",
    }
    terms = {
        term.lower()
        for term in re.findall(r"[A-Za-z0-9]+", query)
        if len(term) > 2 and term.lower() not in stop_words
    }
    if not terms:
        selected = chunks[:k]
    else:
        ranked = sorted(
            enumerate(chunks),
            key=lambda item: (
                sum(
                    1
                    for term in terms
                    if re.search(rf"\b{re.escape(term)}\b", item[1], re.IGNORECASE)
                ),
                -item[0],
            ),
            reverse=True,
        )
        selected = [chunk for _, chunk in ranked[:k]]
        if not selected:
            selected = chunks[:k]

    return "\n\n---\n\n".join(selected), selected


def delete_document_index(user_id: int, document_id: int) -> None:
    try:
        _store(user_id, document_id).delete_collection()
    except Exception:
        pass


def recover_vectorstore() -> None:
    """Rebuild an incompatible persisted Chroma store from uploaded documents."""
    persist = Path(settings.resolved(settings.chroma_dir))
    if not persist.exists():
        return
    marker = persist / ".studysync_rebuilt"
    if marker.exists():
        return

    backup = persist.with_name(
        f"{persist.name}_incompatible_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    try:
        # Do not open the old client: incompatible Chroma Rust stores can poison
        # the process-wide client before the replacement store is created.
        shutil.move(str(persist), str(backup))
        persist.mkdir(parents=True, exist_ok=True)
        logger.warning("Moved persisted Chroma store to %s for rebuilding", backup)
    except OSError:
        logger.exception("Could not move incompatible Chroma store %s", persist)
        return

    from app.db.session import SessionLocal
    from app.models import Document
    from app.services.ingest import extract_text

    db = SessionLocal()
    try:
        documents = db.query(Document).filter(Document.status == "ready").all()
        for document in documents:
            filepath = Path(document.filepath)
            if not filepath.exists():
                logger.warning("Skipping document %s; file is missing: %s", document.id, filepath)
                continue
            try:
                text = extract_text(filepath)
                index_document(document.user_id, document.id, text)
            except Exception:
                logger.exception("Could not rebuild index for document %s", document.id)
    finally:
        db.close()
    marker.touch()



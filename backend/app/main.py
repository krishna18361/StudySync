from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import init_db
from app.models import entities  # noqa: F401
from app.routers import ask, auth, documents, performance, quiz

Path(settings.resolved(settings.upload_dir)).mkdir(parents=True, exist_ok=True)
Path(settings.resolved(settings.chroma_dir)).mkdir(parents=True, exist_ok=True)
init_db()

app = FastAPI(title="StudySync AI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(documents.upload_router)
app.include_router(ask.router)
app.include_router(quiz.router)
app.include_router(performance.router)


@app.get("/")
def home():
    return {"message": "StudySync AI Backend Running"}

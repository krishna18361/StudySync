from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas.question import QuestionRequest


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    learner_level: str = "beginner"
    learning_preferences: Optional[dict[str, Any]] = None

    class Config:
        from_attributes = True


class LearnerAssessmentRequest(BaseModel):
    learner_level: Optional[str] = None  # "beginner" | "intermediate" | "advanced"
    learning_style: Optional[str] = "analogy_and_examples"  # "theory" | "practical" | "analogy_and_examples"
    study_goals: Optional[str] = "exam_prep"  # "conceptual" | "exam_prep" | "quick_revision"
    preferred_depth: Optional[str] = "simplified"  # "simplified" | "detailed" | "deep_dive"


class LearnerAssessmentResponse(BaseModel):
    learner_level: str
    learning_preferences: dict[str, Any]
    message: str


class DocumentOut(BaseModel):
    id: int
    filename: str
    message: str = ""
    status: str
    error: Optional[str] = None
    extracted_text: Optional[str] = None
    chunks: list[str] = []
    chunks_stored: int = 0

    class Config:
        from_attributes = True


class SummaryOut(BaseModel):
    document_id: int
    key_concepts: list[str]
    definitions: list[dict[str, Any]]
    important_points: list[str]
    examples: list[dict[str, Any]] = []
    exam_notes: str
    status: str = "ready"
    error: Optional[str] = None


class AskRequest(BaseModel):
    document_id: int
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[str]


class QuizCreateRequest(BaseModel):
    document_id: int
    focus_weak_areas: bool = False


class QuizQuestionOut(BaseModel):
    id: int
    type: str
    prompt: str
    options: Optional[list[str]] = None
    topic: str


class QuizOut(BaseModel):
    id: int
    document_id: int
    difficulty: str
    status: str = "ready"
    error: Optional[str] = None
    questions: list[QuizQuestionOut]


class QuizSubmitRequest(BaseModel):
    answers: list[str]


class QuizResultItem(BaseModel):
    index: int
    topic: str
    correct: bool
    expected: str
    given: str
    explanation: Optional[str] = ""


class QuizSubmitResponse(BaseModel):
    score: float
    results: list[QuizResultItem]
    difficulty: str
    weak_topics: list[str]


class TopicScoreOut(BaseModel):
    topic: str
    correct: int
    total: int
    skipped: int = 0
    accuracy: float


class SkillScoreOut(BaseModel):
    skill: str
    correct: int
    total: int
    accuracy: float


class AttemptHistoryItem(BaseModel):
    id: int
    score: float
    difficulty: str = "beginner"
    created_at: Optional[datetime] = None


class PerformanceOut(BaseModel):
    document_id: Optional[int] = None
    difficulty: str
    quizzes_taken: int
    average_score: float
    best_score: float = 0
    latest_score: float = 0
    history: list[AttemptHistoryItem] = []
    weak_topics: list[TopicScoreOut]
    topics: list[TopicScoreOut]
    skills: list[SkillScoreOut] = []


from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User
from app.schemas import (
    LearnerAssessmentRequest,
    LearnerAssessmentResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        learner_level="beginner",
        learning_preferences={"learning_style": "analogy_and_examples", "study_goals": "exam_prep"},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/assessment", response_model=LearnerAssessmentResponse)
def assess_learner(
    body: LearnerAssessmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    level = (body.learner_level or "beginner").lower()
    if level not in {"beginner", "intermediate", "advanced", "exam"}:
        level = "beginner"

    prefs = {
        "learning_style": body.learning_style or "analogy_and_examples",
        "study_goals": body.study_goals or "exam_prep",
        "preferred_depth": body.preferred_depth or "simplified",
    }

    user.learner_level = level
    user.learning_preferences = prefs
    db.commit()
    db.refresh(user)

    return LearnerAssessmentResponse(
        learner_level=user.learner_level,
        learning_preferences=user.learning_preferences,
        message=f"Learner profile updated to {user.learner_level.capitalize()}.",
    )


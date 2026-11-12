from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.agents.quiz import normalize_skill
from app.models import Attempt, Performance, Quiz, SkillScore, TopicScore, User
from app.schemas import AttemptHistoryItem, PerformanceOut, QuizSubmitResponse, SkillScoreOut, TopicScoreOut
from app.services.llm import complete

LEVELS = ["beginner", "intermediate", "exam"]
WEAK_THRESHOLD = 0.6


def current_difficulty(db: Optional[Session], user_id: int, document_id: int) -> str:
    if db is None:
        return "beginner"
    row = (
        db.query(Performance)
        .filter(Performance.user_id == user_id, Performance.document_id == document_id)
        .first()
    )
    if row:
        return row.difficulty
    user = db.query(User).filter(User.id == user_id).first()
    return user.learner_level if user and user.learner_level else "beginner"


def weak_topic_names(db: Optional[Session], user_id: int, document_id: int) -> list[str]:
    if db is None:
        return []
    rows = (
        db.query(TopicScore)
        .filter(TopicScore.user_id == user_id, TopicScore.document_id == document_id)
        .all()
    )
    weak = []
    for row in rows:
        if row.total and (row.correct / row.total) < WEAK_THRESHOLD:
            weak.append(row.topic)
    return weak


def _normalize(text: str) -> str:
    """Normalize an answer/option for lenient comparison.

    Lowercases, strips surrounding punctuation/whitespace, and collapses
    internal whitespace so wording drift in AI-generated options does not
    unfairly mark a correct choice as wrong.
    """
    cleaned = re.sub(r"[^\w\s]", " ", str(text or "")).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


def _grade_short(prompt: str, expected: str, given: str) -> bool:
    raw = complete(
        "You grade short answers. Reply with only YES or NO.",
        f"Question: {prompt}\nExpected: {expected}\nStudent: {given}\nIs the student answer essentially correct?",
    )
    return raw.strip().upper().startswith("Y")


def _adapt_difficulty(current: str, score: float) -> str:
    idx = LEVELS.index(current) if current in LEVELS else 0
    if score >= 0.8 and idx < len(LEVELS) - 1:
        return LEVELS[idx + 1]
    if score < 0.5 and idx > 0:
        return LEVELS[idx - 1]
    return LEVELS[idx]


def grade_and_update(db: Session, user: User, quiz: Quiz, answers: list[str]) -> QuizSubmitResponse:
    questions = quiz.questions or []
    results = []
    correct_count = 0
    for idx, question in enumerate(questions):
        given = answers[idx] if idx < len(answers) else ""
        expected = str(question.get("answer", "")).strip()
        qtype = question.get("type")
        # An empty answer counts as "skipped" rather than incorrect.
        skipped = not str(given).strip()
        if skipped:
            ok = False
        elif qtype == "short":
            ok = _grade_short(question.get("prompt", ""), expected, given)
        else:
            ok = _normalize(given) == _normalize(expected)
        if ok:
            correct_count += 1
        results.append(
            {
                "index": idx,
                "topic": question.get("topic", "General"),
                "correct": ok,
                "expected": expected,
                "given": given,
                "explanation": question.get("explanation") or f"According to the notes, the correct answer is {expected}.",
            }
        )
        topic = question.get("topic") or "General"
        row = (
            db.query(TopicScore)
            .filter(
                TopicScore.user_id == user.id,
                TopicScore.document_id == quiz.document_id,
                TopicScore.topic == topic,
            )
            .first()
        )
        if row is None:
            row = TopicScore(
                user_id=user.id,
                document_id=quiz.document_id,
                topic=topic,
                correct=0,
                total=0,
                skipped=0,
            )
            db.add(row)
            # Flush so later questions that map to the same topic reuse this row
            # instead of inserting a duplicate (UNIQUE on user_id/document_id/topic).
            db.flush()
        row.total += 1
        if skipped:
            row.skipped = (row.skipped or 0) + 1
        elif ok:
            row.correct += 1

        # Aggregate per-skill mastery (conceptual / recall / application / problem solving).
        skill = normalize_skill(question.get("skill"), question.get("type") or "mcq")
        srow = (
            db.query(SkillScore)
            .filter(
                SkillScore.user_id == user.id,
                SkillScore.document_id == quiz.document_id,
                SkillScore.skill == skill,
            )
            .first()
        )
        if srow is None:
            srow = SkillScore(
                user_id=user.id,
                document_id=quiz.document_id,
                skill=skill,
                correct=0,
                total=0,
            )
            db.add(srow)
            db.flush()
        srow.total += 1
        if ok:
            srow.correct += 1

    score = correct_count / len(questions) if questions else 0.0
    attempt = Attempt(
        quiz_id=quiz.id,
        user_id=user.id,
        answers=answers,
        results=results,
        score=score,
    )
    db.add(attempt)

    perf = (
        db.query(Performance)
        .filter(Performance.user_id == user.id, Performance.document_id == quiz.document_id)
        .first()
    )
    if perf is None:
        perf = Performance(
            user_id=user.id,
            document_id=quiz.document_id,
            difficulty=quiz.difficulty or "beginner",
            quizzes_taken=0,
            average_score=0,
        )
        db.add(perf)
    taken = perf.quizzes_taken
    perf.average_score = ((perf.average_score * taken) + score) / (taken + 1)
    perf.quizzes_taken = taken + 1
    perf.difficulty = _adapt_difficulty(perf.difficulty or "beginner", score)
    db.commit()

    weak = [
        TopicScoreOut(
            topic=row.topic,
            correct=row.correct,
            total=row.total,
            skipped=row.skipped or 0,
            accuracy=row.correct / row.total if row.total else 0,
        )
        for row in db.query(TopicScore)
        .filter(TopicScore.user_id == user.id, TopicScore.document_id == quiz.document_id)
        .all()
        if row.total and (row.correct / row.total) < WEAK_THRESHOLD
    ]
    return QuizSubmitResponse(
        score=score,
        results=results,
        difficulty=perf.difficulty,
        weak_topics=[item.topic for item in weak],
    )


def _attempt_history(db: Session, user_id: int, document_id: Optional[int]) -> list[AttemptHistoryItem]:
    query = (
        db.query(Attempt, Quiz.difficulty)
        .join(Quiz, Quiz.id == Attempt.quiz_id)
        .filter(Attempt.user_id == user_id)
    )
    if document_id is not None:
        query = query.filter(Quiz.document_id == document_id)
    rows = query.order_by(Attempt.created_at.asc(), Attempt.id.asc()).all()
    return [
        AttemptHistoryItem(
            id=attempt.id,
            score=attempt.score,
            difficulty=difficulty or "beginner",
            created_at=attempt.created_at,
        )
        for attempt, difficulty in rows
    ]


def get_performance(db: Session, user_id: int, document_id: Optional[int]) -> PerformanceOut:
    query = db.query(TopicScore).filter(TopicScore.user_id == user_id)
    perf_query = db.query(Performance).filter(Performance.user_id == user_id)
    skill_query = db.query(SkillScore).filter(SkillScore.user_id == user_id)
    if document_id is not None:
        query = query.filter(TopicScore.document_id == document_id)
        perf_query = perf_query.filter(Performance.document_id == document_id)
        skill_query = skill_query.filter(SkillScore.document_id == document_id)
    topics = []
    for row in query.all():
        topics.append(
            TopicScoreOut(
                topic=row.topic,
                correct=row.correct,
                total=row.total,
                skipped=row.skipped or 0,
                accuracy=row.correct / row.total if row.total else 0,
            )
        )
    weak = [t for t in topics if t.total and t.accuracy < WEAK_THRESHOLD]

    skills = [
        SkillScoreOut(
            skill=row.skill,
            correct=row.correct,
            total=row.total,
            accuracy=row.correct / row.total if row.total else 0,
        )
        for row in skill_query.all()
        if row.total
    ]

    history = _attempt_history(db, user_id, document_id)
    best_score = max((h.score for h in history), default=0)
    latest_score = history[-1].score if history else 0

    perfs = perf_query.all()
    if not perfs:
        return PerformanceOut(
            document_id=document_id,
            difficulty="beginner",
            quizzes_taken=len(history),
            average_score=(sum(h.score for h in history) / len(history)) if history else 0,
            best_score=best_score,
            latest_score=latest_score,
            history=history,
            weak_topics=weak,
            topics=topics,
            skills=skills,
        )
    quizzes_taken = sum(p.quizzes_taken for p in perfs)
    if quizzes_taken:
        average = sum(p.average_score * p.quizzes_taken for p in perfs) / quizzes_taken
    else:
        average = 0
    latest = perfs[-1]
    return PerformanceOut(
        document_id=document_id,
        difficulty=latest.difficulty,
        quizzes_taken=quizzes_taken,
        average_score=average,
        best_score=best_score,
        latest_score=latest_score,
        history=history,
        weak_topics=weak,
        topics=topics,
        skills=skills,
    )

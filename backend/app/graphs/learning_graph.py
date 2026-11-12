from __future__ import annotations

from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.doubt import answer_doubt
from app.agents.quiz import generate_quiz
from app.agents.summarizer import summarize_from_context
from app.models import User, Document
from app.services.llm import complete
from app.services.performance import current_difficulty, weak_topic_names
from app.services.vectorstore import retrieve_context, retrieve_text_context
from app.services.ingest import extract_text
from pathlib import Path


class LearningState(TypedDict, total=False):
    mode: str
    user_id: int
    document_id: int
    question: str
    history: list[dict[str, str]]
    learner_level: str
    context: str
    sources: list[str]
    summary: dict[str, Any]
    answer: str
    quiz: dict[str, Any]
    weak_topics: list[str]
    difficulty: str
    adaptive_advice: str
    next_agent: str
    query: str


def coordinator_node(state: LearningState) -> LearningState:
    """Coordinator Agent: Orchestrates the multi-agent workflow based on user goal and state."""
    mode = state.get("mode") or "summarize"
    weak_topics = state.get("weak_topics") or []

    # Map requested mode to agent and specialized retrieval query
    if mode in {"answer", "doubt"}:
        next_agent = "doubt"
        query = state.get("question") or "important concepts definitions"
    elif mode == "quiz":
        next_agent = "quiz"
        if weak_topics:
            query = f"Targeted review of weak topics: {', '.join(weak_topics)}"
        else:
            query = "key concepts definitions important points principles examples"
    elif mode == "adaptive":
        next_agent = "adaptive"
        query = f"Foundational review: {', '.join(weak_topics)}" if weak_topics else "key concepts"
    else:
        next_agent = "summarize"
        query = "key concepts definitions important points exam notes examples overview"

    return {
        "next_agent": next_agent,
        "query": query,
    }


def retrieve_node(state: LearningState) -> LearningState:
    # If full or partial document context is already supplied
    if state.get("context"):
        return {"context": state["context"], "sources": state.get("sources") or []}

    mode = state.get("mode") or "summarize"
    k = 12 if mode == "summarize" else 6
    query = state.get("query") or state.get("question") or "key concepts definitions"
    
    context, sources = "", []
    try:
        # 1. Try Primary Retrieval: Vector Search via ChromaDB
        context, sources = retrieve_context(state["user_id"], state["document_id"], query, k=k)
    except Exception as exc:
        # 2. Fallback Retrieval: Keyword search on raw document text if vectorstore fails
        # This prevents the whole doubt agent from failing if embeddings are down.
        db = state.get("db")
        if db:
            doc = db.query(Document).filter(Document.id == state["document_id"]).first()
            if doc and Path(doc.filepath).exists():
                try:
                    text = extract_text(Path(doc.filepath))
                    context, sources = retrieve_text_context(text, query, k=k)
                except Exception:
                    pass
    
    return {"context": context, "sources": sources}


def summarize_node(state: LearningState) -> LearningState:
    """Summarization Agent."""
    level = state.get("learner_level") or state.get("difficulty") or "beginner"
    return {"summary": summarize_from_context(state.get("context") or "", learner_level=level)}


def doubt_node(state: LearningState) -> LearningState:
    """Doubt Resolution Agent."""
    level = state.get("learner_level") or state.get("difficulty") or "beginner"
    answer = answer_doubt(
        state.get("question") or "",
        state.get("context") or "",
        learner_level=level,
        history=state.get("history"),
    )
    return {"answer": answer}


def quiz_node(state: LearningState) -> LearningState:
    """Quiz Generation Agent."""
    quiz = generate_quiz(
        state.get("context") or "",
        state.get("difficulty") or "beginner",
        state.get("weak_topics") or [],
    )
    return {"quiz": quiz}


def adaptive_node(state: LearningState) -> LearningState:
    """Adaptive Agent: Evaluates weak areas and crafts a personalized study plan."""
    weak_topics = state.get("weak_topics") or []
    difficulty = state.get("difficulty") or "beginner"
    level = state.get("learner_level") or "beginner"

    system_prompt = (
        "You are the StudySync Adaptive Learning Coach. "
        "Review the student's current level and weak areas, and provide actionable, encouraging advice."
    )
    user_prompt = (
        f"Student Learner Level: {level}\n"
        f"Current Difficulty: {difficulty}\n"
        f"Identified Weak Topics: {', '.join(weak_topics) if weak_topics else 'None yet (Great job!)'}\n\n"
        "Provide a 3-step personalized recovery plan to master these concepts."
    )
    advice = complete(system_prompt, user_prompt, num_predict=500)
    return {"adaptive_advice": advice}


def route_coordinator(state: LearningState) -> str:
    return state.get("next_agent") or "summarize"


def build_graph():
    builder = StateGraph(LearningState)
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("summarize", summarize_node)
    builder.add_node("doubt", doubt_node)
    builder.add_node("quiz", quiz_node)
    builder.add_node("adaptive", adaptive_node)

    # Edge from START to Coordinator
    builder.add_edge(START, "coordinator")
    builder.add_edge("coordinator", "retrieve")

    # Dynamic routing from Retrieve to the assigned worker agent
    builder.add_conditional_edges(
        "retrieve",
        route_coordinator,
        {
            "summarize": "summarize",
            "doubt": "doubt",
            "quiz": "quiz",
            "adaptive": "adaptive",
        },
    )

    builder.add_edge("summarize", END)
    builder.add_edge("doubt", END)
    builder.add_edge("quiz", END)
    builder.add_edge("adaptive", END)
    return builder.compile()


_GRAPH = build_graph()


def run_learning_graph(
    mode: str,
    user_id: int,
    document_id: int,
    question: Optional[str] = None,
    history: Optional[list[dict[str, str]]] = None,
    db: Optional[Session] = None,
    focus_weak_areas: bool = False,
    context: Optional[str] = None,
) -> LearningState:
    learner_level = "beginner"
    if db is not None:
        user_row = db.query(User).filter(User.id == user_id).first()
        if user_row and user_row.learner_level:
            learner_level = user_row.learner_level

    weak = weak_topic_names(db, user_id, document_id) if db is not None else []
    diff = current_difficulty(db, user_id, document_id) if db is not None else learner_level

    state: LearningState = {
        "mode": mode,
        "user_id": user_id,
        "document_id": document_id,
        "question": question or "",
        "history": history or [],
        "learner_level": learner_level,
        "weak_topics": weak if (focus_weak_areas or weak) else [],
        "difficulty": diff,
    }
    if context:
        state["context"] = context
    return _GRAPH.invoke(state)


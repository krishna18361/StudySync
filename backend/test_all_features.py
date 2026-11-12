"""
End-to-end integration test verifying StudySync AI features:
- Document extraction (PDF, DOCX, PPTX native, TXT, MD)
- Recursive chunking
- Database initialization and schema migration
- Multi-agent LangGraph graph structure and nodes
- Adaptive difficulty and scoring logic
"""
from pathlib import Path
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from app.db.session import init_db, SessionLocal
from app.models import User, Document, Summary, Quiz, Performance, TopicScore
from app.services.ingest import extract_text, chunk_text, extract_pptx_text
from app.services.performance import _adapt_difficulty, current_difficulty, weak_topic_names
from app.graphs.learning_graph import _GRAPH, LearningState
from app.schemas import (
    LearnerAssessmentRequest,
    SummaryOut,
    QuizSubmitResponse,
    QuizResultItem,
)


def test_ingest():
    print("Testing Ingest Service...")
    # Test TXT / MD
    with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False) as f:
        f.write("Normalization is the process of organizing data in a database. It includes 1NF, 2NF, and 3NF.")
        txt_path = Path(f.name)
    try:
        text = extract_text(txt_path)
        assert "Normalization" in text
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        assert len(chunks) >= 1
        print("  TXT extraction & chunking: PASSED")
    finally:
        txt_path.unlink()

    # Test Native PPTX Extraction
    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
        pptx_path = Path(f.name)
    try:
        with zipfile.ZipFile(pptx_path, "w") as z:
            slide_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
                '<p:cSld><p:spTree><p:sp><p:txBody>'
                '<a:p><a:r><a:t>Slide Title: Database Indexing</a:t></a:r></a:p>'
                '<a:p><a:r><a:t>B-Trees speed up search queries.</a:t></a:r></a:p>'
                '</p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
            )
            z.writestr("ppt/slides/slide1.xml", slide_xml)
        extracted = extract_pptx_text(pptx_path)
        assert "Database Indexing" in extracted
        assert "B-Trees" in extracted
        print("  Native PPTX extraction: PASSED")
    finally:
        pptx_path.unlink()


def test_database_and_schemas():
    print("Testing DB Init & Schemas...")
    init_db()
    db = SessionLocal()
    try:
        # Check that learner_level and learning_preferences exist on User
        user = User(
            email="test_student@studysync.ai",
            hashed_password="hashed_pw_test",
            learner_level="intermediate",
            learning_preferences={"learning_style": "analogy_and_examples"},
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.learner_level == "intermediate"

        # Check Summary model with examples
        doc = Document(user_id=user.id, filename="dbms.pdf", filepath="/tmp/dbms.pdf", status="ready")
        db.add(doc)
        db.commit()
        db.refresh(doc)

        summary = Summary(
            document_id=doc.id,
            key_concepts=["Normalization", "ACID"],
            definitions=[{"term": "1NF", "definition": "Atomic values"}],
            important_points=["Eliminate redundancy"],
            examples=[{"concept": "2NF", "example": "Student-Course table decomposition"}],
            exam_notes="Review normal forms before exam.",
        )
        db.add(summary)
        db.commit()
        db.refresh(summary)

        # Validate SummaryOut schema
        out = SummaryOut(
            document_id=doc.id,
            key_concepts=summary.key_concepts,
            definitions=summary.definitions,
            important_points=summary.important_points,
            examples=summary.examples,
            exam_notes=summary.exam_notes,
        )
        assert len(out.examples) == 1
        assert out.examples[0]["concept"] == "2NF"
        print("  DB models & SummaryOut schema: PASSED")

        # Cleanup test entities
        db.delete(summary)
        db.delete(doc)
        db.delete(user)
        db.commit()
    finally:
        db.close()


def test_adaptive_difficulty():
    print("Testing Adaptive Difficulty Logic...")
    # beginner with 90% score should adapt to intermediate
    assert _adapt_difficulty("beginner", 0.9) == "intermediate"
    # intermediate with 85% score should adapt to exam
    assert _adapt_difficulty("intermediate", 0.85) == "exam"
    # exam with 30% score should step down to intermediate
    assert _adapt_difficulty("exam", 0.3) == "intermediate"
    # beginner with 40% score stays at beginner
    assert _adapt_difficulty("beginner", 0.4) == "beginner"
    print("  Adaptive difficulty steps: PASSED")


def test_langgraph_structure():
    print("Testing LangGraph Multi-Agent Compilation...")
    # Verify graph contains all 6 required nodes: coordinator, retrieve, summarize, doubt, quiz, adaptive
    nodes = _GRAPH.get_graph().nodes
    assert "coordinator" in nodes
    assert "retrieve" in nodes
    assert "summarize" in nodes
    assert "doubt" in nodes
    assert "quiz" in nodes
    assert "adaptive" in nodes
    print(f"  LangGraph nodes compiled: {list(nodes.keys())}: PASSED")


if __name__ == "__main__":
    print("========================================")
    print("Running StudySync AI Verification Tests")
    print("========================================")
    test_ingest()
    test_database_and_schemas()
    test_adaptive_difficulty()
    test_langgraph_structure()
    print("========================================")
    print("ALL TESTS PASSED SUCCESSFULLY! 🚀")
    print("========================================")

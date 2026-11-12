"""
End-to-end verification test for StudySync AI Summarization Agent:
- Tests PDF extraction
- Tests Summarization Agent execution with Ollama llama3
- Validates the structured output schema (key concepts, definitions, important points, examples, exam notes)
- Validates that exam_notes does NOT contain placeholder template strings
"""
import logging
from pathlib import Path

from app.agents.summarizer import summarize_from_context
from app.db.session import SessionLocal, init_db
from app.models import Document, Summary, User
from app.services.ingest import extract_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_summarizer")


def test_summarizer_agent():
    print("==================================================")
    print("🚀 Testing StudySync AI Summarization Agent")
    print("==================================================")

    pdf_sample = Path("/Users/ananthakrishna/Desktop/StudySync/uploads/2_c2fff189bee0484197c23a38fc419b3e_CODING.pdf")
    if not pdf_sample.exists():
        print(f"⚠️ Sample PDF not found at {pdf_sample}, creating synthetic sample notes...")
        text = (
            "Database Normalization and Relational Design\n"
            "Normalization is the process of organizing data to reduce redundancy and improve data integrity.\n"
            "First Normal Form (1NF): Requires atomic values and unique records.\n"
            "Second Normal Form (2NF): Requires 1NF and no partial dependencies.\n"
            "Third Normal Form (3NF): Requires 2NF and no transitive dependencies.\n"
            "Example: Splitting Student-Course-Instructor into Student-Course and Course-Instructor tables."
        )
    else:
        print(f"📄 Extracting text from real uploaded PDF: {pdf_sample.name}")
        text = extract_text(pdf_sample)
        print(f"✅ Extracted {len(text)} characters of text from PDF.")

    print("\n🧠 Invoking Summarization Agent via Ollama Llama 3...")
    summary = summarize_from_context(text, learner_level="beginner")

    print("\n📊 Agent Output Inspection:")
    print(f"  • Key Concepts found ({len(summary.get('key_concepts', []))}): {summary.get('key_concepts', [])[:5]}...")
    print(f"  • Definitions extracted ({len(summary.get('definitions', []))}):")
    for d in summary.get("definitions", [])[:3]:
        print(f"    - {d.get('term')}: {d.get('definition')[:80]}...")
    print(f"  • Important Points extracted ({len(summary.get('important_points', []))}):")
    for pt in summary.get("important_points", [])[:3]:
        print(f"    - {pt[:80]}...")
    print(f"  • Examples extracted ({len(summary.get('examples', []))}):")
    for eg in summary.get("examples", [])[:2]:
        print(f"    - {eg.get('concept')}: {eg.get('example')[:80]}...")
    
    exam_notes = summary.get("exam_notes", "")
    print(f"\n📝 Exam Revision Notes snippet:\n{exam_notes[:300]}...\n")

    # Schema Assertions
    assert isinstance(summary.get("key_concepts"), list), "key_concepts must be a list"
    assert len(summary["key_concepts"]) > 0, "key_concepts should not be empty"
    assert isinstance(summary.get("definitions"), list), "definitions must be a list"
    assert isinstance(summary.get("important_points"), list), "important_points must be a list"
    assert isinstance(summary.get("examples"), list), "examples must be a list"
    assert isinstance(exam_notes, str) and len(exam_notes.strip()) > 20, "exam_notes must be non-empty"
    assert "Comprehensive markdown notes summarizing the topics for fast exam revision" not in exam_notes, (
        "exam_notes should contain genuine synthesized content, not prompt template placeholders!"
    )

    print("==================================================")
    print("🎉 Summarization Agent Verification: PASSED! 🚀")
    print("==================================================")


if __name__ == "__main__":
    test_summarizer_agent()

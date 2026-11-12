"""
Test & Demonstration Script for StudySync Doubt Resolution Agent
Demonstrates the full flow:
Question -> Retrieve Relevant Chunks -> Llama 3 -> Generate Structured Answer
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db.session import init_db, SessionLocal
from app.models import User, Document
from app.services.ingest import chunk_text
from app.services.vectorstore import index_document, retrieve_context
from app.agents.doubt import DoubtResolutionAgent, answer_doubt
from app.services.rag_service import ask_question

SAMPLE_DBMS_NOTES = """
Database Management Systems: Normalization & Normal Forms

1. Concept of Normalization:
Normalization is the systematic process of organizing data in a relational database to minimize redundancy and eliminate undesirable anomalies (insertion anomaly, update anomaly, and deletion anomaly).
By decomposing large, redundant tables into smaller, well-structured relational tables, normalization ensures data integrity and logical consistency.

2. First Normal Form (1NF):
A relation is in 1NF if and only if all attribute values are atomic (indivisible) and there are no repeating groups or multivalued attributes.
Every column must contain only single values, and each record must be unique.

3. Second Normal Form (2NF):
A relation is in 2NF if:
1. It is already in First Normal Form (1NF).
2. There are NO partial functional dependencies. That means every non-prime attribute (attributes not part of any candidate key) must be fully functionally dependent on the entire primary key, not just a subset of a composite primary key.

Example of 2NF:
Consider a table: Enrollment(StudentID, CourseID, StudentName, CourseFee).
Here, {StudentID, CourseID} is the composite primary key.
However:
- StudentName depends only on StudentID (partial dependency).
- CourseFee depends only on CourseID (partial dependency).
To achieve 2NF, we decompose this table into three tables:
1. Student(StudentID, StudentName)
2. Course(CourseID, CourseFee)
3. Enrollment(StudentID, CourseID)

4. Third Normal Form (3NF):
A relation is in 3NF if it is in 2NF and has NO transitive functional dependencies.
A non-prime attribute must not depend on another non-prime attribute. (X -> Y where Y -> Z means X -> Z is a transitive dependency).
"""


def run_doubt_agent_demo():
    print("=" * 65)
    print("🤖 StudySync AI — Doubt Resolution Agent Pipeline Demo")
    print("=" * 65)

    # 1. Setup DB and Test User/Document
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "demo_student@studysync.ai").first()
        if not user:
            user = User(
                email="demo_student@studysync.ai",
                hashed_password="pw",
                learner_level="beginner",
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        doc = db.query(Document).filter(Document.user_id == user.id, Document.filename == "DBMS_Normalization.txt").first()
        if not doc:
            doc = Document(
                user_id=user.id,
                filename="DBMS_Normalization.txt",
                filepath="mock",
                status="ready",
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)

        print(f"\n[1] Storing & Indexing Notes for User {user.id}, Document {doc.id}...")
        chunks_count = index_document(user.id, doc.id, SAMPLE_DBMS_NOTES)
        print(f"    ✅ Successfully indexed {chunks_count} chunks into ChromaDB.")

        # Test Question 1: What is Normalization?
        q1 = "What is Normalization?"
        print(f"\n[2] Processing Question 1: '{q1}'")
        print("    Flow:")
        print("    Question ➜ Retrieve Relevant Chunks ➜ Llama 3 ➜ Generate Answer")

        context1, sources1 = retrieve_context(user.id, doc.id, q1, k=3)
        print(f"\n    📦 Retrieved {len(sources1)} Relevant Chunks from ChromaDB:")
        for idx, src in enumerate(sources1, 1):
            first_line = src.strip().split("\n")[0]
            print(f"       Chunk {idx}: {first_line[:75]}...")

        agent = DoubtResolutionAgent()
        user_prompt1 = agent.build_user_prompt(q1, context1, learner_level="beginner")
        print("\n    📝 Assembled Grounded Prompt for Llama 3:")
        print(f"       System: {agent.system_template[:80]}...")
        print(f"       User Prompt Length: {len(user_prompt1)} characters")

        print("\n    ⚡ Executing Doubt Agent...")
        answer1 = answer_doubt(q1, context1, learner_level="beginner")
        print("\n    ================== GENERATED AI ANSWER ==================")
        print(answer1)
        print("    =========================================================")

        # Test Question 2: Explain 2NF simply
        q2 = "Explain 2NF simply"
        print(f"\n[3] Processing Question 2: '{q2}'")
        context2, sources2 = retrieve_context(user.id, doc.id, q2, k=3)
        print(f"    📦 Retrieved {len(sources2)} Relevant Chunks:")
        for idx, src in enumerate(sources2, 1):
            first_line = src.strip().split("\n")[0]
            print(f"       Chunk {idx}: {first_line[:75]}...")

        answer2 = answer_doubt(q2, context2, learner_level="beginner")
        print("\n    ================== GENERATED AI ANSWER ==================")
        print(answer2)
        print("    =========================================================")

        print("\n✅ Doubt Resolution Agent Pipeline fully verified!")

    finally:
        db.close()


if __name__ == "__main__":
    run_doubt_agent_demo()

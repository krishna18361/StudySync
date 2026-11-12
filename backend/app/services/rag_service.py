from app.agents.doubt import answer_doubt
from app.services.vectorstore import retrieve_context


def ask_question(
    user_id: int,
    document_id: int,
    question: str,
    learner_level: str = "beginner",
    k: int = 5,
) -> tuple[str, list[str]]:
    """Doubt Resolution RAG pipeline:
    1. Retrieve relevant chunks from ChromaDB
    2. Pass chunks and question to Doubt Resolution Agent (Llama 3)
    3. Return structured answer with source citations
    """
    context, sources = retrieve_context(user_id, document_id, question, k=k)
    answer = answer_doubt(question, context, learner_level=learner_level)
    return answer, sources


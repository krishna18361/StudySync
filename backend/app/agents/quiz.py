from __future__ import annotations

from app.services.llm import complete_json, parse_json

SYSTEM = """You are the StudySync Quiz Generation Agent.
Create an accurate multiple-choice quiz strictly from the student's uploaded notes.
Return ONLY valid JSON with this exact shape (no markdown, no extra text):
{
  "questions": [
    {
      "type": "mcq",
      "prompt": "Clear question text?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": "Option A",
      "topic": "Concept/Topic Name",
      "skill": "recall",
      "explanation": "One short sentence (max 20 words) on why this is correct."
    }
  ]
}

Rules:
1. Generate EXACTLY 10 questions and every question MUST have type "mcq".
2. Every question MUST have exactly 4 distinct options.
3. "answer" MUST exactly match one of the strings in "options" — never a letter like "A".
4. Keep every prompt under 25 words and every explanation under 20 words.
5. Align difficulty with the requested difficulty (beginner, intermediate, exam).
6. Cover different topics from the notes and never repeat the same question.
7. If weak topics are provided, dedicate at least 4 questions to those specific weak topics.
8. "skill" MUST be exactly one of: "conceptual", "recall", "application", "problem_solving".
   - conceptual: understanding of ideas, definitions and why something works.
   - recall: remembering a fact, term, formula or number from the notes.
   - application: using a concept to solve or explain a concrete scenario.
   - problem_solving: multi-step reasoning, comparisons or troubleshooting.
   Across the 10 questions, cover at least three different skills.
"""

# Canonical skills used across grading, storage and the Skill Mastery radar.
SKILLS = {
    "conceptual": "Conceptual Understanding",
    "recall": "Recall",
    "application": "Application",
    "problem_solving": "Problem Solving",
}

# Fallback when the model omits a skill — derived from the question type.
_TYPE_TO_SKILL = {"true_false": "conceptual", "short": "application", "mcq": "recall"}


def normalize_skill(raw: str | None, qtype: str) -> str:
    """Map a model-provided skill (or the question type) onto a canonical key."""
    if raw:
        key = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "concept": "conceptual",
            "understanding": "conceptual",
            "conceptual_understanding": "conceptual",
            "memory": "recall",
            "remembering": "recall",
            "applying": "application",
            "problem": "problem_solving",
            "problem_solving": "problem_solving",
            "problemsolving": "problem_solving",
        }
        key = aliases.get(key, key)
        if key in SKILLS:
            return key
    return _TYPE_TO_SKILL.get(qtype, "recall")


def generate_quiz(context: str, difficulty: str, weak_topics: list[str]) -> dict:
    weak = ", ".join(weak_topics) if weak_topics else "none (general comprehensive coverage)"
    user_prompt = (
        f"Difficulty: {difficulty}\n"
        f"Student weak topics to emphasize: {weak}\n\n"
        f"Source material from student's notes:\n{context[:6000]}\n\n"
        f"Return the quiz JSON with exactly 10 multiple-choice questions now:"
    )

    try:
        raw = complete_json(SYSTEM, user_prompt, num_predict=2800)
        data = parse_json(raw)
    except Exception:
        data = {"questions": []}

    questions = data.get("questions") or []
    cleaned = []
    for q in questions[:10]:
        # Every question is forced to a 4-option MCQ so the quiz is uniform.
        qtype = "mcq"

        options = q.get("options")
        if not isinstance(options, list) or len(options) < 2:
            options = ["Option A", "Option B", "Option C", "Option D"]

        ans = str(q.get("answer", "")).strip()
        explanation = str(
            q.get("explanation")
            or f"Based on the notes, the correct answer is: {ans}."
        ).strip()

        item = {
            "type": qtype,
            "prompt": str(q.get("prompt") or "Question").strip(),
            "options": options,
            "answer": ans,
            "topic": str(q.get("topic") or "General").strip(),
            "skill": normalize_skill(q.get("skill"), qtype),
            "explanation": explanation,
        }
        cleaned.append(item)

    return {"questions": cleaned}


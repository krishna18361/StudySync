from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.services.llm import complete

logger = logging.getLogger(__name__)

# Fallback response when no context is available
FALLBACK_MESSAGE = (
    "### 💡 Explanation\n"
    "I could not find matching content in your uploaded notes for that question.\n\n"
    "### 🔍 Intuitive Analogy\n"
    "Imagine looking for a chapter that isn’t listed in the textbook’s index.\n\n"
    "### 📌 Concrete Example\n"
    "Try asking about a concept that appears in your notes.\n\n"
    "### 📝 Step-by-Step Breakdown\n"
    "1. Open the Summary tab to see indexed concepts.\n2. Choose a concept and ask a question.\n"
    "### 🎯 Exam Revision Tip\n"
    "Focus on the core syllabus terms for accurate answers."
)

SYSTEM_PROMPT = """You are the StudySync Doubt Resolution Agent — an expert pedagogical AI tutor dedicated to helping students deeply understand concepts from their uploaded notes.

Core Directives:
1. Grounding: Answer strictly using facts, principles, formulas, and examples found in the provided notes context.
2. Honesty Guardrail: If the student asks about a concept NOT in the notes, state clearly: "I could not find this concept in your uploaded notes." If possible, suggest the closest relevant topic that IS present in the notes.
3. Learner-Centric Adaptation:
   - Beginner: Use crystal-clear, jargon-free language, relatable everyday analogies, and intuitive walk-throughs.
   - Intermediate: Balance intuition with technical precision, operational logic, and relational mechanisms.
   - Advanced: Focus on formal definitions, edge cases, performance trade-offs, and exam-level rigor.
4. Structured Response Format:
   You MUST structure your response into these 5 distinct Markdown sections with exact headers:

### 💡 Explanation
[Direct, clear conceptual explanation answering the student's question, grounded strictly in the notes.]

### 🔍 Intuitive Analogy
[A memorable, relatable real-world comparison that makes the concept click instantly for a student at their learning level.]

### 📌 Concrete Example
[A concrete scenario, dry-run walkthrough, table, or code snippet directly drawn from or directly illustrating the notes.]

### 📝 Step-by-Step Breakdown
1. [First sequential step, condition, or mechanism]
2. [Second sequential step, condition, or mechanism]
3. [Third sequential step, condition, or mechanism]

### 🎯 Exam Revision Tip
[A high-yield exam takeaway, common trap to avoid, or formula/rule to remember on test day.]
"""


def parse_doubt_sections(text: str) -> dict[str, Any]:
    """Parse the markdown sections produced by Doubt Agent into structured fields for rich UI rendering."""
    if not text or not text.strip():
        return {
            "explanation": "",
            "analogy": "",
            "example": "",
            "steps": [],
            "exam_tip": "",
            "raw_markdown": "",
        }

    sections: dict[str, Any] = {
        "explanation": "",
        "analogy": "",
        "example": "",
        "steps": [],
        "exam_tip": "",
        "raw_markdown": text.strip(),
    }

    # Regex patterns for the 5 standard headers (more flexible with emojis)
    patterns = [
        ("explanation", r"###\s*.*Explanation\s*\n([\s\S]*?)(?=###|$)"),
        ("analogy", r"###\s*.*Analogy\s*\n([\s\S]*?)(?=###|$)"),
        ("example", r"###\s*.*Example\s*\n([\s\S]*?)(?=###|$)"),
        ("steps_raw", r"###\s*.*Breakdown\s*\n([\s\S]*?)(?=###|$)"),
        ("exam_tip", r"###\s*.*Tip\s*\n([\s\S]*?)(?=###|$)"),
    ]

    for key, pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            content = match.group(1).strip()
            if key == "steps_raw":
                # Parse numbered list items
                step_items = [
                    re.sub(r"^\d+[\.\)]\s*", "", line).strip()
                    for line in content.split("\n")
                    if re.match(r"^\s*\d+[\.\)]", line)
                ]
                sections["steps"] = step_items if step_items else [content]
            else:
                sections[key] = content

    # If parsing couldn't find specific sections, treat the whole response as explanation
    if not sections["explanation"] and not sections["analogy"] and not sections["example"]:
        sections["explanation"] = text.strip()

    return sections


class DoubtResolutionAgent:
    """Pedagogical Doubt Resolution Agent for StudySync AI.
    
    Flow:
      Student Question (+ optional conversation history)
             ↓
      Relevant Context Chunks Retrieved from Vectorstore / Document
             ↓
      Level-tailored Prompt Assembly with Grounding Constraints
             ↓
      Llama 3 Generation
             ↓
      Structured Learning Answer & Parsed Pedagogical Sections
    """

    def __init__(self, system_template: str = SYSTEM_PROMPT):
        self.system_template = system_template

    def format_context(self, context: str, max_chars: int = 8000) -> str:
        """Format and constrain retrieved context chunks with clean delimiters."""
        if not context or not context.strip():
            return ""
        cleaned = context.strip()
        if len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars] + "\n\n[... content truncated for length ...]"
        return cleaned

    def build_user_prompt(
        self,
        question: str,
        context: str,
        learner_level: str = "beginner",
        history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        formatted_context = self.format_context(context)
        prompt_parts: list[str] = [
            f"--- Student Learning Profile ---",
            f"Target Level: {learner_level.capitalize()}",
            f"Style: Deliver pedagogical intuition, clarity, and exam readiness.",
            "",
            f"--- Notes Source Material ---",
            formatted_context if formatted_context else "[No document context available]",
            "",
        ]

        if history:
            prompt_parts.append("--- Recent Conversation Context ---")
            for msg in history[-3:]:  # Keep last 3 turns
                role = "Student" if msg.get("role") in {"user", "student"} else "Tutor"
                content = (msg.get("content") or msg.get("text") or "").strip()
                if content:
                    prompt_parts.append(f"{role}: {content}")
            prompt_parts.append("")

        prompt_parts.extend([
            f"--- Current Student Question ---",
            question.strip(),
            "",
            "Resolve this student doubt now using the 5 structured Markdown sections (💡 Explanation, 🔍 Intuitive Analogy, 📌 Concrete Example, 📝 Step-by-Step Breakdown, 🎯 Exam Revision Tip):",
        ])

        return "\n".join(prompt_parts)

    def resolve(
        self,
        question: str,
        context: str,
        learner_level: str = "beginner",
        history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        """Resolve a student doubt against the retrieved context."""
        cleaned_question = question.strip()
        if not cleaned_question:
            return "Please provide a question to resolve."

        if not context or not context.strip():
            return FALLBACK_MESSAGE

        user_prompt = self.build_user_prompt(cleaned_question, context, learner_level, history)
        attempt = 0
        max_attempts = 2
        while attempt < max_attempts:
            try:
                return complete(self.system_template, user_prompt, num_predict=900)
            except Exception as exc:
                attempt += 1
                logger.error(f"Error executing doubt resolution agent (attempt {attempt}): {exc}", exc_info=True)
                if attempt >= max_attempts:
                    return (
                        f"### 💡 Explanation\n"
                        f"The AI tutor encountered an issue: {exc}\n\n"
                        f"**Troubleshooting steps:**\n"
                        f"1. Ensure Ollama is running (`ollama serve`).\n"
                        f"2. Check if the model is pulled (`ollama pull llama3`).\n"
                        f"3. Verify if your computer has enough memory for local LLM."
                    )
                # brief pause could be added, but omitted for simplicity

    def resolve_structured(
        self,
        question: str,
        context: str,
        learner_level: str = "beginner",
        history: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        """Resolve a student doubt and return both the full markdown and parsed structured sections."""
        markdown_answer = self.resolve(question, context, learner_level, history)
        parsed = parse_doubt_sections(markdown_answer)
        parsed["answer"] = markdown_answer
        return parsed


# Default global instance
doubt_agent = DoubtResolutionAgent()


def answer_doubt(
    question: str,
    context: str,
    learner_level: str = "beginner",
    history: Optional[list[dict[str, str]]] = None,
) -> str:
    """Convenience function invoked by LangGraph and RAG services."""
    return doubt_agent.resolve(question, context, learner_level, history)


def answer_doubt_structured(
    question: str,
    context: str,
    learner_level: str = "beginner",
    history: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    """Convenience function returning parsed sections and full markdown."""
    return doubt_agent.resolve_structured(question, context, learner_level, history)


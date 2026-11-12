from __future__ import annotations

import logging
from typing import Optional

from app.services.llm import complete_json, parse_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the StudySync Summarization Agent — an expert pedagogical AI.
Analyze the student uploaded study notes and generate comprehensive, structured study material.

Strict Constraints:
1. Grounding: Rely strictly on facts, concepts, formulas, and algorithms present in the notes. Do not hallucinate external facts.
2. Comprehensive Coverage: Scan and synthesize concepts from across the whole document.
3. Exam Revision Notes: Write real, detailed revision notes in clean Markdown with section headings, bullet points, core mechanisms, and exam takeaways. NEVER return a placeholder string or template instructions.
4. Output Schema: Return valid JSON matching this exact structure:
{
  "key_concepts": ["Concept 1", "Concept 2", ...],
  "definitions": [
    {"term": "Term Name", "definition": "Clear concise definition from notes"}
  ],
  "important_points": [
    "Crucial rule, formula, or takeaway 1",
    "Crucial rule, formula, or takeaway 2"
  ],
  "examples": [
    {"concept": "Concept Name", "example": "Concrete example, scenario, or dry run walkthrough from notes"}
  ],
  "exam_notes": "### Rapid Exam Revision Notes\\n\\n#### 1. Core Principles\\n- Key takeaway 1\\n- Key takeaway 2\\n\\n#### 2. Procedures & Formulas\\n- Step or formula\\n\\n#### 3. High-Yield Exam Summary\\n- Crucial exam points"
}
"""


def _prepare_context(context: str, max_chars: int = 15000) -> str:
    """If context exceeds max_chars, sample across beginning, middle, and end for representative coverage."""
    if len(context) <= max_chars:
        return context

    # 40% from beginning, 30% from middle, 30% from end
    part1_len = int(max_chars * 0.40)
    part2_len = int(max_chars * 0.30)
    part3_len = int(max_chars * 0.30)

    part1 = context[:part1_len]
    mid_start = (len(context) // 2) - (part2_len // 2)
    part2 = context[mid_start : mid_start + part2_len]
    part3 = context[-part3_len:]

    return (
        f"{part1}\n\n[... continuing in document ...]\n\n"
        f"{part2}\n\n[... concluding sections ...]\n\n"
        f"{part3}"
    )


def summarize_from_context(context: str, learner_level: str = "beginner") -> dict:
    if not context or not context.strip():
        return {
            "key_concepts": [],
            "definitions": [],
            "important_points": [],
            "examples": [],
            "exam_notes": "No text content found in document to summarize.",
        }

    prepared = _prepare_context(context)
    user_prompt = (
        f"--- Student Learning Level: {learner_level.capitalize()} ---\n"
        f"Tailor explanations, tone, and depth to a {learner_level} student.\n\n"
        f"--- Source Material from Notes ---\n"
        f"{prepared}\n\n"
        f"Extract and return the structured study summary JSON now:"
    )

    try:
        raw = complete_json(SYSTEM_PROMPT, user_prompt)
        data = parse_json(raw)
    except Exception as exc:
        logger.error(f"Error executing summarizer agent: {exc}", exc_info=True)
        data = {
            "key_concepts": [],
            "definitions": [],
            "important_points": [],
            "examples": [],
            "exam_notes": "The uploaded notes were indexed successfully. You can ask questions and take quizzes on this document.",
        }
    key_concepts = data.get("key_concepts") or data.get("concepts") or []
    definitions = data.get("definitions") or data.get("terms") or []
    important_points = data.get("important_points") or data.get("points") or data.get("takeaways") or []
    examples = data.get("examples") or data.get("scenarios") or []
    
    exam_notes = (
        data.get("exam_notes")
        or data.get("exam_revision_notes")
        or data.get("revision_notes")
        or data.get("study_notes")
        or data.get("notes")
        or ""
    )
    if isinstance(exam_notes, list):
        exam_notes = "\n".join(f"- {item}" for item in exam_notes)

    # If exam_notes was omitted by the LLM, synthesize a clean revision markdown from concepts & definitions
    if not exam_notes.strip() and (key_concepts or definitions):
        sections = ["### Quick Revision Notes\n"]
        if key_concepts:
            sections.append("#### Key Concepts\n" + "\n".join(f"- {c}" for c in key_concepts))
        if definitions:
            sections.append("\n#### Definitions Dictionary\n" + "\n".join(
                f"- **{d.get('term', '')}**: {d.get('definition', '')}" 
                for d in definitions if isinstance(d, dict)
            ))
        if important_points:
            sections.append("\n#### Core Takeaways\n" + "\n".join(f"- {pt}" for pt in important_points))
        exam_notes = "\n".join(sections)

    return {
        "key_concepts": key_concepts,
        "definitions": definitions,
        "important_points": important_points,
        "examples": examples,
        "exam_notes": exam_notes,
    }




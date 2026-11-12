from typing import Optional
from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    document_id: int
    question: str = Field(min_length=1, max_length=2000)
    history: Optional[list[dict[str, str]]] = None

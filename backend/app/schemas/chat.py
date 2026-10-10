from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    page_or_slide: int
    label: str  # "Slide 14" / "Page 3"
    snippet: str
    score: float


class AskIn(BaseModel):
    subject_id: str = Field(max_length=36)
    question: str = Field(min_length=1, max_length=1000)
    session_id: str | None = Field(default=None, max_length=36)
    doc_ids: list[str] | None = Field(default=None, max_length=50)


class AskOut(BaseModel):
    session_id: str
    answer: str
    citations: list[Citation]
    blocked: bool = False
    latency_ms: int


class SearchIn(BaseModel):
    subject_id: str = Field(max_length=36)
    query: str = Field(min_length=1, max_length=1000)
    doc_ids: list[str] | None = Field(default=None, max_length=50)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    subject_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    content: str
    citations: list[Citation] | None = None
    created_at: datetime

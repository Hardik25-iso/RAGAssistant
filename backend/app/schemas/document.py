from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    subject_id: str
    filename: str
    file_type: str
    size_bytes: int
    pages: int
    status: str
    error: str | None = None
    created_at: datetime


class DownloadOut(BaseModel):
    url: str
    expires_in: int

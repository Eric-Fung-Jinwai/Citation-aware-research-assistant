from pydantic import BaseModel, Field
from typing import Optional, Literal


class CitationObject(BaseModel):
    claim: str
    source_type: Literal["sec_filing", "news", "price_data", "macro", "technical"]
    source_name: str
    url: Optional[str] = None
    date: str  # ISO 8601 YYYY-MM-DD
    excerpt: str


class SkillResult(BaseModel):
    status: Literal["success", "degraded", "failed"]
    data: Optional[dict] = None
    citations: list[CitationObject] = Field(default_factory=list)
    error: Optional[str] = None
    source: str
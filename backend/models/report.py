from typing import Optional, Literal
from pydantic import BaseModel


class EvidenceCitation(BaseModel):
    source_name: str
    url: Optional[str] = None
    date: str


class EvidenceBlock(BaseModel):
    citation_index: int
    source_type: Literal["sec_filing", "news", "price_data", "macro", "technical"]
    content: str
    citation: Optional[EvidenceCitation] = None


class ContextBundle(BaseModel):
    ticker: str
    window: str
    generated_at: str  # ISO 8601
    evidence: list[EvidenceBlock]


class ReportOutput(BaseModel):
    ticker: str
    window: str
    generated_at: str
    report_text: str
    evidence: list[EvidenceBlock]
    confidence_score: Optional[float] = None
    confidence_breakdown: Optional[dict] = None
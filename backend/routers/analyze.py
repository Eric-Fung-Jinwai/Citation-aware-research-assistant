from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.skills.confidence_gate import apply_confidence_gate
from backend.skills.stock_retro import run_stock_retro

router = APIRouter()


class AnalyzeRequest(BaseModel):
    ticker: str
    window: Literal["7d", "30d", "90d"] = "7d"
    company_name: Optional[str] = None


@router.post("/analyze")
async def analyze(req: AnalyzeRequest) -> dict:
    result = await run_stock_retro(req.ticker, req.window, req.company_name)
    return apply_confidence_gate(result)
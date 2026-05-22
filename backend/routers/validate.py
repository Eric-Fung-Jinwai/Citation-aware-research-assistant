from fastapi import APIRouter
from pydantic import BaseModel

from backend.skills.view_validator import validate_view

router = APIRouter()


class ValidateViewRequest(BaseModel):
    thesis: str
    ticker: str
    timeframe: str = "6 months"


@router.post("/validate-view")
async def validate(req: ValidateViewRequest) -> dict:
    return await validate_view(req.thesis, req.ticker, req.timeframe)
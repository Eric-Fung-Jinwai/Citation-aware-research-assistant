from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.routers.analyze import router as analyze_router
from backend.routers.validate import router as validate_router

load_dotenv()

app = FastAPI(title="Stock Analysis System")

app.include_router(analyze_router)
app.include_router(validate_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"status": "error", "error": str(exc)},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
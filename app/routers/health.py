from fastapi import APIRouter
from sqlalchemy import text
from starlette.responses import JSONResponse

from app.db import engine

router = APIRouter()


@router.get("/health")
async def health():
    """Health check that verifies database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": str(e)},
        )

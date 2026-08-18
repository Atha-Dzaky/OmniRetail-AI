from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.graph import create_omniretail_graph

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# ── Lazy graph compilation (avoids failure during import if DB is not ready) ─
_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = create_omniretail_graph().compile()
    return _compiled_graph


class GraphRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)


class GraphResponse(BaseModel):
    user_query: str
    sql_result: str = ""
    python_code: Optional[str] = ""
    chart_path: Optional[str] = ""
    final_response: str = ""


@router.post("/query", response_model=GraphResponse)
@limiter.limit("10/minute")
async def run_omniretail_graph(request: Request, body: GraphRequest):
    compiled_graph = _get_graph()

    try:
        result = compiled_graph.invoke({"user_query": body.query})
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Graph execution failed",
                "message": str(exc),
            },
        ) from exc

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=500,
            detail={"error": "Invalid graph response", "message": "Expected dict output"},
        )

    try:
        return GraphResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Response validation failed",
                "message": str(exc),
                "result": result,
            },
        ) from exc

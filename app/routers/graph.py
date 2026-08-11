from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.graph import create_omniretail_graph

router = APIRouter()


class GraphRequest(BaseModel):
    query: str


class GraphResponse(BaseModel):
    user_query: str
    sql_result: str
    python_code: str
    chart_path: str
    final_response: str


compiled_graph = create_omniretail_graph().compile()


@router.post("/query", response_model=GraphResponse)
async def run_omniretail_graph(request: GraphRequest):
    try:
        result = compiled_graph.invoke({"user_query": request.query})
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

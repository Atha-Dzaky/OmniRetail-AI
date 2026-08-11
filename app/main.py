from fastapi import FastAPI
from starlette.responses import JSONResponse
from app.db import init_db, get_db_session
from app.routers import products, health, graph

app = FastAPI(title="OmniRetail AI")

app.include_router(health.router)
app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(graph.router, prefix="/graph", tags=["graph"])

@app.on_event("startup")
async def startup_event():
    init_db()

@app.get("/ready")
async def ready():
    return JSONResponse({"status": "ready"})

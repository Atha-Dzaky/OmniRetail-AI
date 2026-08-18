from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse
from app.db import init_db, get_db_session
from app.routers import products, health, graph


# ── Rate Limiter ────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


# ── Lifespan (replaces deprecated @app.on_event) ───────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="OmniRetail AI", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allow specific origins (not wildcard)
_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8501",      # Streamlit
    "http://127.0.0.1:8501",
    "http://192.168.1.200",
    "http://192.168.1.200:3000",
    "http://192.168.1.200:80",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(graph.router, prefix="/graph", tags=["graph"])

@app.get("/ready")
async def ready():
    return JSONResponse({"status": "ready"})

# Serve generated chart images as static files (for local dev without Nginx)
charts_dir = Path("charts")
charts_dir.mkdir(parents=True, exist_ok=True)
app.mount("/charts", StaticFiles(directory=str(charts_dir)), name="charts")

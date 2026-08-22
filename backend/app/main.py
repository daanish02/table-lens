from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.api.middleware import limiter
from app.api.routes import discover_router, data_router, query_router, charts_router, visualize_router
from app.config import ALLOWED_ORIGINS
from app.utils import get_logger

log = get_logger(__name__)

app = FastAPI(title="Table Lens")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def log_unhandled_exception(request: Request, exc: Exception):
    # FastAPI's default behavior only prints unhandled exceptions to
    # uvicorn's own stderr, which this app's rotating file logger never
    # sees and which a restarted process loses entirely — making this class
    # of failure undiagnosable after the fact. Route it through our logger
    # too before falling back to the same 500 response FastAPI would give.
    log.exception(f"unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(discover_router)
app.include_router(data_router)
app.include_router(query_router)
app.include_router(charts_router)
app.include_router(visualize_router)


@app.get("/health")
def health():
    return {"status": "ok"}

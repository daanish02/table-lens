from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.api.middleware import limiter
from app.api.routes import discover_router, data_router, query_router, charts_router
from app.utils import get_logger

log = get_logger(__name__)

app = FastAPI(title="Table Lens")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(discover_router)
app.include_router(data_router)
app.include_router(query_router)
app.include_router(charts_router)


@app.get("/health")
def health():
    return {"status": "ok"}

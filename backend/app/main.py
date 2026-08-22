from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.api.middleware.rate_limit import limiter
from app.api.routes.discover import router as discover_router
from app.logging.logger import get_logger

log = get_logger(__name__)

app = FastAPI(title="table-lens backend")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(discover_router)


@app.get("/health")
def health():
    return {"status": "ok"}

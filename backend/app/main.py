from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routers import auth, claims, fact_checks, publishing, reels
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import limiter

settings = get_settings()
configure_logging(debug=settings.DEBUG)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("truthlens_startup", env=settings.ENV, human_approval_mode=settings.HUMAN_APPROVAL_MODE)
    yield


app = FastAPI(title="TruthLens API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(reels.router, prefix="/api/reels", tags=["reels"])
app.include_router(claims.router, prefix="/api/claims", tags=["claims"])
app.include_router(fact_checks.router, prefix="/api/fact-checks", tags=["fact-checks"])
app.include_router(publishing.router, prefix="/api/publishing", tags=["publishing"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "human_approval_mode": settings.HUMAN_APPROVAL_MODE}

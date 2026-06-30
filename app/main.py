import logging
import sys
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
from .core.config import settings
from .api.router import api_router
from .api.routes import webhooks_new

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}',
    stream=sys.stdout,
)
logger = logging.getLogger("jisrvoc")

# Initialize Sentry if DSN provided
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.1 if settings.app_env == "production" else 1.0,
    )
    logger.info("Sentry initialized", extra={"environment": settings.app_env})

app = FastAPI(
    title="JisrVOC API",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
origins = settings.allowed_origins.split(",") if settings.allowed_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
    expose_headers=["X-Correlation-ID"],
)


# Request logging middleware with correlation ID
@app.middleware("http")
async def log_requests(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", f"req-{int(time.time() * 1000)}")
    start_time = time.time()

    # Add correlation ID to request state for downstream use
    request.state.correlation_id = correlation_id

    logger.info(
        "Request started",
        extra={
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else None,
        },
    )

    response = await call_next(request)

    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "Request completed",
        extra={
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )

    response.headers["X-Correlation-ID"] = correlation_id
    return response


# Include API router (authenticated endpoints)
app.include_router(api_router, prefix="/api/v1")

# Include public webhooks (no auth)
app.include_router(webhooks_new.router, prefix="/api/public/webhooks", tags=["Webhooks"])


@app.get("/health", tags=["Ops"])
@app.get("/api/v1/healthz", tags=["Ops"])
async def healthz():
    """Basic health check endpoint for load balancers."""
    return {"status": "ok"}


@app.get("/api/v1/readyz", tags=["Ops"])
async def readyz():
    """Readiness check - verifies app dependencies are healthy."""
    health = {
        "status": "ready",
        "environment": settings.app_env,
        "mockData": settings.use_mock_data,
        "checks": {}
    }

    # Check database connectivity
    try:
        from .db.session import get_db
        from sqlalchemy import text
        async for db in get_db():
            await db.execute(text("SELECT 1"))
            health["checks"]["database"] = "ok"
            break
    except Exception as e:
        health["checks"]["database"] = f"error: {str(e)}"
        health["status"] = "degraded"

    # Check Redis connectivity
    try:
        from .core.cache import get_redis
        redis_client = get_redis()
        redis_client.ping()
        health["checks"]["redis"] = "ok"
    except Exception as e:
        health["checks"]["redis"] = f"error: {str(e)}"
        health["status"] = "degraded"

    return health

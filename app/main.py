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
from .agents.orchestrator import AgentOrchestrator
from .services.rule_engine import get_rule_engine
from .db.session import get_db
from .repositories.theme import ThemeRepository

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


# Startup event: Initialize Agent Orchestrator
@app.on_event("startup")
async def startup_event():
    """Initialize application dependencies at startup."""
    logger.info("Application startup: Initializing dependencies")

    # Initialize agent orchestrator if feature is enabled
    if settings.agent_enrichment_enabled:
        try:
            # Get rule engine singleton
            rule_engine = get_rule_engine()

            # Get database session for theme repository
            # We need to create a single session for the orchestrator's theme repository
            async for db in get_db():
                theme_repository = ThemeRepository(db)

                # Initialize orchestrator
                orchestrator = AgentOrchestrator(
                    rule_engine=rule_engine,
                    theme_repository=theme_repository,
                )

                # Store in app state for dependency injection
                app.state.orchestrator = orchestrator

                logger.info(
                    "Agent orchestrator initialized successfully",
                    extra={
                        "agent_count": len(orchestrator.agents),
                        "agents": list(orchestrator.agents.keys()),
                        "feature_enabled": settings.agent_enrichment_enabled,
                        "rollout_percentage": settings.agent_rollout_percentage,
                    }
                )
                break
        except Exception as e:
            logger.error(
                "Failed to initialize agent orchestrator",
                extra={"error": str(e)},
                exc_info=True
            )
            # Don't crash the application, just disable agent enrichment
            app.state.orchestrator = None
            logger.warning("Agent enrichment will be unavailable")
    else:
        app.state.orchestrator = None
        logger.info(
            "Agent enrichment is disabled",
            extra={"agent_enrichment_enabled": settings.agent_enrichment_enabled}
        )


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
async def readyz(request: Request):
    """Readiness check - verifies app dependencies are healthy."""
    from .services.feature_flags import get_feature_status
    from .services.rule_engine import get_rule_engine

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

    # Check agent orchestrator status
    if settings.agent_enrichment_enabled:
        orchestrator = getattr(request.app.state, "orchestrator", None)
        if orchestrator:
            try:
                agent_status = orchestrator.get_agent_status()
                health["checks"]["agent_orchestrator"] = {
                    "status": "ok",
                    "agent_count": agent_status["agent_count"],
                    "agents": agent_status["agents"],
                }
            except Exception as e:
                health["checks"]["agent_orchestrator"] = f"error: {str(e)}"
                health["status"] = "degraded"
        else:
            health["checks"]["agent_orchestrator"] = "not_initialized"
            health["status"] = "degraded"

    # Add agent pipeline status and metrics
    try:
        feature_status = get_feature_status()
        health["agent_pipeline"] = {
            "enabled": feature_status["enabled"],
            "rollout_percentage": feature_status["rollout_percentage"],
            "metrics": feature_status["metrics"],
        }
    except Exception as e:
        logger.error(f"Failed to get agent pipeline status: {e}")
        health["agent_pipeline"] = {"error": str(e)}

    # Add rule engine status
    if settings.agent_enrichment_enabled:
        try:
            rule_engine = get_rule_engine()
            health["rule_engine"] = {
                "status": "ok",
                "disambiguation_rules": len(rule_engine.disambiguation_rules.get("rules", [])),
                "compliance_regulations": len(rule_engine.compliance_lexicon.get("regulations", [])),
                "l1_scopes": len(rule_engine.taxonomy.get("scopes", [])),
            }
        except Exception as e:
            health["rule_engine"] = {"error": str(e)}
            health["status"] = "degraded"

    return health

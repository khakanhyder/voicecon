"""
Voicecon FastAPI Application
Main entry point for the backend API.
"""
import os
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import time
import logging

from app.core.config import settings
from app.database import init_db, close_db
from app.core.exceptions import VoiceconException
from app.services.analytics.scheduler import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Voicecon API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Initialize database
    if settings.DEBUG:
        await init_db()
        logger.info("Database initialized")

    # Seed default subscription plans (idempotent)
    try:
        from app.database import get_db_session
        from app.services.billing.seed_plans import seed_default_plans

        async with get_db_session() as db:
            created = await seed_default_plans(db)
            if created:
                logger.info(f"Seeded {created} subscription plans")
    except Exception as e:
        logger.error(f"Failed to seed subscription plans: {e}")

    # Start analytics scheduler
    try:
        await start_scheduler()
        logger.info("Analytics scheduler started")
    except Exception as e:
        logger.error(f"Failed to start analytics scheduler: {e}")

    # Reap workflow executions left in `running` by a previous process. Runs
    # execute in-process, so any such row is stranded by definition.
    try:
        from app.database import AsyncSessionLocal
        from app.services.workflows import reap_stranded_executions

        async with AsyncSessionLocal() as db:
            reaped = await reap_stranded_executions(db)
        if reaped:
            logger.info(f"Reaped {reaped} stranded workflow execution(s) at startup")
    except Exception as e:
        logger.error(f"Failed to reap stranded workflow executions: {e}")

    # Start workflow scheduler (fires schedule/cron-triggered workflows)
    try:
        from app.services.workflows.scheduler import get_scheduler

        await get_scheduler().start()
        logger.info("Workflow scheduler started")
    except Exception as e:
        logger.error(f"Failed to start workflow scheduler: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Voicecon API...")

    # Stop workflow scheduler
    try:
        from app.services.workflows.scheduler import get_scheduler

        await get_scheduler().stop()
        logger.info("Workflow scheduler stopped")
    except Exception as e:
        logger.error(f"Failed to stop workflow scheduler: {e}")

    # Stop analytics scheduler
    try:
        await stop_scheduler()
        logger.info("Analytics scheduler stopped")
    except Exception as e:
        logger.error(f"Failed to stop analytics scheduler: {e}")

    await close_db()
    logger.info("Database connections closed")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Voice AI Platform with Integration Management",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
    redirect_slashes=False,
)

# The chat widget embeds on arbitrary customer websites, so its public
# endpoints must accept any origin. That is incompatible with the credentialed,
# origin-restricted policy the rest of the app uses, so open CORS is applied
# only to these paths (no credentials — the public_key in the URL is the only
# auth). The middleware itself is registered LAST (see below) so it is the
# outermost layer and handles the CORS preflight before the global,
# origin-restricted CORSMiddleware can reject a customer origin.
_PUBLIC_CHAT_PREFIXES = ("/api/v1/chat/public/", "/api/v1/chat/widget.js")


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip Middleware for response compression
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time header; gracefully skip for streaming responses."""
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        try:
            response.headers["X-Process-Time"] = str(process_time)
        except Exception:
            pass
        return response
    except Exception as e:
        logger.exception(f"Unhandled exception during {request.method} {request.url.path}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "InternalServerError", "message": "An unexpected error occurred"},
        )


# Public-chat CORS — registered LAST so it is the OUTERMOST middleware and runs
# before the global CORSMiddleware. Otherwise CORSMiddleware intercepts the
# preflight from a customer origin (or file:// which sends Origin: null) and
# rejects it with 400 before this handler can allow it.
@app.middleware("http")
async def public_chat_cors(request: Request, call_next):
    path = request.url.path
    is_public_chat = any(path.startswith(p) for p in _PUBLIC_CHAT_PREFIXES)

    if is_public_chat and request.method == "OPTIONS":
        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Max-Age": "600",
            },
        )

    response = await call_next(request)
    if is_public_chat:
        response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# Exception handlers
@app.exception_handler(VoiceconException)
async def voicecon_exception_handler(request: Request, exc: VoiceconException):
    """
    Handle custom Voicecon exceptions.
    """
    logger.error(f"Voicecon exception: {exc.message}", extra={"details": exc.details})
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors.
    """
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected exceptions.
    """
    logger.exception("Unexpected exception occurred")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred" if settings.is_production else str(exc),
        },
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Voice AI Platform with Integration Management",
        "docs": f"{settings.API_V1_PREFIX}/docs" if settings.DEBUG else "Disabled in production",
    }


# Import and include API routers.
#
# This deliberately does NOT swallow import errors. Catching them leaves the
# process serving a healthy-looking app with zero API routes: /health returns
# 200, the platform keeps the deploy live, and every /api/v1/* call 404s — which
# reads like a routing bug rather than a failed build. Crashing here makes the
# deploy fail loudly instead, with the real ImportError at the top of the log.
from app.api.v1.api import api_router

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
logger.info(f"Mounted {len(api_router.routes)} API routes at {settings.API_V1_PREFIX}")

# Serve call recordings as static files
try:
    _recordings_dir = os.path.join(os.path.dirname(__file__), '..', 'recordings')
    os.makedirs(_recordings_dir, exist_ok=True)
    app.mount("/recordings", StaticFiles(directory=_recordings_dir), name="recordings")
except Exception as e:
    logger.warning(f"Could not mount recordings directory: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )

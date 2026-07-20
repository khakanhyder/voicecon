"""
Voicecon FastAPI Application
Main entry point for the backend API.
"""
import os
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
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


# Import and include API routers
try:
    from app.api.v1.api import api_router
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
except Exception as e:
    logger.error(f"Failed to load API routers: {e}", exc_info=True)

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

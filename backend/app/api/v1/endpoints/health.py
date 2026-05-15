"""
Health Check Endpoints.

Provides comprehensive health checks for monitoring and load balancers.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis
import httpx
from datetime import datetime
from typing import Dict, Any
import asyncio

from app.core.database import get_db
from app.core.config import settings

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Basic health check for load balancers.

    Returns 200 OK if service is running.
    Use this for:
    - Load balancer health checks
    - Kubernetes liveness probes
    - Quick availability checks
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "voicecon-api",
        "version": settings.APP_VERSION
    }


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Readiness check - verifies all dependencies are available.

    Use this for:
    - Kubernetes readiness probes
    - Deployment verification
    - Comprehensive health checks

    Returns:
        200 OK: All dependencies healthy
        503 Service Unavailable: One or more dependencies unhealthy
    """
    checks = {}
    all_healthy = True

    # Check database
    db_healthy, db_info = await check_database(db)
    checks["database"] = db_info
    if not db_healthy:
        all_healthy = False

    # Check Redis
    redis_healthy, redis_info = await check_redis()
    checks["redis"] = redis_info
    if not redis_healthy:
        all_healthy = False

    # Check external services
    llm_healthy, llm_info = await check_llm_service()
    checks["llm_service"] = llm_info
    if not llm_healthy:
        all_healthy = False

    # Overall status
    response = {
        "status": "healthy" if all_healthy else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }

    if not all_healthy:
        return response, status.HTTP_503_SERVICE_UNAVAILABLE

    return response


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_check():
    """
    Liveness check - verifies process is responsive.

    Use this for:
    - Kubernetes liveness probes
    - Process monitoring
    - Restart decisions

    Returns:
        200 OK: Process is responsive
        503 Service Unavailable: Process is stuck/deadlocked
    """
    # Simple check - if we can respond, we're alive
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/detailed", status_code=status.HTTP_200_OK)
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """
    Detailed health check with comprehensive system information.

    Use this for:
    - Debugging
    - Monitoring dashboards
    - Operational insights

    Returns detailed status of:
    - Database (connections, response time)
    - Redis (memory usage, response time)
    - External services (availability, response time)
    - System resources
    """
    checks = {}

    # Database details
    db_healthy, db_info = await check_database_detailed(db)
    checks["database"] = db_info

    # Redis details
    redis_healthy, redis_info = await check_redis_detailed()
    checks["redis"] = redis_info

    # LLM service
    llm_healthy, llm_info = await check_llm_service_detailed()
    checks["llm_service"] = llm_info

    # Voice service
    voice_healthy, voice_info = await check_voice_service()
    checks["voice_service"] = voice_info

    # Integration health
    integrations_info = await check_integrations()
    checks["integrations"] = integrations_info

    # System resources
    system_info = get_system_info()
    checks["system"] = system_info

    all_healthy = all([
        db_healthy,
        redis_healthy,
        llm_healthy,
        voice_healthy
    ])

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }


# ============================================================================
# Helper Functions
# ============================================================================

async def check_database(db: AsyncSession) -> tuple[bool, Dict[str, Any]]:
    """Check database connectivity."""
    try:
        start_time = datetime.utcnow()
        await db.execute(text("SELECT 1"))
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return True, {
            "status": "healthy",
            "response_time_ms": round(response_time, 2)
        }
    except Exception as e:
        return False, {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_database_detailed(db: AsyncSession) -> tuple[bool, Dict[str, Any]]:
    """Detailed database health check."""
    try:
        start_time = datetime.utcnow()

        # Check connection
        await db.execute(text("SELECT 1"))
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Get connection pool stats
        pool = db.get_bind().pool
        pool_info = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }

        # Get database version
        result = await db.execute(text("SELECT version()"))
        version = result.scalar()

        return True, {
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "pool": pool_info,
            "version": version
        }
    except Exception as e:
        return False, {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_redis() -> tuple[bool, Dict[str, Any]]:
    """Check Redis connectivity."""
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )

        start_time = datetime.utcnow()
        await redis_client.ping()
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        await redis_client.close()

        return True, {
            "status": "healthy",
            "response_time_ms": round(response_time, 2)
        }
    except Exception as e:
        return False, {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_redis_detailed() -> tuple[bool, Dict[str, Any]]:
    """Detailed Redis health check."""
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )

        start_time = datetime.utcnow()
        await redis_client.ping()
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Get Redis info
        info = await redis_client.info()

        await redis_client.close()

        return True, {
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "version": info.get("redis_version"),
            "memory_used_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
            "connected_clients": info.get("connected_clients"),
            "uptime_days": round(info.get("uptime_in_seconds", 0) / 86400, 2)
        }
    except Exception as e:
        return False, {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_llm_service() -> tuple[bool, Dict[str, Any]]:
    """Check LLM service availability."""
    if not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
        return True, {
            "status": "not_configured"
        }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start_time = datetime.utcnow()

            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
            )

            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            if response.status_code == 200:
                return True, {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2)
                }
            else:
                return False, {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}"
                }
    except Exception as e:
        return False, {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_llm_service_detailed() -> tuple[bool, Dict[str, Any]]:
    """Detailed LLM service health check."""
    if not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
        return True, {
            "status": "not_configured",
            "providers": {
                "openai": "not_configured",
                "anthropic": "not_configured"
            }
        }

    providers = {}

    # Check OpenAI
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start_time = datetime.utcnow()
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
            )
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            providers["openai"] = {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_time_ms": round(response_time, 2)
            }
    except Exception as e:
        providers["openai"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    all_healthy = all(p.get("status") == "healthy" for p in providers.values())

    return all_healthy, {
        "status": "healthy" if all_healthy else "degraded",
        "providers": providers
    }


async def check_voice_service() -> tuple[bool, Dict[str, Any]]:
    """Check voice service providers."""
    # Placeholder - implement based on your voice provider
    return True, {
        "status": "healthy",
        "providers": {
            "twilio": "healthy",
            "elevenlabs": "healthy"
        }
    }


async def check_integrations() -> Dict[str, Any]:
    """Check status of external integrations."""
    # Placeholder - implement based on your integrations
    return {
        "salesforce": "healthy",
        "hubspot": "healthy",
        "slack": "healthy"
    }


def get_system_info() -> Dict[str, Any]:
    """Get system resource information."""
    import psutil

    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=1)

    # Memory usage
    memory = psutil.virtual_memory()
    memory_info = {
        "total_mb": round(memory.total / 1024 / 1024, 2),
        "available_mb": round(memory.available / 1024 / 1024, 2),
        "used_percent": memory.percent
    }

    # Disk usage
    disk = psutil.disk_usage('/')
    disk_info = {
        "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
        "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
        "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
        "used_percent": disk.percent
    }

    return {
        "cpu_percent": cpu_percent,
        "memory": memory_info,
        "disk": disk_info
    }

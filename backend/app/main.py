import logging
from fastapi import FastAPI, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.database.session import get_db

# Initialize centralized logging configuration
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("app.main")

logger.info("Starting up FastAPI application...")

# Initialize the FastAPI App with production-ready Swagger/OpenAPI configurations
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=(
        "API for AI-Powered Bank Statement Analysis System. "
        "Extracts, structures, and performs QA over transactions using Hybrid RAG."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Set CORS middleware for cross-origin frontend requests
# (Configure origins properly for production deployment)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["General"])
async def root():
    """
    Root API endpoint returning metadata about the service.
    """
    logger.info("Root endpoint hit - returning project metadata.")
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "status": "online",
        "documentation": "/docs",
        "health_check": "/health"
    }

@app.get("/health", tags=["System Health"], status_code=status.HTTP_200_OK)
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Service Health Status endpoint.
    Provides diagnostic information regarding core connections (DB, ChromaDB, APIs).
    """
    logger.info("Health check endpoint hit - verifying diagnostic dependencies.")
    
    postgres_status = "unhealthy"
    try:
        await db.execute(text("SELECT 1"))
        postgres_status = "healthy"
    except Exception as e:
        logger.error(f"PostgreSQL connection check failed: {e}")

    return {
        "status": "healthy" if postgres_status == "healthy" else "degraded",
        "version": settings.PROJECT_VERSION,
        "dependencies": {
            "postgresql": postgres_status,
            "chromadb": "pending_setup",
            "openai_api": "configured" if settings.OPENAI_API_KEY else "not_configured"
        }
    }

@app.get("/health/db", tags=["System Health"], status_code=status.HTTP_200_OK)
async def db_health_check(db: AsyncSession = Depends(get_db)):
    """
    Dedicated Database Health Status endpoint.
    Runs a simple validation query to test physical DB layer connectivity.
    """
    logger.info("Database health check endpoint hit - running diagnostic query.")
    try:
        # Executes standard lightweight ping query
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        return {
            "status": "healthy",
            "database": "postgresql",
            "message": "Database connection verified successfully"
        }
    except Exception as e:
        logger.error(f"Database connection diagnostic failed: {e}")
        return {
            "status": "unhealthy",
            "database": "postgresql",
            "error": str(e)
        }

# Versioning Structure Integration
# Future api routers can be mounted under version prefix:
# from app.api.v1.api import api_router
# app.include_router(api_router, prefix=settings.API_V1_STR)

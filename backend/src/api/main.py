# backend/main.py
from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
import logging

# Structured logging config
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}'
)
logger = logging.getLogger(__name__)

# Lifecycle manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: DB connection, Kafka init, etc.
    logger.info("ModelGuardian AI starting up...")
    yield
    # Shutdown: Cleanup
    logger.info("ModelGuardian AI shutting down...")

app = FastAPI(
    title="ModelGuardian AI",
    description="Human-in-the-Loop MLOps Platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Kubernetes & Docker healthcheck endpoint"""
    return {
        "status": "ok",
        "service": "modelguardian-api",
        "version": "1.0.0"
    }

# Root endpoint
@app.get("/", tags=["System"])
async def root():
    return {
        "message": "Welcome to ModelGuardian AI",
        "docs": "/docs",
        "health": "/health"
    }

# API v1 router (PDF yapısına uyumlu)
api_v1 = APIRouter(prefix="/api/v1")

@api_v1.get("/models", tags=["Models"])
async def list_models():
    return {"models": [], "total": 0}

@api_v1.get("/models/{model_id}", tags=["Models"])
async def get_model(model_id: str):
    return {"model_id": model_id, "status": "not_found"}

app.include_router(api_v1)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
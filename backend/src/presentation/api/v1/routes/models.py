from fastapi import APIRouter

router = APIRouter(prefix="/models", tags=["Models"])

@router.get("/")
async def list_models():
    """Placeholder endpoint"""
    return {"models": [], "total": 0, "message": "Coming soon in Phase 3"}
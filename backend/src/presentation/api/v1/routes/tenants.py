from fastapi import APIRouter

router = APIRouter(prefix="/tenants", tags=["Tenants"])

@router.get("/")
async def list_tenants():
    """Placeholder endpoint - Super Admin only"""
    return {"tenants": [], "message": "Coming soon in Phase 2"}
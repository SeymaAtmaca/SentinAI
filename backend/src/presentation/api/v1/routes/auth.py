# ✅ Doğru import'lar
from fastapi import APIRouter, Depends, HTTPException, status, Body  # ← Body eklendi
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

from src.infrastructure.security.auth.jwt_handler import JWTHandler
from src.infrastructure.security.auth.password_hasher import PasswordHasher
from src.domain.entities.user import User, Role
from src.infrastructure.adapters.repositories.postgres_user_repository import PostgresUserRepository


router = APIRouter(prefix="/auth", tags=["Authentication"])

# ================= REQUEST/RESPONSE MODELS =================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    tenant_slug: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-z0-9-]+$')
    tenant_name: str = Field(..., min_length=2, max_length=100)

class RegisterResponse(BaseModel):
    message: str
    tenant_id: str
    user_id: str

class RefreshTokenRequest(BaseModel):
    """Refresh token endpoint'i için body tanımı"""
    refresh_token: str

class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ================= ENDPOINTS =================

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, user_repo: PostgresUserRepository = Depends()):
    """Kullanıcı girişi - JWT token çifti döndürür"""
    user = await user_repo.get_by_email(req.email)
    if not user or not PasswordHasher.verify(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    
    access_token = JWTHandler.create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role.value,
        permissions=["model:read", "audit:read"]  # TODO: DB'den çek
    )
    refresh_token = JWTHandler.create_refresh_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id)
    )
    
    await user_repo.update_last_login(user.id)
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={"id": str(user.id), "email": user.email, "role": user.role.value}
    )

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, user_repo: PostgresUserRepository = Depends()):
    """Yeni tenant + ilk kullanıcı oluştur (self-signup)"""
    if await user_repo.tenant_exists(req.tenant_slug):
        raise HTTPException(status_code=400, detail="Tenant slug already exists")
    
    tenant = await user_repo.create_tenant(
        slug=req.tenant_slug,
        name=req.tenant_name,
        schema_name=f"tenant_{req.tenant_slug}"
    )
    
    password_hash = PasswordHasher.hash(req.password)
    user = await user_repo.create_user(
        tenant_id=tenant.id,
        email=req.email,
        password_hash=password_hash,
        role=Role.TENANT_ADMIN
    )
    
    await user_repo.create_tenant_schema(tenant.schema_name)
    
    return RegisterResponse(
        message="Registration successful. Please login.",
        tenant_id=str(tenant.id),
        user_id=str(user.id)
    )

@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(req: RefreshTokenRequest):
    """Refresh token ile yeni access token al"""
    try:
        user_id, tenant_id, role, permissions = JWTHandler.refresh_access_token(req.refresh_token)
        
        new_access = JWTHandler.create_access_token(
            subject=user_id,
            tenant_id=tenant_id,
            role=role,
            permissions=permissions
        )
        
        return TokenRefreshResponse(access_token=new_access)
        
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
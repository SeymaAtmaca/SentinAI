# ✅ Doğru import'lar
from fastapi import APIRouter, Depends, HTTPException, status, Body  # ← Body eklendi
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
import uuid

from src.infrastructure.security.auth.jwt_handler import JWTHandler
from src.infrastructure.security.auth.password_hasher import PasswordHasher
from src.domain.entities.user import User, Role
from src.infrastructure.adapters.repositories.postgres_user_repository import PostgresUserRepository
from src.presentation.api.v1.schemas.auth import (
    LoginRequest, LoginResponse,
    RegisterRequest, RegisterResponse,
    RefreshTokenRequest, TokenResponse,
    ErrorResponse
)


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

@router.post("/login", response_model=LoginResponse, responses={
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse}
})
async def login(request: LoginRequest, user_repo: PostgresUserRepository = Depends()):
    """Kullanıcı girişi - JWT token çifti döndürür"""
    
    # 1. User'ı public schema'da bul (tenant henüz bilinmiyor)
    user = await user_repo.get_by_email(request.email, tenant_id=None)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # 2. Password'u doğrula
    if not PasswordHasher.verify(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # 3. Account status kontrolü
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    
    # 4. Tenant bilgisini al (public.tenants tablosundan)
    tenant = await user_repo.get_tenant_by_id(user.tenant_id)
    if not tenant or tenant.is_suspended():
        raise HTTPException(
            status_code=402 if tenant and tenant.is_suspended() else 404,
            detail="Account not found or suspended"
        )
    
    # 5. Token'ları oluştur (tenant bilgisi ile)
    access_token = JWTHandler.create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
        tenant_slug=tenant.slug,  # ← Schema name için gerekli
        role=user.role.value,
        permissions=["model:read", "audit:read"],  # TODO: DB'den çek
        deployment_type=tenant.deployment_type
    )
    refresh_token = JWTHandler.create_refresh_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id)
    )
    
    # 6. Last login update
    await user_repo.update_last_login(user.id)
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": str(user.id), 
            "email": user.email, 
            "role": user.role.value,
            "tenant_slug": tenant.slug
        }
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
async def refresh_token(
    req: RefreshTokenRequest, 
    user_repo: PostgresUserRepository = Depends()
):
    """
    Refresh token ile yeni access token al
    Role ve permissions DB'den çekilir (güncel yetkiler için)
    """
    try:
        # 1. Refresh token'ı doğrula - SADECE 2 DEĞER DÖNER
        user_id, tenant_id = JWTHandler.refresh_access_token(req.refresh_token)
        
        # 2. User'ı DB'den bul (güncel role ve status için)
        user = await user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")
        
        # 3. Tenant bilgisini al (güncel status ve slug için)
        tenant = await user_repo.get_tenant_by_id(uuid.UUID(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        if tenant.is_suspended():
            raise HTTPException(
                status_code=402,
                detail=f"Account {tenant.status}. Please contact support."
            )
        
        # 4. Permissions'ı DB'den veya config'den çek (TODO: dynamic)
        # Şimdilik statik, Faz 2'de dinamik olacak
        permissions = ["model:read", "audit:read"]
        
        # 5. Yeni access token oluştur (güncel bilgilerle)
        new_access = JWTHandler.create_access_token(
            subject=user_id,
            tenant_id=tenant_id,
            role=user.role.value,              # ← DB'den gelen güncel role
            permissions=permissions,            # ← DB'den gelen güncel permissions
            tenant_slug=tenant.slug,            # ← Schema routing için
            deployment_type=tenant.deployment_type
        )
        
        return TokenRefreshResponse(access_token=new_access)
        
    except ValueError as e:
        error_msg = str(e)
        if "Invalid token format" in error_msg or "invalid UUID" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Invalid token format")
        raise HTTPException(status_code=401, detail=error_msg)
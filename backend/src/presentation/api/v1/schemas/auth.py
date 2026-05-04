"""
Authentication request/response schemas
Pydantic v2 compatible
"""

from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime

# ================= REQUEST MODELS =================

class LoginRequest(BaseModel):
    """Login request payload"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    
    @field_validator('password')
    @classmethod
    def password_must_contain_special_char(cls, v: str) -> str:
        """Optional: Enforce password complexity"""
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            # Production'da raise ValueError(...) yapabilirsin
            pass
        return v

class RegisterRequest(BaseModel):
    """Registration request payload"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    tenant_slug: str = Field(..., pattern=r'^[a-z0-9-]+$', min_length=3, max_length=50, description="Tenant slug (URL-friendly)")
    tenant_name: str = Field(..., min_length=2, max_length=100, description="Tenant display name")
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce basic password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v) or not any(c.islower() for c in v):
            raise ValueError('Password must contain upper and lowercase letters')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str = Field(..., description="Valid refresh token")

# ================= RESPONSE MODELS =================

class UserResponse(BaseModel):
    """User info in auth responses"""
    id: str
    email: EmailStr
    role: str
    is_active: bool
    is_verified: bool
    tenant_id: str
    tenant_slug: str
    permissions: List[str]
    created_at: datetime
    
    class Config:
        from_attributes = True  # Pydantic v2: ORM mode

class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=1800, description="Access token TTL in seconds")

class LoginResponse(BaseModel):
    """Login success response"""
    message: str = "Login successful"
    user: UserResponse
    token: TokenResponse

class RegisterResponse(BaseModel):
    """Registration success response"""
    message: str = "Registration successful. Please login."
    tenant_id: str
    user_id: str

class ErrorResponse(BaseModel):
    """Standard error response for auth endpoints"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "examples": [
                {"error": "invalid_credentials", "detail": "Invalid email or password"},
                {"error": "user_not_found", "detail": "No account with this email"},
                {"error": "tenant_not_found", "detail": "Tenant slug does not exist"},
                {"error": "user_inactive", "detail": "Account is not active"},
            ]
        }
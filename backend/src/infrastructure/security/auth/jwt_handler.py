from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from src.infrastructure.config.settings import settings

class JWTHandler:
    """
    SOLID: Single Responsibility
    Sadece JWT token yönetimi yapar
    """
    
    @staticmethod
    def create_access_token(
        subject: str,
        tenant_id: str,
        role: str,
        permissions: list[str] = None,
        expires_delta: Optional[timedelta] = None,
        **kwargs  # ← Buraya eklenen **kwargs, auth.py'den gelen fazlalık parametreleri yutar
    ) -> str:
        """Access token oluştur"""
        if expires_delta is None:
            # settings import'una göre burayı kontrol et
            expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        expire = datetime.now(timezone.utc) + expires_delta
        
        payload = {
            "sub": subject,
            "tenant_id": tenant_id,
            "role": role,
            "permissions": permissions or [],
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access"
        }

        # Eğer auth.py'den gelen ek bilgileri de token içine gömmek istersen:
        if "tenant_slug" in kwargs:
            payload["tenant_slug"] = kwargs["tenant_slug"]
        if "deployment_type" in kwargs:
            payload["deployment_type"] = kwargs["deployment_type"]
        
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    @staticmethod
    def create_refresh_token(subject: str, tenant_id: str, expires_delta: Optional[timedelta] = None) -> str:
        """Refresh token oluştur (daha uzun ömürlü)"""
        if expires_delta is None:
            expires_delta = timedelta(days=7)
        
        expire = datetime.now(timezone.utc) + expires_delta
        
        payload = {
            "sub": subject,
            "tenant_id": tenant_id,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        }
        
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
        """Token doğrula ve payload döndür"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            
            if payload.get("type") != token_type:
                raise JWTError(f"Invalid token type: expected {token_type}")
            
            return payload
            
        except JWTError as e:
            raise ValueError(f"Token verification failed: {str(e)}")
    
    @staticmethod
    def refresh_access_token(refresh_token: str) -> tuple[str, str]:
        """Refresh token'dan yeni access token üret"""
        payload = JWTHandler.verify_token(refresh_token, "refresh")
        
        return (
            payload["sub"],  # user_id
            payload["tenant_id"],
            # payload["role"],
            # payload.get("permissions", [])
        )
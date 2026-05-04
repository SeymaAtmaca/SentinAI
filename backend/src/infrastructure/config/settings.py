"""
Application settings loaded from environment variables
Pydantic v2 compatible
"""

from pydantic_settings import BaseSettings, SettingsConfigDict  
from pydantic import Field
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Unknown env vars are ignored
    )
    
    # Database
    DB_USER: str = Field(default="mgadmin")
    DB_PASSWORD: str = Field(default="postgrePass34")
    DB_HOST: str = Field(default="postgres")
    DB_PORT: int = Field(default=5432)
    DB_NAME: str = Field(default="modelguardian")

    DB_POOL_SIZE: int = Field(default=10)
    DB_MAX_OVERFLOW: int = Field(default=20)
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Redis
    REDIS_PASSWORD: str = Field(default="redis")
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@redis:6379/0"
    
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = Field(default="kafka:9092")
    
    # Security
    SECRET_KEY: str = Field(default="change-me-in-production")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    
    # JWT
    JWT_SECRET_KEY: str = Field(default="change-me-too")
    JWT_ALGORITHM: str = Field(default="HS256")
    
    # Application
    APP_ENV: str = Field(default="development")
    APP_NAME: str = Field(default="ModelGuardian AI")
    API_V1_PREFIX: str = Field(default="/api/v1")
    
    # CORS & WebSocket
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8000,ws://localhost:8001,wss://localhost:8001"
    )
    
    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=100)
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
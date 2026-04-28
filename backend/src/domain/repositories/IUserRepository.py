"""
SOLID: Dependency Inversion Principle
Interface definition for User repository
"""

from abc import ABC, abstractmethod
from typing import Optional
import uuid

from src.domain.entities.user import User, Role
from src.domain.entities.tenant import Tenant


class IUserRepository(ABC):
    """
    Repository interface for User & Tenant operations
    Infrastructure layer implements this
    """
    
    @abstractmethod
    async def get_by_email(self, email: str, tenant_id: Optional[str] = None) -> Optional[User]:
        pass
    
    @abstractmethod
    async def create_user(self, tenant_id: uuid.UUID, email: str, 
                         password_hash: str, role: Role) -> User:
        pass
    
    @abstractmethod
    async def update_last_login(self, user_id: uuid.UUID):
        pass
    
    @abstractmethod
    async def tenant_exists(self, slug: str) -> bool:
        pass
    
    @abstractmethod
    async def create_tenant(self, slug: str, name: str, schema_name: str) -> Tenant:
        pass
    
    @abstractmethod
    async def create_tenant_schema(self, schema_name: str):
        pass
    
    @abstractmethod
    async def get_tenant_by_id(self, tenant_id: uuid.UUID) -> Optional[Tenant]:
        pass
    
    @abstractmethod
    async def update_tenant_status(self, tenant_id: uuid.UUID, status: str):
        pass
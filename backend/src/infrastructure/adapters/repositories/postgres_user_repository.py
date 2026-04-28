"""
SOLID: Dependency Inversion Principle
PostgreSQL implementation of IUserRepository interface
Async SQLAlchemy with multi-tenant schema support
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text, select, insert, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
import uuid
from datetime import datetime

from src.domain.entities.user import User, Role
from src.domain.entities.tenant import Tenant
from src.domain.repositories.IUserRepository import IUserRepository
from src.infrastructure.config.settings import settings
from src.infrastructure.security.tenant.context import get_tenant_context


class PostgresUserRepository(IUserRepository):
    """
    Async PostgreSQL repository for User & Tenant entities
    Multi-tenant aware with schema isolation
    """
    
    def __init__(self, engine=None):
        self.engine = engine or create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_pre_ping=True,
            echo=settings.APP_ENV == "development"
        )
        self.SessionLocal = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def get_session(self) -> AsyncSession:
        """Get async DB session"""
        return self.SessionLocal()
    
    async def get_by_email(self, email: str, tenant_id: Optional[str] = None) -> Optional[User]:
        """Get user by email with optional tenant filter"""
        async with self.get_session() as session:
            # Multi-tenant: schema_name'den search_path ayarla
            ctx = get_tenant_context()
            await session.execute(text(f"SET search_path TO {ctx.schema_name}, public"))
            
            query = text("""
                SELECT id, tenant_id, email, password_hash, role, 
                       is_active, is_verified, created_at, updated_at, last_login_at
                FROM users 
                WHERE email = :email 
                AND tenant_id = :tenant_id
                LIMIT 1
            """)
            result = await session.execute(
                query, 
                {"email": email, "tenant_id": tenant_id or ctx.tenant_id}
            )
            row = result.fetchone()
            
            if row:
                return User(
                    id=row[0],
                    tenant_id=row[1],
                    email=row[2],
                    password_hash=row[3],
                    role=Role(row[4]),
                    is_active=row[5],
                    is_verified=row[6],
                    created_at=row[7],
                    updated_at=row[8],
                    last_login_at=row[9]
                )
            return None
    
    async def create_user(self, tenant_id: uuid.UUID, email: str, 
                         password_hash: str, role: Role) -> User:
        """Create new user"""
        async with self.get_session() as session:
            ctx = get_tenant_context()
            await session.execute(text(f"SET search_path TO {ctx.schema_name}, public"))
            
            user_id = uuid.uuid4()
            query = text("""
                INSERT INTO users (id, tenant_id, email, password_hash, role, created_at)
                VALUES (:id, :tenant_id, :email, :password_hash, :role, NOW())
                RETURNING id, tenant_id, email, password_hash, role, 
                         is_active, is_verified, created_at, updated_at, last_login_at
            """)
            result = await session.execute(
                query,
                {
                    "id": user_id,
                    "tenant_id": tenant_id,
                    "email": email,
                    "password_hash": password_hash,
                    "role": role.value
                }
            )
            await session.commit()
            row = result.fetchone()
            
            return User(
                id=row[0],
                tenant_id=row[1],
                email=row[2],
                password_hash=row[3],
                role=Role(row[4]),
                is_active=row[5],
                is_verified=row[6],
                created_at=row[7],
                updated_at=row[8],
                last_login_at=row[9]
            )
    
    async def update_last_login(self, user_id: uuid.UUID):
        """Update last login timestamp"""
        async with self.get_session() as session:
            ctx = get_tenant_context()
            await session.execute(text(f"SET search_path TO {ctx.schema_name}, public"))
            
            await session.execute(
                text("UPDATE users SET last_login_at = NOW() WHERE id = :id"),
                {"id": user_id}
            )
            await session.commit()
    
    async def tenant_exists(self, slug: str) -> bool:
        """Check if tenant slug exists (public schema)"""
        async with self.get_session() as session:
            # Public schema for tenant registry
            await session.execute(text("SET search_path TO public"))
            
            result = await session.execute(
                text("SELECT COUNT(*) FROM tenants WHERE slug = :slug"),
                {"slug": slug}
            )
            count = result.scalar()
            return count > 0
    
    async def create_tenant(self, slug: str, name: str, schema_name: str) -> Tenant:
        """Create new tenant in public schema"""
        async with self.get_session() as session:
            await session.execute(text("SET search_path TO public"))
            
            tenant_id = uuid.uuid4()
            query = text("""
                INSERT INTO tenants (id, slug, name, schema_name, status, created_at)
                VALUES (:id, :slug, :name, :schema_name, 'trial', NOW())
                RETURNING id, slug, name, schema_name, status, deployment_type,
                         stripe_customer_id, subscription_plan, subscription_status,
                         current_period_end, created_at, updated_at
            """)
            result = await session.execute(
                query,
                {
                    "id": tenant_id,
                    "slug": slug,
                    "name": name,
                    "schema_name": schema_name
                }
            )
            await session.commit()
            row = result.fetchone()
            
            return Tenant(
                id=row[0],
                slug=row[1],
                name=row[2],
                schema_name=row[3],
                status=row[4],
                deployment_type=row[5],
                stripe_customer_id=row[6],
                subscription_plan=row[7],
                subscription_status=row[8],
                current_period_end=row[9],
                created_at=row[10],
                updated_at=row[11]
            )
    
    async def create_tenant_schema(self, schema_name: str):
        """Create PostgreSQL schema for new tenant + base tables"""
        async with self.get_session() as session:
            # Create schema
            await session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            
            # Create tenant-specific tables
            await session.execute(text(f"""
                SET search_path TO {schema_name};
                
                -- Models table
                CREATE TABLE IF NOT EXISTS models (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    status VARCHAR(50) DEFAULT 'active',
                    version VARCHAR(50),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                
                -- Actions/Inference log table
                CREATE TABLE IF NOT EXISTS actions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    model_id UUID REFERENCES models(id),
                    action_type VARCHAR(100) NOT NULL,
                    payload JSONB DEFAULT '{{}}',
                    risk_score DECIMAL(3,2),
                    status VARCHAR(50) DEFAULT 'pending',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                
                -- Approvals table
                CREATE TABLE IF NOT EXISTS approvals (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    action_id UUID REFERENCES actions(id),
                    requested_by UUID,
                    approved_by UUID,
                    status VARCHAR(50) DEFAULT 'pending',
                    comments TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    decided_at TIMESTAMPTZ
                );
                
                -- Policies table
                CREATE TABLE IF NOT EXISTS policies (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    rules JSONB NOT NULL,
                    severity VARCHAR(20) DEFAULT 'medium',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                
                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_actions_model ON actions(model_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_policies_active ON policies(is_active) WHERE is_active = TRUE;
            """))
            await session.commit()
    
    async def get_tenant_by_id(self, tenant_id: uuid.UUID) -> Optional[Tenant]:
        """Get tenant from public schema"""
        async with self.get_session() as session:
            await session.execute(text("SET search_path TO public"))
            
            result = await session.execute(
                text("SELECT * FROM tenants WHERE id = :id LIMIT 1"),
                {"id": tenant_id}
            )
            row = result.fetchone()
            
            if row:
                return Tenant(
                    id=row[0],
                    slug=row[1],
                    name=row[2],
                    schema_name=row[3],
                    status=row[4],
                    deployment_type=row[5],
                    stripe_customer_id=row[6],
                    subscription_plan=row[7],
                    subscription_status=row[8],
                    current_period_end=row[9],
                    created_at=row[10],
                    updated_at=row[11]
                )
            return None
    
    async def update_tenant_status(self, tenant_id: uuid.UUID, status: str):
        """Update tenant status (for billing/suspension)"""
        async with self.get_session() as session:
            await session.execute(text("SET search_path TO public"))
            
            await session.execute(
                text("UPDATE tenants SET status = :status, updated_at = NOW() WHERE id = :id"),
                {"status": status, "id": tenant_id}
            )
            await session.commit()
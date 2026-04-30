"""
SOLID: Dependency Inversion Principle
Central dependency container for wiring
"""
from dependency_injector import containers, providers

from src.infrastructure.adapters.repositories.postgres_audit_repository import PostgresAuditRepository
from src.infrastructure.adapters.repositories.postgres_approval_repository import PostgresApprovalRepository
from src.application.use_cases.intercept_action.policy_engine import PolicyEngine
from src.application.use_cases.intercept_action.intercept_action_use_case import InterceptActionUseCase
from src.infrastructure.config.settings import settings

class Container(containers.DeclarativeContainer):
    """Application dependency container"""
    
    config = providers.Configuration()
    
    # Infrastructure: Database engine (shared)
    db_engine = providers.Singleton(
        # SQLAlchemy create_async_engine call here
        # For now, we'll pass URL directly to repos
        settings.DATABASE_URL
    )
    
    # Repositories
    audit_repository = providers.Factory(
        PostgresAuditRepository,
        database_url=settings.DATABASE_URL
    )
    
    approval_repository = providers.Factory(
        PostgresApprovalRepository,
        database_url=settings.DATABASE_URL
    )
    
    # Policy Engine
    policy_engine = providers.Factory(
        PolicyEngine
    )
    
    # Use Cases
    intercept_action_use_case = providers.Factory(
        InterceptActionUseCase,
        audit_repo=audit_repository,
        approval_repo=approval_repository,
        policy_engine=policy_engine
    )
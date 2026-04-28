"""
SOLID: Single Responsibility
Sadece password hashing/verification işlemlerini yönetir
Security: Argon2id (OWASP recommended) veya bcrypt fallback
"""

from passlib.context import CryptContext
from src.infrastructure.config.settings import settings

# Passlib context configuration
# Argon2id > bcrypt > sha256_crypt (fallback chain)
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__rounds=3,
    argon2__memory_cost=65536,
    argon2__parallelism=1,
    bcrypt__rounds=12
)

class PasswordHasher:
    """
    Password hashing & verification utility
    Thread-safe & async-compatible
    """
    
    @staticmethod
    def hash(password: str) -> str:
        """
        Password'u güvenli şekilde hash'le
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string (Argon2id veya bcrypt)
        """
        return pwd_context.hash(password)
    
    @staticmethod
    def verify(plain_password: str, hashed_password: str) -> bool:
        """
        Password'u doğrula
        
        Args:
            plain_password: Kullanıcının girdiği plain password
            hashed_password: DB'den gelen hashed password
            
        Returns:
            bool: Password eşleşiyor mu?
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def needs_rehash(hashed_password: str) -> bool:
        """
        Hash algoritması güncellenmiş mi kontrol et
        
        Returns:
            bool: Yeniden hash gerekiyor mu?
        """
        return pwd_context.needs_rehash(hashed_password)
    
    @staticmethod
    def get_scheme(hashed_password: str) -> str:
        """
        Hangi hashing algoritması kullanılmış öğren
        
        Returns:
            str: "argon2", "bcrypt", vs.
        """
        return pwd_context.identify(hashed_password)
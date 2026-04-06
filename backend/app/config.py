"""Application configuration management"""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Environment
    env: str = os.getenv("ENV", "dev")

    # Server
    port: int = int(os.getenv("PORT", "8000"))
    host: str = os.getenv("HOST", "0.0.0.0")
    reload: bool = os.getenv("RELOAD", "true").lower() == "true"

    # Storage - Deprecated: Redis support removed, always use memory store
    # These are kept for backward compatibility but ignored
    use_redis: bool = False
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # JWT - Deprecated: Replaced by server-side session
    # Kept for backward compatibility but ignored
    jwt_secret: str = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    auth_mock_fallback_enabled: bool = False

    # SSO / Auth Configuration
    enable_mock_login: bool = os.getenv("ENABLE_MOCK_LOGIN", "false").lower() == "true"
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    session_max_age_sec: int = int(os.getenv("SESSION_MAX_AGE_SEC", "86400"))  # 24 hours

    # SSO OAuth2 endpoints
    sso_authorize_url: str = os.getenv("SSO_AUTHORIZE_URL", "")
    sso_token_url: str = os.getenv("SSO_TOKEN_URL", "")
    sso_client_id: str = os.getenv("SSO_CLIENT_ID", "")
    sso_client_secret: str = os.getenv("SSO_CLIENT_SECRET", "")
    sso_redirect_uri: str = os.getenv("SSO_REDIRECT_URI", "http://localhost:8000/api/auth/callback")
    sso_jwks_url: str = os.getenv("SSO_JWKS_URL", "")

    # OpenCode
    opencode_base_url: str = os.getenv("OPENCODE_BASE_URL", "http://127.0.0.1:4096")
    opencode_username: str = os.getenv("OPENCODE_USERNAME", "opencode")
    opencode_password: str = os.getenv("OPENCODE_PASSWORD", "")

    # OpenWork
    openwork_base_url: str = os.getenv("OPENWORK_BASE_URL", "http://127.0.0.1:8787")
    openwork_token: str = os.getenv("OPENWORK_TOKEN", "")

    # Portal
    portal_name: str = os.getenv("PORTAL_NAME", "AI Portal")
    resources_path: str = os.getenv("RESOURCES_PATH", "config/resources.generated.json")

    # CORS (include both localhost and 127.0.0.1 for dev)
    cors_origins: list = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:8000",
    ]
    
    # Allow requests from any origin in dev
    @property
    def cors_origins_list(self) -> list:
        if self.env == "dev":
            return ["*"]
        return self.cors_origins

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # 忽略额外的环境变量


def validate_startup():
    """Validate critical settings on startup (production hard checks)"""
    settings = Settings()
    
    if settings.env != "dev":
        # Production safety checks
        if settings.enable_mock_login:
            raise RuntimeError(
                "ENABLE_MOCK_LOGIN must be disabled in non-dev environment. "
                "Set ENV=dev to enable mock login for development."
            )
        
        if settings.auth_mock_fallback_enabled:
            raise RuntimeError(
                "AUTH_MOCK_FALLBACK_ENABLED must be disabled in non-dev environment. "
                "This is a legacy setting - use ENABLE_MOCK_LOGIN instead."
            )
        
        if not settings.cookie_secure:
            raise RuntimeError(
                "COOKIE_SECURE must be true in non-dev environment. "
                "HTTPS is required for secure session cookies."
            )
        
        if not settings.sso_authorize_url or not settings.sso_token_url:
            raise RuntimeError(
                "SSO configuration missing. "
                "SSO_AUTHORIZE_URL and SSO_TOKEN_URL must be set in production."
            )
        
        if not settings.sso_client_id or not settings.sso_client_secret:
            raise RuntimeError(
                "SSO client credentials missing. "
                "SSO_CLIENT_ID and SSO_CLIENT_SECRET must be set in production."
            )
    
    return settings


# Global settings instance
settings = Settings()

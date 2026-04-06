"""Authentication service - SSO OAuth2 + Local Session implementation"""

import time
import secrets
from typing import Optional, Dict, Any
import httpx

from ..models import UserCtx, AuthSession
from ..config import settings


class UserRepository:
    """Local user repository - in production this should query a user database"""
    
    def __init__(self):
        # In-memory user store for demo/development
        # In production, this should query LDAP/DB
        self._users: Dict[str, UserCtx] = {}
        self._mock_users: Dict[str, UserCtx] = {}
    
    def create_mock_user(self, emp_no: str) -> UserCtx:
        """Create a mock user for development"""
        user = UserCtx(
            emp_no=emp_no,
            name=f"User-{emp_no}",
            dept="demo",
            roles=["employee"],
            email=f"{emp_no}@company.com"
        )
        self._mock_users[emp_no] = user
        return user
    
    async def get_active_user_by_user_name(self, user_name: str) -> Optional[UserCtx]:
        """
        Get active user by login name from SSO.
        In production, this should query your user database/LDAP.
        """
        # For demo: auto-create user if they don't exist
        # In production: check if user exists and is active
        
        # Normalize user_name to emp_no format
        emp_no = user_name.split("@")[0] if "@" in user_name else user_name
        
        # Check existing users
        if emp_no in self._users:
            return self._users[emp_no]
        
        if emp_no in self._mock_users:
            return self._mock_users[emp_no]
        
        # Auto-provision only in dev mode.
        if settings.env != "dev":
            return None

        user = UserCtx(
            emp_no=emp_no,
            name=user_name,
            dept="demo",
            roles=["employee"],
            email=user_name if "@" in user_name else f"{user_name}@company.com"
        )
        self._users[emp_no] = user
        return user
    
    async def get_user_by_emp_no(self, emp_no: str) -> Optional[UserCtx]:
        """Get user by employee number"""
        if emp_no in self._users:
            return self._users[emp_no]
        if emp_no in self._mock_users:
            return self._mock_users[emp_no]
        return None


class SSOService:
    """SSO OAuth2 service"""
    
    async def exchange_code(self, code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        Calls SSO token endpoint.
        """
        if not settings.sso_token_url:
            raise RuntimeError("SSO_TOKEN_URL not configured")
        
        payload = {
            "grant_type": "authorization_code",
            "client_id": settings.sso_client_id,
            "client_secret": settings.sso_client_secret,
            "code": code,
            "redirect_uri": settings.sso_redirect_uri,
        }
        
        if code_verifier:
            payload["code_verifier"] = code_verifier
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.sso_token_url,
                data=payload,
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            return response.json()
    
    def verify_jwt(self, token: str) -> Dict[str, Any]:
        """
        Verify JWT token and return claims.
        In production, this should:
        1. Fetch JWKS from SSO_JWKS_URL
        2. Verify signature
        3. Validate iss, aud, exp claims
        """
        import jwt

        try:
            if settings.env == "dev" and not settings.sso_jwks_url:
                claims = jwt.decode(token, options={"verify_signature": False})
            else:
                if not settings.sso_jwks_url:
                    raise ValueError("SSO_JWKS_URL not configured")
                jwks_client = jwt.PyJWKClient(settings.sso_jwks_url)
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256", "ES256", "HS256"],
                    audience=settings.sso_client_id or None,
                    options={"verify_aud": bool(settings.sso_client_id)},
                )
            return claims
        except jwt.PyJWTError as e:
            raise ValueError(f"Invalid JWT: {e}")


class AuthSessionService:
    """Local session management service"""
    
    async def create_session(
        self,
        user: UserCtx,
        claims: Dict[str, Any]
    ) -> AuthSession:
        """Create new authentication session"""
        
        now = int(time.time())
        session = AuthSession(
            session_id=secrets.token_urlsafe(32),
            user_id=user.emp_no,
            user_name=claims.get("preferred_username") or claims.get("email") or user.emp_no,
            roles=user.roles,
            expires_at=now + settings.session_max_age_sec,
            created_at=now,
            last_seen_at=now,
            sso_access_token=claims.get("access_token"),
            id_token_claims=claims,
        )
        
        # Save to store
        from ..store import store as storage
        await storage.save_auth_session(session)
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[AuthSession]:
        """Get session by ID"""
        from ..store import store as storage
        return await storage.get_auth_session(session_id)
    
    async def delete_session(self, session_id: str) -> None:
        """Delete session (logout)"""
        from ..store import store as storage
        await storage.delete_auth_session(session_id)


# Global service instances
user_repo = UserRepository()
sso_service = SSOService()
auth_session_service = AuthSessionService()


# Legacy compatibility
class AuthService:
    """Legacy auth service - deprecated, kept for backward compatibility"""
    
    def create_mock_user(self, emp_no: str) -> UserCtx:
        return user_repo.create_mock_user(emp_no)
    
    def generate_token(self, user: UserCtx) -> str:
        """Legacy JWT generation - not used in new session-based auth"""
        import jwt
        payload = {
            "emp_no": user.emp_no,
            "name": user.name,
            "dept": user.dept,
            "roles": user.roles,
            "email": user.email,
            "iat": time.time(),
            "exp": time.time() + settings.session_max_age_sec
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    
    def verify_token(self, token: str) -> Optional[UserCtx]:
        """Legacy JWT verification - not used in new session-based auth"""
        import jwt
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
            return UserCtx(**payload)
        except jwt.PyJWTError:
            return None
    
    def resolve_sso_user(self, code: str) -> Optional[UserCtx]:
        """Legacy SSO resolution"""
        return user_repo.create_mock_user("E10001")


# Global legacy instance (deprecated)
auth_service = AuthService()

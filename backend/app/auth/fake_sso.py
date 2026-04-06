"""Fake SSO service for local testing without real SSO infrastructure

This module provides a fake SSO implementation that:
1. Accepts any authorization code
2. Returns mock tokens
3. Validates tokens locally without external calls

WARNING: This is for development/testing only. DO NOT use in production.
"""

import time
import secrets
import json
import base64
from typing import Dict, Any, Optional

from ..models import UserCtx


class FakeSSOService:
    """
    Fake SSO service that simulates OAuth2 flow locally.
    
    Usage:
    1. User is redirected to /api/auth/login-url
    2. Frontend redirects to fake authorize URL (which immediately redirects back)
    3. Frontend calls /api/auth/exchange with code
    4. This service accepts any code and creates a session
    """
    
    def __init__(self, default_user: Optional[UserCtx] = None):
        self.default_user = default_user or UserCtx(
            emp_no="E10001",
            name="测试用户",
            dept="Engineering",
            roles=["employee", "admin"],
            email="test@company.com"
        )
        self._issued_codes: Dict[str, str] = {}  # code -> next_url
    
    def issue_authorization_code(self, next_url: str = "/") -> str:
        """Issue a fake authorization code"""
        code = secrets.token_urlsafe(32)
        self._issued_codes[code] = next_url
        # Clean up old codes (keep for 10 minutes)
        if len(self._issued_codes) > 1000:
            self._issued_codes.clear()
        return code
    
    def build_authorize_url(self, redirect_uri: str, state: str, next_url: str = "/") -> str:
        """
        Build fake authorize URL.
        
        This URL immediately redirects back to the callback with a code,
        simulating the user clicking "Allow" instantly.
        """
        code = self.issue_authorization_code(next_url)
        
        # Build redirect URL with code
        import urllib.parse
        params = {
            "code": code,
            "state": state,
        }
        query = urllib.parse.urlencode(params)
        
        # Return a data URL that immediately redirects (or just return the callback URL)
        # For simplicity, we'll return a special marker that frontend knows to handle
        return f"{redirect_uri}?{query}"
    
    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """
        Exchange any code for tokens.
        
        In fake mode, we accept any code and return mock tokens.
        """
        # Validate code exists (optional - we could accept any code)
        # For testing, accept any code to make it easier
        next_url = self._issued_codes.pop(code, "/")
        
        # Create fake ID token (JWT-like structure, but not actually signed)
        id_token_claims = {
            "sub": self.default_user.emp_no,
            "preferred_username": self.default_user.emp_no,
            "name": self.default_user.name,
            "email": self.default_user.email,
            "roles": self.default_user.roles,
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "iss": "fake-sso",
            "aud": "ai-portal",
        }
        
        # Create fake access token
        access_token_claims = {
            "sub": self.default_user.emp_no,
            "scope": "openid profile",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        
        return {
            "access_token": self._encode_fake_jwt(access_token_claims),
            "id_token": self._encode_fake_jwt(id_token_claims),
            "token_type": "Bearer",
            "expires_in": 3600,
            "__next_url": next_url,  # Internal marker
        }
    
    def verify_jwt(self, token: str) -> Dict[str, Any]:
        """
        Verify fake JWT token.
        
        In fake mode, we just decode without signature verification.
        """
        return self._decode_fake_jwt(token)
    
    def _encode_fake_jwt(self, payload: Dict[str, Any]) -> str:
        """Encode payload as fake JWT (no real signature)"""
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).decode().rstrip("=")
        
        body = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip("=")
        
        # No signature (alg: none)
        return f"{header}.{body}."
    
    def _decode_fake_jwt(self, token: str) -> Dict[str, Any]:
        """Decode fake JWT without verification"""
        parts = token.split(".")
        if len(parts) < 2:
            raise ValueError("Invalid token format")
        
        # Add padding if needed
        body_b64 = parts[1]
        padding = 4 - len(body_b64) % 4
        if padding != 4:
            body_b64 += "=" * padding
        
        body_json = base64.urlsafe_b64decode(body_b64).decode()
        return json.loads(body_json)


# Global fake SSO instance (lazily created)
_fake_sso: Optional[FakeSSOService] = None


def get_fake_sso() -> FakeSSOService:
    """Get or create fake SSO service"""
    global _fake_sso
    if _fake_sso is None:
        _fake_sso = FakeSSOService()
    return _fake_sso


def enable_fake_sso_mode(default_user: Optional[UserCtx] = None):
    """
    Enable fake SSO mode globally.
    
    This patches the auth service to use fake SSO.
    """
    global _fake_sso
    _fake_sso = FakeSSOService(default_user)
    
    # Patch the SSO service module
    from . import service as auth_service_module
    
    # Replace SSOService methods with fake implementations
    auth_service_module.sso_service.exchange_code = _fake_sso.exchange_code
    auth_service_module.sso_service.verify_jwt = _fake_sso.verify_jwt
    
    print("🔓 Fake SSO mode enabled - Any code will be accepted for login")
    return _fake_sso

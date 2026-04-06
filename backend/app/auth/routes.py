"""Authentication routes - SSO OAuth2 + Local Session"""

import secrets
import time
from fastapi import APIRouter, HTTPException, status, Cookie, Request
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Annotated, Optional
from pydantic import BaseModel

from ..config import settings
from ..models import UserCtx, AuthSession
from .service import auth_session_service, sso_service, user_repo
from .deps import SessionUser
from ..store import store as storage


router = APIRouter(prefix="/api/auth", tags=["authentication"])


# Request/Response models
class LoginUrlResponse(BaseModel):
    """Login URL response"""
    login_url: str


class ExchangeCodeRequest(BaseModel):
    """Exchange code request"""
    code: str
    state: Optional[str] = None


class ExchangeCodeResponse(BaseModel):
    """Exchange code response"""
    user: dict
    next: str


class UserInfoResponse(BaseModel):
    """User info response"""
    emp_no: str
    name: str
    dept: str
    roles: list[str]
    email: str | None


class LogoutResponse(BaseModel):
    """Logout response"""
    success: bool


def _build_authorize_url(state: str) -> str:
    """Build SSO authorize URL"""
    import urllib.parse
    
    params = {
        "client_id": settings.sso_client_id,
        "redirect_uri": settings.sso_redirect_uri,
        "response_type": "code",
        "scope": "openid profile",
        "state": state,
    }
    query = urllib.parse.urlencode(params)
    return f"{settings.sso_authorize_url}?{query}"


@router.get("/login-url", response_model=LoginUrlResponse)
async def get_login_url(next: str = "/"):
    """
    Get SSO login URL with state parameter.
    Frontend should redirect user to this URL to start OAuth2 flow.
    """
    if not settings.sso_authorize_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSO not configured"
        )
    
    # Generate state and store it
    state = secrets.token_urlsafe(32)
    await storage.save_oauth_state(state, next)
    
    return LoginUrlResponse(login_url=_build_authorize_url(state))


@router.post("/exchange", response_model=ExchangeCodeResponse)
async def exchange_code(body: ExchangeCodeRequest):
    """
    Exchange OAuth2 authorization code for access token.
    Creates local session and sets portal_sid cookie.
    """
    # Validate state if provided
    if body.state:
        next_url = await storage.consume_oauth_state(body.state)
        if not next_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired state"
            )
    else:
        next_url = "/"
    
    # Exchange code for token with SSO
    try:
        token_resp = await sso_service.exchange_code(body.code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to exchange code: {str(e)}"
        )
    
    # Verify JWT and extract claims
    try:
        claims = sso_service.verify_jwt(
            token_resp.get("id_token") or token_resp.get("access_token")
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to verify token: {str(e)}"
        )
    
    # Extract user identifier from claims
    # Standard OIDC claims: 'preferred_username', 'email', 'sub'
    user_name = claims.get("preferred_username") or claims.get("email") or claims.get("sub")
    if not user_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identifier not found in token"
        )
    
    # Lookup local user
    user = await user_repo.get_active_user_by_user_name(user_name)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not authorized to access this portal"
        )
    
    # Create local session
    auth_session = await auth_session_service.create_session(user, claims)
    
    # Build response with cookie
    resp = JSONResponse({
        "user": {
            "emp_no": user.emp_no,
            "name": user.name,
            "dept": user.dept,
            "roles": user.roles,
            "email": user.email,
        },
        "next": next_url,
    })
    
    resp.set_cookie(
        key="portal_sid",
        value=auth_session.session_id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_max_age_sec,
    )
    
    return resp


@router.get("/callback")
async def sso_callback(code: str, state: Optional[str] = None):
    """
    SSO callback endpoint - handles OAuth2 redirect from identity provider.
    This is an alternative to frontend handling the exchange.
    """
    if settings.enable_mock_login and settings.env == "dev":
        # In dev mode with mock enabled, redirect to mock login
        return RedirectResponse(url=f"/api/auth/mock-login?emp_no=E10001&next=/")
    
    # Exchange code via our own API
    try:
        exchange_body = ExchangeCodeRequest(code=code, state=state)
        result = await exchange_code(exchange_body)
        
        # Redirect to next URL with cookie already set
        next_url = result.body.get("next", "/") if hasattr(result, 'body') else "/"
        return RedirectResponse(url=next_url)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


@router.get("/me", response_model=UserInfoResponse)
async def get_me(user: SessionUser) -> UserInfoResponse:
    """Get current user information"""
    return UserInfoResponse(
        emp_no=user.emp_no,
        name=user.name,
        dept=user.dept,
        roles=user.roles,
        email=user.email
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    portal_sid: Annotated[str | None, Cookie()] = None
):
    """Logout user by clearing session cookie and deleting session"""
    if portal_sid:
        await auth_session_service.delete_session(portal_sid)
    
    resp = JSONResponse({"success": True})
    resp.delete_cookie(key="portal_sid")
    return resp


# Dev-only mock login endpoint
if settings.enable_mock_login and settings.env == "dev":
    
    @router.get("/mock-login")
    async def mock_login(emp_no: str, next: str = "/"):
        """
        Mock SSO login endpoint - DEV ONLY.
        Only available when ENV=dev and ENABLE_MOCK_LOGIN=true.
        """
        user = user_repo.create_mock_user(emp_no)
        
        # Create session
        claims = {
            "preferred_username": user.emp_no,
            "name": user.name,
            "roles": user.roles,
        }
        auth_session = await auth_session_service.create_session(user, claims)
        
        resp = JSONResponse({
            "message": "Mock login successful (dev only)",
            "redirect": next,
            "user": {
                "emp_no": user.emp_no,
                "name": user.name,
                "dept": user.dept
            }
        })
        
        resp.set_cookie(
            key="portal_sid",
            value=auth_session.session_id,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=settings.session_max_age_sec,
        )
        
        return resp

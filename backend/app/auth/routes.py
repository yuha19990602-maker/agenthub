"""Authentication routes - SSO OAuth2 + Local Session"""

import secrets
import urllib.parse
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
_mock_login_enabled = settings.enable_mock_login and settings.env == "dev"


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


def _build_authorize_url(state: str, next_url: str = "/") -> str:
    """Build SSO authorize URL or dev mock-login URL."""
    if _mock_login_enabled and (not settings.sso_authorize_url or not settings.sso_token_url):
        query = urllib.parse.urlencode({"emp_no": "E10001", "next": next_url})
        return f"/api/auth/mock-login?{query}"

    params = {
        "client_id": settings.sso_client_id,
        "redirect_uri": settings.sso_redirect_uri,
        "response_type": "code",
        "scope": "openid profile",
        "state": state,
    }
    query = urllib.parse.urlencode(params)
    return f"{settings.sso_authorize_url}?{query}"


async def _authenticate_from_code(code: str, state: Optional[str]) -> tuple[UserCtx, AuthSession, str]:
    """Exchange code, validate claims, resolve user, and create session."""
    if state:
        next_url = await storage.consume_oauth_state(state)
        if not next_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired state",
            )
    else:
        next_url = "/"

    if not settings.sso_token_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSO token endpoint is not configured",
        )

    try:
        token_resp = await sso_service.exchange_code(code)
        claims = sso_service.verify_jwt(
            token_resp.get("id_token") or token_resp.get("access_token")
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to authenticate code: {str(e)}",
        )

    user_name = claims.get("preferred_username") or claims.get("email") or claims.get("sub")
    if not user_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identifier not found in token",
        )

    user = await user_repo.get_active_user_by_user_name(user_name)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not authorized to access this portal",
        )

    auth_session = await auth_session_service.create_session(user, claims)
    return user, auth_session, next_url


@router.get("/login-url", response_model=LoginUrlResponse)
async def get_login_url(next: str = "/"):
    """
    Get SSO login URL with state parameter.
    Frontend should redirect user to this URL to start OAuth2 flow.
    """
    state = secrets.token_urlsafe(32)
    await storage.save_oauth_state(state, next)
    return LoginUrlResponse(login_url=_build_authorize_url(state, next))


@router.post("/exchange", response_model=ExchangeCodeResponse)
async def exchange_code(body: ExchangeCodeRequest):
    """Exchange OAuth2 authorization code for access token and create local session."""
    user, auth_session, next_url = await _authenticate_from_code(body.code, body.state)
    
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
    """SSO callback endpoint for providers that redirect to the backend."""
    user, auth_session, next_url = await _authenticate_from_code(code, state)
    resp = RedirectResponse(url=next_url, status_code=302)
    resp.set_cookie(
        key="portal_sid",
        value=auth_session.session_id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_max_age_sec,
    )
    return resp


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


# Dev-only mock login endpoint - kept for backward compatibility
# In FAKE SSO mode, this is redundant but kept for compatibility
if _mock_login_enabled:
    
    @router.get("/mock-login")
    async def mock_login(
        request: Request,
        emp_no: str, 
        next: str = "/",
        redirect: bool = True  # New param: if true, redirect to frontend
    ):
        """
        Mock SSO login endpoint - DEV ONLY.
        Direct login without going through OAuth2 flow.
        
        If redirect=true (default), redirects to frontend after login.
        If redirect=false, returns JSON (for AJAX calls).
        """
        user = user_repo.create_mock_user(emp_no)
        
        # Create session
        claims = {
            "preferred_username": user.emp_no,
            "name": user.name,
            "roles": user.roles,
        }
        auth_session = await auth_session_service.create_session(user, claims)
        
        # Determine frontend URL
        frontend_url = "http://127.0.0.1:5173"
        
        # Build redirect URL
        redirect_url = f"{frontend_url}{next}"
        
        # Check if this is an AJAX request or browser direct access
        accept_header = request.headers.get('accept', '')
        is_ajax = 'application/json' in accept_header or not redirect
        
        if is_ajax:
            # Return JSON for AJAX calls
            resp = JSONResponse({
                "message": "Mock login successful (dev only)",
                "redirect": redirect_url,
                "user": {
                    "emp_no": user.emp_no,
                    "name": user.name,
                    "dept": user.dept
                }
            })
        else:
            # Redirect browser to frontend
            resp = RedirectResponse(url=redirect_url, status_code=302)
        
        resp.set_cookie(
            key="portal_sid",
            value=auth_session.session_id,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=settings.session_max_age_sec,
        )
        
        return resp

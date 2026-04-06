"""Authentication dependencies for FastAPI routes - Server-side session version"""

import time
from typing import Annotated
from fastapi import Cookie, Depends, HTTPException, status

from ..config import settings
from ..models import UserCtx
from .service import auth_session_service, user_repo
from ..store import store as storage


async def get_session_user(
    portal_sid: Annotated[str | None, Cookie()] = None
) -> UserCtx:
    """
    Get current user from portal_sid cookie.
    Validates session and returns user context.
    Raises HTTPException if not authenticated.
    """
    if not portal_sid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - no session cookie",
        )
    
    # Get session from store
    auth_session = await storage.get_auth_session(portal_sid)
    
    if not auth_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or expired",
        )
    
    # Check expiration
    now = int(time.time())
    if auth_session.expires_at < now:
        # Clean up expired session
        await storage.delete_auth_session(portal_sid)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )
    
    # Update last seen
    auth_session.last_seen_at = now
    await storage.save_auth_session(auth_session)
    
    # Get user from repository
    user = await user_repo.get_user_by_emp_no(auth_session.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return user


async def get_optional_user(
    portal_sid: Annotated[str | None, Cookie()] = None
) -> UserCtx | None:
    """
    Get current user from portal_sid cookie if available.
    Returns None if not authenticated (no error).
    """
    if not portal_sid:
        return None
    
    try:
        return await get_session_user(portal_sid)
    except HTTPException:
        return None


async def get_admin_user(
    user: UserCtx = Depends(get_session_user)
) -> UserCtx:
    """
    Require admin role for access.
    Must be used after get_session_user.
    """
    if "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# Type aliases for dependency injection
SessionUser = Annotated[UserCtx, Depends(get_session_user)]
OptionalUser = Annotated[UserCtx | None, Depends(get_optional_user)]
AdminUser = Annotated[UserCtx, Depends(get_admin_user)]


# Legacy compatibility - deprecated
CurrentUser = SessionUser

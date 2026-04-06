"""FastAPI application entry point for AI Portal - V2"""

import uuid
import json
import copy
import hashlib
import logging
from contextlib import asynccontextmanager
from typing import List, Optional, AsyncIterator
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status, Request, Query, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import settings, validate_startup
from .models import (
    Resource, LaunchResponse, Message, SkillInfo, EmbedConfig, IframeConfig,
    ResourceType, LaunchMode, PortalSession, LaunchRecord, SessionBinding,
    PortalMessage, ContextScope, EnrichedPortalSession,
    SessionResumePayload
)
from .auth.deps import SessionUser, OptionalUser, AdminUser
from .auth.routes import router as auth_router
from .catalog.service import catalog_service
from .catalog.sync_service import resource_sync_service
from .acl.service import acl_service
from .adapters.opencode import OpenCodeAdapter
from .adapters.skill_chat import SkillChatAdapter
from .adapters.websdk import WebSDKAdapter
from .adapters.iframe import IframeAdapter
from .adapters.openwork import OpenWorkAdapter
from .adapters.openai_compatible import OpenAICompatibleAdapter
from .store import store as storage
from .logging.middleware import TraceMiddleware

# Logger
logger = logging.getLogger(__name__)

# Adapters instances
opencode_adapter = OpenCodeAdapter()
skill_chat_adapter = SkillChatAdapter()
websdk_adapter = WebSDKAdapter()
iframe_adapter = IframeAdapter()
openwork_adapter = OpenWorkAdapter()
openai_compatible_adapter = OpenAICompatibleAdapter()

# Adapter registry for dispatch
adapter_registry = {
    "opencode": opencode_adapter,
    "skill_chat": skill_chat_adapter,
    "websdk": websdk_adapter,
    "iframe": iframe_adapter,
    "openai_compatible": openai_compatible_adapter,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Validate startup configuration
    validate_startup()
    
    # Startup
    print(f"🚀 {settings.portal_name} starting up...")
    print(f"📦 Loaded {len(catalog_service.get_resources())} resources")
    print(f"🤖 OpenCode: {settings.opencode_base_url}")
    print(f"🛠️  OpenWork: {settings.openwork_base_url}")
    print(f"🔐 Auth: Server-side session (Redis deprecated)")

    yield

    # Shutdown
    print("👋 Shutting down...")
    await opencode_adapter.close()
    await skill_chat_adapter.close()
    await openwork_adapter.close()


# Create FastAPI app
app = FastAPI(
    title=settings.portal_name,
    description="Unified entry point for enterprise AI resources",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trace middleware
app.add_middleware(TraceMiddleware)

# Include auth routes
app.include_router(auth_router)

# Mount static files directory for sdk-host.html
from pathlib import Path
static_dir = Path(__file__).parent.parent.parent / "public"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Request models
class SendMessageRequest(BaseModel):
    """Request to send message"""
    text: str


class StreamMessageChunk(BaseModel):
    """SSE stream chunk for message response - V2 unified format"""
    type: str  # "start" | "delta" | "done" | "error"
    content: Optional[str] = None
    message_id: Optional[str] = None
    finish_reason: Optional[str] = None


class FileUploadResponse(BaseModel):
    """Response for file upload"""
    file_id: str
    file_name: str
    file_type: str
    file_size: int
    url: str


class ContextUpdateRequest(BaseModel):
    """Request to update context scope"""
    payload: dict
    summary: Optional[str] = None


class SyncResult(BaseModel):
    """Resource sync result"""
    success: bool
    count: int
    workspace_id: str


# Helpers

async def _get_session_or_404(portal_session_id: str, user) -> PortalSession:
    """Get session or raise 404"""
    session = await storage.get_session(portal_session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {portal_session_id}"
        )
    if session.user_emp_no != user.emp_no:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session"
        )
    return session


async def _get_active_binding(portal_session_id: str) -> SessionBinding:
    """Get active binding for session"""
    binding = await storage.get_active_binding(portal_session_id)
    if not binding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active binding found for session: {portal_session_id}"
        )
    return binding


def _get_resource_or_404(resource_id: str) -> Resource:
    """Get resource or raise 404."""
    return catalog_service.get_resource_or_raise(resource_id)


def _require_resource_access(resource: Resource, user) -> None:
    """Enforce resource ACL."""
    acl_service.require_resource_access(resource, user)


def _get_adapter_for_resource(resource: Resource) -> str:
    """
    Determine adapter name from resource.
    Priority: resource.adapter > resource.type mapping
    """
    # If adapter is explicitly set, use it
    if resource.adapter:
        return resource.adapter
    
    # Otherwise, map from resource type
    type_adapter_map = {
        ResourceType.DIRECT_CHAT: "opencode",
        ResourceType.SKILL_CHAT: "skill_chat",
        ResourceType.KB_WEBSDK: "websdk",
        ResourceType.AGENT_WEBSDK: "websdk",
        ResourceType.IFRAME: "iframe",
        ResourceType.OPENAI_COMPATIBLE_V1: "openai_compatible",
    }
    
    return type_adapter_map.get(resource.type, "opencode")


async def _save_portal_message(
    portal_session_id: str,
    role: str,
    text: str,
    *,
    message_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    dedupe_key: Optional[str] = None,
    source_message_id: Optional[str] = None,
    source_provider: Optional[str] = None,
    status: str = "done",
) -> PortalMessage:
    """
    Save portal message with deduplication support (V2).
    
    Args:
        message_id: Optional pre-generated message ID (for streaming consistency)
        dedupe_key: Key for deduplication
        source_message_id: Original message ID from upstream
        source_provider: Upstream provider name
        status: Message status (streaming, done, error)
    """
    msg = PortalMessage(
        message_id=message_id or str(uuid.uuid4()),
        portal_session_id=portal_session_id,
        role=role,
        text=text,
        trace_id=trace_id,
        metadata=metadata or {},
        dedupe_key=dedupe_key,
        source_message_id=source_message_id,
        source_provider=source_provider,
        status=status,
    )
    return await storage.upsert_message(msg)


def _update_session_preview(session: PortalSession, text: str) -> None:
    """Update session preview after message"""
    session.last_message_at = datetime.utcnow()
    session.last_message_preview = text[:120] if text else None
    session.updated_at = datetime.utcnow()


def _enrich_session(session: PortalSession) -> dict:
    """Enrich session for API response"""
    snapshot = session.resource_snapshot or {}
    resource_name = snapshot.get("resource_name", session.resource_id)
    launch_mode = snapshot.get("launch_mode")
    adapter = snapshot.get("adapter") or session.metadata.get("adapter")
    return {
        "portal_session_id": session.portal_session_id,
        "resource_id": session.resource_id,
        "resource_type": session.resource_type,
        "resource_name": resource_name,
        "user_emp_no": session.user_emp_no,
        "title": session.title,
        "status": session.status,
        "resource_snapshot": snapshot,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "last_message_at": session.last_message_at.isoformat() if session.last_message_at else None,
        "last_message_preview": session.last_message_preview,
        "parent_session_id": session.parent_session_id,
        "metadata": session.metadata,
        "adapter": adapter,
        "mode": "native" if launch_mode == "native" else "embedded",
    }


def _build_resource_snapshot(resource: Resource) -> dict:
    """Build resource snapshot at launch time"""
    return {
        "resource_id": resource.id,
        "resource_name": resource.name,
        "resource_type": resource.type.value,
        "launch_mode": resource.launch_mode.value,
        "adapter": _get_adapter_for_resource(resource),
        "group": resource.group,
        "description": resource.description,
        "workspace_id": resource.config.workspace_id,
        "skill_name": resource.config.skill_name,
        "starter_prompts": resource.config.starter_prompts,
        "model": resource.config.model,
        "iframe_url": resource.config.iframe_url,
        "script_url": resource.config.script_url,
        "app_key": resource.config.app_key,
        "base_url": resource.config.base_url,
    }


def deep_merge(dst: dict, src: dict) -> dict:
    """Deep merge src into dst (mutates dst)"""
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = copy.deepcopy(v)
    return dst


def _stable_text_hash(text: str) -> str:
    """Stable hash for message dedupe across process restarts."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _get_openai_compatible_history(
    portal_session_id: str,
    resource: Optional[Resource],
    current_text: str,
) -> List[PortalMessage]:
    """Exclude the just-persisted current user turn from local history."""
    history = await storage.list_session_messages(
        portal_session_id,
        limit=resource.config.history_window if resource else 20,
    )
    if history:
        last_message = history[-1]
        if last_message.role == "user" and last_message.text == current_text:
            return history[:-1]
    return history


# Context priority order (lowest to highest)
CONTEXT_PRIORITY = ["global", "user", "user_resource", "session"]


# API Routes

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "portal_name": settings.portal_name,
        "version": "2.0.0"
    }


@app.get("/api/resources", response_model=List[Resource])
async def list_resources(user: SessionUser):
    """List all resources accessible to current user"""
    resources = catalog_service.get_resources()
    accessible_resources = acl_service.filter_accessible_resources(resources, user)
    return accessible_resources


@app.get("/api/resources/grouped")
async def list_resources_grouped(user: SessionUser):
    """List resources grouped by category"""
    resources = catalog_service.get_resources()
    accessible_resources = acl_service.filter_accessible_resources(resources, user)

    groups = {}
    for resource in accessible_resources:
        group = resource.group or "Other"
        if group not in groups:
            groups[group] = []
        groups[group].append(resource)

    return groups


@app.get("/api/resources/{resource_id}", response_model=Resource)
async def get_resource(resource_id: str, user: SessionUser):
    """Get resource details by ID"""
    resource = _get_resource_or_404(resource_id)
    _require_resource_access(resource, user)
    return resource


@app.post("/api/resources/{resource_id}/launch", response_model=LaunchResponse)
async def launch_resource(resource_id: str, user: SessionUser):
    """
    Launch a resource (create session or generate launch token).
    Creates a PortalSession + SessionBinding for all resource types.
    """
    resource = _get_resource_or_404(resource_id)
    _require_resource_access(resource, user)

    portal_session_id = str(uuid.uuid4())
    snapshot = _build_resource_snapshot(resource)
    adapter_name = _get_adapter_for_resource(resource)

    portal_session = PortalSession(
        portal_session_id=portal_session_id,
        resource_id=resource_id,
        resource_type=resource.type.value,
        user_emp_no=user.emp_no,
        title=resource.name,
        resource_snapshot=snapshot,
        metadata={"adapter": adapter_name}
    )

    if resource.launch_mode == LaunchMode.NATIVE:
        user_context = {
            "emp_no": user.emp_no,
            "name": user.name,
            "dept": user.dept,
            "email": user.email
        }
        config = resource.config.model_dump()

        # Create engine session based on adapter type
        if adapter_name == "skill_chat":
            engine_session_id = await skill_chat_adapter.create_session(
                resource_id, user_context, config
            )
            engine_type = "opencode"
            skill_name = resource.config.skill_name or resource_id
        elif adapter_name == "openai_compatible":
            # OpenAI compatible doesn't have engine session - use local ID
            engine_session_id = f"compat:{portal_session_id}"
            engine_type = "openai_compatible"
            skill_name = None
        else:
            # Default opencode
            engine_session_id = await opencode_adapter.create_session(
                resource_id, user_context, config
            )
            engine_type = "opencode"
            skill_name = None

        binding = SessionBinding(
            binding_id=str(uuid.uuid4()),
            portal_session_id=portal_session_id,
            engine_type=engine_type,
            adapter=adapter_name,
            engine_session_id=engine_session_id,
            workspace_id=resource.config.workspace_id or "default",
            skill_name=skill_name,
        )
        await storage.save_binding(binding)
        await storage.save_session(portal_session)

        return LaunchResponse(
            kind=LaunchMode.NATIVE,
            portal_session_id=portal_session.portal_session_id,
            adapter=adapter_name,
            mode="native"
        )

    elif resource.launch_mode == LaunchMode.WEBSDK:
        launch_record = websdk_adapter.create_launch_record(resource, user)
        await storage.save_launch(launch_record)

        binding = SessionBinding(
            binding_id=str(uuid.uuid4()),
            portal_session_id=portal_session_id,
            engine_type="websdk",
            adapter="websdk",
            external_session_ref=launch_record.launch_id,
            workspace_id=resource.config.workspace_id or "default",
        )
        await storage.save_binding(binding)
        await storage.save_session(portal_session)

        return LaunchResponse(
            kind=LaunchMode.WEBSDK,
            portal_session_id=portal_session_id,
            launch_id=launch_record.launch_id,
            adapter="websdk",
            mode="embedded"
        )

    elif resource.launch_mode == LaunchMode.IFRAME:
        launch_record = iframe_adapter.create_launch_record(resource, user)
        await storage.save_launch(launch_record)

        binding = SessionBinding(
            binding_id=str(uuid.uuid4()),
            portal_session_id=portal_session_id,
            engine_type="iframe",
            adapter="iframe",
            external_session_ref=launch_record.launch_id,
            workspace_id=resource.config.workspace_id or "default",
        )
        await storage.save_binding(binding)
        await storage.save_session(portal_session)

        return LaunchResponse(
            kind=LaunchMode.IFRAME,
            portal_session_id=portal_session_id,
            launch_id=launch_record.launch_id,
            adapter="iframe",
            mode="embedded"
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported launch mode: {resource.launch_mode}"
        )


@app.get("/api/sessions")
async def list_sessions(
    user: SessionUser,
    limit: int = Query(50, ge=1, le=100),
    resource_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    status: Optional[str] = Query(None),
):
    """List user's sessions sorted by time with optional filters"""
    sessions = await storage.list_user_sessions(
        user.emp_no, limit=limit, resource_id=resource_id, resource_type=type, status=status
    )
    enriched = [_enrich_session(s) for s in sessions]
    return {"sessions": enriched}


@app.get("/api/sessions/{portal_session_id}")
async def get_session(portal_session_id: str, user: SessionUser):
    """Get session details by ID"""
    session = await _get_session_or_404(portal_session_id, user)
    return _enrich_session(session)


@app.get("/api/sessions/{portal_session_id}/resume")
async def get_session_resume(portal_session_id: str, user: SessionUser) -> SessionResumePayload:
    """
    Get session resume payload for frontend restoration.
    This is the single source of truth for session recovery.
    """
    session = await _get_session_or_404(portal_session_id, user)
    binding = await _get_active_binding(portal_session_id)
    
    # Adapter is the source of truth for dispatch
    adapter = binding.adapter
    
    # Get resource for additional info
    resource = catalog_service.get_resource_or_none(session.resource_id)
    
    if adapter in ("websdk", "iframe"):
        # Embedded mode
        launch_id = binding.external_session_ref
        
        # Verify launch still exists, recreate if needed
        launch = await storage.get_launch(launch_id) if launch_id else None
        if not launch and resource:
            # Recreate launch record
            if adapter == "websdk":
                launch = websdk_adapter.create_launch_record(resource, user)
            else:
                launch = iframe_adapter.create_launch_record(resource, user)
            await storage.save_launch(launch)
            binding.external_session_ref = launch.launch_id
            await storage.save_binding(binding)
            launch_id = launch.launch_id
        
        return SessionResumePayload(
            portal_session_id=portal_session_id,
            resource_id=session.resource_id,
            title=session.title or resource.name if resource else session.resource_id,
            adapter=adapter,
            mode="embedded",
            launch_id=launch_id,
            show_chat_history=False,
            show_workspace=True,
        )
    
    # Native mode (chat)
    return SessionResumePayload(
        portal_session_id=portal_session_id,
        resource_id=session.resource_id,
        title=session.title or resource.name if resource else session.resource_id,
        adapter=adapter,
        mode="native",
        launch_id=None,
        show_chat_history=True,
        show_workspace=False,
    )


@app.get("/api/sessions/{portal_session_id}/messages", response_model=List[Message])
async def get_session_messages(portal_session_id: str, user: SessionUser):
    """
    Get messages for a session.
    Returns PortalMessage records. Falls back to engine and backfills if local store is empty
    (only for opencode/skill_chat adapters).
    """
    session = await _get_session_or_404(portal_session_id, user)
    binding = await _get_active_binding(portal_session_id)

    # Get local messages (sorted by seq)
    portal_messages = await storage.list_session_messages(portal_session_id, limit=500)

    if portal_messages:
        return [
            Message(
                role=msg.role,
                text=msg.text,
                timestamp=msg.created_at
            )
            for msg in portal_messages
        ]

    # Migration / fallback: fetch from engine and backfill
    # Only for adapters that have external engine sessions
    if binding.adapter in ("opencode", "skill_chat") and binding.engine_session_id:
        if binding.adapter == "skill_chat":
            messages = await skill_chat_adapter.get_messages(binding.engine_session_id)
        else:
            messages = await opencode_adapter.get_messages(binding.engine_session_id)

        # Backfill into PortalMessage store with stable dedupe
        for i, msg in enumerate(messages):
            source_message_id = getattr(msg, 'engine_message_id', None)
            dedupe_key = source_message_id or (
                f"backfill:{binding.adapter}:{binding.engine_session_id}:{msg.role}:{i}:{_stable_text_hash(msg.text)}"
            )
            await _save_portal_message(
                portal_session_id=portal_session_id,
                role=msg.role,
                text=msg.text,
                dedupe_key=dedupe_key,
                source_provider=binding.adapter,
                source_message_id=source_message_id,
            )

        return messages
    
    # For openai_compatible and others, just return empty
    return []


@app.post("/api/sessions/{portal_session_id}/messages")
async def send_session_message(
    portal_session_id: str,
    body: SendMessageRequest,
    request: Request,
    user: SessionUser
):
    """
    Send a message to a session (non-streaming).
    Persists user message, calls adapter, persists assistant message.
    """
    import traceback

    try:
        session = await _get_session_or_404(portal_session_id, user)
        binding = await _get_active_binding(portal_session_id)

        trace_context = getattr(request.state, "trace_context", None)
        trace_id = getattr(trace_context, "trace_id", None)

        # Persist user message
        await _save_portal_message(
            portal_session_id=portal_session_id,
            role="user",
            text=body.text,
            trace_id=trace_id,
            source_provider=binding.adapter,
        )

        # Get context
        context_data = await _resolve_session_context(portal_session_id, user)
        context = context_data.get("merged", {})

        # Dispatch to adapter
        adapter_name = binding.adapter
        
        if adapter_name == "skill_chat":
            response = await skill_chat_adapter.send_message(
                binding.engine_session_id,
                body.text,
                trace_id,
                skill_name=binding.skill_name,
            )
        elif adapter_name == "openai_compatible":
            # Get history for context
            resource = catalog_service.get_resource_by_id(session.resource_id)
            history = await _get_openai_compatible_history(portal_session_id, resource, body.text)
            response = await openai_compatible_adapter.send_message(
                resource=resource,
                history=history,
                text=body.text,
                context=context,
            )
        else:
            # Default opencode
            response = await opencode_adapter.send_message(
                binding.engine_session_id,
                body.text,
                trace_id,
            )

        # Persist assistant message
        assistant_msg = await _save_portal_message(
            portal_session_id=portal_session_id,
            role="assistant",
            text=response,
            trace_id=trace_id,
            source_provider=binding.adapter,
        )

        _update_session_preview(session, response)
        await storage.save_session(session)

        return {
            "response": response,
            "message_id": assistant_msg.message_id
        }

    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(f"ERROR in send_session_message: {error_detail}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )


async def _resolve_session_context(portal_session_id: str, user) -> dict:
    """Resolve merged context for session with proper priority"""
    session = await storage.get_session(portal_session_id)
    if not session:
        return {"merged": {}}
    
    user_key = user.emp_no
    user_resource_key = f"{user.emp_no}:{session.resource_id}"
    session_key = portal_session_id
    
    # Fetch contexts in priority order
    scopes = {
        "global": await storage.get_latest_context("global", "global"),
        "user": await storage.get_latest_context("user", user_key),
        "user_resource": await storage.get_latest_context("user_resource", user_resource_key),
        "session": await storage.get_latest_context("session", session_key),
    }
    
    # Merge in priority order (lower priority first, higher overwrites)
    merged = {}
    for scope_type in CONTEXT_PRIORITY:
        ctx = scopes[scope_type]
        if ctx:
            deep_merge(merged, ctx.payload or {})
    
    return {
        "portal_session_id": portal_session_id,
        "scopes": {k: (v.payload if v else {}) for k, v in scopes.items()},
        "merged": merged,
        "priority": CONTEXT_PRIORITY,
    }


async def stream_message_response(
    portal_session_id: str,
    body: SendMessageRequest,
    request: Request,
    user: SessionUser
):
    """
    Generator for SSE streaming response with Portal message persistence (V2).
    Uses unified event format: start, delta, done, error.
    """
    accumulated = ""
    assistant_message_id = ""
    
    try:
        session = await _get_session_or_404(portal_session_id, user)
        binding = await _get_active_binding(portal_session_id)

        trace_context = getattr(request.state, "trace_context", None)
        trace_id = getattr(trace_context, "trace_id", None)

        # Persist user message
        await _save_portal_message(
            portal_session_id=portal_session_id,
            role="user",
            text=body.text,
            trace_id=trace_id,
            source_provider=binding.adapter,
        )

        # Pre-generate assistant message ID for consistency
        assistant_message_id = str(uuid.uuid4())
        
        # Create placeholder message with streaming status
        await _save_portal_message(
            portal_session_id=portal_session_id,
            role="assistant",
            text="",
            message_id=assistant_message_id,
            trace_id=trace_id,
            source_provider=binding.adapter,
            status="streaming",
        )

        # Send start event
        yield f"data: {json.dumps({'type': 'start', 'message_id': assistant_message_id})}\n\n"

        # Get context
        context_data = await _resolve_session_context(portal_session_id, user)
        context = context_data.get("merged", {})

        # Get adapter
        adapter_name = binding.adapter
        adapter = adapter_registry.get(adapter_name)
        
        if not adapter:
            raise ValueError(f"Unknown adapter: {adapter_name}")

        # Stream based on adapter type
        if adapter_name == "skill_chat":
            stream_iter = skill_chat_adapter.send_message_stream(
                binding.engine_session_id,
                body.text,
                trace_id,
                skill_name=binding.skill_name,
            )
        elif adapter_name == "openai_compatible":
            resource = catalog_service.get_resource_by_id(session.resource_id)
            history = await _get_openai_compatible_history(portal_session_id, resource, body.text)
            stream_iter = openai_compatible_adapter.send_message_stream(
                resource=resource,
                history=history,
                text=body.text,
                context=context,
            )
        else:
            # Default opencode
            stream_iter = opencode_adapter.send_message_stream(
                binding.engine_session_id,
                body.text,
                trace_id,
            )

        # Stream chunks
        async for chunk in stream_iter:
            accumulated += chunk
            yield f"data: {json.dumps({'type': 'delta', 'content': chunk, 'message_id': assistant_message_id})}\n\n"

        # Update message to done status with full text
        await storage.update_message_status(
            assistant_message_id,
            status="done",
            text=accumulated,
        )

        _update_session_preview(session, accumulated)
        await storage.save_session(session)

        # Send single done event
        yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_message_id, 'finish_reason': 'stop'})}\n\n"

    except Exception as e:
        error_detail = f"{type(e).__name__}: {str(e)}"
        print(f"ERROR in stream_message_response: {error_detail}")

        # Update message to error status if we started streaming
        if assistant_message_id:
            await storage.update_message_status(
                assistant_message_id,
                status="error",
                text=accumulated,
                metadata={"error": str(e)}
            )
        
        # Send error event
        yield f"data: {json.dumps({'type': 'error', 'content': str(e), 'message_id': assistant_message_id or None})}\n\n"


@app.post("/api/sessions/{portal_session_id}/messages/stream")
async def send_session_message_stream(
    portal_session_id: str,
    body: SendMessageRequest,
    request: Request,
    user: SessionUser
):
    """Send a message to a session with SSE streaming response"""
    return StreamingResponse(
        stream_message_response(portal_session_id, body, request, user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/api/sessions/{portal_session_id}/archive")
async def archive_session(portal_session_id: str, user: SessionUser):
    """Archive a session"""
    session = await _get_session_or_404(portal_session_id, user)
    session.status = "archived"
    session.updated_at = datetime.utcnow()
    await storage.save_session(session)
    return {"success": True, "status": "archived"}


@app.post("/api/sessions/{portal_session_id}/upload", response_model=FileUploadResponse)
async def upload_file_to_session(
    portal_session_id: str,
    user: SessionUser,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
):
    """Upload a file to a session"""
    try:
        session = await _get_session_or_404(portal_session_id, user)
        binding = await _get_active_binding(portal_session_id)

        adapter_name = binding.adapter

        if adapter_name == "skill_chat":
            result = await skill_chat_adapter.upload_file(
                binding.engine_session_id,
                file,
                description
            )
        elif adapter_name == "openai_compatible":
            # OpenAI compatible may not support file upload
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File upload not supported for this resource type"
            )
        else:
            # Default opencode
            result = await opencode_adapter.upload_file(
                binding.engine_session_id,
                file,
                description
            )

        return FileUploadResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


@app.get("/api/sessions/{portal_session_id}/context")
async def get_session_context(portal_session_id: str, user: SessionUser):
    """
    Get resolved context for a session by merging applicable scopes.
    Priority: global < user < user_resource < session
    """
    return await _resolve_session_context(portal_session_id, user)


@app.get("/api/launches/{launch_id}/embed-config", response_model=EmbedConfig)
async def get_embed_config(launch_id: str, user: SessionUser):
    """Get WebSDK embed configuration for a launch"""
    launch = await storage.get_launch(launch_id)
    if not launch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Launch not found: {launch_id}"
        )

    if launch.user_emp_no != user.emp_no:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this launch"
        )

    resource = catalog_service.get_resource_by_id(launch.resource_id)
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource not found: {launch.resource_id}"
        )

    if resource.launch_mode != LaunchMode.WEBSDK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Resource '{resource.name}' is not a WebSDK resource"
        )

    embed_config = websdk_adapter.get_embed_config(launch, resource)
    return embed_config


@app.get("/api/launches/{launch_id}/iframe-config", response_model=IframeConfig)
async def get_iframe_config(launch_id: str, user: SessionUser):
    """Get iframe embed configuration for a launch"""
    launch = await storage.get_launch(launch_id)
    if not launch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Launch not found: {launch_id}"
        )

    if launch.user_emp_no != user.emp_no:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this launch"
        )

    resource = catalog_service.get_resource_by_id(launch.resource_id)
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource not found: {launch.resource_id}"
        )

    if resource.launch_mode != LaunchMode.IFRAME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Resource '{resource.name}' is not an iframe resource"
        )

    iframe_config = iframe_adapter.get_iframe_config(launch, resource)
    return iframe_config


@app.get("/api/skills", response_model=List[SkillInfo])
async def list_skills(user: SessionUser):
    """List all skills with installation status"""
    skill_resources = catalog_service.get_skill_resources()

    skills = []
    for resource in skill_resources:
        if not acl_service.check_resource_access(resource, user):
            continue

        skill_name = resource.config.skill_name
        skill_status = await openwork_adapter.get_skill_status(
            skill_name,
            resource.config.workspace_id or "default"
        )

        skills.append(SkillInfo(
            id=resource.id,
            name=resource.name,
            description=resource.description,
            installed=skill_status.get("installed", False),
            skill_name=skill_name,
            starter_prompts=resource.config.starter_prompts
        ))

    return skills


@app.get("/api/launches")
async def list_launches(user: SessionUser, limit: int = Query(50, ge=1, le=100)):
    """List user's WebSDK launches"""
    launches = await storage.list_user_launches(user.emp_no, limit)
    return {"launches": [l.model_dump() for l in launches]}


@app.patch("/api/contexts/user-resource/{resource_id}")
async def update_user_resource_context(
    resource_id: str,
    body: ContextUpdateRequest,
    user: SessionUser
):
    """
    Update user-resource level context scope.
    Validates resource existence and ACL before update.
    """
    # Validate resource exists
    resource = _get_resource_or_404(resource_id)
    _require_resource_access(resource, user)
    
    scope_key = f"{user.emp_no}:{resource_id}"
    
    # Get or create context
    existing = await storage.get_latest_context("user_resource", scope_key)
    
    if existing:
        existing.payload = body.payload
        existing.summary = body.summary
        existing.updated_at = datetime.utcnow()
        existing.updated_by = user.emp_no
        existing.version = existing.version + 1
        await storage.save_context(existing)
        context_id = existing.context_id
    else:
        new_context = ContextScope(
            context_id=str(uuid.uuid4()),
            scope_type="user_resource",
            scope_key=scope_key,
            payload=body.payload,
            summary=body.summary,
            updated_by=user.emp_no,
            version=1,
        )
        await storage.save_context(new_context)
        context_id = new_context.context_id
    
    return {"success": True, "context_id": context_id}


@app.post("/api/admin/resources/sync", response_model=SyncResult)
async def admin_sync_resources(
    workspace_id: str = Query("default"),
    user: AdminUser = None,
):
    """
    Trigger resource sync from OpenWork.
    Requires admin role.
    """
    try:
        merged = await resource_sync_service.sync(workspace_id=workspace_id, operator=user.emp_no)
        logger.info(f"Admin {user.emp_no} triggered resource sync for workspace {workspace_id}")
        
        return SyncResult(
            success=True,
            count=len(merged),
            workspace_id=workspace_id
        )
    except Exception as e:
        logger.error(f"Resource sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


# Serve sdk-host.html explicitly
@app.get("/sdk-host.html")
async def serve_sdk_host():
    """Serve the WebSDK host page"""
    import os
    sdk_host_path = os.path.join(os.path.dirname(__file__), "../../public/sdk-host.html")
    if os.path.exists(sdk_host_path):
        return FileResponse(
            sdk_host_path,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"}
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="sdk-host.html not found"
    )


# Serve frontend (for development/prod)
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str, user: OptionalUser = None):
    """
    Serve frontend application.
    Returns SPA shell - authentication is handled by API routes.
    """
    import os

    # V2: Don't redirect to mock login - let frontend handle auth state
    # API routes will return 401 if not authenticated

    frontend_path = os.path.join(os.path.dirname(__file__), "../../frontend/dist")
    if os.path.exists(frontend_path):
        file_path = os.path.join(frontend_path, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        index_path = os.path.join(frontend_path, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)

    # Fallback API response
    return {
        "message": f"{settings.portal_name} API",
        "docs": "/docs",
        "user": user.model_dump() if user else None,
        "authenticated": user is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload
    )

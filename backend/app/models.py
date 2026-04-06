"""Core Pydantic models for AI Portal"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class ResourceType(str, Enum):
    """Resource types in the portal"""
    DIRECT_CHAT = "direct_chat"
    SKILL_CHAT = "skill_chat"
    KB_WEBSDK = "kb_websdk"
    AGENT_WEBSDK = "agent_websdk"
    IFRAME = "iframe"
    OPENAI_COMPATIBLE_V1 = "openai_compatible_v1"


class LaunchMode(str, Enum):
    """Resource launch modes"""
    NATIVE = "native"  # Native chat interface
    WEBSDK = "websdk"  # WebSDK iframe embed
    IFRAME = "iframe"  # Direct iframe embed


class UserCtx(BaseModel):
    """User context from SSO"""
    emp_no: str = Field(..., description="Employee number")
    name: str = Field(..., description="User display name")
    dept: str = Field(default="demo", description="Department")
    roles: List[str] = Field(default_factory=lambda: ["employee"], description="User roles")
    email: Optional[str] = Field(None, description="Email address")


class ResourceConfig(BaseModel):
    """Base configuration for resources"""
    workspace_id: Optional[str] = None
    model: Optional[str] = None
    script_url: Optional[str] = None
    app_key: Optional[str] = None
    base_url: Optional[str] = None
    skill_name: Optional[str] = None
    starter_prompts: Optional[List[str]] = None
    iframe_url: Optional[str] = None  # Direct iframe URL for iframe mode

    # OpenAI Compatible v1 config
    request_path: str = "/chat/completions"
    api_key_env: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    default_params: Dict[str, Any] = Field(default_factory=dict)
    history_window: int = 20
    stream_supported: bool = True
    timeout_sec: int = 120


class ResourceSyncMeta(BaseModel):
    """Metadata about how a resource was discovered and synchronized"""
    origin: str = Field(..., description="Source of resource: static, openwork, manual")
    origin_key: str = Field(..., description="Unique key in origin system, e.g. default:coding")
    workspace_id: Optional[str] = Field(None, description="Workspace ID for openwork origin")
    version: Optional[str] = Field(None, description="Skill version if available")
    sync_status: str = Field(default="active", description="active, missing, stale")
    last_seen_at: Optional[datetime] = Field(None, description="Last sync timestamp")


class Resource(BaseModel):
    """Resource catalog item"""
    id: str = Field(..., description="Unique resource identifier")
    name: str = Field(..., description="Resource display name")
    type: ResourceType = Field(..., description="Resource type")
    launch_mode: LaunchMode = Field(..., description="Launch mode")
    adapter: Optional[str] = Field(None, description="Adapter name for dispatch")
    group: str = Field(..., description="Resource group for UI")
    description: str = Field(..., description="Resource description")
    enabled: bool = Field(default=True, description="Whether resource is enabled")
    tags: List[str] = Field(default_factory=list, description="Resource tags")
    config: ResourceConfig = Field(default_factory=ResourceConfig, description="Resource configuration")
    acl: Optional[Dict[str, Any]] = Field(default=None, description="Access control rules")
    sync_meta: Optional[ResourceSyncMeta] = Field(default=None, description="Synchronization metadata")


class PortalSession(BaseModel):
    """Portal session for native/skill chat and embedded resources"""
    portal_session_id: str = Field(..., description="Portal session UUID")
    resource_id: str = Field(..., description="Resource that created this session")
    resource_type: str = Field(default="", description="Resource type at creation time")
    user_emp_no: str = Field(..., description="User employee number")
    title: Optional[str] = Field(None, description="Session title")
    status: str = Field(default="active", description="Session status: active, archived")
    resource_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Frozen resource config at launch")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    last_message_at: Optional[datetime] = Field(None, description="Last message timestamp")
    last_message_preview: Optional[str] = Field(None, description="Preview of last message")
    parent_session_id: Optional[str] = Field(None, description="Parent session for forked sessions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional session metadata")


class SessionBinding(BaseModel):
    """Binding between a PortalSession and an underlying engine"""
    binding_id: str = Field(..., description="Binding UUID")
    portal_session_id: str = Field(..., description="Portal session UUID")
    engine_type: str = Field(..., description="Engine type: opencode, websdk, iframe, openai_compatible")
    adapter: str = Field(default="opencode", description="Adapter name for dispatch")
    engine_session_id: Optional[str] = Field(None, description="Engine session ID for opencode")
    external_session_ref: Optional[str] = Field(None, description="External reference: launch_id for websdk/iframe")
    workspace_id: Optional[str] = Field(None, description="Workspace ID for skill sessions")
    skill_name: Optional[str] = Field(None, description="Skill name for skill chat sessions")
    binding_status: str = Field(default="active", description="Binding status: active, closed, stale")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Binding creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")


class PortalMessage(BaseModel):
    """Canonical message persisted in Portal"""
    message_id: str = Field(..., description="Message UUID")
    portal_session_id: str = Field(..., description="Portal session UUID")
    role: str = Field(..., description="Message role: user, assistant, system")
    text: str = Field(..., description="Message content")
    engine_message_id: Optional[str] = Field(None, description="Upstream message ID if available")
    trace_id: Optional[str] = Field(None, description="Trace ID for the request")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Message creation time")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional message metadata")
    
    # New fields for V2
    status: str = Field(default="done", description="Message status: streaming, done, error")
    dedupe_key: Optional[str] = Field(None, description="Deduplication key")
    source_provider: Optional[str] = Field(None, description="Source provider: opencode, openai_compatible, backfill")
    source_message_id: Optional[str] = Field(None, description="Source message ID for deduplication")
    seq: int = Field(default=0, description="Sequence number for ordering")


class ContextScope(BaseModel):
    """Context scope for global, user, user_resource, or session level"""
    context_id: str = Field(..., description="Context UUID")
    scope_type: str = Field(..., description="Scope type: global, user, user_resource, session")
    scope_key: str = Field(..., description="Scope identifier: emp_no or emp_no:resource_id")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Context payload")
    summary: Optional[str] = Field(None, description="Text summary of context")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    updated_by: Optional[str] = Field(None, description="User who last updated")
    version: int = Field(default=1, description="Context version")


class LaunchRecord(BaseModel):
    """Launch record for WebSDK applications"""
    launch_id: str = Field(..., description="Launch record UUID")
    resource_id: str = Field(..., description="Resource that was launched")
    user_emp_no: str = Field(..., description="User employee number")
    launched_at: datetime = Field(default_factory=datetime.utcnow, description="Launch time")
    launch_token: str = Field(..., description="Launch token for WebSDK")
    user_context: Dict[str, Any] = Field(default_factory=dict, description="User context for WebSDK")


class Message(BaseModel):
    """Chat message"""
    role: str = Field(..., description="Message role: user/assistant/system")
    text: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")


class LaunchResponse(BaseModel):
    """Response from resource launch"""
    kind: LaunchMode = Field(..., description="Launch mode: native or websdk")
    portal_session_id: Optional[str] = Field(None, description="Portal session ID for native mode")
    launch_id: Optional[str] = Field(None, description="Launch ID for websdk mode")
    adapter: Optional[str] = Field(None, description="Adapter used")
    mode: Optional[str] = Field(None, description="Mode: native or embedded")


class MessageCreateResponse(BaseModel):
    """Response after sending a message"""
    response: str = Field(..., description="Assistant response text")
    message_id: Optional[str] = Field(None, description="Persisted assistant message ID")


class EnrichedPortalSession(BaseModel):
    """PortalSession with derived display fields for frontend"""
    portal_session_id: str
    resource_id: str
    resource_type: str
    resource_name: str = Field(default="", description="Resource name from snapshot")
    user_emp_no: str
    title: Optional[str] = None
    status: str = "active"
    resource_snapshot: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    parent_session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SkillInfo(BaseModel):
    """Skill information for skill store"""
    id: str = Field(..., description="Skill resource ID")
    name: str = Field(..., description="Skill name")
    description: str = Field(..., description="Skill description")
    installed: bool = Field(default=False, description="Whether skill is installed")
    skill_name: Optional[str] = Field(None, description="OpenCode skill name")
    starter_prompts: Optional[List[str]] = Field(None, description="Starter prompts")


class EmbedConfig(BaseModel):
    """WebSDK embed configuration"""
    script_url: str = Field(..., description="WebSDK script URL")
    app_key: str = Field(..., description="WebSDK app key")
    base_url: str = Field(..., description="WebSDK base URL")
    launch_token: str = Field(..., description="Launch token")
    user_context: Dict[str, Any] = Field(..., description="User context")


class IframeConfig(BaseModel):
    """Iframe embed configuration"""
    iframe_url: str = Field(..., description="Iframe URL to embed")
    user_context: Dict[str, Any] = Field(..., description="User context")


# V2 Models

class AuthSession(BaseModel):
    """Local authentication session after SSO exchange"""
    session_id: str = Field(..., description="Portal session ID (portal_sid cookie)")
    user_id: str = Field(..., description="User ID")
    user_name: str = Field(..., description="User login name from SSO")
    roles: List[str] = Field(default_factory=list, description="User roles")
    expires_at: int = Field(..., description="Session expiration timestamp (seconds)")
    created_at: int = Field(..., description="Session creation timestamp (seconds)")
    last_seen_at: int = Field(..., description="Last activity timestamp (seconds)")
    sso_access_token: Optional[str] = Field(None, description="SSO access token (optional)")
    id_token_claims: Dict[str, Any] = Field(default_factory=dict, description="ID token claims")


class SessionResumePayload(BaseModel):
    """Payload for session resume endpoint"""
    portal_session_id: str = Field(..., description="Portal session ID")
    resource_id: str = Field(..., description="Resource ID")
    title: str = Field(..., description="Session title")
    adapter: str = Field(..., description="Adapter name")
    mode: str = Field(..., description="Mode: native or embedded")
    launch_id: Optional[str] = Field(None, description="Launch ID for embedded mode")
    show_chat_history: bool = Field(default=False, description="Whether to show chat history")
    show_workspace: bool = Field(default=False, description="Whether to show workspace")


class OAuthState(BaseModel):
    """OAuth state for SSO flow"""
    state: str = Field(..., description="State parameter")
    next_url: str = Field(default="/", description="Redirect after login")
    code_verifier: Optional[str] = Field(None, description="PKCE code verifier")
    expires_at: int = Field(..., description="Expiration timestamp (seconds)")

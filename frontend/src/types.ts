/** Type definitions for AI Portal V2 */

export type ResourceType =
  | 'direct_chat'
  | 'skill_chat'
  | 'kb_websdk'
  | 'agent_websdk'
  | 'iframe'
  | 'openai_compatible_v1';

export type LaunchMode = 'native' | 'websdk' | 'iframe';

export type AdapterType =
  | 'opencode'
  | 'skill_chat'
  | 'websdk'
  | 'iframe'
  | 'openai_compatible';

export type MessageStatus = 'streaming' | 'done' | 'error';

export interface UserCtx {
  emp_no: string;
  name: string;
  dept: string;
  roles: string[];
  email?: string;
}

export interface ResourceConfig {
  workspace_id?: string;
  model?: string;
  script_url?: string;
  app_key?: string;
  base_url?: string;
  skill_name?: string;
  starter_prompts?: string[];
  iframe_url?: string;
  // OpenAI Compatible v1 config
  request_path?: string;
  api_key_env?: string;
  headers?: Record<string, string>;
  default_params?: Record<string, any>;
  history_window?: number;
  stream_supported?: boolean;
  timeout_sec?: number;
  [key: string]: any;
}

export interface ResourceSyncMeta {
  origin: string;
  origin_key: string;
  workspace_id?: string;
  version?: string;
  sync_status?: string;
  last_seen_at?: string;
}

export interface Resource {
  id: string;
  name: string;
  type: ResourceType;
  launch_mode: LaunchMode;
  adapter?: AdapterType;
  group: string;
  description: string;
  enabled: boolean;
  tags: string[];
  config: ResourceConfig;
  acl?: any;
  sync_meta?: ResourceSyncMeta;
}

export interface PortalSession {
  portal_session_id: string;
  resource_id: string;
  resource_type: string;
  resource_name?: string;
  user_emp_no: string;
  title?: string;
  status?: string;
  resource_snapshot?: Record<string, any>;
  created_at: string;
  updated_at: string;
  last_message_at?: string;
  last_message_preview?: string;
  parent_session_id?: string;
  metadata?: Record<string, any>;
  adapter?: AdapterType;
  mode?: 'native' | 'embedded';
}

export interface SessionBinding {
  binding_id: string;
  portal_session_id: string;
  engine_type: string;
  adapter: AdapterType;
  engine_session_id?: string;
  external_session_ref?: string;
  workspace_id?: string;
  skill_name?: string;
  binding_status: string;
  created_at: string;
  updated_at: string;
}

export interface PortalMessage {
  message_id: string;
  portal_session_id: string;
  role: 'user' | 'assistant' | 'system';
  text: string;
  engine_message_id?: string;
  trace_id?: string;
  created_at: string;
  metadata?: Record<string, any>;
  // V2 fields
  status?: MessageStatus;
  dedupe_key?: string;
  source_provider?: string;
  source_message_id?: string;
  seq?: number;
}

export interface ContextScope {
  context_id: string;
  scope_type: string;
  scope_key: string;
  payload: Record<string, any>;
  summary?: string;
  updated_at: string;
  updated_by?: string;
  version?: number;
}

export interface LaunchRecord {
  launch_id: string;
  resource_id: string;
  user_emp_no: string;
  launched_at: string;
  launch_token: string;
  user_context: any;
}

export interface Message {
  role: 'user' | 'assistant' | 'system';
  text: string;
  timestamp?: string;
}

// V2 Unified Stream Event Format
export type StreamEvent =
  | { type: 'start'; message_id: string }
  | { type: 'delta'; message_id: string; content: string }
  | { type: 'done'; message_id: string; finish_reason?: string }
  | { type: 'error'; message_id?: string; content: string };

// Legacy StreamChunk for backward compatibility during migration
export interface StreamChunk {
  type: 'start' | 'chunk' | 'delta' | 'done' | 'error';
  content?: string;
  message_id?: string;
  finish_reason?: string;
}

export interface PendingFile {
  file: File;
  id: string;
  previewUrl?: string;
  status: 'pending' | 'uploading' | 'uploaded' | 'error';
}

export interface LaunchResponse {
  kind: LaunchMode;
  portal_session_id?: string;
  launch_id?: string;
  adapter?: AdapterType;
  mode?: 'native' | 'embedded';
}

export interface SkillInfo {
  id: string;
  name: string;
  description: string;
  installed: boolean;
  skill_name?: string;
  starter_prompts?: string[];
}

export interface EmbedConfig {
  script_url: string;
  app_key: string;
  base_url: string;
  launch_token: string;
  user_context: any;
}

export interface IframeConfig {
  iframe_url: string;
  user_context: any;
}

// V2 Session Resume
export interface SessionResumePayload {
  portal_session_id: string;
  resource_id: string;
  title: string;
  adapter: AdapterType;
  mode: 'native' | 'embedded';
  launch_id?: string | null;
  show_chat_history: boolean;
  show_workspace: boolean;
}

// V2 Stream Handlers
export interface StreamHandlers {
  onStart?: (messageId: string) => void;
  onDelta: (delta: string, messageId: string) => void;
  onDone?: (messageId: string) => void;
  onError?: (error: string, messageId?: string) => void;
}

// Session Summary for sidebar
export interface SessionSummary {
  portal_session_id: string;
  title: string;
  resource_id: string;
  adapter: AdapterType;
  mode: 'native' | 'embedded';
  updated_at: number;
}

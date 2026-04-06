/** API client for AI Portal backend - V2 */

import axios from 'axios';
import type {
  Resource,
  PortalSession,
  LaunchRecord,
  Message,
  LaunchResponse,
  SkillInfo,
  EmbedConfig,
  IframeConfig,
  StreamEvent,
  SessionResumePayload,
  StreamHandlers,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/';

const buildApiUrl = (path: string): string => {
  const normalizedBase = API_BASE_URL.endsWith('/') ? API_BASE_URL : `${API_BASE_URL}/`;
  return new URL(path.replace(/^\//, ''), normalizedBase).toString();
};

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // Send cookies (portal_sid)
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

// Auth APIs - V2 (SSO + Local Session)
export const authApi = {
  /** Get SSO login URL */
  getLoginUrl: (next: string = '/') =>
    api.get<{ login_url: string }>(`/api/auth/login-url?next=${encodeURIComponent(next)}`),

  /** Exchange OAuth2 code for local session */
  exchangeCode: (code: string, state?: string | null) =>
    api.post<{ user: any; next: string }>('/api/auth/exchange', { code, state }),

  /** Get current user info (validates portal_sid cookie) */
  getMe: () => api.get<{ emp_no: string; name: string; dept: string; roles: string[]; email?: string }>('/api/auth/me'),

  /** Logout - clears portal_sid cookie and server session */
  logout: () => api.post<{ success: boolean }>('/api/auth/logout'),

  /** Redirect to SSO login */
  redirectToSSO: (next: string = '/') => {
    authApi.getLoginUrl(next).then((res) => {
      window.location.href = res.data.login_url;
    }).catch((err) => {
      console.error('Failed to get login URL:', err);
    });
  },
};

// Resource APIs
export const resourceApi = {
  listResources: () => api.get<Resource[]>('/api/resources'),

  listResourcesGrouped: () =>
    api.get<Record<string, Resource[]>>('/api/resources/grouped'),

  getResource: (id: string) => api.get<Resource>(`/api/resources/${id}`),

  launchResource: (id: string) =>
    api.post<LaunchResponse>(`/api/resources/${id}/launch`),

  syncResources: (workspaceId = 'default') =>
    api.post<{ success: boolean; count: number; workspace_id: string }>(
      `/api/admin/resources/sync?workspace_id=${workspaceId}`
    ),
};

// Session APIs
export const sessionApi = {
  listSessions: (params?: {
    limit?: number;
    resource_id?: string;
    type?: string;
    status?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.limit) search.append('limit', String(params.limit));
    if (params?.resource_id) search.append('resource_id', params.resource_id);
    if (params?.type) search.append('type', params.type);
    if (params?.status) search.append('status', params.status);
    const query = search.toString();
    return api.get<{ sessions: PortalSession[] }>(`/api/sessions${query ? '?' + query : ''}`);
  },

  getSession: (sessionId: string) =>
    api.get<PortalSession>(`/api/sessions/${sessionId}`),

  /** V2: Get session resume payload for restoration */
  getSessionResume: (sessionId: string) =>
    api.get<SessionResumePayload>(`/api/sessions/${sessionId}/resume`),

  getMessages: (sessionId: string) =>
    api.get<Message[]>(`/api/sessions/${sessionId}/messages`),

  sendMessage: (sessionId: string, text: string) =>
    api.post<{ response: string; message_id?: string }>(`/api/sessions/${sessionId}/messages`, { text }),

  archiveSession: (sessionId: string) =>
    api.post<{ success: boolean; status: string }>(`/api/sessions/${sessionId}/archive`),

  getSessionContext: (sessionId: string) =>
    api.get<{
      portal_session_id: string;
      scopes: Record<string, Record<string, any>>;
      merged: Record<string, any>;
      priority: string[];
    }>(`/api/sessions/${sessionId}/context`),

  /**
   * V2: Send message with streaming response using SSE.
   * Uses unified event format: start, delta, done, error.
   * Calls handlers.onDone exactly once.
   */
  sendMessageStream: (
    sessionId: string,
    text: string,
    handlers: StreamHandlers
  ): AbortController => {
    const controller = new AbortController();
    const { signal } = controller;

    const url = buildApiUrl(`/api/sessions/${sessionId}/messages/stream`);

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      credentials: 'include',
      body: JSON.stringify({ text }),
      signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('Response body is null');
        }

        const decoder = new TextDecoder();
        let buffer = '';
        let currentMessageId = '';
        let doneSeen = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmedLine = line.trim();
            if (!trimmedLine) continue;

            if (trimmedLine.startsWith('data: ')) {
              const dataStr = trimmedLine.slice(6);

              if (dataStr === '[DONE]') {
                // Legacy format - ignore, wait for proper done event
                continue;
              }

              try {
                const data: StreamEvent = JSON.parse(dataStr);

                if (data.type === 'start') {
                  currentMessageId = data.message_id;
                  handlers.onStart?.(currentMessageId);
                } else if (data.type === 'delta') {
                  handlers.onDelta(data.content ?? '', data.message_id || currentMessageId);
                } else if (data.type === 'done') {
                  if (!doneSeen) {
                    doneSeen = true;
                    handlers.onDone?.(data.message_id || currentMessageId);
                  }
                } else if (data.type === 'error') {
                  handlers.onError?.(data.content || 'Unknown error', data.message_id);
                  return;
                }
              } catch (e) {
                // If not valid JSON, ignore (old format compatibility)
                console.warn('Failed to parse SSE event:', dataStr);
              }
            }
          }
        }

        // Process remaining buffer
        if (buffer.trim()) {
          const trimmedBuffer = buffer.trim();
          if (trimmedBuffer.startsWith('data: ')) {
            const dataStr = trimmedBuffer.slice(6);
            try {
              const data: StreamEvent = JSON.parse(dataStr);
              if (data.type === 'done') {
                if (!doneSeen) {
                  doneSeen = true;
                  handlers.onDone?.(data.message_id || currentMessageId);
                }
              } else if (data.type === 'error') {
                handlers.onError?.(data.content || 'Unknown error', data.message_id);
                return;
              }
            } catch (e) {
              // Ignore parse errors at end
            }
          }
        }

        if (!doneSeen) {
          handlers.onError?.('stream closed without done', currentMessageId);
        }
      })
      .catch((error) => {
        if (error.name === 'AbortError') {
          console.log('Request aborted');
          return;
        }
        console.error('Fetch error:', error);
        handlers.onError?.(error.message || 'Failed to send message');
      });

    return controller;
  },
};

// Launch APIs
export const launchApi = {
  getEmbedConfig: (launchId: string) =>
    api.get<EmbedConfig>(`/api/launches/${launchId}/embed-config`),

  getIframeConfig: (launchId: string) =>
    api.get<IframeConfig>(`/api/launches/${launchId}/iframe-config`),

  listLaunches: (limit = 50) =>
    api.get<{ launches: LaunchRecord[] }>(`/api/launches?limit=${limit}`),
};

// Context APIs
export const contextApi = {
  updateUserResourceContext: (resourceId: string, payload: Record<string, any>, summary?: string) =>
    api.patch<{ success: boolean; context_id: string }>(
      `/api/contexts/user-resource/${resourceId}`,
      { payload, summary }
    ),
};

// Skill APIs
export const skillApi = {
  listSkills: () => api.get<SkillInfo[]>('/api/skills'),
};

export default api;

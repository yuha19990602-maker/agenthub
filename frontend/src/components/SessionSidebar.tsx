/** Session sidebar component */

import { useEffect, useState } from 'react';
import { MessageSquare, Clock } from 'lucide-react';
import { sessionApi } from '../api';
import type { PortalSession } from '../types';

interface SessionSidebarProps {
  currentSessionId?: string;
  onSelectSession: (session: PortalSession) => void;
  onNewChat: () => void;
}

export function SessionSidebar({
  currentSessionId,
  onSelectSession,
  onNewChat,
}: SessionSidebarProps) {
  const [sessions, setSessions] = useState<PortalSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    loadSessions(limit);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSessionId, limit]);

  const loadSessions = async (requestLimit: number) => {
    try {
      const response = await sessionApi.listSessions({ limit: requestLimit });
      setSessions(response.data.sessions);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const formatTime = (dateStr?: string) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const nativeSessions = sessions.filter((session) => session.mode === 'native');
  const embeddedSessions = sessions.filter((session) => session.mode === 'embedded');

  const renderSessionGroup = (title: string, items: PortalSession[]) => {
    if (items.length === 0) return null;

    return (
      <div className="space-y-2">
        <div className="px-1 pt-2 text-xs font-semibold tracking-wide text-gray-400 uppercase">
          {title}
        </div>
        {items.map((session) => (
          <div
            key={session.portal_session_id}
            onClick={() => onSelectSession(session)}
            className={`p-3 rounded-lg cursor-pointer transition-colors ${
              currentSessionId === session.portal_session_id
                ? 'bg-primary-50 border border-primary-200'
                : 'hover:bg-gray-50 border border-transparent'
            }`}
          >
            <div className="flex items-start space-x-2">
              <MessageSquare className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {session.resource_name || session.title || session.resource_id || '未知资源'}
                </p>
                {session.last_message_preview && (
                  <p className="text-xs text-gray-500 truncate mt-0.5">
                    {session.last_message_preview}
                  </p>
                )}
                <div className="flex items-center mt-1 text-xs text-gray-500">
                  <Clock className="w-3 h-3 mr-1" />
                  {formatTime(session.last_message_at || session.updated_at)}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="w-64 bg-white border-r flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">会话历史</h2>
        <button
          onClick={onNewChat}
          className="w-full px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors font-medium text-sm"
        >
          新建对话
        </button>
      </div>

      {/* Sessions */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <div className="text-center text-gray-500 text-sm">加载中...</div>
        ) : sessions.length === 0 ? (
          <div className="text-center text-gray-500 text-sm">
            暂无会话历史
          </div>
        ) : (
          <div className="space-y-2">
            {renderSessionGroup('对话历史', nativeSessions)}
            {renderSessionGroup('最近打开', embeddedSessions)}
            {sessions.length >= limit && (
              <button
                onClick={() => setLimit((current) => current + 50)}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"
              >
                加载更多
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** Main application component - V2 */

import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useParams } from 'react-router-dom';
import { User, LogOut, PanelRightOpen, PanelRightClose } from 'lucide-react';
import { resourceApi, sessionApi, authApi } from './api';
import { useAuth } from './auth/AuthProvider';
import type { Resource, LaunchResponse, SessionResumePayload, PortalSession } from './types';
import { ResourceSidebar } from './components/ResourceSidebar';
import { ChatInterface } from './components/ChatInterface';
import { SessionSidebar } from './components/SessionSidebar';
import { WorkspacePane } from './components/WorkspacePane';
import { IframeWorkspace } from './components/IframeWorkspace';

// Default resource ID to load on startup
const DEFAULT_RESOURCE_ID = 'general-chat';

function App() {
  const { user, loading: authLoading, logout } = useAuth();
  const [resourcesGrouped, setResourcesGrouped] = useState<Record<string, Resource[]>>({});
  const [currentResource, setCurrentResource] = useState<Resource | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [currentLaunchId, setCurrentLaunchId] = useState<string | null>(null);
  const [showWorkspace, setShowWorkspace] = useState(false);
  const [workspaceMode, setWorkspaceMode] = useState<'websdk' | 'iframe' | null>(null);
  const [isLaunching, setIsLaunching] = useState(false);
  const navigate = useNavigate();

  // Load resources when authenticated
  useEffect(() => {
    if (user) {
      loadResources();
    }
  }, [user]);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      console.log('Not authenticated, redirecting to login...');
      authApi.redirectToSSO(window.location.pathname + window.location.search);
    }
  }, [authLoading, user]);

  // Load default resource when resources are loaded
  useEffect(() => {
    if (Object.keys(resourcesGrouped).length > 0 && !currentResource) {
      launchDefaultResource();
    }
  }, [resourcesGrouped]);

  const loadResources = async () => {
    try {
      const response = await resourceApi.listResourcesGrouped();
      setResourcesGrouped(response.data);
    } catch (error) {
      console.error('Failed to load resources:', error);
    }
  };

  const launchDefaultResource = async () => {
    const allResources = Object.values(resourcesGrouped).flat();
    const defaultResource = allResources.find((r) => r.id === DEFAULT_RESOURCE_ID) || allResources[0];
    
    if (defaultResource) {
      await handleSelectResource(defaultResource);
    }
  };

  const handleSelectResource = async (resource: Resource) => {
    if (isLaunching) return;
    
    setIsLaunching(true);
    setCurrentResource(resource);

    try {
      // For native resources, try to resume the most recent active session
      if (resource.launch_mode === 'native') {
        const sessionsRes = await sessionApi.listSessions({
          resource_id: resource.id,
          status: 'active',
          limit: 1,
        });
        const recentSession = sessionsRes.data.sessions[0];
        if (recentSession) {
          // Use resume endpoint to properly restore session
          const resumeRes = await sessionApi.getSessionResume(recentSession.portal_session_id);
          applyResumePayload(resumeRes.data);
          setIsLaunching(false);
          return;
        }
      }

      // No recent session or non-native resource: create new launch/session
      const response = await resourceApi.launchResource(resource.id);
      const launchData: LaunchResponse = response.data;
      applyLaunchResponse(launchData);
    } catch (error: any) {
      console.error('Failed to launch resource:', error);
      alert(error.response?.data?.detail || '启动失败');
    } finally {
      setIsLaunching(false);
    }
  };

  /**
   * V2: Apply session resume payload from backend
   * This is the single source of truth for session restoration
   */
  const applyResumePayload = (resume: SessionResumePayload) => {
    setCurrentSessionId(resume.portal_session_id);
    
    if (resume.mode === 'native') {
      setCurrentLaunchId(null);
      setWorkspaceMode(null);
      setShowWorkspace(false);
      navigate('/');
    } else {
      // Embedded mode
      setCurrentLaunchId(resume.launch_id ?? null);
      setWorkspaceMode(resume.adapter === 'iframe' ? 'iframe' : 'websdk');
      setShowWorkspace(resume.show_workspace);
      navigate('/');
    }
  };

  /**
   * Apply launch response
   */
  const applyLaunchResponse = (launchData: LaunchResponse) => {
    if (launchData.mode === 'native' && launchData.portal_session_id) {
      setCurrentSessionId(launchData.portal_session_id);
      setCurrentLaunchId(null);
      setWorkspaceMode(null);
      setShowWorkspace(false);
      navigate('/');
    } else if (launchData.mode === 'embedded' && launchData.launch_id) {
      setCurrentSessionId(launchData.portal_session_id ?? null);
      setCurrentLaunchId(launchData.launch_id);
      setWorkspaceMode(launchData.adapter === 'iframe' ? 'iframe' : 'websdk');
      setShowWorkspace(true);
      navigate('/');
    }
  };

  /**
   * V2: Select session using resume endpoint
   */
  const handleSelectSession = async (sessionId: string) => {
    try {
      const resumeRes = await sessionApi.getSessionResume(sessionId);
      const resume = resumeRes.data;
      
      // Set resource if different
      if (resume.resource_id !== currentResource?.id) {
        const allResources = Object.values(resourcesGrouped).flat();
        const resource = allResources.find((r) => r.id === resume.resource_id);
        if (resource) {
          setCurrentResource(resource);
        }
      }
      
      applyResumePayload(resume);
    } catch (error) {
      console.error('Failed to select session:', error);
      alert('无法恢复会话');
    }
  };

  const handleNewChat = async () => {
    if (currentResource) {
      setIsLaunching(true);
      try {
        const response = await resourceApi.launchResource(currentResource.id);
        const launchData: LaunchResponse = response.data;
        applyLaunchResponse(launchData);
      } catch (error: any) {
        console.error('Failed to start new chat:', error);
        alert(error.response?.data?.detail || '启动失败');
      } finally {
        setIsLaunching(false);
      }
    } else {
      await launchDefaultResource();
    }
  };

  const handleLogout = async () => {
    await logout();
    setCurrentResource(null);
    setCurrentSessionId(null);
    setCurrentLaunchId(null);
    navigate('/');
  };

  const toggleWorkspace = () => {
    setShowWorkspace((prev) => !prev);
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
          <p className="text-gray-600">加载中...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-gray-600 mb-4">正在重定向到登录页面...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      {/* Header */}
      <header className="bg-white shadow-sm border-b sticky top-0 z-50">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-gradient-to-br from-primary-400 to-primary-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">AI</span>
                </div>
                <span className="font-bold text-xl text-gray-900">AI Portal</span>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              {/* Workspace toggle button (only for websdk/iframe modes) */}
              {(workspaceMode === 'websdk' || workspaceMode === 'iframe') && (
                <button
                  onClick={toggleWorkspace}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  {showWorkspace ? (
                    <>
                      <PanelRightClose className="w-4 h-4" />
                      <span className="hidden sm:inline">隐藏工作区</span>
                    </>
                  ) : (
                    <>
                      <PanelRightOpen className="w-4 h-4" />
                      <span className="hidden sm:inline">显示工作区</span>
                    </>
                  )}
                </button>
              )}

              <div className="flex items-center space-x-2 text-sm text-gray-600 bg-gray-50 px-3 py-1.5 rounded-lg">
                <User className="w-4 h-4" />
                <span className="font-medium">{user.name}</span>
                <span className="text-gray-400">({user.emp_no})</span>
              </div>
              <button
                onClick={handleLogout}
                className="text-gray-400 hover:text-red-600 transition-colors p-2 hover:bg-red-50 rounded-lg"
                title="退出登录"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main content - Three column layout */}
      <main className="flex-1 flex overflow-hidden">
        {/* Left: Resource Sidebar */}
        <ResourceSidebar
          resourcesGrouped={resourcesGrouped}
          currentResourceId={currentResource?.id}
          onSelectResource={handleSelectResource}
        />

        {/* Middle: Chat/Content Area */}
        <div className="flex-1 flex min-w-0">
          <Routes>
            <Route
              path="/"
              element={
                <MainContent
                  currentResource={currentResource}
                  currentSessionId={currentSessionId}
                  currentLaunchId={currentLaunchId}
                  workspaceMode={workspaceMode}
                  showWorkspace={showWorkspace}
                  onSelectSession={handleSelectSession}
                  onNewChat={handleNewChat}
                  isLaunching={isLaunching}
                />
              }
            />
            <Route
              path="/chat/:sessionId"
              element={
                <ChatRoutePage
                  resourcesGrouped={resourcesGrouped}
                  onResourceChange={setCurrentResource}
                  onSelectSession={handleSelectSession}
                  onNewChat={handleNewChat}
                />
              }
            />
            <Route
              path="/launch/:launchId"
              element={<LaunchRoutePage />}
            />
            <Route
              path="/iframe/:launchId"
              element={<IframeRoutePage />}
            />
          </Routes>
        </div>
      </main>
    </div>
  );
}

// Main content component
interface MainContentProps {
  currentResource: Resource | null;
  currentSessionId: string | null;
  currentLaunchId: string | null;
  workspaceMode: 'websdk' | 'iframe' | null;
  showWorkspace: boolean;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  isLaunching: boolean;
}

function MainContent({
  currentResource,
  currentSessionId,
  currentLaunchId,
  workspaceMode,
  showWorkspace,
  onSelectSession,
  onNewChat,
  isLaunching,
}: MainContentProps) {
  const handleSessionSelect = (session: PortalSession) => {
    onSelectSession(session.portal_session_id);
  };

  if (isLaunching) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
          <p className="text-gray-600">正在启动资源...</p>
        </div>
      </div>
    );
  }

  if (!currentResource) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center text-gray-500">
          <p className="text-lg mb-2">请从左侧选择一个资源</p>
          <p className="text-sm">开始与 AI 助手对话</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex w-full h-full">
      {/* Left part: Session Sidebar + Chat Area */}
      <div className="flex flex-1 min-w-0">
        {/* Session Sidebar - only for native chat mode */}
        {currentResource.launch_mode === 'native' && (
          <div className="w-60 border-r bg-white hidden xl:flex flex-col flex-shrink-0">
            <SessionSidebar
              currentSessionId={currentSessionId || undefined}
              onSelectSession={handleSessionSelect}
              onNewChat={onNewChat}
            />
          </div>
        )}

        {/* Chat/Content Area */}
        <div className="flex-1 min-w-0">
          {currentResource.launch_mode === 'native' && currentSessionId ? (
            <ChatInterface
              sessionId={currentSessionId}
              resource={currentResource}
              onRestart={onNewChat}
            />
          ) : (workspaceMode === 'websdk' || workspaceMode === 'iframe') && currentLaunchId ? (
            showWorkspace ? (
              <div className="h-full flex items-center justify-center bg-gray-50 text-gray-500">
                <div className="text-center">
                  <p className="text-lg mb-2">工作区已在右侧显示</p>
                  <p className="text-sm">点击右上角按钮可以隐藏工作区</p>
                </div>
              </div>
            ) : (
              workspaceMode === 'websdk' ? (
                <WorkspacePane launchId={currentLaunchId} />
              ) : (
                <IframeWorkspace launchId={currentLaunchId} />
              )
            )
          ) : (
            <div className="h-full flex items-center justify-center bg-gray-50 text-gray-500">
              <div className="text-center">
                <p className="text-lg mb-2">准备就绪</p>
                <p className="text-sm">正在加载资源...</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right part: Workspace Pane (for websdk/iframe modes) */}
      {showWorkspace && currentLaunchId && (workspaceMode === 'websdk' || workspaceMode === 'iframe') && (
        <div className="w-5/12 min-w-[380px] max-w-[600px] border-l bg-white flex-shrink-0">
          {workspaceMode === 'websdk' ? (
            <WorkspacePane launchId={currentLaunchId} />
          ) : (
            <IframeWorkspace launchId={currentLaunchId} />
          )}
        </div>
      )}
    </div>
  );
}

// Route page components
function ChatRoutePage({
  resourcesGrouped,
  onResourceChange,
  onSelectSession,
  onNewChat,
}: {
  resourcesGrouped: Record<string, Resource[]>;
  onResourceChange: (resource: Resource) => void;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
}) {
  const { sessionId } = useParams();
  const [resource, setResource] = useState<Resource | null>(null);

  useEffect(() => {
    const loadSessionResource = async () => {
      if (!sessionId) return;
      try {
        const sessionRes = await sessionApi.getSession(sessionId);
        const session = sessionRes.data;
        const allResources = Object.values(resourcesGrouped).flat();
        const matchedResource = allResources.find((item) => item.id === session.resource_id);
        if (matchedResource) {
          setResource(matchedResource);
          onResourceChange(matchedResource);
        }
      } catch (error) {
        console.error('Failed to load chat route session:', error);
      }
    };

    void loadSessionResource();
  }, [sessionId, resourcesGrouped, onResourceChange]);

  if (!sessionId) return null;

  return (
    <div className="flex h-full w-full">
      <div className="w-64 border-r bg-white hidden lg:flex flex-col">
        <SessionSidebar
          currentSessionId={sessionId}
          onSelectSession={(session) => onSelectSession(session.portal_session_id)}
          onNewChat={onNewChat}
        />
      </div>
      <div className="flex-1">
        <ChatInterface sessionId={sessionId} resource={resource || undefined} />
      </div>
    </div>
  );
}

function LaunchRoutePage() {
  const { launchId } = useParams();
  if (!launchId) return null;
  return (
    <div className="w-full h-full">
      <WorkspacePane launchId={launchId} />
    </div>
  );
}

function IframeRoutePage() {
  const { launchId } = useParams();
  if (!launchId) return null;
  return (
    <div className="w-full h-full">
      <IframeWorkspace launchId={launchId} />
    </div>
  );
}

function AppWithRouter() {
  return (
    <Router>
      <App />
    </Router>
  );
}

export default AppWithRouter;

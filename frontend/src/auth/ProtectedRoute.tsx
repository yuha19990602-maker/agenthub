/** Protected Route - redirects to SSO if not authenticated */

import { useEffect } from 'react';
import { useAuth } from './AuthProvider';
import { authApi } from '../api';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      // Redirect to SSO login
      authApi.redirectToSSO(window.location.pathname + window.location.search);
    }
  }, [user, loading]);

  if (loading) {
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
    // Will redirect in useEffect above
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-gray-600">重定向到登录页面...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

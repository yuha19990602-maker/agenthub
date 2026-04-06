/** Development Auto Login - For testing without SSO */

import { useEffect, useState, useRef } from 'react';
import { authApi } from '../api';

/**
 * This component automatically logs in the user in development mode.
 * It requests a login URL from the backend, which may resolve to mock-login in dev.
 */
export function DevAutoLogin() {
  const [status, setStatus] = useState<'logging_in' | 'success' | 'error'>('logging_in');
  const [error, setError] = useState<string>('');
  const loginAttempted = useRef(false);

  useEffect(() => {
    // Prevent duplicate login attempts (React StrictMode renders twice)
    if (loginAttempted.current) {
      console.log('DevAutoLogin: Already attempted, skipping...');
      return;
    }
    loginAttempted.current = true;
    
    console.log('DevAutoLogin: Attempting auto-login...');
    
    // Force redirect to localhost to avoid 127.0.0.1 cookie issues
    const url = new URL(window.location.href);
    if (url.hostname === '127.0.0.1') {
      console.log('DevAutoLogin: Redirecting from 127.0.0.1 to localhost...');
      window.location.replace(`http://localhost:${url.port}${url.pathname}${url.search}`);
      return;
    }
    
    // Check if we're already on the mock-login callback
    if (url.pathname.includes('mock-login')) {
      console.log('DevAutoLogin: Detected mock-login redirect, going home...');
      // We're on backend mock-login page, go back to frontend root
      window.location.replace('/');
      return;
    }
    
    authApi.getLoginUrl('/')
      .then((response) => {
        setStatus('success');
        window.location.replace(response.data.login_url);
      })
      .catch((err) => {
        console.error('DevAutoLogin: Failed', err);
        setStatus('error');
        setError(err?.response?.data?.detail || err?.message || 'Login failed');
      });
    
    return () => {
      loginAttempted.current = true;
    };
  }, []);

  if (status === 'error') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-red-600 mb-4">自动登录失败</p>
          <p className="text-sm text-gray-500">{error}</p>
          <button 
            onClick={() => {
              loginAttempted.current = false;
              window.location.reload();
            }}
            className="mt-4 px-4 py-2 bg-primary-500 text-white rounded hover:bg-primary-600"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
        <p className="text-gray-600">开发模式自动登录中...</p>
        <p className="text-sm text-gray-400 mt-2">E10001 (测试用户)</p>
      </div>
    </div>
  );
}

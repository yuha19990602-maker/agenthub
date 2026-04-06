/** Authentication Provider - V2 (SSO + Local Session) */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import { authApi } from '../api';
import type { UserCtx } from '../types';

interface AuthContextValue {
  user: UserCtx | null;
  loading: boolean;
  error: string | null;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<UserCtx | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Redirect to SSO login
   */
  const redirectToLogin = useCallback(() => {
    console.log('Redirecting to SSO login...');
    authApi.redirectToSSO(window.location.pathname + window.location.search);
  }, []);

  /**
   * Bootstrap authentication on mount.
   * Checks for OAuth2 callback (code/state) or existing session.
   */
  const bootstrap = useCallback(async () => {
    setLoading(true);
    setError(null);

    const url = new URL(window.location.href);
    const code = url.searchParams.get('code');
    const state = url.searchParams.get('state');

    try {
      if (code) {
        // OAuth2 callback - exchange code for session
        console.log('Handling OAuth2 callback...');
        const response = await authApi.exchangeCode(code, state);
        setUser(response.data.user);

        // Clean up URL (remove code/state)
        url.searchParams.delete('code');
        url.searchParams.delete('state');
        window.history.replaceState({}, '', url.toString());

        // Navigate to intended destination
        if (response.data.next && response.data.next !== '/') {
          window.location.href = response.data.next;
        }
      } else {
        // Check existing session
        const response = await authApi.getMe();
        setUser(response.data);
      }
    } catch (err: any) {
      console.log('Not authenticated:', err?.response?.data?.detail || err?.message);
      setUser(null);
      // Only set error for unexpected errors, not 401
      if (err?.response?.status !== 401) {
        setError(err?.message || 'Authentication failed');
      }
      // Trigger redirect to login after a short delay
      setTimeout(() => {
        redirectToLogin();
      }, 100);
    } finally {
      setLoading(false);
    }
  }, [redirectToLogin]);

  /**
   * Refresh user info from current session
   */
  const refreshUser = useCallback(async () => {
    try {
      const response = await authApi.getMe();
      setUser(response.data);
    } catch (err: any) {
      console.error('Failed to refresh user:', err);
      setUser(null);
      if (err?.response?.status === 401) {
        // Session expired, redirect to login
        authApi.redirectToSSO(window.location.pathname + window.location.search);
      }
    }
  }, []);

  /**
   * Logout - clears local session
   */
  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setUser(null);
      // Redirect to SSO login
      authApi.redirectToSSO('/');
    }
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const value: AuthContextValue = {
    user,
    loading,
    error,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

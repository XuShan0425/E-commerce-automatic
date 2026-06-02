import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { initClient, setToken, getToken, clearAuth, setApiKey, getApiKey } from '../api/client';
import { login as apiLogin, createApiKey, fetchApiKeys } from '../api/endpoints';
import type { AuthState } from '../types';

interface AuthContextValue extends AuthState {
  login: (username: string, password: string, baseUrl?: string) => Promise<void>;
  logout: () => Promise<void>;
  bindApiKey: (key: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null,
    username: null,
    role: null,
    apiKey: null,
    isLoading: true,
  });

  // Restore session on mount
  useEffect(() => {
    (async () => {
      try {
        await initClient();
        const storedToken = await getToken();
        const storedApiKey = await getApiKey();
        if (storedToken) {
          setState((prev) => ({
            ...prev,
            token: storedToken,
            apiKey: storedApiKey,
            isLoading: false,
          }));
        } else {
          setState((prev) => ({ ...prev, isLoading: false }));
        }
      } catch {
        setState((prev) => ({ ...prev, isLoading: false }));
      }
    })();
  }, []);

  const login = async (username: string, password: string, baseUrl?: string) => {
    if (baseUrl) {
      await initClient(baseUrl);
    } else {
      await initClient();
    }
    const tokenRes = await apiLogin({ username, password });
    await setToken(tokenRes.access_token);

    // Try to get or create an API key for public API access
    try {
      const keys = await fetchApiKeys();
      let apiKey: string | null = null;
      if (keys.length > 0) {
        // We have keys but the raw key isn't returned; create a new one
        const newKey = await createApiKey('mobile-app', 'admin');
        apiKey = newKey.raw_key;
      } else {
        const newKey = await createApiKey('mobile-app', 'admin');
        apiKey = newKey.raw_key;
      }
      if (apiKey) {
        await setApiKey(apiKey);
      }
    } catch {
      // API key creation is best-effort; user can bind manually
    }

    const storedApiKey = await getApiKey();
    setState({
      token: tokenRes.access_token,
      username: tokenRes.username,
      role: tokenRes.role,
      apiKey: storedApiKey,
      isLoading: false,
    });
  };

  const logout = async () => {
    await clearAuth();
    setState({
      token: null,
      username: null,
      role: null,
      apiKey: null,
      isLoading: false,
    });
  };

  const bindApiKey = async (key: string) => {
    await setApiKey(key);
    setState((prev) => ({ ...prev, apiKey: key }));
  };

  const value = useMemo(
    () => ({ ...state, login, logout, bindApiKey }),
    [state]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}

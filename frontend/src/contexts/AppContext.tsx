import React, { createContext, useCallback, useContext, useState } from 'react';
import { getApiKey, setApiKey as storeApiKey } from '../api/client';

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface AppState {
  apiKey: string;
  setApiKey: (key: string) => void;
  toasts: Toast[];
  addToast: (message: string, type?: Toast['type']) => void;
  // JWT 用户认证
  jwtToken: string;
  setJwtToken: (token: string) => void;
  username: string;
  setUsername: (name: string) => void;
  userRole: string | null;
  setUserRole: (role: string | null) => void;
}

const AppContext = createContext<AppState | null>(null);

let toastId = 0;

function loadJwtToken(): string {
  try { return localStorage.getItem('jwt_token') || ''; } catch { return ''; }
}

function loadUsername(): string {
  try { return localStorage.getItem('jwt_username') || ''; } catch { return ''; }
}

function loadUserRole(): string | null {
  try { return localStorage.getItem('jwt_role') || null; } catch { return null; }
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [apiKey, setApiKeyState] = useState(getApiKey() || '');
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [jwtToken, setJwtTokenState] = useState(loadJwtToken());
  const [username, setUsernameState] = useState(loadUsername());
  const [userRole, setUserRoleState] = useState<string | null>(loadUserRole());

  const setApiKey = useCallback((key: string) => {
    storeApiKey(key);
    setApiKeyState(key);
  }, []);

  const setJwtToken = useCallback((token: string) => {
    localStorage.setItem('jwt_token', token);
    setJwtTokenState(token);
  }, []);

  const setUsername = useCallback((name: string) => {
    localStorage.setItem('jwt_username', name);
    setUsernameState(name);
  }, []);

  const setUserRole = useCallback((role: string | null) => {
    if (role) {
      localStorage.setItem('jwt_role', role);
    } else {
      localStorage.removeItem('jwt_role');
    }
    setUserRoleState(role);
  }, []);

  const clearJwt = useCallback(() => {
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('jwt_username');
    localStorage.removeItem('jwt_role');
    setJwtTokenState('');
    setUsernameState('');
    setUserRoleState(null);
  }, []);

  const addToast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = ++toastId;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  }, []);

  return (
    <AppContext.Provider value={{ apiKey, setApiKey, toasts, addToast, jwtToken, setJwtToken, username, setUsername, userRole, setUserRole }}>
      {children}
      {/* Toast 通知浮层 */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`px-4 py-2 rounded-lg shadow-lg text-white text-sm animate-slide-up ${
              t.type === 'error' ? 'bg-red-500' : t.type === 'success' ? 'bg-green-500' : 'bg-blue-500'
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}

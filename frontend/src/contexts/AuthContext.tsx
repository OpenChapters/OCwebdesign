import { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from 'react';
import axios from 'axios';
import { authApi } from '../api/auth';

interface AuthContextValue {
  isAuthenticated: boolean;
  isStaff: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, turnstileToken?: string, fullName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Decode a JWT payload without a library. */
function decodeToken(token: string): Record<string, any> | null {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch {
    return null;
  }
}

function readIsStaff(): boolean {
  const token = localStorage.getItem('access_token');
  if (!token) return false;
  const payload = decodeToken(token);
  return payload?.is_staff === true;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => !!localStorage.getItem('access_token'),
  );
  const [isStaff, setIsStaff] = useState(readIsStaff);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setIsAuthenticated(false);
    setIsStaff(false);
  }, []);

  const scheduleRefresh = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    const token = localStorage.getItem('access_token');
    if (!token) return;
    const payload = decodeToken(token);
    if (!payload?.exp) return;

    const msUntilRefresh = Math.max(0, (payload.exp - 60) * 1000 - Date.now());

    timerRef.current = setTimeout(async () => {
      const refresh = localStorage.getItem('refresh_token');
      if (!refresh) { logout(); return; }
      try {
        const { data } = await axios.post('/api/auth/token/refresh/', { refresh });
        localStorage.setItem('access_token', data.access);
        setIsStaff(readIsStaff());
        scheduleRefresh();
      } catch {
        logout();
      }
    }, msUntilRefresh);
  }, [logout]);

  const login = useCallback(async (email: string, password: string) => {
    const { access, refresh } = await authApi.login(email, password);
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    setIsAuthenticated(true);
    setIsStaff(readIsStaff());
    scheduleRefresh();
  }, [scheduleRefresh]);

  const register = useCallback(async (email: string, password: string, turnstileToken?: string, fullName?: string) => {
    await authApi.register(email, password, turnstileToken ?? '', fullName);
  }, []);

  useEffect(() => {
    if (isAuthenticated) scheduleRefresh();
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [isAuthenticated, scheduleRefresh]);

  return (
    <AuthContext.Provider value={{ isAuthenticated, isStaff, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

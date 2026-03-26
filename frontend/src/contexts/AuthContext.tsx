import { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from 'react';
import axios from 'axios';
import { authApi } from '../api/auth';

interface AuthContextValue {
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, turnstileToken?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Decode the `exp` claim from a JWT without a library. */
function getTokenExp(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp ?? null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => !!localStorage.getItem('access_token'),
  );
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setIsAuthenticated(false);
  }, []);

  /** Schedule a token refresh 60 seconds before the access token expires. */
  const scheduleRefresh = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    const token = localStorage.getItem('access_token');
    if (!token) return;

    const exp = getTokenExp(token);
    if (!exp) return;

    // ms until 60s before expiry (or 0 if already past that point)
    const msUntilRefresh = Math.max(0, (exp - 60) * 1000 - Date.now());

    timerRef.current = setTimeout(async () => {
      const refresh = localStorage.getItem('refresh_token');
      if (!refresh) {
        logout();
        return;
      }
      try {
        const { data } = await axios.post('/api/auth/token/refresh/', { refresh });
        localStorage.setItem('access_token', data.access);
        scheduleRefresh(); // schedule the next refresh
      } catch {
        // Refresh token expired or invalid
        logout();
      }
    }, msUntilRefresh);
  }, [logout]);

  const login = useCallback(async (email: string, password: string) => {
    const { access, refresh } = await authApi.login(email, password);
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    setIsAuthenticated(true);
    scheduleRefresh();
  }, [scheduleRefresh]);

  const register = useCallback(async (email: string, password: string, turnstileToken?: string) => {
    await authApi.register(email, password, turnstileToken ?? '');
  }, []);

  // On mount, schedule a refresh if already logged in
  useEffect(() => {
    if (isAuthenticated) scheduleRefresh();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isAuthenticated, scheduleRefresh]);

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}

import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { getMe, login as apiLogin, logout as apiLogout, register as apiRegister } from "../api/auth";
import { onUnauthorized } from "../api/client";
import { clearToken, getToken, setToken } from "./tokenStore";
import type { User } from "../types/user";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (organizationName: string, name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => onUnauthorized(() => setUser(null)), []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiLogin(email, password);
    setToken(response.access_token);
    setUser(response.user);
  }, []);

  const register = useCallback(
    async (organizationName: string, name: string, email: string, password: string) => {
      // Auto-login on success, same shape as login() - registration returns a token
      // just like /auth/login does.
      const response = await apiRegister(organizationName, name, email, password);
      setToken(response.access_token);
      setUser(response.user);
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      clearToken();
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}

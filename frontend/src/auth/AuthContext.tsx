import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { getMe, login as apiLogin, logout as apiLogout, register as apiRegister } from "../api/auth";
import { ApiError, onUnauthorized } from "../api/client";
import { clearToken, getToken, setToken } from "./tokenStore";
import type { User } from "../types/user";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  loginAsPlatformAdmin: (email: string, password: string) => Promise<void>;
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

  const login = useCallback(async (email: string, password: string): Promise<User> => {
    const response = await apiLogin(email, password);
    setToken(response.access_token);
    setUser(response.user);
    // Returned (not just set into context state) so callers like LoginPage can
    // branch their post-login redirect immediately, without relying on a
    // re-render having already picked up the new context value.
    return response.user;
  }, []);

  const loginAsPlatformAdmin = useCallback(async (email: string, password: string) => {
    // Same /auth/login call as login() - auth is unified, is_platform_admin is
    // just a flag on the user row - but this rejects (without setting the
    // session) an account that isn't actually a platform admin, so a regular
    // user landing on this form by mistake never gets logged in on the wrong
    // surface. Kept as a separate method rather than a param on login() so the
    // regular /login flow used by every non-admin stays untouched.
    const response = await apiLogin(email, password);
    if (!response.user.is_platform_admin) {
      throw new ApiError(403, "This account is not a platform admin.");
    }
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
    <AuthContext.Provider value={{ user, loading, login, loginAsPlatformAdmin, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}

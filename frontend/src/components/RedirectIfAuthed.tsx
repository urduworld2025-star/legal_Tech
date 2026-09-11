import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

// Deliberately doesn't gate on `loading` the way RequireAuth does — the
// landing/login pages should paint immediately for the common case (a
// signed-out visitor), then bounce to the dashboard once the session check
// resolves, rather than blocking first paint on it.
export function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (user) return <Navigate to={user.is_platform_admin ? "/platform-admin" : "/dashboard"} replace />;
  return <>{children}</>;
}

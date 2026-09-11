import { requestJson } from "./client";
import type { AuditLogEntry, Role, TokenResponse, User } from "../types/user";

export function register(
  organizationName: string,
  name: string,
  email: string,
  password: string
): Promise<TokenResponse> {
  return requestJson<TokenResponse>("/auth/register", {
    method: "POST",
    body: { organization_name: organizationName, name, email, password },
  });
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return requestJson<TokenResponse>("/auth/login", { method: "POST", body: { email, password } });
}

export function logout(): Promise<void> {
  return requestJson<void>("/auth/logout", { method: "POST" });
}

export function getMe(): Promise<User> {
  return requestJson<User>("/auth/me");
}

export function createUser(email: string, name: string, password: string, role: Role): Promise<User> {
  return requestJson<User>("/auth/users", { method: "POST", body: { email, name, password, role } });
}

export function listAuditLog(): Promise<AuditLogEntry[]> {
  return requestJson<AuditLogEntry[]>("/auth/audit-log");
}

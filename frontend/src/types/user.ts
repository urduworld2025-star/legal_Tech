// Mirrors src/legalintel/models/user.py

export type Role = "attorney" | "paralegal" | "support_staff";

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  is_active: boolean;
  // organization_id is null only for platform-admin accounts (Ranksol's own staff,
  // not a customer org) - every org member has one.
  organization_id: number | null;
  is_platform_admin: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export interface AuditLogEntry {
  id: number;
  user_id: number | null;
  action: string;
  detail: string | null;
  created_at: string;
}

export interface ClauseReview {
  matter_document_id: number;
  clause_index: number;
  reviewed_by: number;
  reviewed_by_name: string;
  reviewed_at: string;
}

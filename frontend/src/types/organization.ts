// Mirrors src/legalintel/models/organization.py
import type { User } from "./user";

export type Plan = "free" | "pro";
export type SubscriptionStatus = "active" | "past_due" | "canceled";

export interface Organization {
  id: number;
  name: string;
  plan: Plan;
  subscription_status: SubscriptionStatus;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  created_at: string;
}

// Platform-admin only (app/api/routes/platform_admin.py)
export interface OrganizationSummary extends Organization {
  user_count: number;
}

export interface OrganizationDetail {
  organization: Organization;
  users: User[];
}

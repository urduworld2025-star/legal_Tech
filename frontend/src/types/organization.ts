// Mirrors src/legalintel/models/organization.py

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

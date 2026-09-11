import { requestJson } from "./client";
import type { Organization } from "../types/organization";

export function getBillingStatus(): Promise<Organization> {
  return requestJson<Organization>("/billing/status");
}

export function createCheckoutSession(): Promise<{ checkout_url: string }> {
  return requestJson<{ checkout_url: string }>("/billing/checkout-session", { method: "POST" });
}

export function createPortalSession(): Promise<{ portal_url: string }> {
  return requestJson<{ portal_url: string }>("/billing/portal-session", { method: "POST" });
}

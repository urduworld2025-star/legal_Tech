import { requestJson } from "./client";
import type { Organization, OrganizationDetail, OrganizationSummary, Plan, SubscriptionStatus } from "../types/organization";

export function listOrganizations(): Promise<OrganizationSummary[]> {
  return requestJson<OrganizationSummary[]>("/platform-admin/organizations");
}

export function getOrganizationDetail(organizationId: number): Promise<OrganizationDetail> {
  return requestJson<OrganizationDetail>(`/platform-admin/organizations/${organizationId}`);
}

export function updateOrganizationPlan(
  organizationId: number,
  plan: Plan,
  subscriptionStatus: SubscriptionStatus
): Promise<Organization> {
  return requestJson<Organization>(`/platform-admin/organizations/${organizationId}/plan`, {
    method: "PATCH",
    body: { plan, subscription_status: subscriptionStatus },
  });
}

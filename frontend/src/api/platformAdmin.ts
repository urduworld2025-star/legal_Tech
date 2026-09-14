import { requestJson } from "./client";
import type { Organization, OrganizationDetail, OrganizationSummary, Plan, SubscriptionStatus } from "../types/organization";
import type { Role, User } from "../types/user";

export function listOrganizations(): Promise<OrganizationSummary[]> {
  return requestJson<OrganizationSummary[]>("/platform-admin/organizations");
}

export function createOrganization(
  organizationName: string,
  name: string,
  email: string,
  password: string
): Promise<OrganizationSummary> {
  return requestJson<OrganizationSummary>("/platform-admin/organizations", {
    method: "POST",
    body: { organization_name: organizationName, name, email, password },
  });
}

export function getOrganizationDetail(organizationId: number): Promise<OrganizationDetail> {
  return requestJson<OrganizationDetail>(`/platform-admin/organizations/${organizationId}`);
}

export function createUserInOrganization(
  organizationId: number,
  email: string,
  name: string,
  password: string,
  role: Role
): Promise<User> {
  return requestJson<User>(`/platform-admin/organizations/${organizationId}/users`, {
    method: "POST",
    body: { email, name, password, role },
  });
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

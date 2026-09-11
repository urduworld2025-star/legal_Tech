import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { getOrganizationDetail, listOrganizations, updateOrganizationPlan } from "../api/platformAdmin";
import { ApiError } from "../api/client";
import { formatApiError } from "../utils/formatApiError";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingIndicator } from "../components/LoadingIndicator";
import type { OrganizationDetail, OrganizationSummary, Plan, SubscriptionStatus } from "../types/organization";
import styles from "./PlatformAdminPage.module.css";

const PLANS: Plan[] = ["free", "pro"];
const STATUSES: SubscriptionStatus[] = ["active", "past_due", "canceled"];

export function PlatformAdminPage() {
  const { user } = useAuth();
  const [organizations, setOrganizations] = useState<OrganizationSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<OrganizationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [edits, setEdits] = useState<Record<number, { plan: Plan; subscription_status: SubscriptionStatus }>>({});
  const [saving, setSaving] = useState<number | null>(null);

  useEffect(() => {
    if (!user?.is_platform_admin) return;
    listOrganizations()
      .then(setOrganizations)
      .catch((err) => setError(err instanceof ApiError ? formatApiError(err) : "Unexpected error."));
  }, [user]);

  if (!user?.is_platform_admin) {
    return <p className={styles.denied}>Platform admins only.</p>;
  }

  function editFor(org: OrganizationSummary) {
    return edits[org.id] ?? { plan: org.plan, subscription_status: org.subscription_status };
  }

  function setEdit(org: OrganizationSummary, patch: Partial<{ plan: Plan; subscription_status: SubscriptionStatus }>) {
    setEdits((prev) => ({ ...prev, [org.id]: { ...editFor(org), ...patch } }));
  }

  async function handleToggleExpand(orgId: number) {
    if (expandedId === orgId) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(orgId);
    setDetail(null);
    setDetailLoading(true);
    try {
      const d = await getOrganizationDetail(orgId);
      setDetail(d);
    } catch (err) {
      setError(err instanceof ApiError ? formatApiError(err) : "Unexpected error.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleSave(orgId: number) {
    const edit = edits[orgId];
    if (!edit) return;
    setSaving(orgId);
    setError(null);
    try {
      const updated = await updateOrganizationPlan(orgId, edit.plan, edit.subscription_status);
      setOrganizations(
        (prev) => prev?.map((o) => (o.id === orgId ? { ...o, plan: updated.plan, subscription_status: updated.subscription_status } : o)) ?? null
      );
    } catch (err) {
      setError(err instanceof ApiError ? formatApiError(err) : "Unexpected error.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className={styles.page}>
      <header>
        <h1>Platform Admin</h1>
        <p className={styles.subtitle}>Every organization on the platform.</p>
      </header>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {organizations === null ? (
        <LoadingIndicator message="Loading organizations…" />
      ) : organizations.length === 0 ? (
        <p className={styles.empty}>No organizations yet.</p>
      ) : (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Organization</th>
                <th>Users</th>
                <th>Plan</th>
                <th>Status</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {organizations.map((org) => {
                const edit = editFor(org);
                const dirty = edit.plan !== org.plan || edit.subscription_status !== org.subscription_status;
                return (
                  <>
                    <tr key={org.id}>
                      <td>
                        <button type="button" className={styles.expandButton} onClick={() => handleToggleExpand(org.id)}>
                          {expandedId === org.id ? "▾" : "▸"} {org.name}
                        </button>
                      </td>
                      <td>{org.user_count}</td>
                      <td>
                        <select value={edit.plan} onChange={(e) => setEdit(org, { plan: e.target.value as Plan })}>
                          {PLANS.map((p) => (
                            <option key={p} value={p}>
                              {p}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <select
                          value={edit.subscription_status}
                          onChange={(e) => setEdit(org, { subscription_status: e.target.value as SubscriptionStatus })}
                        >
                          {STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>{new Date(org.created_at).toLocaleDateString()}</td>
                      <td>
                        <button
                          type="button"
                          className={styles.saveButton}
                          disabled={!dirty || saving === org.id}
                          onClick={() => handleSave(org.id)}
                        >
                          {saving === org.id ? "Saving…" : "Save"}
                        </button>
                      </td>
                    </tr>
                    {expandedId === org.id && (
                      <tr key={`${org.id}-detail`}>
                        <td colSpan={6} className={styles.detailCell}>
                          {detailLoading ? (
                            <LoadingIndicator message="Loading users…" />
                          ) : detail ? (
                            <ul className={styles.userList}>
                              {detail.users.map((u) => (
                                <li key={u.id}>
                                  {u.name} — {u.email} ({u.role}) {u.is_active ? "" : "— inactive"}
                                </li>
                              ))}
                            </ul>
                          ) : null}
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

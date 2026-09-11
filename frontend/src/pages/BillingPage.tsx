import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { createCheckoutSession, createPortalSession, getBillingStatus } from "../api/billing";
import { ApiError } from "../api/client";
import { formatApiError } from "../utils/formatApiError";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingIndicator } from "../components/LoadingIndicator";
import type { Organization } from "../types/organization";
import styles from "./BillingPage.module.css";

const PLAN_LABEL: Record<Organization["plan"], string> = { free: "Free", pro: "Pro" };
const STATUS_LABEL: Record<Organization["subscription_status"], string> = {
  active: "Active",
  past_due: "Payment past due",
  canceled: "Canceled",
};

export function BillingPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const checkoutResult = searchParams.get("checkout");

  const [organization, setOrganization] = useState<Organization | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [redirecting, setRedirecting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    function load() {
      getBillingStatus()
        .then((org) => {
          if (!cancelled) setOrganization(org);
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof ApiError ? formatApiError(err) : "Unexpected error.");
        });
    }

    load();
    // The Stripe webhook that activates a plan can take a couple seconds to land -
    // if we just came back from a successful Checkout, refetch once more shortly
    // after so the page doesn't look stuck on "Free."
    if (checkoutResult === "success") {
      const timer = setTimeout(load, 2500);
      return () => {
        cancelled = true;
        clearTimeout(timer);
      };
    }
    return () => {
      cancelled = true;
    };
  }, [checkoutResult]);

  async function handleUpgrade() {
    setRedirecting(true);
    setError(null);
    try {
      const { checkout_url } = await createCheckoutSession();
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof ApiError ? formatApiError(err) : "Unexpected error.");
      setRedirecting(false);
    }
  }

  async function handleManageBilling() {
    setRedirecting(true);
    setError(null);
    try {
      const { portal_url } = await createPortalSession();
      window.location.href = portal_url;
    } catch (err) {
      setError(err instanceof ApiError ? formatApiError(err) : "Unexpected error.");
      setRedirecting(false);
    }
  }

  const canManageBilling = user?.role === "attorney";

  return (
    <div className={styles.page}>
      <header>
        <h1>Billing</h1>
        <p className={styles.subtitle}>Your organization's plan and subscription.</p>
      </header>

      {checkoutResult === "success" && (
        <p className={styles.notice}>
          Payment received — this can take a few seconds to reflect below.
        </p>
      )}
      {checkoutResult === "cancelled" && <p className={styles.notice}>Checkout was cancelled.</p>}
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {organization === null ? (
        <LoadingIndicator message="Loading billing status…" />
      ) : (
        <section className={styles.card}>
          <div className={styles.planRow}>
            <div>
              <span className={styles.planName}>{PLAN_LABEL[organization.plan]} plan</span>
              <span
                className={`${styles.statusBadge} ${
                  organization.subscription_status === "active" ? styles.statusActive : styles.statusIssue
                }`}
              >
                {STATUS_LABEL[organization.subscription_status]}
              </span>
            </div>
          </div>

          {canManageBilling ? (
            organization.plan === "free" ? (
              <button type="button" onClick={handleUpgrade} disabled={redirecting}>
                {redirecting ? "Redirecting…" : "Upgrade to Pro"}
              </button>
            ) : (
              <button type="button" onClick={handleManageBilling} disabled={redirecting}>
                {redirecting ? "Redirecting…" : "Manage billing"}
              </button>
            )
          ) : (
            <p className={styles.readOnlyNote}>
              Ask an attorney at your organization to change the plan or payment details.
            </p>
          )}
        </section>
      )}
    </div>
  );
}

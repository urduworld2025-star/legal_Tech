import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { formatApiError } from "../utils/formatApiError";
import { ErrorBanner } from "../components/ErrorBanner";
import styles from "./LoginPage.module.css";

export function AdminLoginPage() {
  const { loginAsPlatformAdmin } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await loginAsPlatformAdmin(email.trim(), password);
      navigate("/platform-admin", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? formatApiError(err) : "Unexpected error.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.page}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <h1>Platform admin sign in</h1>
        <p className={styles.subtitle}>For Ranksol staff only</p>

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        <label className={styles.field}>
          <span>Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={submitting}
            autoFocus
          />
        </label>
        <label className={styles.field}>
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
          />
        </label>
        <button type="submit" disabled={submitting || !email.trim() || !password}>
          {submitting ? "Signing in…" : "Sign in"}
        </button>
        <p className={styles.altAction}>
          <Link to="/login">Back to regular sign in</Link>
        </p>
      </form>
    </div>
  );
}

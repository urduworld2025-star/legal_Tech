import { FormEvent, useState } from "react";
import { Link, NavLink, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import styles from "./NavBar.module.css";

export function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [searchInput, setSearchInput] = useState(searchParams.get("q") ?? "");

  function handleSearchSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = searchInput.trim();
    if (trimmed) navigate(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  return (
    <nav className={styles.nav}>
      <Link to={user ? "/dashboard" : "/"} className={styles.brand}>
        <span className={styles.monogram} aria-hidden="true">
          LI
        </span>
        <span className={styles.brandText}>Legal Document Intelligence</span>
      </Link>
      <div className={styles.links}>
        {user && (
          <>
            <NavLink
              to="/dashboard"
              className={({ isActive }) => `${styles.link} ${isActive ? styles.linkActive : ""}`}
            >
              Matters
            </NavLink>
            <NavLink
              to="/quick-analyze"
              className={({ isActive }) => `${styles.link} ${isActive ? styles.linkActive : ""}`}
            >
              Quick Analyze (not saved)
            </NavLink>
            <NavLink
              to="/billing"
              className={({ isActive }) => `${styles.link} ${isActive ? styles.linkActive : ""}`}
            >
              Billing
            </NavLink>
            {user.role === "attorney" && (
              <NavLink
                to="/admin"
                className={({ isActive }) => `${styles.link} ${isActive ? styles.linkActive : ""}`}
              >
                Admin
              </NavLink>
            )}
          </>
        )}
      </div>
      {user && (
        <form className={styles.searchForm} onSubmit={handleSearchSubmit}>
          <input
            type="search"
            placeholder="Search matters, documents, dockets…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </form>
      )}
      {user && (
        <div className={styles.userArea}>
          <span className={styles.userInfo}>
            {user.name} <span className={styles.role}>({user.role})</span>
          </span>
          <button type="button" className={styles.logoutButton} onClick={() => logout()}>
            Log out
          </button>
        </div>
      )}
    </nav>
  );
}

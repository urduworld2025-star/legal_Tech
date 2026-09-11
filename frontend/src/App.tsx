import { Routes, Route, useLocation } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { RequireAuth } from "./components/RequireAuth";
import { RedirectIfAuthed } from "./components/RedirectIfAuthed";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { MattersListPage } from "./pages/MattersListPage";
import { MatterDetailPage } from "./pages/MatterDetailPage";
import { QuickAnalyzePage } from "./pages/QuickAnalyzePage";
import { AdminPage } from "./pages/AdminPage";
import { BillingPage } from "./pages/BillingPage";
import { SearchResultsPage } from "./pages/SearchResultsPage";
import styles from "./App.module.css";

export default function App() {
  const location = useLocation();
  const isLandingPage = location.pathname === "/";

  return (
    <div className={styles.appShell}>
      {!isLandingPage && <NavBar />}
      <Routes>
        <Route
          path="/"
          element={
            <RedirectIfAuthed>
              <LandingPage />
            </RedirectIfAuthed>
          }
        />
        <Route
          path="/login"
          element={
            <RedirectIfAuthed>
              <LoginPage />
            </RedirectIfAuthed>
          }
        />
        <Route
          path="/register"
          element={
            <RedirectIfAuthed>
              <RegisterPage />
            </RedirectIfAuthed>
          }
        />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <MattersListPage />
            </RequireAuth>
          }
        />
        <Route
          path="/matters/:matterId"
          element={
            <RequireAuth>
              <MatterDetailPage />
            </RequireAuth>
          }
        />
        <Route
          path="/quick-analyze"
          element={
            <RequireAuth>
              <QuickAnalyzePage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin"
          element={
            <RequireAuth>
              <AdminPage />
            </RequireAuth>
          }
        />
        <Route
          path="/billing"
          element={
            <RequireAuth>
              <BillingPage />
            </RequireAuth>
          }
        />
        <Route
          path="/search"
          element={
            <RequireAuth>
              <SearchResultsPage />
            </RequireAuth>
          }
        />
      </Routes>
    </div>
  );
}

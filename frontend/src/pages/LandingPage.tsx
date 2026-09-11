import { Link } from "react-router-dom";
import styles from "./LandingPage.module.css";

const FEATURES = [
  {
    icon: "§",
    title: "Clause Extraction & Risk Flagging",
    body:
      "Automatically locates Governing Law, Termination for Convenience, Uncapped Liability, and " +
      "Non-Compete clauses in a contract, then scores and risk-bands each one so reviewers know what " +
      "to look at first.",
  },
  {
    icon: "▤",
    title: "eDiscovery Triage",
    body:
      "Sorts incoming documents into Contract, Email, or Other in seconds, so your review team spends " +
      "time on documents that actually need attorney eyes.",
  },
  {
    icon: "⚖",
    title: "Federal Docket Monitoring",
    body:
      "Tracks any federal docket through the CourtListener/RECAP API and raises an alert the moment a " +
      "new entry is filed — no manually refreshing a case page.",
  },
  {
    icon: "▣",
    title: "Matter Organization & Reporting",
    body:
      "Groups documents and dockets under a case “matter,” keeps a persistent clause-review trail with " +
      "reviewer bylines, and exports a client-ready PDF report in one click.",
  },
];

const STEPS = [
  {
    n: "1",
    title: "Sign up",
    body: "Create your firm's private workspace, then add paralegal and support-staff accounts as needed.",
  },
  {
    n: "2",
    title: "Upload or track",
    body: "Upload a contract for analysis, or track a federal docket, under a matter you're working on.",
  },
  {
    n: "3",
    title: "Review",
    body: "Work through AI-flagged clauses and risk levels, marking each one reviewed as your team clears it.",
  },
  {
    n: "4",
    title: "Report & monitor",
    body: "Export a PDF for stakeholders, and keep watching for new docket activity — every action is audited.",
  },
];

const CATEGORIES = ["Governing Law", "Termination for Convenience", "Uncapped Liability", "Non-Compete"];

const ROLES = [
  { role: "Attorney", body: "Full access — create and delete matters, manage user accounts, view the audit log." },
  { role: "Paralegal", body: "Day-to-day work — upload and analyze documents, track dockets, review clauses." },
  { role: "Support Staff", body: "Read-only access across the whole platform — view, never modify." },
];

export function LandingPage() {
  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <div className={styles.brand}>
          <span className={styles.monogram} aria-hidden="true">LI</span>
          <span className={styles.brandText}>Legal Document Intelligence</span>
        </div>
        <div className={styles.topBarActions}>
          <Link to="/login" className={styles.topBarSignIn}>Sign In</Link>
          <Link to="/register" className={styles.topBarSignUp}>Sign Up</Link>
        </div>
      </header>

      <section className={styles.hero}>
        <p className={styles.eyebrow}>Built for U.S. corporate counsel &amp; law firms</p>
        <h1 className={styles.headline}>
          Contract review, eDiscovery triage, and docket monitoring —<br className={styles.heroBreak} />
          powered by AI, verified by attorneys.
        </h1>
        <p className={styles.subhead}>
          Legal Document Intelligence extracts risk-relevant clauses, flags exposure, sorts documents by
          type, and watches federal dockets for new filings — every result reviewed by your team before
          anyone relies on it.
        </p>
        <div className={styles.heroActions}>
          <Link to="/register" className={styles.primaryButton}>Start free</Link>
          <Link to="/login" className={styles.secondaryButton}>Sign In</Link>
          <a href="#how-it-works" className={styles.secondaryButton}>See how it works</a>
        </div>
      </section>

      <section className={styles.trustStrip}>
        <div className={styles.trustItem}>
          <strong>CUAD-trained</strong>
          <span>510 contracts, 13,000+ expert legal annotations (The Atticus Project)</span>
        </div>
        <div className={styles.trustDivider} aria-hidden="true" />
        <div className={styles.trustItem}>
          <strong>Federal docket data via CourtListener/RECAP</strong>
          <span>The same free, public court-records API attorneys already trust</span>
        </div>
        <div className={styles.trustDivider} aria-hidden="true" />
        <div className={styles.trustItem}>
          <strong>Human-in-the-loop by design</strong>
          <span>Every AI output requires attorney review — never a fully automated decision</span>
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>What it does</h2>
        <div className={styles.featureGrid}>
          {FEATURES.map((f) => (
            <div className={styles.featureCard} key={f.title}>
              <span className={styles.featureIcon} aria-hidden="true">{f.icon}</span>
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className={`${styles.section} ${styles.sectionAlt}`} id="how-it-works">
        <h2 className={styles.sectionTitle}>How it works</h2>
        <div className={styles.steps}>
          {STEPS.map((s) => (
            <div className={styles.step} key={s.n}>
              <span className={styles.stepNumber}>{s.n}</span>
              <div>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>We started narrow, on purpose</h2>
        <p className={styles.sectionBody}>
          The clause-extraction model currently covers 4 of CUAD's 41 clause categories, validated
          end-to-end before expanding further:
        </p>
        <ul className={styles.categoryList}>
          {CATEGORIES.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
        <p className={styles.sectionBody}>
          Document classification is similarly scoped to Contract / Email / Other today. We'd rather ship
          a narrow model that works than a broad one that doesn't — both expand as they're validated
          against real legal-domain review.
        </p>
      </section>

      <section className={`${styles.section} ${styles.sectionAlt}`}>
        <h2 className={styles.sectionTitle}>Access built for how firms actually work</h2>
        <div className={styles.roleGrid}>
          {ROLES.map((r) => (
            <div className={styles.roleCard} key={r.role}>
              <h3>{r.role}</h3>
              <p>{r.body}</p>
            </div>
          ))}
        </div>
        <p className={styles.sectionBody}>
          Every login, matter, and clause review is written to an audit trail. Sign up your firm to get a
          private workspace, then add paralegal and support-staff accounts from there.
        </p>
      </section>

      <section className={styles.ctaBanner}>
        <h2>Ready to get started?</h2>
        <div className={styles.heroActions}>
          <Link to="/register" className={styles.primaryButton}>Start free</Link>
          <Link to="/login" className={styles.secondaryButton}>Sign In</Link>
        </div>
        <p className={styles.ctaNote}>Free to start — no card required.</p>
      </section>

      <footer className={styles.footer}>
        <p>
          Legal Document Intelligence is a first-pass analysis aid. It does not provide legal advice, and
          no output should be relied upon without review by qualified counsel.
        </p>
        <p className={styles.copyright}>&copy; {new Date().getFullYear()} Legal Document Intelligence</p>
      </footer>
    </div>
  );
}

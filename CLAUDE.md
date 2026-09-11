# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Legal Document Intelligence — Project Brief

## What this project is
AI tools to accelerate contract review, eDiscovery classification, and court
docket monitoring for legal teams. The platform ingests contracts, discovery
documents, and docket data, applies NLP to extract risk-relevant clauses,
classify documents, and alert legal teams to relevant docket activity.

## Target users
Corporate counsel, paralegals, litigation support teams, law firms doing
high-volume contract review, compliance/risk departments.

## Tech stack
- **Backend:** Python, FastAPI
- **Frontend:** React
- **Database:** SQLite for now — step 8 (RBAC) shipped on it too; multiple
  users hitting the same file concurrently works fine at this app's current
  scale. PostgreSQL remains a possible future target if real write
  concurrency ever becomes a bottleneck, but that's not auto-triggered by
  RBAC existing — it's a separate decision if/when it comes up.
- **NLP/ML:** Hugging Face `transformers` + `datasets`, PyTorch
- **Document parsing:** `pdfplumber` (PDF), `python-docx` (Word)
- **Docket monitoring:** custom scraping/integration + diff-based change detection (not ML)

## Hardware constraint — IMPORTANT
This machine (Intel i7-8550U, 4C/8T, 16GB RAM, no dedicated GPU) is not
suitable for local model training. Rules to follow:
- Do NOT install or run heavy training workloads locally (no `torch` training
  loops, no local fine-tuning jobs).
- All model fine-tuning happens in **Google Colab** (free GPU tier). Write
  training scripts so they can be copy-pasted into a Colab notebook with
  minimal changes (avoid local-only file paths, keep dependencies minimal).
- Locally, only run **inference** on already-trained/downloaded model
  checkpoints — this is light enough for CPU.
- Keep local RAM usage in mind: prefer streaming/batched data loading over
  loading full datasets into memory at once.

## Core dataset
- **CUAD (Contract Understanding Atticus Dataset)** — 510 contracts, 13,000+
  expert annotations across 41 clause categories. Source of truth for clause
  extraction and risk-flagging model training.
  - https://huggingface.co/datasets/theatticusproject/cuad
  - Paper: https://arxiv.org/abs/2103.06268

## Clause categories to start with (narrow scope first)
Start with these 4 before expanding to all 41 CUAD categories:
1. Governing Law
2. Termination for Convenience
3. Uncapped Liability
4. Non-Compete

## Build order (do not skip ahead)
1. Document ingestion pipeline — PDF/DOCX parsing, text extraction
2. Baseline clause-extraction model (Colab) — fine-tune a small model
   (e.g. `distilbert-base-uncased`) on the 4 clause categories above, framed
   as extractive QA (same approach as the original CUAD paper)
3. Risk-flagging logic + confidence scoring on top of extraction output
4. eDiscovery document classification model (Colab)
5. Docket monitoring integration + change-detection + alerting (backend only, no ML)
6. Review interface — highlighted clauses, risk scores, case/matter organization
7. Reporting/export for stakeholders
8. Role-based access control (attorneys / paralegals / support staff) + audit trail
9. Testing & QA against legal-domain review
10. UAT, refinement, deployment

## Conventions
- Keep experimentation (`notebooks/`, one-off scripts) separate from
  production code (`src/`, `app/`). Only promote validated pipelines into
  production folders.
- Use Plan mode for any milestone before letting Claude Code write files —
  review the plan, then approve.
- Every clause-extraction/classification output should be reviewable by a
  human (this is a human-in-the-loop tool, not full automation) — reflect
  this in UI and API design.
- Sensitive legal documents: RBAC is implemented (build-order step 8 —
  JWT auth, 3 roles, route-level enforcement, audit trail). Encrypted
  storage at rest is a deliberate, tracked follow-up, not forgotten — see
  README's "Authentication / RBAC" section.
- Multi-tenancy: the app supports self-registration into isolated
  organizations (each registrant gets their own matters/documents/dockets/
  users, like separate law firms each with their own account) — see
  `src/legalintel/organizations/` and `app/core/security.py`'s
  `get_current_org_user` in the Architecture section below. Real Stripe
  subscription billing is wired up too (`src/legalintel/billing/`,
  `app/api/routes/billing.py`) — every org starts on a permanent free plan;
  an attorney can upgrade via Stripe Checkout from `/billing`, and a webhook
  is the source of truth for plan/subscription state, not client-side
  confirmation. A platform-admin panel (for viewing/managing every org's
  subscription across the whole app, not just your own) is deliberately not
  built yet — see plan history for that phase.

## Non-goals for now
- Do not attempt full 41-category CUAD coverage until the 4-category
  baseline is working end-to-end.
- Do not build custom legal-taxonomy definitions without validating against
  CUAD's existing categories first.

## Setup

```
python -m venv venv
venv\Scripts\activate      # Windows
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt
```

`torch` is installed separately from the CPU-only index first to avoid
pulling in CUDA packages this machine doesn't need.

## Commands

```
uvicorn app.main:app --reload   # run the API (http://127.0.0.1:8000)
pytest                          # run the full test suite
pytest tests/extraction         # run one test package
pytest tests/ingestion/test_pdf_parser.py::test_parse_pdf_extracts_text  # single test
```

There is no configured lint/format command yet.

```
python -m scripts.eval_models              # build-order step 9: model accuracy QA (see below)
python -m scripts.upload_models_to_hub     # build-order step 10: push trained checkpoints to
                                            # Hugging Face Hub for deployment (see README's
                                            # Deployment section) - render.yaml's
                                            # CLAUSE_MODEL_DIR/DOCUMENT_CLASSIFICATION_MODEL_DIR
                                            # point at the repo ids it creates
```

The clause-extraction model itself is trained in
`notebooks/02_baseline_clause_extraction_colab.ipynb` on Google Colab, not
locally (see hardware constraint above). Once trained, download
`clause_extraction_model.zip` and unzip it into `models/clause-extraction-baseline/`
— `POST /documents/extract-clauses` fails fast with a clear error if that
folder is missing. Tests don't need the real trained model: they build a
throwaway model with an untrained QA head from the base `distilbert-base-uncased`
checkpoint (`tests/extraction/conftest.py::stub_model_dir`) to exercise the
extraction code path without asserting on prediction quality.

## Model evaluation (build-order step 9)

`scripts/eval_models.py` evaluates both trained checkpoints against validation data
reconstructed with the *exact* filtering/sampling/split logic (same seed=42) as their
training notebooks — this is what the unit test suite deliberately doesn't check (tests
use an untrained-head stub model to exercise code paths, not assert on prediction
quality). Requires `datasets` (`requirements-dev.txt`, not a runtime dependency of the
app itself). Clause extraction is CPU-slow (sliding-window QA over full contract text,
10-30s/example on this hardware) so it's capped to a stratified per-category sample by
default (`--sample-per-category`, default 20); document classification is a fast single
forward pass per example and always runs the full validation split. Results are printed
to stdout and written to `docs/model-eval-report.md`.

`--calibrate` (with `--calibrate-categories`, default the two weak ones, and
`--calibrate-sample-per-category`) switches modes: it scores each row *once* via
`clause_extractor._score_span` (cached margin, independent of any threshold), then sweeps
a threshold grid cheaply against those cached margins — this is how
`clause_extractor.NULL_MARGIN_THRESHOLD`'s values were picked (data-driven, not guessed).
Writes `docs/threshold-calibration-report.md`.

**Important caveat carried through both the script and its output**: the validation
split evaluated is the *same* split each notebook passed as `eval_dataset` to its
`Trainer` for best-checkpoint selection (`load_best_model_at_end=True`) — so these are
best-checkpoint validation numbers, not a held-out generalization estimate. A true
held-out test set would need the notebooks re-run with a 3-way split before training,
which hasn't happened.

## Architecture

Two layers: `app/` is a thin FastAPI layer, `src/legalintel/` is the
importable core library the API calls into. `pyproject.toml` puts both
`src` and the repo root on `pythonpath` for pytest, so tests import
`legalintel.*` the same way `app/` does.

- `app/api/routes/documents.py` — `POST /documents/parse` writes the upload
  to a temp file, calls `legalintel.ingestion.pipeline.parse_document`, then
  deletes the temp file (nothing is persisted to disk yet — see README
  notes). `POST /documents/extract-clauses` does the same parse, then runs
  extraction + risk-flagging. `POST /documents/classify` does the same parse,
  then runs the document-type classifier — kept as its own endpoint (not
  folded into `/extract-clauses`) since it's a separate, independent model
  and shouldn't require loading the (larger) clause-extraction model. All
  three require `attorney` or `paralegal` (`Depends(require_role(...))`, captured
  as a `user` param so `user.organization_id` can be threaded into
  `_require_matter`) — support staff is read-only across this whole app.
- `app/api/routes/dockets.py` — separate router, no relation to `documents.py`.
  `POST /dockets/track`, `POST /dockets/{id}/check` require attorney/paralegal;
  `GET /dockets`, `GET /dockets/{id}/alerts`, `GET /dockets/{id}/entries` require
  any authenticated org user — thin HTTP-status mapping (503/404/409/502) over
  `legalintel.docket`'s exceptions; all persistence/business logic lives in
  `src/legalintel/docket/`, not here. `/track` validates a given `matter_id`
  exists in the caller's org (404 if not) before contacting CourtListener.
  `_require_tracked_docket` 404s alerts/entries lookups for a tracked docket
  outside the caller's org. `get_tracked_docket_by_courtlistener_id` (the
  already-tracked 409 check) is deliberately the one docket lookup that stays
  *not* org-scoped — `courtlistener_docket_id` carries a table-wide `UNIQUE`
  constraint (see `storage.py` below), so a given real-world docket can only be
  tracked by one organization platform-wide today; making that per-org needs a
  composite unique constraint, which would require a full SQLite table
  rebuild (deliberately not introduced) — a known, accepted Phase 1 limit.
- `app/api/routes/matters.py` — `POST /matters` (attorney/paralegal, sets
  `organization_id`/`created_by` from the current user, logs `"matter_created"`),
  `GET /matters` and `GET /matters/{id}` (any authenticated org user, org-scoped;
  composed `MatterDetail`: the matter plus its
  `legalintel.matters.db.list_matter_documents` and
  `legalintel.docket.db.list_tracked_dockets_for_matter`), `DELETE /matters/{id}`
  (attorney-only, org-scoped, cascades child rows via `matters_db.delete_matter`
  before deleting the matter itself, logs `"matter_deleted"`). Also nests the
  clause-review endpoints here (matter-document-scoped, not a separate
  router): `GET .../review` (any authenticated org user), `POST`/`DELETE
  .../review/{clause_index}` (attorney/paralegal; POST logs
  `"clause_reviewed"` and resolves the reviewer's name via `auth_db.get_user_by_id`
  for the response, since `legalintel.auth.db` only stores `reviewed_by` as
  an id). `_require_matter_document` checks the matter belongs to the caller's
  org *before* checking the document belongs to that matter — `matter_documents`
  has no `organization_id` column of its own, so skipping the first check would
  let a guessed `document_id` be reached by pairing it with someone else's
  `matter_id`.
- `app/api/routes/auth.py` — `POST /auth/register` (public, no auth; rate-limited
  via `app.core.rate_limit.enforce_registration_rate_limit` since it's this
  app's first public unauthenticated write endpoint; creates a brand-new
  organization plus its first user, always `role="attorney"`, in one
  transaction via `legalintel.organizations.db.create_organization_with_owner`
  — see that module and `src/legalintel/organizations/` below), `POST
  /auth/login` (401 on bad email OR bad password, always the same generic
  message — never reveal which one was wrong; logs `"login"`), `POST
  /auth/logout` (204, stateless JWT so there's nothing to invalidate
  server-side — exists purely so a `"logout"` audit event has somewhere to
  fire from), `GET /auth/me`, `POST /auth/users` (attorney-only, 201, 409 on
  duplicate email, `organization_id` always forced from the caller's own
  session — never accepted from the request body — so an attorney can only
  ever create peers in their own org), `GET /auth/audit-log` (attorney-only,
  org-scoped).
- `app/api/routes/search.py` — `GET /search?q=...` (any authenticated org
  user). Thin: fetches the caller's org's matters/documents/dockets (org
  filtering happens here, at the fetch layer, before the free-text match) and
  hands them to `legalintel.search.search_all`, which stays a pure,
  tenant-unaware function; no query-specific DB filtering beyond that.
- `app/core/security.py` — `get_current_user` (FastAPI dependency; decodes
  the bearer token, then re-fetches the user from the DB and checks
  `is_active` on *every* request rather than trusting a role embedded in the
  token, so deactivating a user takes effect immediately with no blacklist
  needed — the same re-fetch also picks up `organization_id`/`is_platform_admin`
  fresh every request, so no JWT claim carries those either) and
  `get_current_org_user` (wraps `get_current_user`, 403s a platform-admin
  account — `organization_id is None` — since it's authenticated but not
  authorized for any tenant's resources). `require_role(*roles)` now depends
  on `get_current_org_user` rather than `get_current_user` directly, so a
  platform-admin account's placeholder `role` (see `organizations/` below)
  can never pass a role check on a tenant-scoped route. Status mapping:
  no/bad/expired token or a deactivated user → 401 (never distinguish which,
  same principle as login); missing `JWT_SECRET_KEY` (server misconfig) →
  503; authenticated but wrong role, or a platform-admin hitting a
  tenant-scoped route → 403.
- `app/core/rate_limit.py` — `enforce_registration_rate_limit` (a FastAPI
  dependency), a tiny in-process sliding-window limiter (5/hour/IP) guarding
  `POST /auth/register`. In-process, module-level state is deliberate and
  sufficient since production runs a single uvicorn worker (see README's
  shared-hosting deployment notes) — no Redis dependency added for this.
  `reset()` is a test-only hook `tests/conftest.py`'s `client` fixture calls
  every test, since the state would otherwise leak across the whole pytest
  session (every `TestClient` request shares the same client host).
- `src/legalintel/organizations/` — `db.py` has
  `create_organization_with_owner` (the one multi-table transactional write
  in this app outside `matters_db.delete_matter`'s cascade — inserts
  `organizations` then `users` in a single `connect()` block so a crash
  mid-way never leaves an org with no owner; used by `/auth/register` and by
  `scripts/create_admin.py`), `create_organization` (standalone, no owner —
  used by tests and future platform-admin tooling), `get_organization`,
  `get_organization_by_stripe_customer_id`/`_by_stripe_subscription_id`
  (used by the webhook handlers below to map a Stripe event back to an org),
  and `update_organization(db_path, organization_id, **fields)` (allow-lists
  `{"plan", "subscription_status", "stripe_customer_id",
  "stripe_subscription_id"}`, raises `ValueError` on anything else — not a
  general-purpose setter, only ever called by
  `legalintel.billing.webhook_handlers`). `src/legalintel/models/organization.py`
  holds the `Organization` pydantic model. Platform-admin accounts
  (`is_platform_admin=1`, `organization_id=NULL`) are a separate, not-yet-built
  concept — see `get_current_org_user` above for how they're already fenced
  off from tenant routes even before that admin surface exists.
- `src/legalintel/billing/` — `stripe_client.py` is a thin wrapper around the
  `stripe` SDK (`create_checkout_session`, `create_portal_session`,
  `construct_webhook_event`), passing `api_key=` as a per-call kwarg rather
  than mutating the `stripe.api_key` module global, since FastAPI's sync
  routes run in a threadpool and a shared mutable global would race under
  concurrent requests. `webhook_handlers.py` has one function per handled
  Stripe event type (`handle_checkout_completed`,
  `handle_subscription_updated`, `handle_subscription_deleted`,
  `handle_invoice_payment_failed`), each doing 1-2 `organizations_db` writes
  and silently no-op-ing if the org lookup fails (e.g. a stale/replayed
  event) rather than raising — a webhook handler failing loudly just means
  Stripe retries it, which doesn't help if the org is genuinely gone.
  `handle_checkout_completed` reads the organization id from the Checkout
  Session's `metadata`, falling back to `client_reference_id` — both are set
  by `app/api/routes/billing.py::create_checkout_session` on purpose,
  redundantly, since a missed org id on a real payment is worse than one
  extra field. `app/api/routes/billing.py`: `GET /billing/status` (any org
  member, read-only), `POST /billing/checkout-session`/`/portal-session`
  (attorney-only — `require_role("attorney")` — 503 if Stripe isn't
  configured, matching `JWT_SECRET_KEY`'s 503 pattern in
  `app/core/security.py`), and `POST /billing/webhook` (fully public — no
  auth dependency, since Stripe can't send a JWT; verifies the
  `Stripe-Signature` header via `stripe_client.construct_webhook_event`
  instead, 400 on `InvalidWebhookSignatureError`; unhandled event types are
  silently accepted with 200 rather than erroring, since Stripe sends many
  event types this app doesn't act on and erroring would make Stripe retry
  them forever). No Stripe.js/Elements on the frontend at all — both
  Checkout and the Customer Portal are Stripe-hosted redirects
  (`frontend/src/pages/BillingPage.tsx` just calls
  `window.location.href = checkout_url`/`portal_url`), keeping
  `package.json` free of a payment SDK.
- `src/legalintel/auth/` — `security.py` holds pure functions with no DB/
  Settings access (`hash_password`/`verify_password` via `bcrypt`,
  `create_access_token`/`decode_access_token` via `PyJWT`, HS256, 8h expiry,
  `sub` = user id only, no refresh token, no org/role claim — see
  `app/core/security.py` above for why). `db.py` mirrors `docket/db.py`'s/
  `matters/db.py`'s conventions (`db_path` first arg) for `users`,
  `audit_log`, and `clause_reviews` — `create_user` takes `organization_id`
  (required for every org member; `None` only valid with
  `is_platform_admin=True`) and `is_platform_admin` keyword args now.
  `set_clause_reviewed` is an upsert on `clause_reviews`'
  `(matter_document_id, clause_index)` UNIQUE constraint, so re-reviewing
  overwrites who/when (it's current-state, not a log; the `audit_log`
  `"clause_reviewed"` entry is what preserves history). `log_action`/
  `list_audit_log` both take `organization_id` (nullable on write, required
  on read) so the audit log is org-scoped like everything else.
  `clause_reviews` has no FK to a clauses table since clauses aren't
  normalized (`matter_documents.result_json` is an opaque blob, existing
  convention) — `clause_index` is positional into that document's `clauses`
  array.
- `app/core/config.py` — single `Settings` object (pydantic-settings, reads
  `.env`) with upload limits, allowed extensions, `clause_model_dir`,
  `document_classification_model_dir`, `cors_allow_origins`,
  `courtlistener_api_token`/`courtlistener_base_url`, `jwt_secret_key`,
  `db_path` (shared SQLite file for dockets + matters + auth + organizations
  — see `storage.py` below), and the Stripe billing fields
  (`stripe_secret_key`/`stripe_webhook_secret`/`stripe_price_id_pro`, all
  `None` by default so billing routes 503 rather than misbehave when
  unconfigured, and `frontend_base_url` — needed server-side to build
  Checkout/Portal `success_url`/`cancel_url`/`return_url`, which must point
  at the frontend, not this API).
- `src/legalintel/ingestion/` — `pdf_parser.py` (pdfplumber) and
  `docx_parser.py` (python-docx) each return a list of `ParsedPage`;
  `pipeline.py` dispatches by file extension and joins pages into a
  `ParsedDocument`. Add a new file type by adding a parser function and
  registering it in `pipeline.py`'s `_PARSERS` dict.
- `src/legalintel/extraction/clause_extractor.py` — loads the fine-tuned QA
  model as a process-wide singleton (`@lru_cache`), one hardcoded question
  per clause category in `QUESTIONS` (must exactly match the question
  phrasing used during training in the Colab notebook — QA models are
  sensitive to this). Inference runs CUAD/SQuAD2.0-style: sliding-window
  tokenization (`MAX_LENGTH`/`STRIDE` must match the notebook's training
  config), best-span decoding per window, and a null-vs-span score
  comparison so the model can report "no clause of this type found" instead
  of forcing a low-quality match. `_score_span` (pure scoring) is split from
  `_predict_answer` (applies the null-vs-span decision) specifically so
  `scripts/eval_models.py --calibrate` can sweep decision thresholds without
  re-running inference per threshold. `NULL_MARGIN_THRESHOLD` lowers that
  decision bar per-category — Uncapped Liability and Non-Compete had strong
  no-answer accuracy but weak has-answer recall in step-9 QA (see
  docs/model-eval-report.md), so their threshold trades some precision for
  recall; Governing Law/Termination For Convenience keep the model's default
  (0.0) since their recall was already fine. `_looks_negated` is a separate
  regex heuristic (not a model) that sets `ClauseMatch.possible_negation`
  when a match is preceded by or begins with negation language (e.g.
  "Neither Party may terminate...for convenience") — a real false-positive
  shape found during step-9 QA where the model matches on surface phrasing
  without registering the negation. It only adds a reviewer-facing warning,
  never suppresses a match, since suppressing on a heuristic could hide a
  genuine clause. `_load_model` checks for a local folder first (unchanged
  dev behavior/error message); if that's not there and the string looks
  like a Hugging Face Hub repo id (`_looks_like_hub_repo_id` — deliberately
  excludes Windows paths so a missing local folder still fails fast offline
  in tests, rather than attempting a real Hub network call), it falls
  through to `from_pretrained` fetching from the Hub — see "Deployment" in
  README for why (the 250MB+ checkpoint can't be committed to git).
- `src/legalintel/risk/flagging.py` — pure rule-based Python (no model), run
  after extraction in `app/api/routes/documents.py`. A static
  `SEVERITY_BY_CATEGORY` dict assigns each clause category a fixed
  `RiskLevel`, and `band_for_confidence` buckets the extractor's raw
  confidence float into HIGH/MEDIUM/LOW for reviewer legibility.
  `apply_risk_flags`/`summarize_risk` enrich `ClauseMatch`es and build the
  document-level `RiskSummary`.
- `src/legalintel/classification/document_classifier.py` — mirrors
  `clause_extractor.py`'s lazy-singleton (`@lru_cache`) + `ModelNotFoundError`
  pattern, but for 3-class sequence classification (Contract/Email/Other,
  trained in `notebooks/03_document_classification_colab.ipynb`) via
  `POST /documents/classify`. Returns the full softmax probability
  distribution, not just the top label, for human-in-the-loop transparency.
  The "Other" class is a placeholder proxy (news-article text) — see README.
  `_load_model` has the same local-folder-then-Hub-repo-id fallback as
  `clause_extractor.py`, for the same reason.
- `src/legalintel/storage.py` — the single source of schema truth for every
  SQLite table in the app (`organizations`, `users`, `matters` — including
  its `organization_id`/`created_by REFERENCES users(id)` columns —
  `matter_documents`, `tracked_dockets` — including `organization_id` —
  `seen_docket_entries`, `docket_alerts`, `audit_log` — including
  `organization_id` — `clause_reviews`), plus the shared `connect(db_path)`
  context manager (`PRAGMA foreign_keys = ON`, `sqlite3.Row` row factory,
  `CREATE TABLE IF NOT EXISTS` re-run cheaply on every connect, followed by
  `_apply_add_column_migrations` and `_backfill_legacy_organization`).
  `_apply_add_column_migrations` is this repo's first schema change to an
  *existing* table (`CREATE TABLE IF NOT EXISTS` alone only helps brand-new
  databases) — `ALTER TABLE ... ADD COLUMN`, wrapped to swallow "duplicate
  column name" so it's idempotent like everything else here; SQLite can't add
  a `NOT NULL`/`CHECK`-constrained column to a non-empty table without a full
  table rebuild, so `organization_id` etc. land nullable at the schema level
  even though every *new* row is required to set one — that requirement is
  enforced in the `*_db.py` write functions instead (deliberately not
  introducing table-rebuild migration machinery for this).
  `_backfill_legacy_organization` runs once (checks for any orphaned user
  first): groups every pre-existing user/matter/tracked-docket into one new
  "Legacy Organization" row — correct, not a hack, since that data already
  had zero isolation from each other before organizations existed.
  `docket/db.py`, `matters/db.py`, `auth/db.py`, and `organizations/db.py`
  all import `connect` from here rather than defining their own — each still
  only queries the tables it "owns."
- `src/legalintel/docket/` — no ML, unlike everything above. `db.py` stores
  `tracked_dockets` (`matter_id` is a real `INTEGER REFERENCES matters(id)`,
  nullable; `organization_id` is its own column, not derived via `matter_id`,
  specifically because `matter_id` is nullable), `seen_docket_entries`,
  `docket_alerts`; it's the only place raw SQL rows get converted to/from
  `legalintel.models.docket` pydantic types. Every lookup/list function
  except `get_tracked_docket_by_courtlistener_id` (see
  `app/api/routes/dockets.py` above for why that one stays global) takes a
  required `organization_id` keyword arg. `docket/monitor.py`'s
  `check_docket_for_updates` also takes `organization_id` now, threaded into
  its own `db.get_tracked_docket` call — a 4th call site (beyond the 3 route
  files) that needed org-scoping, found by reading the actual call graph
  rather than assumed from the routes alone.
  `courtlistener_client.py` wraps the free CourtListener/RECAP API
  (`Authorization: Token <key>` header; 5/min-50/hr-125/day rate limit, so
  this is on-demand only, no background polling — its `_get` retries on 429
  with a backoff parsed from CourtListener's own "expected available in N
  seconds" message, since a single large docket's pagination can exhaust the
  budget on its own) with a `transport=` seam for test doubles
  (`httpx.MockTransport`) and a `ModelNotFoundError`-style
  `CourtListenerConfigError` when the token is missing. `monitor.py`'s
  `check_docket_for_updates` is the diff: fetch current entries, compare
  against `db.get_seen_entry_ids`, persist + alert only on what's new.
- `src/legalintel/matters/db.py` — mirrors `docket/db.py`'s conventions
  exactly (`db_path` first arg, rows → pydantic models inside `db.py`).
  `matter_documents` is one generic row per persisted analysis
  (`analysis_type` discriminant + `result_json` blob of the corresponding
  `ParsedDocument`/`ClauseExtractionResult`/`DocumentClassificationResult`),
  not three normalized tables — nothing yet needs cross-document clause
  querying. `app/api/routes/documents.py`'s three endpoints persist into
  this only when a caller supplies `matter_id`; omitting it keeps today's
  fully-ephemeral behavior (parse, analyze, discard). `matters` has its own
  `organization_id` column (not derived from `created_by`) since every org
  member sees all of that org's matters, not just ones they personally
  created — `add_matter`/`get_matter`/`list_matters`/`delete_matter` all take
  a required `organization_id` now. `matter_documents` itself has no
  `organization_id` column (every route validates the parent matter's org
  first, so it doesn't need one) except `list_all_matter_documents` (no
  `matter_id` filter, exists solely for `search.py` below), which takes
  `organization_id` and `JOIN`s through `matters` to filter, since it has no
  single already-validated matter to inherit scoping from.
- `src/legalintel/search.py` — `search_all` is a pure function over
  already-fetched `Matter`/`MatterDocument`/`TrackedDocket` lists (same
  already-fetched-data convention as `risk/flagging.py` and
  `reporting/report_generator.py` — `app/api/routes/search.py` does the
  fetching via `matters_db`/`docket_db`, org-scoped, *before* handing the
  lists to this function, which stays tenant-unaware by design). Plain
  case-insensitive substring
  matching (no FTS5, no ranking) against matter name/description, document
  filename, document content (re-hydrated per `analysis_type` the same way
  `report_generator.py` does), and tracked-docket case name/docket number —
  deliberately simple, matching this codebase's "don't add abstractions
  beyond what's needed" convention; an FTS5 virtual table is a natural
  upgrade if search performance or relevance ranking ever becomes a real
  problem, not before. Requires 2+ characters; a document whose
  `matter_id` no longer resolves to a matter (or a docket with no
  `matter_id`) is silently skipped rather than erroring.
- `src/legalintel/reporting/report_generator.py` — `generate_matter_report`
  is a pure function (no DB access, mirroring `risk/flagging.py`'s
  already-fetched-data convention) that takes a composed `MatterDetail` plus
  a `tracked_docket_id -> alerts` dict (alerts aren't included in
  `MatterDetail` itself) and returns PDF bytes via
  `reportlab.platypus.SimpleDocTemplate` — the first use of the higher-level
  flowables API in this repo (vs. `tests/conftest.py`'s low-level
  `canvas.drawString`, fine for one fixed line but unworkable for this
  report's variable-length, multi-section content). Branches on each
  `MatterDocument.analysis_type` exactly like
  `frontend/src/components/MatterDocumentCard.tsx` does, re-hydrating the raw
  `result` dict into `ParsedDocument`/`ClauseExtractionResult`/
  `DocumentClassificationResult` via `.model_validate(...)` rather than
  indexing the dict by hand. `GET /matters/{id}/report` in
  `app/api/routes/matters.py` does all the querying (via a shared
  `_load_matter_detail` helper also used by `GET /matters/{id}`) and returns
  a raw `fastapi.responses.Response` with `Content-Disposition: attachment`.
  Carries the same human-in-the-loop disclaimer this codebase already
  surfaces in the UI (e.g. `DocumentClassificationCard`'s "First-pass triage
  only" notice) since the report hands AI-derived analysis to someone
  without app access to see those in-app caveats.
- `src/legalintel/models/document.py` — the pydantic models
  (`ParsedPage`, `ParsedDocument`, `ClauseMatch`, `ClauseExtractionResult`,
  `RiskSummary`, `DocumentClassification`, `DocumentClassificationResult`)
  shared across ingestion, extraction, risk-flagging, classification, and
  API responses/schemas. `src/legalintel/models/docket.py` holds the
  docket-monitoring models (`TrackedDocket`, `DocketEntry`, `DocketAlert`,
  `DocketCheckResult`) separately, since it's an unrelated domain.
  `src/legalintel/models/matter.py` holds `Matter`/`MatterDocument`/
  `MatterDetail` — `MatterDocument.result` is typed as a plain `dict` here
  (it's an opaque JSON blob on the backend); the frontend re-adds precision
  via a discriminated union on `analysis_type`. `Matter` deliberately does
  *not* expose `organization_id` (org is always implicit from the logged-in
  caller, never something the frontend needs to read back off a matter) —
  `User` does, since the frontend needs it for `get_current_org_user`-style
  UI gating. `src/legalintel/models/user.py`'s `User` also carries
  `is_platform_admin: bool` (always `False` today - no
  platform-admin bootstrap script exists yet, see `organizations/` above) and
  `RegisterRequest` (`organization_name`/`email`/`name`/`password`, the
  public self-registration payload).
- `tests/` mirrors `src/legalintel/`'s package layout. Fixtures generate
  sample PDF/DOCX files on the fly (`tests/conftest.py`, via `reportlab`/
  `python-docx`) rather than checking in binary fixture files. Root
  `tests/conftest.py` also has `make_org` (creates a standalone
  `Organization`) and `make_user` (auto-creates an org when
  `organization_id` isn't given, so every pre-multi-tenancy test keeps
  passing unchanged — only tests that care about cross-org isolation pass
  `organization_id` explicitly) and `auth_headers` (same auto-org behavior;
  **two separate `auth_headers(...)` calls with no shared `organization_id`
  land in two different organizations** — a real gotcha when writing a new
  test that needs two roles to see the *same* data, e.g.
  `tests/search/test_routes_search.py::test_search_visible_to_support_staff`
  passes `organization_id=make_org().id` to both calls for exactly this
  reason). `tests/matters/test_org_isolation.py` and
  `tests/docket/test_org_isolation.py` are the dedicated cross-org isolation
  suites (a category that didn't exist before multi-tenancy). `tests/billing/`
  never hits real Stripe — `test_routes_billing.py` monkeypatches
  `app.api.routes.billing.stripe_client`'s functions directly (same
  call-site-patching convention as `tests/docket/conftest.py`'s
  `patch_courtlistener_client`), and `test_webhook_handlers.py` tests each
  handler as a pure function against hand-built event-data dicts. Model-backed
  test packages (`tests/extraction/`, `tests/classification/`) each have a
  `conftest.py` that builds a throwaway untrained-head model from the base
  checkpoint, so tests exercise the code path without needing real trained
  weights or asserting on prediction quality. `tests/docket/` never hits the
  real CourtListener API — every test uses an `httpx.MockTransport` double
  (`tests/docket/conftest.py`) and a `tmp_path`-based SQLite file. It also
  has this repo's first `TestClient` (route-level) tests. `tests/matters/`
  mirrors that style (no external API, so no mocking needed) and includes a
  regression test that `matter_documents`' FK constraint is actually
  enforced (`PRAGMA foreign_keys = ON` in `storage.py`).
- `frontend/` — a Vite + React + TypeScript app with `react-router-dom`
  (`frontend/src/types/api.ts`/`docket.ts`/`matter.ts`/`user.ts`/`search.ts`
  mirror the backend pydantic models). Routes: `/` (`LandingPage`, public
  marketing page — U.S. legal-audience copy, no fabricated stats), `/login`
  (`LoginPage`), and `/register` (`RegisterPage` — organization name, name,
  email, password/confirm; calls `AuthContext`'s `register`, which
  auto-logs-in on success just like `login` does; reuses
  `LoginPage.module.css` directly rather than a near-duplicate stylesheet)
  all wrapped in `<RedirectIfAuthed>` (bounces an
  already-signed-in visitor to `/dashboard` without blocking first paint for
  anonymous ones — see `RedirectIfAuthed.tsx`); everything else is wrapped
  in `<RequireAuth>` (redirects to `/login` if no session) — `/dashboard`
  (`MattersListPage` — create/list, create-form hidden for support staff),
  `/matters/:matterId` (`MatterDetailPage` — the review interface: upload
  form scoped to the matter, persisted `MatterDocument`s rendered via
  `MatterDocumentCard` reusing the same `ClauseList`/`DocumentTextViewer`/
  `DocumentClassificationCard` components as live results, plus tracked
  dockets/alerts, plus an attorney-only delete-matter button), `/quick-analyze`
  (`QuickAnalyzePage` — today's original ephemeral flow, kept but relocated,
  always analyzes with `matterId: null` so nothing persists), `/admin`
  (`AdminPage` — attorney-only, create-user form + audit-log table),
  `/billing` (`BillingPage` — visible to any authenticated user, not just
  attorneys, since paralegal/support-staff should be able to see their
  org's plan even though only `role === "attorney"` sees the actual
  Upgrade/Manage-billing buttons; both buttons are a one-line
  `window.location.href = checkout_url`/`portal_url` redirect to
  Stripe-hosted pages, no custom payment UI), `/search`
  (`SearchResultsPage` — reads `?q=` from the URL rather than
  component state, so the URL itself is shareable/bookmarkable; results
  grouped into Matters/Documents/Dockets sections, each linking to the
  owning matter). The search box lives in `NavBar.tsx` itself (visible on
  every authenticated page, not just a dedicated search page) and navigates
  to `/search?q=...` on submit.
  `auth/AuthContext.tsx` holds `{user, loading, login, register, logout}`
  (backed by `auth/tokenStore.ts`'s plain `localStorage` get/set/clear, not
  React state, so `api/client.ts` can read the token without importing React);
  `api/client.ts` attaches `Authorization: Bearer <token>` to every request
  and exposes a tiny `onUnauthorized` pub-sub so a 401 from *any* call
  clears the session immediately, not just the one currently in flight.
  Clause-review persistence is split by call site: `QuickAnalyzePage` still
  uses `hooks/useReviewedClauses.ts` (client-only `Set<number>`, resets on
  reload — it carries no audit meaning), while `MatterDocumentCard` uses the
  new `hooks/usePersistedClauseReviews.ts` (hits
  `GET/POST/DELETE /matters/{id}/documents/{id}/review...`, exposes a
  `reviewerFor(index)` resolver so `ClauseListItem` can render a "Reviewed
  by X" byline). No state library, no UI kit — still deliberately minimal
  beyond the router and this one auth context.

# Legal Document Intelligence

AI tools to accelerate contract review, eDiscovery classification, and court
docket monitoring for legal teams. See [CLAUDE.md](CLAUDE.md) for the full
project brief, build order, and conventions.

## Status

Build order steps 1-8 are done: document ingestion, a baseline
clause-extraction model (Colab-trained), rule-based risk-flagging on top of
extraction, a 3-class document-type classification model (Contract / Email /
Other, also Colab-trained), docket monitoring against the free
CourtListener/RECAP API, a review interface with case/matter
organization — analyze a document or track a docket under a "matter" and
its results persist there for later review — a downloadable per-matter
PDF report for handing to stakeholders without app access, and RBAC + an
audit trail (JWT-based login, 3 roles, permission enforcement on every
route, clause-review persistence with a reviewer byline). Quick, un-saved
analysis is still available too (`/quick-analyze` in the frontend).

**Caveat on step 8's audit scope**: the audit log records login/logout,
matter creation, and clause-review actions — not every action (document
analysis, docket checks, and report downloads are not logged). Encryption
at rest for stored documents/results is explicitly deferred, tracked as a
separate future decision.

**Caveat:** the classifier's "Other" class is a placeholder proxy (trained on
generic news-article text), not a validated eDiscovery document-type
category — see "Document classification model" below.

Build order step 9 (testing/QA) is in progress: `scripts/eval_models.py`
measures both trained models against reconstructed validation data — see
"Measured accuracy" under each model below and the full
[model-eval-report.md](docs/model-eval-report.md). It originally found weak
recall (20-30%) on Uncapped Liability and Non-Compete; that's since been
mitigated (not fully fixed — see below) by lowering the model's null-answer
threshold specifically for those two categories, and a new
`possible_negation` warning flag catches a related false-positive pattern
(surface-level phrase matches that ignore negation, e.g. "Neither Party may
terminate... for convenience"). A manual QA pass and expanded automated test
coverage — the other half of step 9 — are still open.

## Setup

```
python -m venv venv
venv\Scripts\activate      # Windows
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt
```

`torch` is installed separately from the CPU-only index first — this avoids
pulling in large CUDA packages this machine doesn't need (see hardware
constraint below).

### Clause-extraction model

Train the baseline model in `notebooks/02_baseline_clause_extraction_colab.ipynb`
(runs on Google Colab's free GPU — see that notebook for instructions). Once
it downloads `clause_extraction_model.zip`, unzip it into:

```
models/clause-extraction-baseline/
```

`POST /documents/extract-clauses` will not work without this — it fails fast
with a clear error if the model folder is missing.

**Measured accuracy** (via `python -m scripts.eval_models`, full results in
[docs/model-eval-report.md](docs/model-eval-report.md); see that script's
docstring for the "best-checkpoint validation, not held-out test" caveat):
Governing Law is strong (EM 0.95, F1 0.95, finds the clause when present 100%
of the time). Termination for Convenience is decent (EM 0.75, F1 0.78, 80%
has-answer recall).

Uncapped Liability and Non-Compete originally had weak has-answer recall
(20-30%) — real clauses were being missed more often than found, while
"no clause found" on true negatives was ~100% reliable. `clause_extractor.py`
now applies a lower, per-category null-answer threshold
(`NULL_MARGIN_THRESHOLD`) for just these two categories, tuned data-driven
via `scripts/eval_models.py --calibrate` (not guessed — see
[docs/threshold-calibration-report.md](docs/threshold-calibration-report.md)
for the full sweep). Confirmed effect: Uncapped Liability recall 20%→60%
(EM/F1 also improved: 0.60/0.60→0.60/0.72), Non-Compete recall 30%→50% (EM/F1
0.60/0.62→0.70/0.72), no-answer accuracy held at 100% for both in this run
(the larger calibration sample suggests Non-Compete's true no-answer accuracy
sits closer to ~93% — a small, deliberate precision cost for a large recall
gain). **This is a mitigation, not a fix**: recall is meaningfully better but
still well under 100% — treat a "no clause found" result for these two
categories with real but reduced skepticism, and expect a somewhat higher
false-positive rate on them too (a genuine tradeoff, now visible to reviewers
via each match's existing confidence band — a mitigated-threshold match on a
category that's actually clean tends to come back at very low confidence,
e.g. `LOW`, not `HIGH`).

**Negation false positives**: the extractor can match on surface phrasing
without registering negation (e.g. flagging "Neither Party may terminate...
for convenience" as an affirmative Termination for Convenience clause). Every
`ClauseMatch` now carries a `possible_negation` flag (regex heuristic, not a
model) set when the match is preceded by or begins with negation language
("shall not", "neither party may", etc.) — surfaced in the UI as a
"⚠ possible negation — verify" badge. It never suppresses a match (a false
negative here just means no warning shown, same as before this existed); it
only adds a reviewer-facing signal.

### Document classification model

Train the baseline model in `notebooks/03_document_classification_colab.ipynb`
(runs on Google Colab's free GPU — see that notebook for instructions). Once
it downloads `document_classification_model.zip`, unzip it into:

```
models/document-classification-baseline/
```

`POST /documents/classify` will not work without this — it fails fast with a
clear error if the model folder is missing.

**Caveat:** the 3 classes are Contract, Email, and Other. "Other" is trained
on generic news-article text as an explicit placeholder — no clean public
dataset of generic business memos/letters/invoices exists yet. Treat it as
"not a contract, not an email," not as a validated eDiscovery category.

**Measured accuracy**: 0.99 accuracy / 0.99 macro-F1 across all 3 classes
(see [docs/model-eval-report.md](docs/model-eval-report.md)). Read this
generously — distinguishing a contract from an email from a random news
article is an easy version of the real triage task; it says less about how
the model would perform on genuinely ambiguous eDiscovery documents (memos,
letters, invoices) than the number suggests, per the "Other" caveat above.

### Docket monitoring

Uses the free [CourtListener/RECAP API](https://www.courtlistener.com/) to
track a federal court docket and detect new entries. Sign up for a free
account and generate a token at
https://www.courtlistener.com/profile/api-token/, then set it in `.env`:

```
COURTLISTENER_API_TOKEN=your-token-here
```

Endpoints:
- `POST /dockets/track` — body `{"courtlistener_docket_id": <id>, "matter_id": null}`,
  where `<id>` is the number in a CourtListener docket URL (e.g.
  `https://www.courtlistener.com/docket/69510553/...` → `69510553`).
- `GET /dockets` — list tracked dockets.
- `POST /dockets/{id}/check` — check for new docket entries since the last
  check; records an alert if any are found.
- `GET /dockets/{id}/alerts` — alert history for a tracked docket.

**CourtListener's free tier is limited to 5 requests/minute, 50/hour,
125/day** — this integration is on-demand only by design (no background
polling); don't script a loop calling `/check`. A docket with enough entries
to span several pages can hit that limit on its own within a single check —
the client retries automatically on a 429, so this just means a check on a
large docket may take a few minutes rather than failing.

State is stored in a local SQLite file (`legalintel.db` by default,
gitignored) — shared with matters (see below).

### Matters / case organization

A "matter" is a case/project you organize documents and dockets under.

- `POST /matters` — body `{"name": "...", "description": null}`.
- `GET /matters` — list matters.
- `GET /matters/{id}` — a matter plus its analyzed documents and tracked dockets.

Pass an integer `matter_id` to `POST /documents/parse`, `/extract-clauses`,
or `/classify` (or to `POST /dockets/track`) to save the result under that
matter — it becomes visible in `GET /matters/{id}` and, in the frontend, on
that matter's page. Omit `matter_id` and behavior is unchanged from before:
fully ephemeral, nothing saved (this is what `/quick-analyze` in the
frontend does).

- `GET /matters/{id}/report` — download a PDF report summarizing the
  matter's analyzed documents and tracked dockets/alerts, for handing to a
  client or partner who doesn't have access to this app. Like the AI
  outputs it summarizes, treat it as a first-pass artifact for attorney
  review, not a final work product — the PDF itself carries that
  disclaimer.

**One-time step if you have an existing local `legalintel_docket.db` from
before this feature**: delete it. The database was renamed to `legalintel.db`
and `tracked_dockets.matter_id` changed from free text to a real reference —
it's gitignored, disposable local cache, not real data.

## Authentication / RBAC

Every route except `GET /health` requires a bearer token. Set a signing
secret in `.env` (generate one, don't hand-pick it):

```
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

**One-time step if you have an existing local `legalintel.db` from before
this feature**: delete it. RBAC added new tables (`users`, `audit_log`,
`clause_reviews`) and a `matters.created_by` column with no migration
framework in place yet — it's gitignored, disposable local cache, not real
data.

There's no public registration endpoint by design — bootstrap the first
account (an attorney, since only attorneys can create other users) with the
CLI script:

```
python -m scripts.create_admin --email you@firm.com --name "Jane Attorney"
```

It prompts for a password (min. 8 characters) and writes directly to
`legalintel.db`, bypassing the API. Log in via the frontend's `/login` page,
or directly:

```
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@firm.com", "password": "..."}'
```

Send the returned `access_token` as `Authorization: Bearer <token>` on
subsequent requests (8-hour expiry, no refresh token). Once logged in as an
attorney, create paralegal/support-staff accounts via `POST /auth/users` or
the frontend's `/admin` page.

**Permission matrix:**

| Action | Attorney | Paralegal | Support staff |
|---|---|---|---|
| View matters, dockets, documents, audit log entries you're allowed to see | ✅ | ✅ | ✅ (read-only) |
| Create matters; upload/analyze documents; track dockets; mark clauses reviewed | ✅ | ✅ | ❌ |
| Delete a matter | ✅ | ❌ | ❌ |
| Create users; view the audit log | ✅ | ❌ | ❌ |

`get_current_user` re-checks `is_active` against the database on every
request rather than trusting a role baked into the token, so deactivating a
user takes effect immediately without a token blacklist.

## Run the API

```
uvicorn app.main:app --reload
```

Then `POST` a `.pdf` or `.docx` file to `http://127.0.0.1:8000/documents/parse`
to extract text, to `http://127.0.0.1:8000/documents/extract-clauses` to also
run the trained clause-extraction model against it (requires the model to be
downloaded and unzipped locally — see "Clause-extraction model" above), or to
`http://127.0.0.1:8000/documents/classify` to run the document-type
classifier (requires "Document classification model" above).

## Frontend

The React frontend lives in `frontend/`. It talks to the API over CORS (see
`Settings.cors_allow_origins` in `app/core/config.py`) rather than a
dev-server proxy.

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. It expects the backend running at
http://127.0.0.1:8000 by default; override with `VITE_API_BASE_URL` (see
`frontend/.env.example`) if needed.

Routes: `/` (public landing page), `/login` (sign in — every route below
requires an active session and redirects here otherwise), `/dashboard`
(create/browse matters), `/matters/:matterId` (a matter's review page —
upload/analyze into it, browse persisted results with reviewer bylines,
track dockets, download a PDF report, delete the matter if you're an
attorney), `/quick-analyze` (the original one-off flow — analyze a document
without saving it anywhere), `/admin` (attorney-only — create users, view
the audit log), `/search` (search box lives in the nav bar on every page —
finds matters, documents by filename/content, and tracked dockets).

## Run tests

```
pytest
```

## Deployment

Build-order step 10. Targets [Render](https://render.com) via the
`render.yaml` blueprint at the repo root, which provisions two services: the
FastAPI backend (with a persistent disk for the SQLite file) and the React
frontend as a static site. The same general approach (a Python web service +
a persistent disk + a static site) works on Railway/Fly.io too, just without
the one-click blueprint.

**The trained model checkpoints (~510MB combined) can't be committed to
git**, so they're loaded from your own Hugging Face Hub account in
production instead of a local folder — `clause_extractor._load_model` and
`document_classifier._load_model` both check for a local folder first
(unchanged local-dev behavior) and, if it's not there, try loading the same
string as a Hub repo id.

```
hf auth login   # paste a token from huggingface.co/settings/tokens (write access) -
                 # older huggingface_hub versions use `huggingface-cli login` instead
python -m scripts.upload_models_to_hub --username yourname
python -m scripts.upload_models_to_hub --username yourname --private  # keep them private
```

This prints the two repo ids to set as `CLAUSE_MODEL_DIR` and
`DOCUMENT_CLASSIFICATION_MODEL_DIR` in the deployment environment. If you
used `--private`, the deployed backend also needs an `HF_TOKEN` env var (a
"read" token is enough) to fetch them - `render.yaml` already has a slot for
it, `sync: false`.

**Steps:**
1. Run the upload script above and note the two repo ids.
2. In Render: New → Blueprint → point it at this repo. Review the two
   services it proposes before creating them.
3. The backend defaults to Render's free plan (512MB RAM) — not enough to
   hold two transformer models + PyTorch at once. After the first deploy,
   upgrade the backend service's plan to one with at least ~2GB RAM via its
   Settings tab.
4. Fill in the env vars `render.yaml` marks `sync: false` (they're
   deliberately not in the file — secrets and deployment-specific values):
   `JWT_SECRET_KEY`, `COURTLISTENER_API_TOKEN`, `CLAUSE_MODEL_DIR`,
   `DOCUMENT_CLASSIFICATION_MODEL_DIR`, and `HF_TOKEN` (only if the repos are
   private) on the backend; `VITE_API_BASE_URL` on the frontend (set once
   the backend's URL is known); `CORS_ALLOW_ORIGINS` on the backend as a
   JSON list once the frontend's URL is known, e.g.
   `["https://legalintel-frontend.onrender.com"]`.
5. Bootstrap the first attorney account against the deployed backend —
   Render's dashboard has a "Shell" tab for the web service:
   `python -m scripts.create_admin --email you@firm.com --name "..."`.
6. Smoke-test the deployed app end-to-end (see "Deployment procedure" in
   `docs/Legal-Document-Intelligence-Technical-Documentation.pdf` for the
   full checklist).

See that same PDF for the recommended architecture and a cost estimate
(~$22-68/month depending on tier) — written for a raw-VPS deployment, so
treat the Render/PaaS cost as directionally similar rather than identical,
since the RAM this app needs (for two loaded transformer models) is the
main cost driver either way, not the platform choice.

### Alternative: shared cPanel / LiteSpeed hosting

The live client deployment runs on shared cPanel hosting (CloudLinux +
LiteSpeed), not Render. This path is fiddlier but needs no card and no VPS.
Key facts learned doing it, so the next deploy is faster:

- **cPanel's "Setup Python App" (Phusion Passenger) cannot run this app.**
  Passenger is WSGI-only; FastAPI is ASGI, and the `a2wsgi` bridge
  (`passenger_wsgi.py`) silently hangs inside LiteSpeed's LSAPI worker.
  Instead, run real uvicorn as a standalone background process and reverse-proxy
  to it from `.htaccess`:
  - `~/legalintel/` — the repo (via cPanel Git Version Control). `chmod 755
    ~/legalintel` (cPanel creates it `700`; the web server can't traverse it).
  - Virtualenv (Python 3.12): `pip install --only-binary=:all: -r
    requirements.txt` then `pip install -e .` — `/tmp` is mounted `noexec` so
    any source build fails; `--only-binary` forces wheels.
  - `~/legalintel/.env` holds all config (uvicorn started via `nohup` does
    **not** inherit cPanel's Python-App env vars): `JWT_SECRET_KEY`,
    `COURTLISTENER_API_TOKEN`, `CLAUSE_MODEL_DIR`,
    `DOCUMENT_CLASSIFICATION_MODEL_DIR`, `HF_TOKEN`, `DB_PATH`, and the four
    `*_NUM_THREADS=1` vars (OpenBLAS otherwise spawns a thread per host core
    and segfaults under the account's process limit).
  - `~/legalintel/keepalive.sh` — `curl -sf http://127.0.0.1:30001/health ||
    nohup .../bin/uvicorn app.main:app --host 127.0.0.1 --port 30001
    --workers 1 >> uvicorn.log 2>&1 &`. Cron: `*/3 * * * *
    /home/<acct>/legalintel/keepalive.sh` (shared hosting has no systemd).
  - `~/public_html/<app-path>/.htaccess` — the API proxy, replacing the
    CloudLinux-generated Passenger block (keep a `.htaccess.passenger` backup):
    ```
    RewriteEngine On
    RewriteRule ^(.*)$ http://127.0.0.1:30001/$1 [P,L]
    ```
- **Frontend** builds locally (server has no Node): `VITE_API_BASE_URL=<public
  API URL>` then `npm run build`. Transfer `frontend/dist/` to the server via
  a throwaway git branch (`git add -f frontend/dist` past `.gitignore`, push,
  then `git archive <branch> frontend/dist | tar -x` on the server) and copy
  its contents into `~/public_html/`. Its `.htaccess` there does SPA fallback
  to `index.html` and **must** exclude the API path so the proxy still wins:
  ```
  RewriteEngine On
  RewriteCond %{REQUEST_URI} !^/<app-path>/
  RewriteCond %{REQUEST_FILENAME} !-f
  RewriteCond %{REQUEST_FILENAME} !-d
  RewriteRule ^ /index.html [L]
  ```
- **numpy is pinned to `1.26.4`** in `requirements.txt` — numpy 2.x's SIMD
  dispatcher crashes on CloudLinux/CageFS. Deployment target must be Python
  3.10–3.12 (1.26.4 has no 3.13 wheel).

## Notes

- All model fine-tuning happens in Google Colab, not locally (see
  hardware-constraint section of CLAUDE.md). Locally we only run inference
  and non-ML pipeline code such as document parsing.
- Uploaded documents are always parsed from a temporary file that's deleted
  immediately after. The original file itself is never persisted — only
  structured analysis results (parsed text / clauses+risk / classification)
  are saved, and only when a `matter_id` is given. Encrypting that stored
  data at rest is deliberately deferred (see "Authentication / RBAC" above).

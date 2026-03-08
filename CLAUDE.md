# Split App — Codebase Reference

A personal web app for two users to review AMEX transactions, split expenses, and push them to Splitwise. Includes a memory system that learns split preferences per merchant over time.

---

## Project Structure

```
split-app/
├── backend/               # FastAPI backend (deployed to Fly.io)
├── frontend/              # React + Vite frontend (deployed to Netlify)
├── .github/workflows/     # CI/CD (auto-deploys backend on push to main)
└── netlify.toml           # Netlify frontend build config
```

---

## Tech Stack

### Backend
- **FastAPI** 0.129.0 with Uvicorn
- **SQLAlchemy** 2.0 ORM + **Alembic** migrations
- **SQLite** (Postgres-ready schema)
- **Authlib** for Google OAuth
- **itsdangerous** session cookies (HttpOnly, 7-day expiry)
- **requests** for Splitwise REST API

### Frontend
- **React** 19 + **Vite**
- **BlueprintJS** 6 (UI components)
- **React Router** 7
- **Axios** (withCredentials for cookie auth)
- **TypeScript**

---

## Key Files

### Backend
| Path | Purpose |
|------|---------|
| `backend/app/main.py` | App init, CORS, session middleware |
| `backend/app/config.py` | Settings from env vars |
| `backend/app/models.py` | SQLAlchemy models |
| `backend/app/schemas.py` | Pydantic schemas |
| `backend/app/database.py` | DB engine + session factory |
| `backend/app/auth.py` | Session token sign/verify |
| `backend/app/routes/auth_routes.py` | `/auth/*` endpoints |
| `backend/app/routes/transaction_routes.py` | `/transactions/*` endpoints |
| `backend/app/utils/normalization.py` | AMEX description → merchant keys |
| `backend/app/utils/suggestion.py` | Recency-weighted split suggestion |
| `backend/app/utils/calculations.py` | Split amount math |
| `backend/app/utils/splitwise.py` | Splitwise API wrapper |
| `backend/alembic/versions/0001_initial_schema.py` | DB schema |
| `backend/alembic/versions/0002_seed_users.py` | Seeds 2 users from env vars |
| `backend/scripts/match_amex_to_splitwise.py` | Local script: match AMEX CSV to Splitwise history → enriched CSV |

### Frontend
| Path | Purpose |
|------|---------|
| `frontend/src/App.tsx` | Root routing |
| `frontend/src/context/AuthContext.tsx` | Auth state (React Context) |
| `frontend/src/components/ProtectedRoute.tsx` | Auth guard |
| `frontend/src/components/AppShell.tsx` | Nav + layout |
| `frontend/src/pages/LoginPage.tsx` | Google OAuth entry |
| `frontend/src/pages/DashboardPage.tsx` | Upload CSV + transaction history |
| `frontend/src/pages/ReviewPage.tsx` | Review splits + confirm to Splitwise |
| `frontend/src/api/client.ts` | Axios base client |
| `frontend/src/api/auth.ts` | Auth API calls |
| `frontend/src/api/transactions.ts` | Transaction API calls |
| `frontend/src/types.ts` | Shared TypeScript types |
| `frontend/src/utils/calculations.ts` | Split calculation helpers |

---

## Database Schema

### `users`
- `id`, `email` (unique), `splitwise_user_id`, `amex_account_number`, `created_at`
- Only 2 rows. Seeded by Alembic migration from env vars.

### `transactions`
- `id`, `amex_reference` (unique), `date`, `description_raw`, `description_normalized`
- `merchant_key`, `sub_merchant_key` (nullable)
- `amount` (decimal 10,2), `category`
- `card_member` (name on card), `account_number` (e.g. `-XXXXX`, used to identify payer)
- `uploaded_by` (fk users), `synced` (bool), `splitwise_expense_id`, `created_at`

### `split_history`
- `id`, `transaction_id` (fk), `merchant_key`, `sub_merchant_key`
- `split_type` (enum), `percent_you`, `exact_you`, `created_at`
- Every confirmed Splitwise push writes a row here automatically.

---

## Split Types

```python
equal         # 50/50
full_you      # You owe all
full_other    # Other person owes all
percent       # You owe total * (percent_you / 100)
exact         # You owe exact_you
personal      # Skip Splitwise, record in history only
already_added # Skip Splitwise AND history (already in Splitwise manually)
```

---

## Split Suggestion Algorithm

1. Query `split_history` by priority, stopping at first non-empty result:
   - merchant + sub_merchant + amount_bucket
   - merchant + sub_merchant
   - merchant + amount_bucket
   - merchant only
   - default `equal`
2. Score rows with exponential decay: `weight = exp(-0.3 * rank)` (rank 0 = most recent)
3. Sum weights per split_type; highest wins
4. `confidence = winning_score / total_score`

## Amount Buckets

Transactions are bucketed by amount for more precise suggestions (e.g. a $12 Amazon charge vs a $150 Amazon charge may have different split patterns):

| Bucket | Range |
|--------|-------|
| `xs` | < $20 |
| `sm` | $20 – $75 |
| `md` | $75 – $250 |
| `lg` | $250+ |

Defined in `backend/app/utils/normalization.py → amount_to_bucket()`. Stored in `split_history.amount_bucket`. Migration 0006 backfills existing rules automatically from the linked transaction amount.

---

## API Endpoints

### Auth (`/auth`)
- `GET /auth/login` — Redirect to Google OAuth (accepts `?next=` for localhost redirect)
- `GET /auth/callback` — OAuth callback; redirects to `/finalize?token=...`
- `GET /auth/finalize` — Exchange short-lived token for `auth_session` cookie
- `POST /auth/logout` — Clear session cookie
- `GET /auth/me` — Returns current user or 401

### Transactions (`/transactions`)
- `POST /transactions/upload` — Upload AMEX CSV; returns unsynced transactions with suggestions (10 MB limit)
- `GET /transactions/` — List unsynced transactions with split suggestions
- `GET /transactions/history` — Synced transactions (paginated, 25/page)
- `GET /transactions/last-date` — Date of most recent transaction
- `POST /transactions/{id}/confirm` — Confirm split, push to Splitwise, record history
- `POST /transactions/import-historical?confirm=wipe` — Wipe all data and bulk-import from enriched CSV (see below)
- `DELETE /transactions/pending` — Delete all unsynced transactions
- `GET /transactions/fetch-amex?start_date=YYYY-MM-DD` — (dev-only) Fetch AMEX CSV via Chrome cookies, returns raw CSV

---

## Environment Variables

### Backend (`.env` or Fly.io secrets)
```
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=<session signing key>
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
FRONTEND_URL=https://<netlify-url>
SPLITWISE_API_KEY=
SPLITWISE_GROUP_ID=
USER_1_EMAIL=
USER_1_SPLITWISE_ID=
USER_1_AMEX_ACCOUNT=-XXXXX
USER_2_EMAIL=
USER_2_SPLITWISE_ID=
USER_2_AMEX_ACCOUNT=-YYYYY
HISTORY_WINDOW=10       # optional, default 10
DECAY_LAMBDA=0.3        # optional, default 0.3
```

### Frontend
```
VITE_API_BASE_URL=           # empty — all API calls use relative paths, proxied to fly.dev
VITE_API_DIRECT_URL=https://split-app-api.fly.dev  # used only for full-page OAuth redirect
```

### Dev-only (backend `.env`)
```
AMEX_ACCOUNT_KEY=            # AMEX account key for local CSV fetch
DEV_AUTO_LOGIN_EMAIL=        # (optional) skip Google OAuth for local dev
```

---

## Proxy Architecture

All API calls (`/auth/*`, `/transactions/*`) are proxied through the same origin as the
frontend so that auth cookies are first-party (avoids cross-site cookie blocks).

| Environment | Proxy | Config |
|-------------|-------|--------|
| Dev (Vite) | `/auth`, `/transactions` → `https://split-app-api.fly.dev` | `vite.config.ts` |
| Dev (Vite) | `/api` → `http://localhost:8000` (local-only endpoints) | `vite.config.ts` |
| Prod (Netlify) | `/auth/*`, `/transactions/*` → `https://split-app-api.fly.dev` | `netlify.toml` |

The OAuth login redirect (`window.location.href`) goes directly to fly.dev via
`VITE_API_DIRECT_URL` because OAuth callbacks must hit fly.dev's real hostname.

---

## Merchant Normalization

Raw AMEX descriptions are normalized:
1. Lowercase, strip numbers and special chars, collapse whitespace
2. Platform-specific rules extract `merchant_key` and `sub_merchant_key`:
   - `GRUBHUB*JOES PIZZA 239182` → merchant=`grubhub`, sub=`joes`
   - Handles AplPay, TST, SQ, PayPal, Doordash prefixes
3. `sub_merchant_key` is null when not extractable

---

## CSV Upload

`POST /transactions/upload` accepts an AMEX CSV. It:
- Detects reference column flexibly (Reference, Reference #, Ref #, etc.)
- Parses dates as MM/DD/YYYY, amounts handling commas
- Skips amounts ≤ 0 (credits/payments)
- Skips duplicate `amex_reference` values (deduplication)
- Returns unsynced transactions with split suggestions

---

## Historical Import

Used to seed the database from past AMEX + Splitwise data.

### Step 1 — Generate enriched CSV (run locally)
```bash
cd backend
python scripts/match_amex_to_splitwise.py --amex amex.csv --out enriched.csv --group-id <id>
```
Config (`SPLITWISE_API_KEY`, `USER_1/2_AMEX_ACCOUNT`, `USER_1/2_SPLITWISE_ID`) read from `backend/.env`.

For each AMEX charge the script:
- Matches Splitwise expenses by amount (±2¢) and date (±5 days, configurable)
- Derives `split_type` from the payer's `owed_share` in the matched expense
- Marks unmatched charges as `personal`; leaves ambiguous matches blank

Output columns added: `split_type`, `percent_you`, `exact_you`, `splitwise_expense_id`

### Step 2 — Import via API
```bash
POST /transactions/import-historical
```
- **Wipes all `split_history` and `transactions` rows first**
- Imports every charge as `synced=True`
- Creates a `split_history` rule for every row with a known `split_type`
- Blank `split_type` rows are imported as transactions only (no rule)
- Returns `{ inserted, rules_created, skipped }`

---

## Payer Detection

AMEX CSV includes an "Account #" field (e.g., `-XXXXX`). The backend maps this to `users.amex_account_number` to determine who paid, so Splitwise expenses are created with the correct payer.

---

## Deployment

### Backend → Fly.io
- Region: `lax`, 1 shared CPU, 256 MB RAM
- Container starts with: `alembic upgrade head && uvicorn app.main:app ...`
- Auto-deployed via GitHub Actions on push to `main` (changes under `backend/`)

### Frontend → Netlify
- Builds from `frontend/`, publishes `dist/`
- SPA routing: all paths → `index.html`
- Auto-deployed by Netlify on push to `main`

---

## Local Dev

```bash
# Single command (starts backend + frontend, opens browser)
./dev.sh           # fetch-only mode: only /transactions/fetch-amex exposed locally
./dev.sh --full    # full mode: all backend routes exposed for code testing
```

Or manually:
```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### AMEX Auto-Fetch (dev only)

The "Fetch from AMEX" button on the dashboard (dev mode only):
1. Calls local backend `GET /transactions/fetch-amex` which reads Chrome's AMEX cookies via `browser_cookie3`
2. Returns raw CSV text
3. Frontend uploads CSV to prod backend's `POST /transactions/upload`
4. If AMEX session expired (401), shows callout to log in at americanexpress.com and retry

### FETCH_ONLY Mode

When `FETCH_ONLY=true` (default in `dev.sh`), a middleware blocks all local backend routes
except `/transactions/fetch-amex`. Pass `--full` to `dev.sh` to disable this and test all routes locally.

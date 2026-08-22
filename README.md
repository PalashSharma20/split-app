# Split App

A personal web app for two users to review AMEX transactions, add shared expenses, and see the current settle-up amount. Learns split preferences per merchant over time.

## How it works

1. Export a CSV from AMEX and upload it
2. Review each transaction — the app suggests a split based on past history
3. Save splits to the app's local shared-expense ledger
4. Add cash or other non-AMEX expenses directly, then settle the displayed net amount
5. The app remembers your choices and improves suggestions over time

## Tech stack

- **Backend** — FastAPI + SQLAlchemy + SQLite (Postgres in prod), deployed to Fly.io
- **Frontend** — React 19 + TypeScript + BlueprintJS, deployed to Netlify
- **Auth** — Google OAuth with signed session cookies

## Local development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in your secrets
alembic upgrade head
uvicorn app.main:app --reload
```

Runs at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs at `http://localhost:5173`. API calls are proxied to the backend automatically via Vite config.

## Environment variables

Copy `backend/.env.example` and fill in:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Session signing key (any random string) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth app credentials |
| `USER_1_EMAIL` / `USER_2_EMAIL` | Email addresses of the two users |
| `USER_1_AMEX_ACCOUNT` / `USER_2_AMEX_ACCOUNT` | Last 5 digits of each AMEX account (e.g. `-12345`) |

## Deployment

- **Backend** auto-deploys to Fly.io on push to `main` (only when `backend/` files change)
- **Frontend** auto-deploys to Netlify on push to `main`

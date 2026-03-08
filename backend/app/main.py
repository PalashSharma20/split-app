import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routes import transaction_routes, auth_routes

_is_prod = settings.FRONTEND_URL.startswith("https://")

if _is_prod and settings.SECRET_KEY == "dev-secret-change-me":
    raise RuntimeError("SECRET_KEY must be set to a secure value in production")

app = FastAPI(title="Split App")

# Only allow localhost origins in dev; in prod only the deployed frontend URL is needed.
_origins: set[str] = set()
if not _is_prod:
    _origins.update({"http://localhost:5173", "http://localhost:3000"})
if settings.FRONTEND_URL:
    _origins.add(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
)

app.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
app.include_router(transaction_routes.router, prefix="/transactions", tags=["transactions"])

# In fetch-only mode, block every route except the AMEX proxy and dev-login.
# Run dev.sh with --full to disable this and expose all routes for local testing.
_FETCH_ONLY_ALLOWED = {"/transactions/fetch-amex"}

if os.getenv("FETCH_ONLY"):
    @app.middleware("http")
    async def fetch_only_guard(request: Request, call_next):
        if request.method != "OPTIONS" and request.url.path not in _FETCH_ONLY_ALLOWED:
            return JSONResponse({"detail": "Not available in fetch-only mode"}, status_code=404)
        return await call_next(request)

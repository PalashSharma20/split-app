from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routes import transaction_routes, auth_routes

app = FastAPI(title="Split App")

_origins = {"http://localhost:5173", "http://localhost:3000"}
if settings.FRONTEND_URL:
    _origins.add(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
)

app.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
app.include_router(transaction_routes.router, prefix="/transactions", tags=["transactions"])

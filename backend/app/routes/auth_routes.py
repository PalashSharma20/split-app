from fastapi import APIRouter, Request, Depends, HTTPException, Query
from urllib.parse import urlparse
from fastapi.responses import JSONResponse, RedirectResponse
from authlib.integrations.starlette_client import OAuth
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.orm import Session

from app.config import settings
from app.auth import create_session, get_current_user
from app.database import get_db
from app.models import User

# Short-lived token used to hand off identity from fly.dev callback → frontend → /auth/finalize
_finalize_serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="finalize-auth")


router = APIRouter()

oauth = OAuth()

oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login")
async def login(request: Request, next: str = Query(default=None)):
    redirect_uri = str(request.url_for("auth_callback"))
    # Allow localhost override so local dev redirects back to localhost after OAuth
    parsed = urlparse(next) if next else None
    if parsed and parsed.scheme in ("http", "https") and parsed.hostname == "localhost":
        request.session["next_url"] = next
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    user_info = token["userinfo"]

    email = user_info["email"]

    if email not in settings.ALLOWED_EMAILS:
        raise HTTPException(status_code=403, detail="Unauthorized email")

    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)

    # Issue a short-lived one-time token and redirect to the frontend finalize page.
    # The frontend exchanges this token via the Netlify proxy so the auth_session cookie
    # ends up on the frontend's domain (fixes iOS Safari ITP cross-site cookie blocking).
    finalize_token = _finalize_serializer.dumps(email)
    next_url = request.session.pop("next_url", None) or settings.FRONTEND_URL
    return RedirectResponse(url=f"{next_url}/finalize?token={finalize_token}")


@router.get("/finalize")
async def finalize_auth(token: str = Query(...), db: Session = Depends(get_db)):
    """Exchange a short-lived finalize token for an auth_session cookie."""
    try:
        email = _finalize_serializer.loads(token, max_age=120)  # 2-minute window
    except (SignatureExpired, BadSignature):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = db.query(User).filter_by(email=email).first()
    if not user:
        raise HTTPException(status_code=403, detail="Unauthorized")

    signed_email = create_session(email)
    is_prod = settings.FRONTEND_URL.startswith("https://")
    response = JSONResponse({"email": email})
    response.set_cookie(
        key="auth_session",
        value=signed_email,
        httponly=True,
        secure=is_prod,
        samesite="none" if is_prod else "lax",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )
    return response


@router.post("/logout")
def logout():
    response = JSONResponse({"message": "Logged out"})
    is_prod = settings.FRONTEND_URL.startswith("https://")
    response.delete_cookie(
        "auth_session",
        httponly=True,
        secure=is_prod,
        samesite="none" if is_prod else "lax",
        path="/",
    )
    return response



@router.get("/me")
def me(user=Depends(get_current_user)):
    return {
        "email": user.email
    }



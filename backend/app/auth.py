from fastapi import Request, HTTPException, Depends
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.config import settings
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

_SESSION_MAX_AGE = 7 * 24 * 60 * 60  # 7 days, must match cookie max_age

serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="session")


def create_session(email: str):
    return serializer.dumps({"email": email})


def verify_session(token: str):
    try:
        return serializer.loads(token, max_age=_SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("auth_session")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    data = verify_session(token)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid session")

    user = db.query(User).filter_by(email=data["email"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user

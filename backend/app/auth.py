from fastapi import Request, HTTPException, Depends
from itsdangerous import URLSafeSerializer, BadSignature
from app.config import settings
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

serializer = URLSafeSerializer(settings.SECRET_KEY, salt="session")


def create_session(email: str):
    return serializer.dumps({"email": email})


def verify_session(token: str):
    try:
        return serializer.loads(token)
    except BadSignature:
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

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # Google OAuth
    GOOGLE_CLIENT_ID: str | None = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str | None = os.getenv("GOOGLE_CLIENT_SECRET")

    # Derived from USER_1_EMAIL / USER_2_EMAIL if present, else fall back to
    # the legacy ALLOWED_EMAILS env var so existing .env files keep working.
    _user1_email: str | None = os.getenv("USER_1_EMAIL")
    _user2_email: str | None = os.getenv("USER_2_EMAIL")
    ALLOWED_EMAILS: set[str] = (
        {e for e in [_user1_email, _user2_email] if e}
        or {e.strip() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()}
    )

    # Frontend URL (used for post-login redirect)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")


    # Splitwise
    SPLITWISE_API_KEY: str | None = os.getenv("SPLITWISE_API_KEY")
    SPLITWISE_GROUP_ID: str = os.getenv("SPLITWISE_GROUP_ID", "94331017")

    # Suggestion engine tuning
    HISTORY_WINDOW: int = int(os.getenv("HISTORY_WINDOW", "10"))
    DECAY_LAMBDA: float = float(os.getenv("DECAY_LAMBDA", "0.3"))


settings = Settings()

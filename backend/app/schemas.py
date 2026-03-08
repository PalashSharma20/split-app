from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date as DateType
from app.models import SplitType


class SplitSuggestion(BaseModel):
    split_type: SplitType
    percent_you: Optional[float] = None
    exact_you: Optional[float] = None
    you_owed: float
    other_owed: float
    confidence: Optional[float] = None  # None = no history; 0.0–1.0 otherwise


class TransactionOut(BaseModel):
    id: int
    date: DateType
    description_raw: str
    amount: str
    merchant_key: str
    sub_merchant_key: Optional[str]
    card_member: Optional[str]   # who paid — from the CSV "Card Member" column
    you_paid: bool               # True if current user is the card member who paid
    suggestion: SplitSuggestion

    model_config = {"from_attributes": True}


class ConfirmRequest(BaseModel):
    split_type: SplitType
    percent_you: Optional[float] = None
    exact_you: Optional[float] = None

    @field_validator("percent_you")
    @classmethod
    def validate_percent(cls, v, info):
        if info.data.get("split_type") == SplitType.percent:
            if v is None:
                raise ValueError("percent_you is required for split_type=percent")
            if not (0 <= v <= 100):
                raise ValueError("percent_you must be between 0 and 100")
        return v

    @field_validator("exact_you")
    @classmethod
    def validate_exact(cls, v, info):
        if info.data.get("split_type") == SplitType.exact:
            if v is None:
                raise ValueError("exact_you is required for split_type=exact")
            if v < 0:
                raise ValueError("exact_you cannot be negative")
        return v


class ConfirmResponse(BaseModel):
    splitwise_expense_id: Optional[str] = None  # None for personal transactions
    you_owed: float
    other_owed: float


class UploadResult(BaseModel):
    inserted: int
    skipped: int
    transactions: list[TransactionOut]


class SyncedTransactionOut(BaseModel):
    id: int
    date: DateType
    description_raw: str
    amount: str
    merchant_key: str
    sub_merchant_key: Optional[str]
    card_member: Optional[str]
    splitwise_expense_id: Optional[str]
    split_type: Optional[SplitType]  # from most recent split_history row

    model_config = {"from_attributes": True}


class SyncedPage(BaseModel):
    items: list[SyncedTransactionOut]
    total: int
    has_more: bool


class ImportResult(BaseModel):
    inserted: int
    rules_created: int
    skipped: int

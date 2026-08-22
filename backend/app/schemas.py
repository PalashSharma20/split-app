from pydantic import BaseModel, field_validator, model_validator
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
    splitwise_expense_id: Optional[str] = None  # Retained for historical imports.
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
    paid_by: str
    splitwise_expense_id: Optional[str]
    split_type: Optional[SplitType]  # from most recent split_history row
    percent_you: Optional[float] = None
    exact_you: Optional[float] = None
    you_paid: bool
    source: str  # amex | custom | recurring

    model_config = {"from_attributes": True}


class SyncedPage(BaseModel):
    items: list[SyncedTransactionOut]
    total: int
    has_more: bool


class ImportResult(BaseModel):
    inserted: int
    rules_created: int
    skipped: int


class BalanceResult(BaseModel):
    """
    All-time net AMEX balance per person (charges + payments) based on which
    card each transaction appeared on.
    """
    your_amex_total: float
    other_amex_total: float
    your_name: str
    other_name: str
    # Net shared-expense settlement. Positive amount is always owed by the
    # named person to the other person.
    settlement_from: Optional[str] = None
    settlement_to: Optional[str] = None
    settlement_amount: float = 0.0


class MarkSettlementRequest(BaseModel):
    settled_on: Optional[DateType] = None
    note: Optional[str] = None


class CustomExpenseRequest(ConfirmRequest):
    description: str
    amount: float
    date: DateType
    payer: str  # "you" or "other"

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        if not v.strip():
            raise ValueError("description is required")
        return v.strip()

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("amount must be greater than zero")
        return v

    @field_validator("payer")
    @classmethod
    def validate_payer(cls, v):
        if v not in {"you", "other"}:
            raise ValueError("payer must be 'you' or 'other'")
        return v

    @model_validator(mode="after")
    def validate_share_is_within_expense(self):
        if self.split_type == SplitType.exact and self.exact_you is not None and self.exact_you > self.amount:
            raise ValueError("exact_you cannot exceed the expense amount")
        return self


class RecurringExpenseRequest(ConfirmRequest):
    description: str
    amount: float
    start_date: DateType
    cadence: str  # weekly | monthly
    payer: str  # you | other

    @field_validator("description")
    @classmethod
    def validate_recurring_description(cls, v):
        if not v.strip():
            raise ValueError("description is required")
        return v.strip()

    @field_validator("amount")
    @classmethod
    def validate_recurring_amount(cls, v):
        if v <= 0:
            raise ValueError("amount must be greater than zero")
        return v

    @field_validator("cadence")
    @classmethod
    def validate_cadence(cls, v):
        if v not in {"weekly", "monthly"}:
            raise ValueError("cadence must be weekly or monthly")
        return v

    @field_validator("payer")
    @classmethod
    def validate_recurring_payer(cls, v):
        if v not in {"you", "other"}:
            raise ValueError("payer must be 'you' or 'other'")
        return v

    @model_validator(mode="after")
    def validate_recurring_share(self):
        if self.split_type in {SplitType.personal, SplitType.already_added}:
            raise ValueError("Recurring expenses must be shared expenses")
        if self.split_type == SplitType.exact and self.exact_you is not None and self.exact_you > self.amount:
            raise ValueError("exact_you cannot exceed the expense amount")
        return self


class RecurringExpenseOut(BaseModel):
    id: int
    description: str
    amount: float
    start_date: DateType
    cadence: str
    active: bool
    payer: str
    split_type: SplitType
    percent_you: Optional[float] = None
    exact_you: Optional[float] = None


class EditTransactionRequest(ConfirmRequest):
    payer: str  # you | other
    description: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[DateType] = None

    @field_validator("payer")
    @classmethod
    def validate_edit_payer(cls, v):
        if v not in {"you", "other"}:
            raise ValueError("payer must be 'you' or 'other'")
        return v

    @field_validator("description")
    @classmethod
    def validate_edit_description(cls, v):
        if v is not None and not v.strip():
            raise ValueError("description cannot be empty")
        return v.strip() if v is not None else None

    @field_validator("amount")
    @classmethod
    def validate_edit_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError("amount must be greater than zero")
        return v

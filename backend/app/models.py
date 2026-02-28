from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, Numeric, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class SplitType(str, enum.Enum):
    equal = "equal"
    full_you = "full_you"
    full_other = "full_other"
    percent = "percent"
    exact = "exact"
    personal = "personal"       # not split; skips Splitwise but recorded in history
    already_added = "already_added"  # already in Splitwise; skips push AND history


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    splitwise_user_id = Column(String, nullable=True)
    amex_account_number = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="uploader")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    amex_reference = Column(String, unique=True, index=True, nullable=False)
    date = Column(Date, nullable=False)
    description_raw = Column(String, nullable=False)
    description_normalized = Column(String, nullable=False)
    merchant_key = Column(String, index=True, nullable=False)
    sub_merchant_key = Column(String, nullable=True, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    category = Column(String, nullable=True)
    card_member = Column(String, nullable=True)      # "PALASH SHARMA" / "ANUSHKA R MAGANTI"
    account_number = Column(String, nullable=True)   # "-51010" — used to infer who paid
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    synced = Column(Boolean, default=False, nullable=False)
    splitwise_expense_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    uploader = relationship("User", back_populates="transactions")
    split_history = relationship("SplitHistory", back_populates="transaction")


class SplitHistory(Base):
    """
    Audit trail and memory source. Written on every confirmed push (including personal).
    merchant_key and sub_merchant_key are denormalised so the suggestion engine can
    query without joining to transactions.
    """
    __tablename__ = "split_history"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    merchant_key = Column(String, nullable=False)
    sub_merchant_key = Column(String, nullable=True)
    split_type = Column(Enum(SplitType), nullable=False)
    percent_you = Column(Numeric(5, 2), nullable=True)
    exact_you = Column(Numeric(10, 2), nullable=True)
    amount_bucket = Column(String, nullable=True)  # xs / sm / md / lg
    created_at = Column(DateTime, default=datetime.utcnow)

    transaction = relationship("Transaction", back_populates="split_history")

    __table_args__ = (
        Index("ix_split_history_merchant", "merchant_key"),
        Index("ix_split_history_merchant_sub", "merchant_key", "sub_merchant_key"),
        Index("ix_split_history_created_at", "created_at"),
    )

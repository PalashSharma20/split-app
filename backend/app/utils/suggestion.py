"""
Recency-weighted split suggestion engine.

Queries split_history for the last N confirmed splits for the same merchant
(and optionally sub-merchant), then picks the winning split type using
exponential decay weighting so recent behaviour dominates.
"""
import math
from collections import defaultdict
from sqlalchemy.orm import Session

from app.models import SplitHistory, SplitType
from app.config import settings
from app.utils.calculations import calculate_split
from app.utils.normalization import amount_to_bucket


def suggest_split(
    db: Session,
    merchant_key: str,
    sub_merchant_key: str | None,
    amount: float,
) -> dict:
    """
    Return a suggestion dict with keys:
        split_type, percent_you, exact_you, you_owed, other_owed, confidence
    """
    rows = _fetch_history(db, merchant_key, sub_merchant_key, amount_to_bucket(amount))

    if not rows:
        you_owed, other_owed = calculate_split(SplitType.equal, amount)
        return {
            "split_type": SplitType.equal,
            "percent_you": None,
            "exact_you": None,
            "you_owed": you_owed,
            "other_owed": other_owed,
            "confidence": None,
        }

    winner, confidence, percent_you, exact_you = _score(rows)

    you_owed, other_owed = calculate_split(
        winner, amount, percent_you=percent_you, exact_you=exact_you
    )

    return {
        "split_type": winner,
        "percent_you": percent_you,
        "exact_you": exact_you,
        "you_owed": you_owed,
        "other_owed": other_owed,
        "confidence": confidence,
    }


def _fetch_history(
    db: Session,
    merchant_key: str,
    sub_merchant_key: str | None,
    amount_bucket: str | None = None,
) -> list[SplitHistory]:
    """
    Lookup priority (stops at first non-empty result):
      1. merchant + sub_merchant + bucket
      2. merchant + sub_merchant
      3. merchant + bucket
      4. merchant only
    """
    n = settings.HISTORY_WINDOW

    def _query(**filters):
        # Drop None-valued filters (amount_bucket may be absent on old rows)
        q = db.query(SplitHistory)
        for col, val in filters.items():
            q = q.filter(getattr(SplitHistory, col) == val)
        return q.order_by(SplitHistory.created_at.desc()).limit(n).all()

    if sub_merchant_key:
        if amount_bucket:
            rows = _query(merchant_key=merchant_key, sub_merchant_key=sub_merchant_key, amount_bucket=amount_bucket)
            if rows:
                return rows
        rows = _query(merchant_key=merchant_key, sub_merchant_key=sub_merchant_key)
        if rows:
            return rows

    if amount_bucket:
        rows = _query(merchant_key=merchant_key, amount_bucket=amount_bucket)
        if rows:
            return rows

    return _query(merchant_key=merchant_key)


def _score(rows: list[SplitHistory]) -> tuple:
    """
    Assign exponential-decay weights (most recent = rank 0) and return:
        (winning_split_type, confidence, avg_percent_you, avg_exact_you)
    """
    lam = settings.DECAY_LAMBDA

    scores: dict[str, float] = defaultdict(float)
    weighted_percent: dict[str, float] = defaultdict(float)
    weighted_exact: dict[str, float] = defaultdict(float)

    for rank, row in enumerate(rows):
        w = math.exp(-lam * rank)
        scores[row.split_type] += w

        if row.split_type == SplitType.percent and row.percent_you is not None:
            weighted_percent[row.split_type] += w * float(row.percent_you)

        if row.split_type == SplitType.exact and row.exact_you is not None:
            weighted_exact[row.split_type] += w * float(row.exact_you)

    total = sum(scores.values())
    winner = max(scores, key=scores.get)  # type: ignore[arg-type]
    confidence = round(scores[winner] / total, 3)

    percent_you = None
    exact_you = None

    if winner == SplitType.percent and scores[winner] > 0:
        percent_you = round(weighted_percent[winner] / scores[winner], 2)

    if winner == SplitType.exact and scores[winner] > 0:
        exact_you = round(weighted_exact[winner] / scores[winner], 2)

    return winner, confidence, percent_you, exact_you

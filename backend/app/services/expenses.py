from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import SplitHistory, SplitType, Transaction, User
from app.schemas import ConfirmRequest, ConfirmResponse
from app.utils.calculations import calculate_split
from app.utils.normalization import amount_to_bucket


@dataclass
class ConfirmationError(Exception):
    status_code: int
    detail: str


def confirm_expense(
    db: Session,
    transaction_id: int,
    split: ConfirmRequest,
    current_user: User,
) -> ConfirmResponse:
    """Stage one pending expense confirmation without committing it."""
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise ConfirmationError(404, f"Transaction {transaction_id} was not found")
    if transaction.synced:
        raise ConfirmationError(409, f"Transaction {transaction_id} is already saved")

    transaction.synced = True

    if split.split_type == SplitType.already_added:
        db.flush()
        return ConfirmResponse(you_owed=0.0, other_owed=0.0)

    if split.split_type == SplitType.personal:
        db.add(
            SplitHistory(
                transaction_id=transaction.id,
                merchant_key=transaction.merchant_key,
                sub_merchant_key=transaction.sub_merchant_key,
                split_type=SplitType.personal,
                split_for_user_id=current_user.id,
                amount_bucket=amount_to_bucket(float(transaction.amount)),
            )
        )
        db.flush()
        return ConfirmResponse(you_owed=0.0, other_owed=0.0)

    total = float(transaction.amount)
    if (
        split.split_type == SplitType.exact
        and split.exact_you is not None
        and split.exact_you > abs(total)
    ):
        raise ConfirmationError(
            422,
            f"Exact share for transaction {transaction_id} exceeds its amount",
        )

    try:
        you_owed, other_owed = calculate_split(
            split.split_type,
            total,
            percent_you=split.percent_you,
            exact_you=split.exact_you,
        )
    except ValueError as exc:
        raise ConfirmationError(422, str(exc)) from exc

    if total < 0:
        you_owed, other_owed = abs(you_owed), abs(other_owed)

    db.add(
        SplitHistory(
            transaction_id=transaction.id,
            merchant_key=transaction.merchant_key,
            sub_merchant_key=transaction.sub_merchant_key,
            split_type=split.split_type,
            percent_you=split.percent_you,
            exact_you=split.exact_you,
            split_for_user_id=current_user.id,
            amount_bucket=amount_to_bucket(float(transaction.amount)),
        )
    )
    db.flush()
    return ConfirmResponse(you_owed=you_owed, other_owed=other_owed)

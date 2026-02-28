"""
Split amount calculations.

"you_owed" = your share of the total.
"other_owed" = the other person's share.
Who actually paid (and therefore which direction the debt flows) is determined
at confirm-time using the transaction's account_number, not here.
"""
from app.models import SplitType


def calculate_split(
    split_type: SplitType,
    total: float,
    percent_you: float | None = None,
    exact_you: float | None = None,
) -> tuple[float, float]:
    """
    Returns (you_owed, other_owed) rounded to 2 decimal places.
    For non-personal types the two values always sum to total.
    """
    total = float(total)

    match split_type:
        case SplitType.equal:
            you_owed = round(total / 2, 2)
            other_owed = round(total - you_owed, 2)

        case SplitType.full_you:
            you_owed = round(total, 2)
            other_owed = 0.0

        case SplitType.full_other:
            you_owed = 0.0
            other_owed = round(total, 2)

        case SplitType.percent:
            if percent_you is None:
                raise ValueError("percent_you required for split_type=percent")
            you_owed = round(total * percent_you / 100, 2)
            other_owed = round(total - you_owed, 2)

        case SplitType.exact:
            if exact_you is None:
                raise ValueError("exact_you required for split_type=exact")
            you_owed = round(float(exact_you), 2)
            other_owed = round(total - you_owed, 2)

        case SplitType.personal:
            you_owed = 0.0
            other_owed = 0.0

        case _:
            raise ValueError(f"Unknown split_type: {split_type}")

    return you_owed, other_owed

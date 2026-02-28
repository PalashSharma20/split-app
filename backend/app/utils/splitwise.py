"""
Thin wrapper around the Splitwise REST API.
"""
import datetime
import requests
from fastapi import HTTPException

SPLITWISE_BASE = "https://secure.splitwise.com/api/v3.0"


def create_expense(
    api_key: str,
    group_id: str,
    description: str,
    total: float,
    payer_user_id: str,    # the person who physically paid (AMEX card holder)
    other_user_id: str,
    payer_owed: float,     # payer's share of the total
    other_owed: float,     # other person's share of the total
    date: datetime.date | None = None,
) -> str:
    """
    Creates a Splitwise expense inside the configured group.
    Returns the expense ID as a string.
    The payer is recorded as having fronted the full amount.
    """
    headers = {"Authorization": f"Bearer {api_key}"}

    data = {
        "cost": f"{round(total, 2):.2f}",
        "description": description,
        "currency_code": "USD",
        "group_id": group_id,
        "date": (date or datetime.date.today()).strftime("%Y-%m-%dT00:00:00Z"),
        "users__0__user_id": payer_user_id,
        "users__0__paid_share": f"{round(total, 2):.2f}",
        "users__0__owed_share": f"{round(payer_owed, 2):.2f}",
        "users__1__user_id": other_user_id,
        "users__1__paid_share": "0.00",
        "users__1__owed_share": f"{round(other_owed, 2):.2f}",
    }

    try:
        resp = requests.post(
            f"{SPLITWISE_BASE}/create_expense",
            headers=headers,
            data=data,
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Splitwise API error: {exc}") from exc

    body = resp.json()
    expenses = body.get("expenses", [])
    if not expenses:
        raise HTTPException(status_code=502, detail="Splitwise returned no expense")

    return str(expenses[0]["id"])

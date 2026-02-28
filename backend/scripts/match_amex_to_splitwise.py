#!/usr/bin/env python3
"""Match AMEX transactions to Splitwise expenses and produce an enriched CSV.

For each AMEX transaction:
  - Matched to 1+ Splitwise expense(s) with a consistent split → split_type inferred
  - Matched to multiple Splitwise expenses with conflicting splits → split_type left blank
  - Not matched to any Splitwise expense → split_type = personal

Output CSV has all original AMEX columns plus:
  split_type            — equal | full_you | full_other | percent | personal | (blank)
  percent_you           — filled when split_type=percent
  exact_you             — leave blank for script output; fill manually for exact splits
  splitwise_expense_id  — Splitwise expense ID when matched

Usage:
  # Run from backend/ directory with venv active
  python scripts/match_amex_to_splitwise.py --amex amex.csv --out output.csv

Config is read from backend/.env (or the parent .env) and can be overridden via flags:
  --api-key        SPLITWISE_API_KEY
  --group-id       SPLITWISE_GROUP_ID
  --user1-amex     USER_1_AMEX_ACCOUNT  (e.g. -51010)
  --user1-sw       USER_1_SPLITWISE_ID
  --user2-amex     USER_2_AMEX_ACCOUNT
  --user2-sw       USER_2_SPLITWISE_ID
  --date-tolerance Days ±N for date matching (default: 5)
"""

import argparse
import csv
import io
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

import requests

# Load .env from backend/ (parent of scripts/) if dotenv is available
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

SPLITWISE_BASE = "https://secure.splitwise.com/api/v3.0"

# 2-cent tolerance for floating-point rounding in amounts and share comparisons
_CENT = Decimal("0.02")

# AMEX has used several names for the reference column across export versions
_REFERENCE_CANDIDATES = ("Reference", "Reference #", "Ref #", "Ref", "Transaction ID")


# ---------------------------------------------------------------------------
# Splitwise API helpers
# ---------------------------------------------------------------------------

def fetch_splitwise_expenses(api_key: str, group_id: str) -> list[dict]:
    """Fetch ALL non-deleted expenses for the group (handles pagination)."""
    headers = {"Authorization": f"Bearer {api_key}"}
    all_expenses: list[dict] = []
    offset = 0
    limit = 1000

    while True:
        resp = requests.get(
            f"{SPLITWISE_BASE}/get_expenses",
            headers=headers,
            params={"group_id": group_id, "offset": offset, "limit": limit},
            timeout=30,
        )
        if not resp.ok:
            sys.exit(f"ERROR: Splitwise API returned {resp.status_code}: {resp.text[:300]}")

        batch = resp.json().get("expenses", [])
        non_deleted = [e for e in batch if not e.get("deleted_at")]
        all_expenses.extend(non_deleted)

        if len(batch) < limit:
            break
        offset += limit

    return all_expenses


def _parse_sw_date(date_str: str):
    """Parse Splitwise date string '2024-01-15T00:00:00Z' → datetime.date."""
    return datetime.strptime(date_str[:10], "%Y-%m-%d").date()


def derive_split_type(
    expense: dict,
    payer_sw_id: str,
    total: Decimal,
) -> tuple[str, Optional[float]]:
    """
    Determine split_type and optional percent_you from the AMEX payer's perspective.

    The AMEX payer is "you" — we look at their owed_share relative to total:
      - owed ≈ 0            → full_other  (you paid on AMEX but they owe everything)
      - owed ≈ total        → full_you    (you paid and you owe everything — personal charge)
      - owed ≈ total/2      → equal
      - anything else       → percent     (returns percent_you as a float)

    Returns ("", None) if the payer is not found in the expense's user list.
    """
    payer_entry: Optional[dict] = None
    other_entry: Optional[dict] = None

    for ue in expense.get("users", []):
        # user_id can be nested under "user" or directly on the entry
        uid = str(ue.get("user_id") or ue.get("user", {}).get("id", ""))
        if uid == str(payer_sw_id):
            payer_entry = ue
        else:
            other_entry = ue

    if payer_entry is None:
        return "", None

    you_owed = Decimal(str(payer_entry["owed_share"]))
    other_owed = (
        Decimal(str(other_entry["owed_share"]))
        if other_entry
        else (total - you_owed)
    )

    if you_owed <= _CENT:
        return "full_other", None
    if other_owed <= _CENT:
        return "full_you", None
    if abs(you_owed - other_owed) <= _CENT:
        return "equal", None

    # Non-standard percent split
    pct = float(
        (you_owed / total * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    return "percent", pct


# ---------------------------------------------------------------------------
# AMEX CSV helpers
# ---------------------------------------------------------------------------

def load_amex_csv(path: str) -> tuple[list[dict], str, list[str]]:
    """Load AMEX CSV. Returns (rows, ref_col_name, fieldnames)."""
    with open(path, "rb") as f:
        raw = f.read()

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = list(reader.fieldnames or [])
    fieldnames_set = set(fieldnames)

    ref_col = next((c for c in _REFERENCE_CANDIDATES if c in fieldnames_set), None)
    if ref_col is None:
        sys.exit(
            f"ERROR: Could not find a reference column in the CSV.\n"
            f"Expected one of: {_REFERENCE_CANDIDATES}\n"
            f"Columns found:   {sorted(fieldnames_set)}"
        )

    rows = list(reader)
    return rows, ref_col, fieldnames


# ---------------------------------------------------------------------------
# Core matching logic
# ---------------------------------------------------------------------------

def match_amex_to_splitwise(
    amex_rows: list[dict],
    ref_col: str,
    sw_expenses: list[dict],
    user1_amex: str,
    user1_sw: str,
    user2_amex: str,
    user2_sw: str,
    date_tolerance: int,
) -> list[dict]:
    """
    For each AMEX row find matching Splitwise expense(s) and determine split_type.

    Returns enriched rows — every input row is present with three extra fields:
      split_type, percent_you, splitwise_expense_id
    Credits / payments (amount ≤ 0) are included but left blank.
    """
    amex_account_map = {
        user1_amex.strip(): user1_sw.strip(),
        user2_amex.strip(): user2_sw.strip(),
    }

    enriched: list[dict] = []
    stats = {"matched": 0, "personal": 0, "ambiguous": 0, "skipped": 0}

    for row in amex_rows:
        blank_row = {**row, "split_type": "", "percent_you": "", "exact_you": "", "splitwise_expense_id": ""}

        # Parse amount — skip credits/payments and bad rows
        try:
            amount_raw = float(row["Amount"].strip().replace(",", ""))
        except (ValueError, KeyError):
            stats["skipped"] += 1
            enriched.append(blank_row)
            continue

        if amount_raw <= 0:
            stats["skipped"] += 1
            enriched.append(blank_row)
            continue

        amount = Decimal(str(round(amount_raw, 2)))

        # Parse date
        try:
            amex_date = datetime.strptime(row["Date"].strip(), "%m/%d/%Y").date()
        except (ValueError, KeyError):
            print(f"  WARN: Skipping row with unparseable date: {row.get('Date')!r}")
            stats["skipped"] += 1
            enriched.append(blank_row)
            continue

        # Determine payer's Splitwise ID from AMEX account number
        account_num = row.get("Account #", "").strip()
        payer_sw_id = amex_account_map.get(account_num)
        if payer_sw_id is None:
            # Fall back to user1 if account not recognised; a warning is printed once
            payer_sw_id = user1_sw.strip()

        # Find Splitwise expenses within amount + date tolerance
        date_min = amex_date - timedelta(days=date_tolerance)
        date_max = amex_date + timedelta(days=date_tolerance)

        candidates: list[dict] = []
        for exp in sw_expenses:
            try:
                sw_amount = Decimal(str(round(float(exp["cost"]), 2)))
            except (ValueError, KeyError, TypeError):
                continue

            if abs(sw_amount - amount) > _CENT:
                continue

            try:
                sw_date = _parse_sw_date(exp["date"])
            except (ValueError, KeyError):
                continue

            if not (date_min <= sw_date <= date_max):
                continue

            candidates.append(exp)

        if not candidates:
            stats["personal"] += 1
            enriched.append({**row, "split_type": "personal", "percent_you": "", "exact_you": "", "splitwise_expense_id": ""})
            continue

        # Derive split type for each candidate from the payer's perspective
        resolved: list[tuple[str, Optional[float], str]] = []  # (split_type, percent_you, expense_id)
        for exp in candidates:
            st, pct = derive_split_type(exp, payer_sw_id, amount)
            if st:  # empty string means payer not found in this expense — skip it
                resolved.append((st, pct, str(exp["id"])))

        if not resolved:
            # Payer not found in any candidate — treat as personal
            stats["personal"] += 1
            enriched.append({**row, "split_type": "personal", "percent_you": "", "exact_you": "", "splitwise_expense_id": ""})
            continue

        # Check for conflicting split types across candidates
        unique_types = {r[0] for r in resolved}
        if len(unique_types) > 1:
            stats["ambiguous"] += 1
            enriched.append(blank_row)  # leave blank — user must review
            continue

        # All candidates agree — use the first
        split_type, percent_you, sw_id = resolved[0]
        stats["matched"] += 1
        enriched.append({
            **row,
            "split_type": split_type,
            "percent_you": f"{percent_you:.2f}" if percent_you is not None else "",
            "exact_you": "",  # script uses percent for non-standard splits; set manually if needed
            "splitwise_expense_id": sw_id,
        })

    total_tx = sum(1 for r in amex_rows if _is_positive_amount(r))
    print(f"\nMatching results ({total_tx} charge rows):")
    print(f"  Matched to Splitwise:  {stats['matched']}")
    print(f"  Personal (no match):   {stats['personal']}")
    print(f"  Ambiguous (blank):     {stats['ambiguous']}")
    print(f"  Skipped (credits/err): {stats['skipped']}")

    return enriched


def _is_positive_amount(row: dict) -> bool:
    try:
        return float(row["Amount"].strip().replace(",", "")) > 0
    except (ValueError, KeyError):
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--amex", required=True, metavar="PATH", help="Input AMEX CSV file")
    parser.add_argument("--out", required=True, metavar="PATH", help="Output enriched CSV file")
    parser.add_argument(
        "--api-key",
        default=os.getenv("SPLITWISE_API_KEY"),
        metavar="KEY",
        help="Splitwise API key (env: SPLITWISE_API_KEY)",
    )
    parser.add_argument(
        "--group-id",
        default=os.getenv("SPLITWISE_GROUP_ID"),
        metavar="ID",
        help="Splitwise group ID (env: SPLITWISE_GROUP_ID)",
    )
    parser.add_argument(
        "--user1-amex",
        default=os.getenv("USER_1_AMEX_ACCOUNT"),
        metavar="ACCT",
        help="User 1 AMEX account number, e.g. -51010 (env: USER_1_AMEX_ACCOUNT)",
    )
    parser.add_argument(
        "--user1-sw",
        default=os.getenv("USER_1_SPLITWISE_ID"),
        metavar="ID",
        help="User 1 Splitwise user ID (env: USER_1_SPLITWISE_ID)",
    )
    parser.add_argument(
        "--user2-amex",
        default=os.getenv("USER_2_AMEX_ACCOUNT"),
        metavar="ACCT",
        help="User 2 AMEX account number (env: USER_2_AMEX_ACCOUNT)",
    )
    parser.add_argument(
        "--user2-sw",
        default=os.getenv("USER_2_SPLITWISE_ID"),
        metavar="ID",
        help="User 2 Splitwise user ID (env: USER_2_SPLITWISE_ID)",
    )
    parser.add_argument(
        "--date-tolerance",
        type=int,
        default=5,
        metavar="DAYS",
        help="Days ± allowed between AMEX date and Splitwise date (default: 5)",
    )

    args = parser.parse_args()

    # Validate required config
    required = {
        "--api-key / SPLITWISE_API_KEY": args.api_key,
        "--group-id / SPLITWISE_GROUP_ID": args.group_id,
        "--user1-amex / USER_1_AMEX_ACCOUNT": args.user1_amex,
        "--user1-sw / USER_1_SPLITWISE_ID": args.user1_sw,
        "--user2-amex / USER_2_AMEX_ACCOUNT": args.user2_amex,
        "--user2-sw / USER_2_SPLITWISE_ID": args.user2_sw,
    }
    missing = [label for label, val in required.items() if not val]
    if missing:
        sys.exit("ERROR: Missing required config:\n" + "\n".join(f"  {m}" for m in missing))

    # Load AMEX CSV
    print(f"Reading AMEX CSV: {args.amex}")
    amex_rows, ref_col, fieldnames = load_amex_csv(args.amex)
    charge_count = sum(1 for r in amex_rows if _is_positive_amount(r))
    print(f"  {len(amex_rows)} total rows, {charge_count} charges, reference column: '{ref_col}'")

    # Fetch Splitwise expenses
    print(f"\nFetching Splitwise expenses for group {args.group_id}...")
    sw_expenses = fetch_splitwise_expenses(args.api_key, args.group_id)
    print(f"  {len(sw_expenses)} non-deleted expenses")

    # Match
    print(f"\nMatching with date tolerance ±{args.date_tolerance} days...")
    enriched = match_amex_to_splitwise(
        amex_rows,
        ref_col,
        sw_expenses,
        args.user1_amex,
        args.user1_sw,
        args.user2_amex,
        args.user2_sw,
        args.date_tolerance,
    )

    # Write output — preserve original column order, append new columns at end
    out_fieldnames = fieldnames + [
        f for f in ("split_type", "percent_you", "exact_you", "splitwise_expense_id")
        if f not in fieldnames
    ]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched)

    print(f"\nOutput written to: {args.out}")
    print("Review the file, adjust any blank or incorrect split_type values, then")
    print("upload to POST /transactions/import-historical to seed the database.")


if __name__ == "__main__":
    main()

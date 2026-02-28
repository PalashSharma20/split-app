from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
import csv
import io
from datetime import datetime

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import SplitHistory, SplitType, Transaction, User
from app.schemas import ConfirmRequest, ConfirmResponse, ImportResult, SyncedPage, SyncedTransactionOut, TransactionOut, UploadResult
from app.utils.calculations import calculate_split
from app.utils.normalization import amount_to_bucket, parse_description
from app.utils.splitwise import create_expense
from app.utils.suggestion import suggest_split

router = APIRouter()

# Columns that must be present. Category is optional on some AMEX exports.
AMEX_REQUIRED_COLUMNS = {"Date", "Description", "Amount", "Reference"}

# AMEX has used several names for the reference column across export versions.
_REFERENCE_CANDIDATES = ("Reference", "Reference #", "Ref #", "Ref", "Transaction ID")


# ---------------------------------------------------------------------------
# POST /transactions/upload
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadResult)
async def upload_csv(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contents = await file.read()
    try:
        text = contents.decode("utf-8-sig")  # handle BOM from Excel/AMEX exports
    except UnicodeDecodeError:
        text = contents.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = set(reader.fieldnames or [])

    ref_col = next((c for c in _REFERENCE_CANDIDATES if c in fieldnames), None)

    required = (AMEX_REQUIRED_COLUMNS - {"Reference"}) | ({"Reference"} if ref_col else set())
    missing = required - fieldnames
    if missing or ref_col is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"CSV is missing required columns: {sorted(missing or {'Reference (or similar)'})}. "
                f"Columns detected: {sorted(fieldnames)}"
            ),
        )

    inserted = 0
    skipped = 0
    new_transactions: list[Transaction] = []

    for row in reader:
        # Skip credits and payments (negative or zero amounts)
        try:
            amount = float(row["Amount"].strip().replace(",", ""))
        except ValueError:
            continue
        if amount <= 0:
            continue

        # AMEX wraps Reference values in single quotes — strip them
        ref = row[ref_col].strip().strip("'")
        if not ref:
            continue

        if db.query(Transaction).filter_by(amex_reference=ref).first():
            skipped += 1
            continue

        normalized, merchant, sub = parse_description(row["Description"])
        if not merchant:
            merchant = "unknown"

        try:
            tx_date = datetime.strptime(row["Date"].strip(), "%m/%d/%Y").date()
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Unrecognised date format: {row['Date']!r} (expected MM/DD/YYYY)",
            )

        tx = Transaction(
            amex_reference=ref,
            date=tx_date,
            description_raw=row["Description"].strip(),
            description_normalized=normalized,
            merchant_key=merchant,
            sub_merchant_key=sub,
            amount=str(amount),
            category=row.get("Category", "").strip() or None,
            card_member=row.get("Card Member", "").strip() or None,
            account_number=row.get("Account #", "").strip() or None,
            uploaded_by=current_user.id,
            synced=False,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)

        inserted += 1
        new_transactions.append(tx)

    results = [_tx_to_out(db, tx, current_user) for tx in new_transactions]
    return UploadResult(inserted=inserted, skipped=skipped, transactions=results)


# ---------------------------------------------------------------------------
# GET /transactions/   — list unsynced with suggestions
# ---------------------------------------------------------------------------

@router.get("/history", response_model=SyncedPage)
def list_synced(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from sqlalchemy import func

    base = db.query(Transaction).filter_by(synced=True)
    total = base.count()

    rows = (
        base
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Fetch most recent split_history entry per transaction in one query
    tx_ids = [tx.id for tx in rows]
    latest_history: dict[int, SplitHistory] = {}
    if tx_ids:
        # subquery: max(id) per transaction_id
        subq = (
            db.query(func.max(SplitHistory.id).label("id"))
            .filter(SplitHistory.transaction_id.in_(tx_ids))
            .group_by(SplitHistory.transaction_id)
            .subquery()
        )
        for h in db.query(SplitHistory).filter(SplitHistory.id.in_(subq)):
            latest_history[h.transaction_id] = h

    items = [
        SyncedTransactionOut(
            id=tx.id,
            date=tx.date,
            description_raw=tx.description_raw,
            amount=str(tx.amount),
            merchant_key=tx.merchant_key,
            sub_merchant_key=tx.sub_merchant_key,
            card_member=tx.card_member,
            splitwise_expense_id=tx.splitwise_expense_id,
            split_type=latest_history[tx.id].split_type if tx.id in latest_history else None,
        )
        for tx in rows
    ]

    return SyncedPage(items=items, total=total, has_more=(offset + limit) < total)


@router.get("/last-date")
def last_transaction_date(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from sqlalchemy import func
    result = db.query(func.max(Transaction.date)).scalar()
    return {"date": result.isoformat() if result else None}


@router.get("/", response_model=list[TransactionOut])
def list_unsynced(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transactions = (
        db.query(Transaction)
        .filter_by(synced=False)
        .order_by(Transaction.date.asc())
        .all()
    )
    return [_tx_to_out(db, tx, current_user) for tx in transactions]


# ---------------------------------------------------------------------------
# POST /transactions/{id}/confirm   — push to Splitwise (or mark personal)
# ---------------------------------------------------------------------------

@router.post("/{tx_id}/confirm", response_model=ConfirmResponse)
def confirm_transaction(
    tx_id: int,
    body: ConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.synced:
        raise HTTPException(status_code=409, detail="Transaction already synced")

    # Personal — record in history (so we learn the merchant is personal) then done
    if body.split_type == SplitType.personal:
        tx.synced = True
        db.add(SplitHistory(
            transaction_id=tx.id,
            merchant_key=tx.merchant_key,
            sub_merchant_key=tx.sub_merchant_key,
            split_type=SplitType.personal,
            amount_bucket=amount_to_bucket(float(tx.amount)),
        ))
        db.commit()
        return ConfirmResponse(you_owed=0.0, other_owed=0.0)

    # Already added to Splitwise manually — mark synced, no push, no history entry
    if body.split_type == SplitType.already_added:
        tx.synced = True
        db.commit()
        return ConfirmResponse(you_owed=0.0, other_owed=0.0)

    # Resolve both users
    other_user = db.query(User).filter(User.id != current_user.id).first()
    if other_user is None:
        raise HTTPException(status_code=500, detail="Could not find the second user")

    if not current_user.splitwise_user_id or not other_user.splitwise_user_id:
        raise HTTPException(
            status_code=500,
            detail="Splitwise user IDs are not set — populate users.splitwise_user_id.",
        )

    if not settings.SPLITWISE_API_KEY:
        raise HTTPException(status_code=500, detail="SPLITWISE_API_KEY is not configured")

    total = float(tx.amount)
    you_owed, other_owed = calculate_split(
        body.split_type, total,
        percent_you=body.percent_you,
        exact_you=body.exact_you,
    )

    # Determine who actually paid based on which account the charge appeared on.
    # Falls back to current_user if account_number isn't matched to anyone.
    payer, non_payer = _resolve_payer(tx, current_user, other_user)

    # From the payer's perspective: payer_owed is their share, other_owed is non-payer's share.
    # If payer == current_user, you_owed / other_owed map directly.
    # If payer == other_user, the roles are flipped.
    if payer.id == current_user.id:
        payer_owed, non_payer_owed = you_owed, other_owed
    else:
        payer_owed, non_payer_owed = other_owed, you_owed

    expense_id = create_expense(
        api_key=settings.SPLITWISE_API_KEY,
        group_id=settings.SPLITWISE_GROUP_ID,
        description=tx.description_raw,
        total=total,
        payer_user_id=payer.splitwise_user_id,
        other_user_id=non_payer.splitwise_user_id,
        payer_owed=payer_owed,
        other_owed=non_payer_owed,
        date=tx.date,
    )

    tx.synced = True
    tx.splitwise_expense_id = expense_id
    db.add(SplitHistory(
        transaction_id=tx.id,
        merchant_key=tx.merchant_key,
        sub_merchant_key=tx.sub_merchant_key,
        split_type=body.split_type,
        percent_you=body.percent_you,
        exact_you=body.exact_you,
        amount_bucket=amount_to_bucket(float(tx.amount)),
    ))
    db.commit()

    return ConfirmResponse(
        splitwise_expense_id=expense_id,
        you_owed=you_owed,
        other_owed=other_owed,
    )


# ---------------------------------------------------------------------------
# POST /transactions/import-historical — wipe + reload from enriched CSV
# ---------------------------------------------------------------------------

@router.post("/import-historical", response_model=ImportResult)
async def import_historical(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Wipe all transactions and split_history, then bulk-import from an enriched CSV
    produced by scripts/match_amex_to_splitwise.py.

    Expected columns (standard AMEX columns plus):
      split_type            — equal | full_you | full_other | percent | personal | (blank)
      percent_you           — required when split_type=percent
      splitwise_expense_id  — optional; stored on the transaction if present

    All imported transactions are marked synced=True.
    Rows with a known split_type get a corresponding split_history entry (used by
    the suggestion engine). Rows with a blank split_type are imported without history.
    Credits/payments (amount ≤ 0) are skipped.
    """
    contents = await file.read()
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = contents.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = set(reader.fieldnames or [])

    ref_col = next((c for c in _REFERENCE_CANDIDATES if c in fieldnames), None)
    if ref_col is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"CSV is missing a reference column. "
                f"Expected one of {list(_REFERENCE_CANDIDATES)}. "
                f"Columns found: {sorted(fieldnames)}"
            ),
        )

    rows = list(reader)

    # Wipe existing data — split_history first (FK → transactions)
    db.query(SplitHistory).delete(synchronize_session=False)
    db.query(Transaction).delete(synchronize_session=False)
    db.commit()

    valid_split_types = {st.value for st in SplitType} - {SplitType.already_added.value}

    inserted = 0
    rules_created = 0
    skipped = 0
    seen_refs: set[str] = set()  # deduplicate within the CSV itself

    for row in rows:
        # Parse amount — skip credits/payments
        try:
            amount = float(row["Amount"].strip().replace(",", ""))
        except (ValueError, KeyError):
            skipped += 1
            continue
        if amount <= 0:
            skipped += 1
            continue

        ref = row.get(ref_col, "").strip().strip("'")
        if not ref or ref in seen_refs:
            skipped += 1
            continue
        seen_refs.add(ref)

        try:
            tx_date = datetime.strptime(row["Date"].strip(), "%m/%d/%Y").date()
        except (ValueError, KeyError):
            skipped += 1
            continue

        normalized, merchant, sub = parse_description(row["Description"])
        if not merchant:
            merchant = "unknown"

        split_type_raw = row.get("split_type", "").strip().lower()
        percent_you_raw = row.get("percent_you", "").strip()
        exact_you_raw = row.get("exact_you", "").strip()
        sw_expense_id = row.get("splitwise_expense_id", "").strip() or None

        # Validate split type and parse auxiliary values
        split_type: SplitType | None = None
        percent_you: float | None = None
        exact_you: float | None = None
        if split_type_raw and split_type_raw in valid_split_types:
            split_type = SplitType(split_type_raw)
            if split_type == SplitType.percent:
                try:
                    percent_you = float(percent_you_raw)
                except (ValueError, TypeError):
                    # percent_you missing/invalid — fall back to equal rather than skipping
                    split_type = SplitType.equal
            elif split_type == SplitType.exact:
                try:
                    exact_you = float(exact_you_raw)
                except (ValueError, TypeError):
                    # exact_you missing/invalid — fall back to equal
                    split_type = SplitType.equal

        tx = Transaction(
            amex_reference=ref,
            date=tx_date,
            description_raw=row["Description"].strip(),
            description_normalized=normalized,
            merchant_key=merchant,
            sub_merchant_key=sub,
            amount=str(amount),
            category=row.get("Category", "").strip() or None,
            card_member=row.get("Card Member", "").strip() or None,
            account_number=row.get("Account #", "").strip() or None,
            uploaded_by=current_user.id,
            synced=True,
            splitwise_expense_id=sw_expense_id,
        )
        db.add(tx)
        db.flush()  # get tx.id without committing

        if split_type is not None:
            db.add(SplitHistory(
                transaction_id=tx.id,
                merchant_key=merchant,
                sub_merchant_key=sub,
                split_type=split_type,
                percent_you=percent_you,
                exact_you=exact_you,
                amount_bucket=amount_to_bucket(amount),
            ))
            rules_created += 1

        inserted += 1

    db.commit()
    return ImportResult(inserted=inserted, rules_created=rules_created, skipped=skipped)


# ---------------------------------------------------------------------------
# DELETE /transactions/pending   — clear all unsynced transactions
# ---------------------------------------------------------------------------

@router.delete("/pending", status_code=204)
def clear_pending(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    db.query(Transaction).filter_by(synced=False).delete()
    db.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_payer(tx: Transaction, current_user: User, other_user: User) -> tuple[User, User]:
    """
    Return (payer, non_payer) based on account_number matching.
    Falls back to current_user as payer if no match is found.
    """
    if tx.account_number:
        if other_user.amex_account_number and tx.account_number == other_user.amex_account_number:
            return other_user, current_user
        if current_user.amex_account_number and tx.account_number == current_user.amex_account_number:
            return current_user, other_user
    return current_user, other_user


def _you_paid(tx: Transaction, current_user: User, other_user: User) -> bool:
    payer, _ = _resolve_payer(tx, current_user, other_user)
    return payer.id == current_user.id


def _tx_to_out(db: Session, tx: Transaction, current_user: User) -> TransactionOut:
    other_user = db.query(User).filter(User.id != current_user.id).first()

    suggestion_data = suggest_split(db, tx.merchant_key, tx.sub_merchant_key, float(tx.amount))

    from app.schemas import SplitSuggestion
    return TransactionOut(
        id=tx.id,
        date=tx.date,
        description_raw=tx.description_raw,
        amount=str(tx.amount),
        merchant_key=tx.merchant_key,
        sub_merchant_key=tx.sub_merchant_key,
        card_member=tx.card_member,
        you_paid=_you_paid(tx, current_user, other_user) if other_user else True,
        suggestion=SplitSuggestion(**suggestion_data),
    )

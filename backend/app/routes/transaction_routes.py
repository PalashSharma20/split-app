from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import func, case, select
from sqlalchemy.orm import Session
import csv
import io
from datetime import date, datetime, timedelta
import calendar

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import RecurringExpense, Settlement, SplitHistory, SplitType, Transaction, User
from app.schemas import BalanceResult, ConfirmRequest, ConfirmResponse, CustomExpenseRequest, EditTransactionRequest, ImportResult, MarkSettlementRequest, RecurringExpenseOut, RecurringExpenseRequest, SyncedPage, SyncedTransactionOut, TransactionOut, UploadResult
from app.utils.calculations import calculate_split
from app.utils.normalization import amount_to_bucket, is_payment_transaction, parse_description
from app.utils.suggestion import suggest_split
from uuid import uuid4

router = APIRouter()

# Columns that must be present. Category is optional on some AMEX exports.
AMEX_REQUIRED_COLUMNS = {"Date", "Description", "Amount", "Reference"}

# AMEX has used several names for the reference column across export versions.
_REFERENCE_CANDIDATES = ("Reference", "Reference #", "Ref #", "Ref", "Transaction ID")


# ---------------------------------------------------------------------------
# Shared CSV parsing helper
# ---------------------------------------------------------------------------

def _parse_and_insert_csv(
    text: str, current_user: User, db: Session
) -> tuple[int, int, list[Transaction]]:
    """Parse AMEX CSV text, insert new transactions, return (inserted, skipped, new_txs)."""
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
        try:
            amount = float(row["Amount"].strip().replace(",", ""))
        except ValueError:
            continue
        if amount == 0:
            continue

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

        is_payment = is_payment_transaction(row["Description"])

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
            synced=is_payment,  # auto-confirm payments, queue everything else
        )
        db.add(tx)
        db.flush()

        if is_payment:
            db.add(SplitHistory(
                transaction_id=tx.id,
                merchant_key=tx.merchant_key,
                sub_merchant_key=tx.sub_merchant_key,
                split_type=SplitType.personal,
                amount_bucket=amount_to_bucket(float(tx.amount)),
            ))

        db.commit()
        db.refresh(tx)

        inserted += 1
        if not is_payment:
            new_transactions.append(tx)

    return inserted, skipped, new_transactions


# ---------------------------------------------------------------------------
# POST /transactions/upload
# ---------------------------------------------------------------------------

_MAX_CSV_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload", response_model=UploadResult)
async def upload_csv(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contents = await file.read()
    if len(contents) > _MAX_CSV_SIZE:
        raise HTTPException(status_code=413, detail="CSV file exceeds 10 MB limit")
    try:
        text = contents.decode("utf-8-sig")  # handle BOM from Excel/AMEX exports
    except UnicodeDecodeError:
        text = contents.decode("latin-1")

    inserted, skipped, new_transactions = _parse_and_insert_csv(text, current_user, db)
    results = [_tx_to_out(db, tx, current_user) for tx in new_transactions]
    return UploadResult(inserted=inserted, skipped=skipped, transactions=results)


# ---------------------------------------------------------------------------
# POST /transactions/fetch-amex  (dev only)
# ---------------------------------------------------------------------------

@router.get("/fetch-amex")
def fetch_amex(start_date: str = Query(...)):
    """
    Dev-only proxy: fetches the AMEX CSV using Chrome cookies and returns raw CSV.
    The frontend uploads the result to the prod backend — nothing is written locally.
    """
    import requests as _requests
    from datetime import date
    from fastapi.responses import PlainTextResponse

    try:
        datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD format")

    if not settings.AMEX_ACCOUNT_KEY:
        raise HTTPException(status_code=503, detail="AMEX_ACCOUNT_KEY is not set in .env")

    try:
        import browser_cookie3
        jar = browser_cookie3.chrome(domain_name=".americanexpress.com")
        cookies = {c.name: c.value for c in jar}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not read Chrome cookies: {e}")

    end_date = date.today().isoformat()
    url = (
        "https://global.americanexpress.com/api/servicing/v1/financials/documents"
        f"?file_format=csv&limit=ALL&start_date={start_date}&end_date={end_date}"
        f"&additional_fields=true&status=posted"
        f"&account_key={settings.AMEX_ACCOUNT_KEY}&client_id=AmexAPI"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://global.americanexpress.com/dashboard",
        "Origin": "https://global.americanexpress.com",
    }

    try:
        resp = _requests.get(url, cookies=cookies, headers=headers, timeout=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AMEX request failed: {e}")

    body = resp.text
    if resp.status_code != 200 or body.lstrip().startswith("<"):
        raise HTTPException(status_code=401, detail="AMEX session expired — log in at americanexpress.com")

    return PlainTextResponse(content=body, media_type="text/csv")


# ---------------------------------------------------------------------------
# GET /transactions/   — list unsynced with suggestions
# ---------------------------------------------------------------------------

@router.get("/history", response_model=SyncedPage)
def list_synced(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _generate_due_recurring_expenses(db)
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

    other_user = db.query(User).filter(User.id != current_user.id).first()
    items = [
        SyncedTransactionOut(
            id=tx.id,
            date=tx.date,
            description_raw=tx.description_raw,
            amount=str(tx.amount),
            merchant_key=tx.merchant_key,
            sub_merchant_key=tx.sub_merchant_key,
            card_member=tx.card_member,
            paid_by=_user_name(_resolve_payer(tx, current_user, other_user)[0]) if other_user else "You",
            splitwise_expense_id=tx.splitwise_expense_id,
            split_type=latest_history[tx.id].split_type if tx.id in latest_history else None,
            percent_you=float(latest_history[tx.id].percent_you) if tx.id in latest_history and latest_history[tx.id].percent_you is not None else None,
            exact_you=float(latest_history[tx.id].exact_you) if tx.id in latest_history and latest_history[tx.id].exact_you is not None else None,
            you_paid=_you_paid(tx, current_user, other_user) if other_user else True,
            source="recurring" if tx.recurring_expense_id else "custom" if tx.is_custom else "amex",
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
    _generate_due_recurring_expenses(db)
    transactions = (
        db.query(Transaction)
        .filter_by(synced=False)
        .order_by(Transaction.date.asc())
        .all()
    )
    return [_tx_to_out(db, tx, current_user) for tx in transactions]


# ---------------------------------------------------------------------------
# POST /transactions/{id}/confirm   — record in the local ledger
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

    # Legacy historical-import marker — mark synced, no history entry.
    if body.split_type == SplitType.already_added:
        tx.synced = True
        db.commit()
        return ConfirmResponse(you_owed=0.0, other_owed=0.0)

    # Resolve both users
    other_user = db.query(User).filter(User.id != current_user.id).first()
    if other_user is None:
        raise HTTPException(status_code=500, detail="Could not find the second user")

    total = float(tx.amount)
    you_owed, other_owed = calculate_split(
        body.split_type, total,
        percent_you=body.percent_you,
        exact_you=body.exact_you,
    )

    # Determine who actually paid (or received the refund) based on account_number.
    payer, non_payer = _resolve_payer(tx, current_user, other_user)

    # For refunds, flip the payer/non-payer roles so the credit reverses the debt.
    if total < 0:
        payer, non_payer = non_payer, payer
        total = abs(total)
        you_owed, other_owed = abs(you_owed), abs(other_owed)

    tx.synced = True
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
        you_owed=you_owed,
        other_owed=other_owed,
    )


@router.post("/custom", response_model=ConfirmResponse)
def create_custom_expense(
    body: CustomExpenseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add an expense directly to the shared local ledger, outside AMEX."""
    other_user = db.query(User).filter(User.id != current_user.id).first()
    if other_user is None:
        raise HTTPException(status_code=500, detail="Could not find the second user")
    if body.split_type in {SplitType.personal, SplitType.already_added}:
        raise HTTPException(status_code=422, detail="Custom expenses must be shared expenses")

    normalized, merchant, sub = parse_description(body.description)
    payer = current_user if body.payer == "you" else other_user
    tx = Transaction(
        amex_reference=f"custom-{uuid4()}",
        date=body.date,
        description_raw=body.description,
        description_normalized=normalized,
        merchant_key=merchant or "custom",
        sub_merchant_key=sub,
        amount=str(body.amount),
        card_member=_user_name(payer),
        uploaded_by=current_user.id,
        payer_id=payer.id,
        is_custom=True,
        synced=True,
    )
    db.add(tx)
    db.flush()
    db.add(SplitHistory(
        transaction_id=tx.id,
        merchant_key=tx.merchant_key,
        sub_merchant_key=tx.sub_merchant_key,
        split_type=body.split_type,
        percent_you=body.percent_you,
        exact_you=body.exact_you,
        amount_bucket=amount_to_bucket(body.amount),
    ))
    you_owed, other_owed = calculate_split(body.split_type, body.amount, body.percent_you, body.exact_you)
    db.commit()
    return ConfirmResponse(you_owed=you_owed, other_owed=other_owed)


@router.get("/recurring", response_model=list[RecurringExpenseOut])
def list_recurring_expenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    other_user = db.query(User).filter(User.id != current_user.id).first()
    return [
        _recurring_to_out(template, current_user, other_user)
        for template in db.query(RecurringExpense).filter_by(active=True).order_by(RecurringExpense.description).all()
    ]


@router.post("/recurring", response_model=RecurringExpenseOut)
def create_recurring_expense(
    body: RecurringExpenseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    other_user = db.query(User).filter(User.id != current_user.id).first()
    if other_user is None:
        raise HTTPException(status_code=500, detail="Could not find the second user")
    template = RecurringExpense(
        description=body.description,
        amount=str(body.amount),
        start_date=body.start_date,
        cadence=body.cadence,
        payer_id=current_user.id if body.payer == "you" else other_user.id,
        split_type=body.split_type,
        percent_you=body.percent_you,
        exact_you=body.exact_you,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    _generate_due_recurring_expenses(db)
    return _recurring_to_out(template, current_user, other_user)


@router.patch("/recurring/{recurring_id}", response_model=RecurringExpenseOut)
def edit_recurring_expense(
    recurring_id: int,
    body: RecurringExpenseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = db.get(RecurringExpense, recurring_id)
    if template is None or not template.active:
        raise HTTPException(status_code=404, detail="Recurring expense not found")
    other_user = db.query(User).filter(User.id != current_user.id).first()
    if other_user is None:
        raise HTTPException(status_code=500, detail="Could not find the second user")
    template.description = body.description
    template.amount = str(body.amount)
    template.start_date = body.start_date
    template.cadence = body.cadence
    template.payer_id = current_user.id if body.payer == "you" else other_user.id
    template.split_type = body.split_type
    template.percent_you = body.percent_you
    template.exact_you = body.exact_you
    db.commit()
    db.refresh(template)
    _generate_due_recurring_expenses(db)
    return _recurring_to_out(template, current_user, other_user)


@router.delete("/recurring/{recurring_id}", status_code=204)
def delete_recurring_expense(
    recurring_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    template = db.get(RecurringExpense, recurring_id)
    if template is None or not template.active:
        raise HTTPException(status_code=404, detail="Recurring expense not found")
    # Preserve generated occurrences as history; only stop future generation.
    template.active = False
    db.commit()


@router.post("/settlements/mark-settled", response_model=BalanceResult)
def mark_settled(
    body: MarkSettlementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record payment of the currently outstanding net balance."""
    balance = _calculate_balance(db, current_user, generate=False)
    if balance.settlement_amount <= 0 or not balance.settlement_from or not balance.settlement_to:
        raise HTTPException(status_code=422, detail="There is no outstanding settlement to mark as paid")
    other_user = db.query(User).filter(User.id != current_user.id).first()
    from_user = current_user if balance.settlement_from == _user_name(current_user) else other_user
    to_user = current_user if balance.settlement_to == _user_name(current_user) else other_user
    db.add(Settlement(
        from_user_id=from_user.id,
        to_user_id=to_user.id,
        amount=balance.settlement_amount,
        settled_on=body.settled_on or date.today(),
        note=body.note,
    ))
    db.commit()
    return _calculate_balance(db, current_user, generate=False)


@router.patch("/{tx_id}", response_model=ConfirmResponse)
def edit_transaction(
    tx_id: int,
    body: EditTransactionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Correct a ledger entry; recurring edits affect this occurrence only."""
    tx = db.get(Transaction, tx_id)
    if tx is None or not tx.synced:
        raise HTTPException(status_code=404, detail="Saved transaction not found")
    other_user = db.query(User).filter(User.id != current_user.id).first()
    if other_user is None:
        raise HTTPException(status_code=500, detail="Could not find the second user")
    if body.split_type == SplitType.already_added:
        raise HTTPException(status_code=422, detail="Already recorded is only for legacy imports")

    # Imported AMEX records are an audit of the statement, so only their
    # allocation can change. Local entries may be corrected in full.
    if not tx.is_custom and any(value is not None for value in (body.description, body.amount, body.date)):
        raise HTTPException(status_code=422, detail="AMEX amount, date, and description cannot be edited")
    if tx.is_custom:
        if body.description is not None:
            normalized, merchant, sub = parse_description(body.description)
            tx.description_raw = body.description
            tx.description_normalized = normalized
            tx.merchant_key = merchant or "custom"
            tx.sub_merchant_key = sub
        if body.amount is not None:
            tx.amount = str(body.amount)
        if body.date is not None:
            tx.date = body.date

    total = float(tx.amount)
    if body.split_type == SplitType.exact and (body.exact_you is None or body.exact_you > total):
        raise HTTPException(status_code=422, detail="Exact share must not exceed the expense amount")
    try:
        you_owed, other_owed = calculate_split(body.split_type, total, body.percent_you, body.exact_you)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    tx.payer_id = current_user.id if body.payer == "you" else other_user.id
    tx.card_member = _user_name(current_user if body.payer == "you" else other_user)
    db.add(SplitHistory(
        transaction_id=tx.id,
        merchant_key=tx.merchant_key,
        sub_merchant_key=tx.sub_merchant_key,
        split_type=body.split_type,
        percent_you=body.percent_you,
        exact_you=body.exact_you,
        amount_bucket=amount_to_bucket(total),
    ))
    db.commit()
    return ConfirmResponse(you_owed=you_owed, other_owed=other_owed)


@router.delete("/{tx_id}/custom", status_code=204)
def delete_custom_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    tx = db.get(Transaction, tx_id)
    if tx is None or not tx.synced:
        raise HTTPException(status_code=404, detail="Saved transaction not found")
    if not tx.is_custom:
        raise HTTPException(status_code=422, detail="Imported AMEX transactions cannot be deleted")
    if tx.recurring_expense_id:
        raise HTTPException(status_code=422, detail="Delete or change the recurring template instead")
    db.query(SplitHistory).filter_by(transaction_id=tx.id).delete()
    db.delete(tx)
    db.commit()


# ---------------------------------------------------------------------------
# POST /transactions/import-historical — wipe + reload from enriched CSV
# ---------------------------------------------------------------------------

@router.post("/import-historical", response_model=ImportResult)
async def import_historical(
    file: UploadFile,
    confirm: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if confirm != "wipe":
        raise HTTPException(status_code=400, detail="Pass ?confirm=wipe to confirm deleting all data")
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
        try:
            amount = float(row["Amount"].strip().replace(",", ""))
        except (ValueError, KeyError):
            skipped += 1
            continue
        if amount == 0:
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
# GET /transactions/balance
# ---------------------------------------------------------------------------

@router.get("/balance", response_model=BalanceResult)
def get_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sum each person's imported AMEX transactions by card (all-time), plus the
    shared-ledger net settlement. Custom expenses deliberately do not affect AMEX.
    Uses a SQL aggregate so performance stays constant regardless of row count.
    """
    return _calculate_balance(db, current_user, generate=True)


def _calculate_balance(db: Session, current_user: User, generate: bool) -> BalanceResult:
    if generate:
        _generate_due_recurring_expenses(db)
    other_user = db.query(User).filter(User.id != current_user.id).first()
    if other_user is None:
        raise HTTPException(status_code=500, detail="Could not find the second user")

    your_account = current_user.amex_account_number
    other_account = other_user.amex_account_number

    row = db.query(
        func.sum(case((Transaction.account_number == your_account, Transaction.amount), else_=0)).label("your_total"),
        func.sum(case((Transaction.account_number == other_account, Transaction.amount), else_=0)).label("other_total"),
    ).filter(Transaction.synced == True, Transaction.is_custom == False).one()

    latest_history_ids = (
        select(func.max(SplitHistory.id))
        .group_by(SplitHistory.transaction_id)
    )
    histories = (
        db.query(SplitHistory, Transaction)
        .join(Transaction, SplitHistory.transaction_id == Transaction.id)
        .filter(
            SplitHistory.id.in_(latest_history_ids),
            Transaction.synced == True,
            SplitHistory.split_type.notin_([SplitType.personal, SplitType.already_added]),
        )
        .all()
    )
    net_you_owed = 0.0
    for history, tx in histories:
        you_share, other_share = calculate_split(
            history.split_type, float(tx.amount),
            float(history.percent_you) if history.percent_you is not None else None,
            float(history.exact_you) if history.exact_you is not None else None,
        )
        payer, _ = _resolve_payer(tx, current_user, other_user)
        # Positive means the other person owes the current user.
        net_you_owed += other_share if payer.id == current_user.id else -you_share

    for settlement in db.query(Settlement).all():
        if settlement.from_user_id == current_user.id:
            net_you_owed += float(settlement.amount)
        elif settlement.to_user_id == current_user.id:
            net_you_owed -= float(settlement.amount)

    settlement_from = settlement_to = None
    if round(net_you_owed, 2) > 0:
        settlement_from, settlement_to = _user_name(other_user), _user_name(current_user)
    elif round(net_you_owed, 2) < 0:
        settlement_from, settlement_to = _user_name(current_user), _user_name(other_user)

    return BalanceResult(
        your_amex_total=round(float(row.your_total or 0), 2),
        other_amex_total=round(float(row.other_total or 0), 2),
        your_name=_user_name(current_user),
        other_name=_user_name(other_user),
        settlement_from=settlement_from,
        settlement_to=settlement_to,
        settlement_amount=round(abs(net_you_owed), 2),
    )


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
    if tx.payer_id:
        return (current_user, other_user) if tx.payer_id == current_user.id else (other_user, current_user)
    if tx.account_number:
        if other_user.amex_account_number and tx.account_number == other_user.amex_account_number:
            return other_user, current_user
        if current_user.amex_account_number and tx.account_number == current_user.amex_account_number:
            return current_user, other_user
    return current_user, other_user


def _user_name(user: User) -> str:
    return user.display_name or user.email.split("@")[0]


def _recurring_to_out(template: RecurringExpense, current_user: User, other_user: User | None) -> RecurringExpenseOut:
    return RecurringExpenseOut(
        id=template.id,
        description=template.description,
        amount=float(template.amount),
        start_date=template.start_date,
        cadence=template.cadence,
        active=template.active,
        payer="you" if template.payer_id == current_user.id else "other",
        split_type=template.split_type,
        percent_you=float(template.percent_you) if template.percent_you is not None else None,
        exact_you=float(template.exact_you) if template.exact_you is not None else None,
    )


def _next_occurrence(occurrence: date, cadence: str, anchor_day: int | None = None) -> date:
    if cadence == "weekly":
        return occurrence + timedelta(days=7)
    # Preserve the configured day where possible; e.g. Jan 31 → Feb 28 → Mar 31.
    next_month = occurrence.month % 12 + 1
    year = occurrence.year + (1 if occurrence.month == 12 else 0)
    day = min(anchor_day or occurrence.day, calendar.monthrange(year, next_month)[1])
    return date(year, next_month, day)


def _generate_due_recurring_expenses(db: Session) -> int:
    """Materialize each missing recurring occurrence through today.

    This deliberately runs during normal app use, avoiding a scheduler while
    still catching up after the app has not been opened for a while.
    """
    created = 0
    today = date.today()
    templates = db.query(RecurringExpense).filter(
        RecurringExpense.active == True,
        RecurringExpense.start_date <= today,
    ).all()
    for template in templates:
        existing_dates = {
            row[0] for row in db.query(Transaction.date).filter(
                Transaction.recurring_expense_id == template.id
            ).all()
        }
        occurrence = template.start_date
        while occurrence <= today:
            if occurrence not in existing_dates:
                normalized, merchant, sub = parse_description(template.description)
                tx = Transaction(
                    amex_reference=f"recurring-{template.id}-{occurrence.isoformat()}",
                    date=occurrence,
                    description_raw=template.description,
                    description_normalized=normalized,
                    merchant_key=merchant or "recurring",
                    sub_merchant_key=sub,
                amount=str(template.amount),
                card_member=_user_name(db.get(User, template.payer_id)),
                    payer_id=template.payer_id,
                    is_custom=True,
                    recurring_expense_id=template.id,
                    synced=True,
                )
                db.add(tx)
                db.flush()
                db.add(SplitHistory(
                    transaction_id=tx.id,
                    merchant_key=tx.merchant_key,
                    sub_merchant_key=tx.sub_merchant_key,
                    split_type=template.split_type,
                    percent_you=template.percent_you,
                    exact_you=template.exact_you,
                    amount_bucket=amount_to_bucket(float(tx.amount)),
                ))
                created += 1
            occurrence = _next_occurrence(occurrence, template.cadence, template.start_date.day)
    if created:
        db.commit()
    return created


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

"""Parsing and matching for the OFX/QFX bank-statement reconciliation feature
(see app/routes/transactions.py::reconcile). Kept separate from app/utils.py
since it's specific to this one feature."""
import io
from decimal import Decimal

from ofxparse import OfxParser

RECONCILE_DATE_TOLERANCE_DAYS = 7


def parse_ofx_bytes(raw_bytes):
    """Return {"rows": [...], "start_date": date|None, "end_date": date|None}.
    `rows` holds a {date, amount (Decimal), description} dict per transaction,
    across every account found in the file (an OFX export can contain more
    than one statement). `start_date`/`end_date` are the bank's own declared
    coverage period for the statement (its <DTSTART>/<DTEND> tags) — the file
    typically only covers a recent window, not the account's full history, so
    this is what callers should use to know which period the bank actually
    vouches for, rather than assuming the min/max of the transactions found
    inside it. Raises ValueError on anything ofxparse can't make sense of —
    this is parsing an arbitrary uploaded file, so catching broadly here
    (unlike elsewhere in the app) and converting to one clean exception is
    deliberate."""
    try:
        ofx = OfxParser.parse(io.BytesIO(raw_bytes))
    except Exception as exc:
        raise ValueError(str(exc)) from exc

    rows = []
    start_dates = []
    end_dates = []
    for account in getattr(ofx, "accounts", None) or []:
        statement = getattr(account, "statement", None)
        if getattr(statement, "start_date", None):
            start_dates.append(statement.start_date.date())
        if getattr(statement, "end_date", None):
            end_dates.append(statement.end_date.date())
        for t in getattr(statement, "transactions", []) or []:
            if t.date is None or t.amount is None:
                continue
            rows.append({
                "date": t.date.date(),
                "amount": Decimal(str(t.amount)),
                "description": (t.payee or t.memo or "").strip(),
            })
    return {
        "rows": rows,
        "start_date": min(start_dates) if start_dates else None,
        "end_date": max(end_dates) if end_dates else None,
    }


def match_ofx_transactions(ofx_rows, db_txs, tolerance_days=RECONCILE_DATE_TOLERANCE_DAYS):
    """Greedy bipartite match on amount (exact, or sign-inverted — a bank can
    export income/expense with the opposite sign comptaPerso uses) + date
    within `tolerance_days`. Exact-sign candidates are preferred over
    inverted ones at an equal date difference.
    Returns (matches, missing_ofx_indices, extra_db_txs):
    - matches: list of (ofx_index, db_tx, date_diff_days, inverted)
    - missing_ofx_indices: OFX rows with no corresponding DB transaction
    - extra_db_txs: DB transactions with no corresponding OFX row
    """
    candidates = []
    for oi, row in enumerate(ofx_rows):
        for tx in db_txs:
            if row["amount"] == tx.amount:
                inverted = False
            elif row["amount"] == -tx.amount:
                inverted = True
            else:
                continue
            diff = (row["date"] - tx.date).days
            if abs(diff) <= tolerance_days:
                candidates.append((abs(diff), inverted, oi, tx, diff))
    candidates.sort(key=lambda c: (c[0], c[1]))

    matched_ofx = set()
    matched_db = set()
    matches = []
    for _, inverted, oi, tx, diff in candidates:
        if oi in matched_ofx or tx.id in matched_db:
            continue
        matched_ofx.add(oi)
        matched_db.add(tx.id)
        matches.append((oi, tx, diff, inverted))

    missing = [i for i in range(len(ofx_rows)) if i not in matched_ofx]
    extra = [tx for tx in db_txs if tx.id not in matched_db]
    return matches, missing, extra

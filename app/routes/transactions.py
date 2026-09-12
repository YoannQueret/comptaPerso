import base64
import os
import uuid
from datetime import datetime, timedelta

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, g,
    current_app, send_from_directory, abort,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Transaction, Account, Category
from app.ofx_reconcile import parse_ofx_bytes, match_ofx_transactions, RECONCILE_DATE_TOLERANCE_DAYS
from app.utils import (
    resolve_account_id,
    ordered_categories,
    categories_by_owner,
    parse_decimal,
    safe_next as _safe_next,
    accessible_account_ids,
    account_access,
    get_accessible_account_or_404,
    today_for_user,
)

bp = Blueprint("transactions", __name__, url_prefix="/transactions")

TRANSACTIONS_PER_PAGE = 50


def _pagination_pages(page, total_pages, window=2):
    """Bootstrap-style page list for a pager: first and last page always
    shown, plus a `window`-sized range around the current page; `None`
    marks a collapsed gap (rendered as "…")."""
    pages = {1, total_pages}
    for p in range(page - window, page + window + 1):
        if 1 <= p <= total_pages:
            pages.add(p)
    ordered = sorted(pages)
    result = []
    prev = None
    for p in ordered:
        if prev is not None and p - prev > 1:
            result.append(None)
        result.append(p)
        prev = p
    return result


def _parse_date(s, default=None):
    if not s:
        return default
    return datetime.strptime(s, "%Y-%m-%d").date()


def _parse_budget_month(s, fallback_date):
    if s:
        return datetime.strptime(s, "%Y-%m").date().replace(day=1)
    return fallback_date.replace(day=1)


def _attachment_extension(file_storage):
    if not file_storage or not file_storage.filename or "." not in file_storage.filename:
        return None
    return file_storage.filename.rsplit(".", 1)[-1].lower()


def _is_allowed_attachment(file_storage):
    ext = _attachment_extension(file_storage)
    return ext is not None and ext in current_app.config["ALLOWED_ATTACHMENT_EXTENSIONS"]


def _save_attachment(file_storage):
    """Save an uploaded attachment under a generated name and return it. Caller
    must check _is_allowed_attachment first."""
    ext = _attachment_extension(file_storage)
    filename = f"{uuid.uuid4()}.{ext}"
    attachments_dir = current_app.config["ATTACHMENTS_DIR"]
    os.makedirs(attachments_dir, exist_ok=True)
    file_storage.save(os.path.join(attachments_dir, filename))
    return filename


def _delete_attachment(filename):
    if not filename:
        return
    path = os.path.join(current_app.config["ATTACHMENTS_DIR"], filename)
    if os.path.exists(path):
        os.remove(path)


@bp.route("/")
@login_required
def list_transactions():
    account_id = resolve_account_id(current_user, request.args.get("account_id"))
    category_id = request.args.get("category_id") or None
    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"))

    accounts = Account.query.filter(
        Account.id.in_(accessible_account_ids(current_user))
    ).order_by(Account.name).all()
    active_accounts = Account.query.filter(
        Account.id.in_(accessible_account_ids(current_user, permission="write")),
        Account.active.is_(True),
    ).order_by(Account.name).all()
    selected_account = next((a for a in accounts if a.id == account_id), None)
    owner_id = selected_account.user_id if selected_account else current_user.id
    categories_by_owner_map = categories_by_owner(active_accounts)
    can_add_here = account_id in {a.id for a in active_accounts}

    q = Transaction.query.filter(Transaction.account_id.in_(accessible_account_ids(current_user)))
    if account_id:
        q = q.filter(Transaction.account_id == account_id)
    if category_id:
        category = Category.query.filter_by(id=category_id, user_id=owner_id).first()
        if category:
            category_ids = [category.id] + [child.id for child in category.children]
            q = q.filter(Transaction.category_id.in_(category_ids))
    if date_from:
        q = q.filter(Transaction.date >= date_from)
    if date_to:
        q = q.filter(Transaction.date <= date_to)

    sort = request.args.get("sort") or "date_desc"
    if sort == "date_asc":
        q = q.order_by(Transaction.date.asc(), Transaction.created_at.asc())
    else:
        sort = "date_desc"
        q = q.order_by(Transaction.date.desc(), Transaction.created_at.desc())

    total_count = q.order_by(None).count()
    total_pages = max(1, (total_count + TRANSACTIONS_PER_PAGE - 1) // TRANSACTIONS_PER_PAGE)
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    page = min(max(page, 1), total_pages)
    txs = q.offset((page - 1) * TRANSACTIONS_PER_PAGE).limit(TRANSACTIONS_PER_PAGE).all()

    group_ids = {t.transfer_group_id for t in txs if t.is_transfer}
    counterparts = {}
    if group_ids:
        legs = Transaction.query.filter(Transaction.transfer_group_id.in_(group_ids)).all()
        by_group = {}
        for leg in legs:
            by_group.setdefault(leg.transfer_group_id, []).append(leg)
        for t in txs:
            if t.is_transfer:
                counterparts[t.id] = next(
                    (leg for leg in by_group.get(t.transfer_group_id, []) if leg.id != t.id), None
                )

    categories = ordered_categories(owner_id)

    return render_template(
        "transactions.html",
        transactions=txs,
        accounts=accounts,
        active_accounts=active_accounts,
        categories=categories,
        categories_by_owner=categories_by_owner_map,
        filters=request.args,
        transfer_counterparts=counterparts,
        sort=sort,
        today=today_for_user(current_user),
        selected_account_id=account_id,
        selected_account=selected_account,
        can_add_here=can_add_here,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        pagination_pages=_pagination_pages(page, total_pages),
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_transaction():
    accounts = Account.query.filter(
        Account.id.in_(accessible_account_ids(current_user, permission="write")),
        Account.active.is_(True),
    ).order_by(Account.name).all()
    categories_by_owner_map = categories_by_owner(accounts)

    preselected_account_id = resolve_account_id(current_user, request.args.get("account_id"))
    write_ids = {a.id for a in accounts}
    if preselected_account_id not in write_ids:
        preselected_account_id = accounts[0].id if accounts else None
    initial_owner_id = next(
        (a.user_id for a in accounts if a.id == preselected_account_id), current_user.id
    )
    categories = ordered_categories(initial_owner_id)

    if request.method == "POST":
        attachment_file = request.files.get("attachment")
        if attachment_file and attachment_file.filename and not _is_allowed_attachment(attachment_file):
            flash(g._("attachment_invalid_type"), "danger")
            return render_template(
                "transaction_form.html",
                transaction=None,
                accounts=accounts,
                categories=categories,
                categories_by_owner=categories_by_owner_map,
                preselected_account_id=preselected_account_id,
                next_url=_safe_next(request.form.get("next")),
            )

        acc = get_accessible_account_or_404(request.form.get("account_id"), current_user, permission="write")
        kind = request.form["kind"]  # expense | income
        try:
            amount = parse_decimal(request.form.get("amount"))
            tx_date = _parse_date(request.form["date"], today_for_user(current_user))
        except ValueError:
            flash(g._("invalid_transaction_data"), "danger")
            return render_template(
                "transaction_form.html",
                transaction=None,
                accounts=accounts,
                categories=categories,
                categories_by_owner=categories_by_owner_map,
                preselected_account_id=preselected_account_id,
                next_url=_safe_next(request.form.get("next")),
            )
        if kind == "expense":
            amount = -abs(amount)
        else:
            amount = abs(amount)
        tx = Transaction(
            user_id=acc.user_id,
            account_id=acc.id,
            category_id=request.form.get("category_id") or None,
            date=tx_date,
            budget_month=_parse_budget_month(request.form.get("budget_month"), tx_date),
            amount=amount,
            description=request.form.get("description", "").strip(),
        )
        if attachment_file and attachment_file.filename:
            tx.attachment_filename = _save_attachment(attachment_file)
        db.session.add(tx)
        db.session.commit()
        flash(g._("transaction_saved"), "success")
        next_url = _safe_next(request.form.get("next"))
        return redirect(next_url or url_for("transactions.list_transactions"))

    return render_template(
        "transaction_form.html",
        transaction=None,
        accounts=accounts,
        categories=categories,
        categories_by_owner=categories_by_owner_map,
        preselected_account_id=preselected_account_id,
        next_url=_safe_next(request.args.get("next")),
    )


@bp.route("/<tx_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, is_transfer=False).first_or_404()
    if account_access(tx.account, current_user) not in ("owner", "write"):
        abort(404)

    accounts = Account.query.filter(
        Account.id.in_(accessible_account_ids(current_user, permission="write"))
    ).order_by(Account.name).all()
    categories_by_owner_map = categories_by_owner(accounts)
    categories = ordered_categories(tx.account.user_id)

    if request.method == "POST":
        attachment_file = request.files.get("attachment")
        if attachment_file and attachment_file.filename and not _is_allowed_attachment(attachment_file):
            flash(g._("attachment_invalid_type"), "danger")
            return render_template(
                "transaction_form.html",
                transaction=tx,
                accounts=accounts,
                categories=categories,
                categories_by_owner=categories_by_owner_map,
                next_url=_safe_next(request.form.get("next")),
            )

        acc = get_accessible_account_or_404(request.form.get("account_id"), current_user, permission="write")
        kind = request.form["kind"]
        try:
            amount = parse_decimal(request.form.get("amount"))
            tx_date = _parse_date(request.form["date"], tx.date)
        except ValueError:
            flash(g._("invalid_transaction_data"), "danger")
            return render_template(
                "transaction_form.html",
                transaction=tx,
                accounts=accounts,
                categories=categories,
                categories_by_owner=categories_by_owner_map,
                next_url=_safe_next(request.form.get("next")),
            )
        amount = -abs(amount) if kind == "expense" else abs(amount)
        tx.account_id = acc.id
        tx.user_id = acc.user_id
        tx.category_id = request.form.get("category_id") or None
        tx.date = tx_date
        tx.budget_month = _parse_budget_month(request.form.get("budget_month"), tx.date)
        tx.amount = amount
        tx.description = request.form.get("description", "").strip()

        if request.form.get("remove_attachment"):
            _delete_attachment(tx.attachment_filename)
            tx.attachment_filename = None
        if attachment_file and attachment_file.filename:
            _delete_attachment(tx.attachment_filename)
            tx.attachment_filename = _save_attachment(attachment_file)

        db.session.commit()
        flash(g._("transaction_updated"), "success")
        next_url = _safe_next(request.form.get("next"))
        return redirect(next_url or url_for("transactions.list_transactions"))

    return render_template(
        "transaction_form.html",
        transaction=tx,
        accounts=accounts,
        categories=categories,
        categories_by_owner=categories_by_owner_map,
        next_url=_safe_next(request.args.get("next")),
    )


@bp.route("/<tx_id>/toggle-reviewed", methods=["POST"])
@login_required
def toggle_reviewed(tx_id):
    tx = Transaction.query.filter_by(id=tx_id).first_or_404()
    if account_access(tx.account, current_user) is None:
        abort(404)
    tx.reviewed = not tx.reviewed
    db.session.commit()
    return {"reviewed": tx.reviewed}


@bp.route("/<tx_id>/delete", methods=["POST"])
@login_required
def delete_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id).first_or_404()
    if account_access(tx.account, current_user) not in ("owner", "write"):
        abort(404)
    _delete_attachment(tx.attachment_filename)
    db.session.delete(tx)
    db.session.commit()
    flash(g._("transaction_deleted"), "success")
    return redirect(url_for("transactions.list_transactions"))


@bp.route("/<tx_id>/attachment")
@login_required
def view_attachment(tx_id):
    tx = Transaction.query.filter_by(id=tx_id).first_or_404()
    if account_access(tx.account, current_user) is None:
        abort(404)
    if not tx.attachment_filename:
        abort(404)
    return send_from_directory(current_app.config["ATTACHMENTS_DIR"], tx.attachment_filename)


def _apply_reconcile_action(action, form, acc, ofx_rows):
    """Mutates the DB according to one reconciliation row action. `ofx_rows`
    is the freshly re-parsed list from the resubmitted OFX content, so
    `ofx_index` always refers to the same row it did when the button was
    rendered."""
    if action == "add":
        try:
            index = int(form.get("ofx_index", ""))
            row = ofx_rows[index]
        except (ValueError, IndexError):
            return
        tx = Transaction(
            user_id=acc.user_id,
            account_id=acc.id,
            category_id=form.get("category_id") or None,
            date=row["date"],
            budget_month=row["date"].replace(day=1),
            amount=row["amount"],
            description=row["description"],
        )
        db.session.add(tx)
        db.session.commit()
        flash(g._("transaction_saved"), "success")

    elif action == "delete":
        tx = Transaction.query.filter_by(id=form.get("tx_id"), account_id=acc.id).first()
        if tx:
            _delete_attachment(tx.attachment_filename)
            db.session.delete(tx)
            db.session.commit()
            flash(g._("transaction_deleted"), "success")

    elif action == "sync_date":
        tx = Transaction.query.filter_by(id=form.get("tx_id"), account_id=acc.id).first()
        try:
            index = int(form.get("ofx_index", ""))
            row = ofx_rows[index]
        except (ValueError, IndexError):
            row = None
        if tx and row:
            tx.date = row["date"]
            db.session.commit()
            flash(g._("reconcile_date_updated"), "success")

    elif action == "flip_sign":
        tx = Transaction.query.filter_by(id=form.get("tx_id"), account_id=acc.id).first()
        if tx:
            tx.amount = -tx.amount
            db.session.commit()
            flash(g._("reconcile_sign_flipped"), "success")


@bp.route("/reconcile", methods=["GET", "POST"])
@login_required
def reconcile():
    account_id = resolve_account_id(current_user, request.values.get("account_id"))
    acc = get_accessible_account_or_404(account_id, current_user, permission="write")

    error = None
    ofx_rows = None
    period_start = period_end = None
    ofx_content_b64 = request.form.get("ofx_content")

    if request.method == "POST":
        upload = request.files.get("file")
        raw = None
        if upload and upload.filename:
            raw = upload.read()
            ofx_content_b64 = base64.b64encode(raw).decode("ascii")
        elif ofx_content_b64:
            raw = base64.b64decode(ofx_content_b64)

        if raw is not None:
            try:
                parsed = parse_ofx_bytes(raw)
                ofx_rows = parsed["rows"]
                period_start = parsed["start_date"]
                period_end = parsed["end_date"]
            except ValueError:
                error = g._("ofx_parse_error")
                ofx_content_b64 = None

        action = request.form.get("action")
        if ofx_rows is not None and action:
            _apply_reconcile_action(action, request.form, acc, ofx_rows)

    matches, missing, extra = [], [], []
    if ofx_rows is not None:
        # The bank's own declared statement period is the only period it
        # actually vouches for — it typically doesn't cover the account's
        # full history. Fall back to the transactions' own min/max only when
        # the file doesn't declare one (some banks omit DTSTART/DTEND).
        if not (period_start and period_end) and ofx_rows:
            period_start = min(r["date"] for r in ofx_rows)
            period_end = max(r["date"] for r in ofx_rows)

        if period_start and period_end:
            fetch_start = period_start - timedelta(days=RECONCILE_DATE_TOLERANCE_DAYS)
            fetch_end = period_end + timedelta(days=RECONCILE_DATE_TOLERANCE_DAYS)
            db_txs = Transaction.query.filter(
                Transaction.account_id == acc.id,
                Transaction.date >= fetch_start,
                Transaction.date <= fetch_end,
            ).all()
        else:
            db_txs = []

        raw_matches, missing_idx, extra_candidates = match_ofx_transactions(ofx_rows, db_txs)
        matches = [
            {
                "index": i,
                "row": ofx_rows[i],
                "tx": tx,
                "date_diff": diff,
                "inverted": inverted,
                "anomaly": bool(diff) or inverted,
            }
            for i, tx, diff, inverted in raw_matches
        ]
        missing = [{"index": i, "row": ofx_rows[i]} for i in missing_idx]
        # A DB transaction outside the bank's declared period is never flagged
        # as "extra": the file simply doesn't cover that period, so we can't
        # tell whether it's really missing from the bank's side or just out
        # of scope for this statement.
        if period_start and period_end:
            extra = [tx for tx in extra_candidates if period_start <= tx.date <= period_end]
        else:
            extra = extra_candidates

    return render_template(
        "reconcile.html",
        account=acc,
        ofx_content=ofx_content_b64,
        matches=matches,
        missing=missing,
        extra=extra,
        error=error,
        uploaded=ofx_rows is not None,
        categories=ordered_categories(acc.user_id),
    )

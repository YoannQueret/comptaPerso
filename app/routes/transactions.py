import os
import uuid
from datetime import datetime, date

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, g,
    current_app, send_from_directory, abort,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Transaction, Account, Category
from app.utils import (
    resolve_account_id,
    ordered_categories,
    categories_by_owner,
    parse_decimal,
    safe_next as _safe_next,
    accessible_account_ids,
    account_access,
    get_accessible_account_or_404,
)

bp = Blueprint("transactions", __name__, url_prefix="/transactions")


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
    txs = q.limit(300).all()

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
        today=date.today(),
        selected_account_id=account_id,
        selected_account=selected_account,
        can_add_here=can_add_here,
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
            tx_date = _parse_date(request.form["date"], date.today())
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

import os
import uuid
from datetime import datetime, date
from decimal import Decimal

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, g,
    current_app, send_from_directory, abort,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Transaction, Account
from app.utils import resolve_account_id, ordered_categories, safe_next as _safe_next

bp = Blueprint("transactions", __name__, url_prefix="/transactions")


def _parse_date(s, default=None):
    if not s:
        return default
    return datetime.strptime(s, "%Y-%m-%d").date()


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

    q = Transaction.query.filter_by(user_id=current_user.id)
    if account_id:
        q = q.filter(Transaction.account_id == account_id)
    if category_id:
        q = q.filter(Transaction.category_id == category_id)
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

    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.name).all()
    active_accounts = Account.query.filter_by(user_id=current_user.id, active=True).order_by(
        Account.name
    ).all()
    categories = ordered_categories(current_user.id)

    return render_template(
        "transactions.html",
        transactions=txs,
        accounts=accounts,
        active_accounts=active_accounts,
        categories=categories,
        filters=request.args,
        transfer_counterparts=counterparts,
        sort=sort,
        today=date.today(),
        selected_account_id=account_id,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_transaction():
    accounts = Account.query.filter_by(user_id=current_user.id, active=True).order_by(
        Account.name
    ).all()
    categories = ordered_categories(current_user.id)

    if request.method == "POST":
        attachment_file = request.files.get("attachment")
        if attachment_file and attachment_file.filename and not _is_allowed_attachment(attachment_file):
            flash(g._("attachment_invalid_type"), "danger")
            return render_template(
                "transaction_form.html",
                transaction=None,
                accounts=accounts,
                categories=categories,
                preselected_account_id=resolve_account_id(current_user, request.args.get("account_id")),
                next_url=_safe_next(request.form.get("next")),
            )

        kind = request.form["kind"]  # expense | income
        amount = Decimal(request.form["amount"].replace(",", "."))
        if kind == "expense":
            amount = -abs(amount)
        else:
            amount = abs(amount)
        tx = Transaction(
            user_id=current_user.id,
            account_id=request.form["account_id"],
            category_id=request.form.get("category_id") or None,
            date=_parse_date(request.form["date"], date.today()),
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

    preselected_account_id = resolve_account_id(current_user, request.args.get("account_id"))
    return render_template(
        "transaction_form.html",
        transaction=None,
        accounts=accounts,
        categories=categories,
        preselected_account_id=preselected_account_id,
        next_url=_safe_next(request.args.get("next")),
    )


@bp.route("/<tx_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id, is_transfer=False).first_or_404()
    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.name).all()
    categories = ordered_categories(current_user.id)

    if request.method == "POST":
        attachment_file = request.files.get("attachment")
        if attachment_file and attachment_file.filename and not _is_allowed_attachment(attachment_file):
            flash(g._("attachment_invalid_type"), "danger")
            return render_template(
                "transaction_form.html",
                transaction=tx,
                accounts=accounts,
                categories=categories,
                next_url=_safe_next(request.form.get("next")),
            )

        kind = request.form["kind"]
        amount = Decimal(request.form["amount"].replace(",", "."))
        amount = -abs(amount) if kind == "expense" else abs(amount)
        tx.account_id = request.form["account_id"]
        tx.category_id = request.form.get("category_id") or None
        tx.date = _parse_date(request.form["date"], tx.date)
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
        next_url=_safe_next(request.args.get("next")),
    )


@bp.route("/<tx_id>/delete", methods=["POST"])
@login_required
def delete_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first_or_404()
    _delete_attachment(tx.attachment_filename)
    db.session.delete(tx)
    db.session.commit()
    flash(g._("transaction_deleted"), "success")
    return redirect(url_for("transactions.list_transactions"))


@bp.route("/<tx_id>/attachment")
@login_required
def view_attachment(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first_or_404()
    if not tx.attachment_filename:
        abort(404)
    return send_from_directory(current_app.config["ATTACHMENTS_DIR"], tx.attachment_filename)

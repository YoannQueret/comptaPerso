import uuid
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, g, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Transaction, Account
from app.utils import (
    safe_next,
    accessible_account_ids,
    account_access,
    get_accessible_account_or_404,
    parse_decimal,
    today_for_user,
)

bp = Blueprint("transfers", __name__, url_prefix="/transfers")


def _parse_date(s, default=None):
    if not s:
        return default
    return datetime.strptime(s, "%Y-%m-%d").date()


def _parse_budget_month(s, fallback_date):
    if s:
        return datetime.strptime(s, "%Y-%m").date().replace(day=1)
    return fallback_date.replace(day=1)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_transfer():
    accounts = Account.query.filter(
        Account.id.in_(accessible_account_ids(current_user, permission="write")),
        Account.active.is_(True),
    ).order_by(Account.name).all()

    if request.method == "POST":
        from_account = get_accessible_account_or_404(
            request.form.get("from_account_id"), current_user, permission="write"
        )
        to_account = get_accessible_account_or_404(
            request.form.get("to_account_id"), current_user, permission="write"
        )

        next_url = safe_next(request.form.get("next"))

        if from_account.id == to_account.id:
            flash(g._("transfer_accounts_must_differ"), "danger")
            return redirect(next_url or url_for("transfers.new_transfer"))

        try:
            amount_sent = abs(parse_decimal(request.form.get("amount_sent")))
            amount_received = abs(parse_decimal(request.form.get("amount_received")))
            d = _parse_date(request.form["date"], today_for_user(current_user))
        except ValueError:
            flash(g._("invalid_transaction_data"), "danger")
            return redirect(next_url or url_for("transfers.new_transfer"))
        budget_month = _parse_budget_month(request.form.get("budget_month"), d)
        description = request.form.get("description", "").strip() or g._("transfer")

        group_id = str(uuid.uuid4())

        out_tx = Transaction(
            user_id=from_account.user_id,
            account_id=from_account.id,
            date=d,
            budget_month=budget_month,
            amount=-amount_sent,
            description=description,
            is_transfer=True,
            transfer_group_id=group_id,
        )
        in_tx = Transaction(
            user_id=to_account.user_id,
            account_id=to_account.id,
            date=d,
            budget_month=budget_month,
            amount=amount_received,
            description=description,
            is_transfer=True,
            transfer_group_id=group_id,
        )
        db.session.add_all([out_tx, in_tx])
        db.session.commit()
        flash(g._("transfer_saved"), "success")
        return redirect(next_url or url_for("transactions.list_transactions"))

    return render_template(
        "transfer_form.html",
        accounts=accounts,
        out_tx=None,
        in_tx=None,
        next_url=safe_next(request.args.get("next")),
    )


@bp.route("/<group_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transfer(group_id):
    legs = Transaction.query.filter_by(transfer_group_id=group_id, is_transfer=True).all()
    out_tx = next((t for t in legs if t.amount < 0), None)
    in_tx = next((t for t in legs if t is not out_tx), None)
    if not out_tx or not in_tx:
        abort(404)
    if account_access(out_tx.account, current_user) not in ("owner", "write") and \
            account_access(in_tx.account, current_user) not in ("owner", "write"):
        abort(404)

    accounts = Account.query.filter(
        Account.id.in_(accessible_account_ids(current_user, permission="write"))
    ).order_by(Account.name).all()

    if request.method == "POST":
        from_account = get_accessible_account_or_404(
            request.form.get("from_account_id"), current_user, permission="write"
        )
        to_account = get_accessible_account_or_404(
            request.form.get("to_account_id"), current_user, permission="write"
        )

        next_url = safe_next(request.form.get("next"))

        if from_account.id == to_account.id:
            flash(g._("transfer_accounts_must_differ"), "danger")
            return redirect(next_url or url_for("transfers.edit_transfer", group_id=group_id))

        try:
            amount_sent = abs(parse_decimal(request.form.get("amount_sent")))
            amount_received = abs(parse_decimal(request.form.get("amount_received")))
            d = _parse_date(request.form["date"], out_tx.date)
        except ValueError:
            flash(g._("invalid_transaction_data"), "danger")
            return redirect(next_url or url_for("transfers.edit_transfer", group_id=group_id))
        budget_month = _parse_budget_month(request.form.get("budget_month"), d)
        description = request.form.get("description", "").strip() or g._("transfer")

        out_tx.account_id = from_account.id
        out_tx.user_id = from_account.user_id
        out_tx.date = d
        out_tx.budget_month = budget_month
        out_tx.amount = -amount_sent
        out_tx.description = description

        in_tx.account_id = to_account.id
        in_tx.user_id = to_account.user_id
        in_tx.date = d
        in_tx.budget_month = budget_month
        in_tx.amount = amount_received
        in_tx.description = description

        db.session.commit()
        flash(g._("transfer_updated"), "success")
        return redirect(next_url or url_for("transactions.list_transactions"))

    return render_template(
        "transfer_form.html",
        accounts=accounts,
        out_tx=out_tx,
        in_tx=in_tx,
        next_url=safe_next(request.args.get("next")),
    )


@bp.route("/<group_id>/delete", methods=["POST"])
@login_required
def delete_transfer(group_id):
    legs = Transaction.query.filter_by(transfer_group_id=group_id).all()
    if not legs or not any(account_access(t.account, current_user) in ("owner", "write") for t in legs):
        abort(404)
    for t in legs:
        db.session.delete(t)
    db.session.commit()
    flash(g._("transfer_deleted"), "success")
    next_url = safe_next(request.form.get("next"))
    return redirect(next_url or url_for("transactions.list_transactions"))

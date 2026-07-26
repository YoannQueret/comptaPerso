import uuid
from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, request, flash, g
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Transaction, Account
from app.utils import safe_next

bp = Blueprint("transfers", __name__, url_prefix="/transfers")


def _parse_date(s, default=None):
    if not s:
        return default
    return datetime.strptime(s, "%Y-%m-%d").date()


def _parse_budget_month(s, fallback_date):
    if s:
        return datetime.strptime(s, "%Y-%m").date().replace(day=1)
    return fallback_date.replace(day=1)


@bp.route("/")
@login_required
def list_transfers():
    # only show one row per transfer group (the "outgoing" row, negative amount)
    txs = (
        Transaction.query.filter_by(user_id=current_user.id, is_transfer=True)
        .filter(Transaction.amount < 0)
        .order_by(Transaction.date.desc())
        .limit(200)
        .all()
    )
    pairs = []
    for t in txs:
        dest = Transaction.query.filter_by(
            transfer_group_id=t.transfer_group_id, is_transfer=True
        ).filter(Transaction.id != t.id).first()
        pairs.append((t, dest))

    accounts = Account.query.filter_by(user_id=current_user.id, active=True).order_by(
        Account.name
    ).all()
    return render_template("transfers.html", pairs=pairs, accounts=accounts, today=date.today())


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_transfer():
    accounts = Account.query.filter_by(user_id=current_user.id, active=True).order_by(
        Account.name
    ).all()

    if request.method == "POST":
        from_account = Account.query.filter_by(
            id=request.form["from_account_id"], user_id=current_user.id
        ).first_or_404()
        to_account = Account.query.filter_by(
            id=request.form["to_account_id"], user_id=current_user.id
        ).first_or_404()

        next_url = safe_next(request.form.get("next"))

        if from_account.id == to_account.id:
            flash(g._("transfer_accounts_must_differ"), "danger")
            return redirect(next_url or url_for("transfers.new_transfer"))

        amount_sent = abs(Decimal(request.form["amount_sent"].replace(",", ".")))
        amount_received = abs(Decimal(request.form["amount_received"].replace(",", ".")))
        d = _parse_date(request.form["date"], date.today())
        budget_month = _parse_budget_month(request.form.get("budget_month"), d)
        description = request.form.get("description", "").strip() or g._("transfer")

        group_id = str(uuid.uuid4())

        out_tx = Transaction(
            user_id=current_user.id,
            account_id=from_account.id,
            date=d,
            budget_month=budget_month,
            amount=-amount_sent,
            description=description,
            is_transfer=True,
            transfer_group_id=group_id,
        )
        in_tx = Transaction(
            user_id=current_user.id,
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
        return redirect(next_url or url_for("transfers.list_transfers"))

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
    out_tx = Transaction.query.filter_by(
        transfer_group_id=group_id, user_id=current_user.id, is_transfer=True
    ).filter(Transaction.amount < 0).first_or_404()
    in_tx = Transaction.query.filter_by(
        transfer_group_id=group_id, user_id=current_user.id, is_transfer=True
    ).filter(Transaction.id != out_tx.id).first_or_404()

    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.name).all()

    if request.method == "POST":
        from_account = Account.query.filter_by(
            id=request.form["from_account_id"], user_id=current_user.id
        ).first_or_404()
        to_account = Account.query.filter_by(
            id=request.form["to_account_id"], user_id=current_user.id
        ).first_or_404()

        next_url = safe_next(request.form.get("next"))

        if from_account.id == to_account.id:
            flash(g._("transfer_accounts_must_differ"), "danger")
            return redirect(next_url or url_for("transfers.edit_transfer", group_id=group_id))

        amount_sent = abs(Decimal(request.form["amount_sent"].replace(",", ".")))
        amount_received = abs(Decimal(request.form["amount_received"].replace(",", ".")))
        d = _parse_date(request.form["date"], out_tx.date)
        budget_month = _parse_budget_month(request.form.get("budget_month"), d)
        description = request.form.get("description", "").strip() or g._("transfer")

        out_tx.account_id = from_account.id
        out_tx.date = d
        out_tx.budget_month = budget_month
        out_tx.amount = -amount_sent
        out_tx.description = description

        in_tx.account_id = to_account.id
        in_tx.date = d
        in_tx.budget_month = budget_month
        in_tx.amount = amount_received
        in_tx.description = description

        db.session.commit()
        flash(g._("transfer_updated"), "success")
        return redirect(next_url or url_for("transfers.list_transfers"))

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
    Transaction.query.filter_by(
        transfer_group_id=group_id, user_id=current_user.id
    ).delete()
    db.session.commit()
    flash(g._("transfer_deleted"), "success")
    return redirect(url_for("transfers.list_transfers"))

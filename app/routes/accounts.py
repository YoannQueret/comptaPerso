from flask import Blueprint, render_template, redirect, url_for, request, flash, g
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Account, AccountType
from app.config import Config


bp = Blueprint("accounts", __name__, url_prefix="/accounts")


def _account_types_for_select():
    return AccountType.query.filter_by(user_id=current_user.id).order_by(AccountType.name).all()


@bp.route("/")
@login_required
def list_accounts():
    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.name).all()
    return render_template("accounts.html", accounts=accounts)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_account():
    if request.method == "POST":
        acc = Account(
            user_id=current_user.id,
            name=request.form["name"].strip(),
            account_number=request.form.get("account_number", "").strip() or None,
            account_type_id=request.form.get("account_type_id") or None,
            currency=request.form["currency"],
            initial_balance=request.form.get("initial_balance") or 0,
        )
        db.session.add(acc)
        db.session.flush()
        if not current_user.default_account_id:
            current_user.default_account_id = acc.id
        db.session.commit()
        flash(g._("account_created"), "success")
        return redirect(url_for("accounts.list_accounts"))
    return render_template(
        "account_form.html",
        account=None,
        account_types=_account_types_for_select(),
        currencies=Config.DEFAULT_CURRENCIES,
    )


@bp.route("/<account_id>/edit", methods=["GET", "POST"])
@login_required
def edit_account(account_id):
    acc = Account.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    if request.method == "POST":
        acc.name = request.form["name"].strip()
        acc.account_number = request.form.get("account_number", "").strip() or None
        acc.account_type_id = request.form.get("account_type_id") or None
        acc.currency = request.form["currency"]
        acc.initial_balance = request.form.get("initial_balance") or 0
        acc.active = bool(request.form.get("active"))
        db.session.commit()
        flash(g._("account_updated"), "success")
        return redirect(url_for("accounts.list_accounts"))
    return render_template(
        "account_form.html",
        account=acc,
        account_types=_account_types_for_select(),
        currencies=Config.DEFAULT_CURRENCIES,
    )


@bp.route("/<account_id>/delete", methods=["POST"])
@login_required
def delete_account(account_id):
    acc = Account.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    if current_user.default_account_id == acc.id:
        current_user.default_account_id = None
    db.session.delete(acc)
    db.session.commit()
    flash(g._("account_deleted"), "success")
    return redirect(url_for("accounts.list_accounts"))


@bp.route("/<account_id>/set-default", methods=["POST"])
@login_required
def set_default_account(account_id):
    acc = Account.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    current_user.default_account_id = acc.id
    db.session.commit()
    flash(g._("default_account_updated"), "success")
    return redirect(url_for("accounts.list_accounts"))

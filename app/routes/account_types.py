from flask import Blueprint, render_template, redirect, url_for, request, flash, g
from flask_login import login_required, current_user

from app.extensions import db
from app.models import AccountType

bp = Blueprint("account_types", __name__, url_prefix="/account-types")


@bp.route("/")
@login_required
def list_account_types():
    account_types = (
        AccountType.query.filter_by(user_id=current_user.id).order_by(AccountType.name).all()
    )
    return render_template("account_types.html", account_types=account_types)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_account_type():
    if request.method == "POST":
        account_type = AccountType(user_id=current_user.id, name=request.form["name"].strip())
        db.session.add(account_type)
        db.session.commit()
        flash(g._("account_type_created"), "success")
        return redirect(url_for("account_types.list_account_types"))
    return render_template("account_type_form.html", account_type=None)


@bp.route("/<account_type_id>/edit", methods=["GET", "POST"])
@login_required
def edit_account_type(account_type_id):
    account_type = AccountType.query.filter_by(
        id=account_type_id, user_id=current_user.id
    ).first_or_404()
    if request.method == "POST":
        account_type.name = request.form["name"].strip()
        db.session.commit()
        flash(g._("account_type_updated"), "success")
        return redirect(url_for("account_types.list_account_types"))
    return render_template("account_type_form.html", account_type=account_type)


@bp.route("/<account_type_id>/delete", methods=["POST"])
@login_required
def delete_account_type(account_type_id):
    account_type = AccountType.query.filter_by(
        id=account_type_id, user_id=current_user.id
    ).first_or_404()
    if account_type.accounts:
        flash(g._("account_type_in_use"), "danger")
        return redirect(url_for("account_types.list_account_types"))
    db.session.delete(account_type)
    db.session.commit()
    flash(g._("account_type_deleted"), "success")
    return redirect(url_for("account_types.list_account_types"))

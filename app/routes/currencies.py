from flask import Blueprint, render_template, redirect, url_for, request, flash, g
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Currency, Account

bp = Blueprint("currencies", __name__, url_prefix="/currencies")


@bp.route("/")
@login_required
def list_currencies():
    currencies = Currency.query.filter_by(user_id=current_user.id).order_by(Currency.code).all()
    used_codes = {
        row[0] for row in db.session.query(Account.currency)
        .filter(Account.user_id == current_user.id)
        .distinct()
    }
    return render_template("currencies.html", currencies=currencies, used_codes=used_codes)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_currency():
    if request.method == "POST":
        code = request.form["code"].strip().upper()
        exists = Currency.query.filter_by(user_id=current_user.id, code=code).first()
        if exists:
            flash(g._("currency_already_exists"), "danger")
            return render_template("currency_form.html", currency=None)
        currency = Currency(user_id=current_user.id, code=code, active=True)
        db.session.add(currency)
        db.session.commit()
        flash(g._("currency_created"), "success")
        return redirect(url_for("currencies.list_currencies"))
    return render_template("currency_form.html", currency=None)


@bp.route("/<currency_id>/toggle", methods=["POST"])
@login_required
def toggle_currency(currency_id):
    currency = Currency.query.filter_by(id=currency_id, user_id=current_user.id).first_or_404()
    if currency.active:
        in_use = Account.query.filter_by(user_id=current_user.id, currency=currency.code).first()
        if in_use:
            flash(g._("currency_cannot_deactivate"), "danger")
            return redirect(url_for("currencies.list_currencies"))
        active_count = Currency.query.filter_by(user_id=current_user.id, active=True).count()
        if active_count <= 1:
            flash(g._("currency_last_active"), "danger")
            return redirect(url_for("currencies.list_currencies"))
    currency.active = not currency.active
    db.session.commit()
    flash(g._("currency_updated"), "success")
    return redirect(url_for("currencies.list_currencies"))


@bp.route("/<currency_id>/delete", methods=["POST"])
@login_required
def delete_currency(currency_id):
    currency = Currency.query.filter_by(id=currency_id, user_id=current_user.id).first_or_404()
    in_use = Account.query.filter_by(user_id=current_user.id, currency=currency.code).first()
    if in_use:
        flash(g._("currency_in_use"), "danger")
        return redirect(url_for("currencies.list_currencies"))
    db.session.delete(currency)
    db.session.commit()
    flash(g._("currency_deleted"), "success")
    return redirect(url_for("currencies.list_currencies"))

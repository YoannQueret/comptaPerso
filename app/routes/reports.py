from datetime import datetime, date
from collections import defaultdict

from flask import Blueprint, render_template, request, g
from flask_login import login_required, current_user
from sqlalchemy import extract

from app.extensions import db
from app.models import Transaction, Category, Account
from app.utils import resolve_account_id

bp = Blueprint("reports", __name__, url_prefix="/reports")


def _parse_date(s, default=None):
    if not s:
        return default
    return datetime.strptime(s, "%Y-%m-%d").date()


def _accounts_for_select():
    return Account.query.filter_by(user_id=current_user.id).order_by(Account.name).all()


def _currency_for(account_id):
    if not account_id:
        return ""
    acc = Account.query.filter_by(id=account_id, user_id=current_user.id).first()
    return acc.currency if acc else ""


def _initial_balance_for(account_id):
    if not account_id:
        return 0.0
    acc = Account.query.filter_by(id=account_id, user_id=current_user.id).first()
    return float(acc.initial_balance or 0) if acc else 0.0


def _category_totals(account_id, date_from, date_to):
    """Return {category_full_name: total} of expenses and income over a period."""
    txs = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.account_id == account_id,
        Transaction.date >= date_from,
        Transaction.date <= date_to,
    ).all()
    totals = defaultdict(float)
    for t in txs:
        if t.is_transfer:
            name = g._("transfers")
        else:
            name = t.category.full_name if t.category else g._("no_category")
        totals[name] += float(t.amount)
    return dict(totals)


@bp.route("/")
@login_required
def index():
    account_id = resolve_account_id(current_user, request.args.get("account_id"))

    today = date.today()
    default_a_from = today.replace(day=1)
    default_a_to = today

    a_from = _parse_date(request.args.get("a_from"), default_a_from)
    a_to = _parse_date(request.args.get("a_to"), default_a_to)
    b_from = _parse_date(request.args.get("b_from"))
    b_to = _parse_date(request.args.get("b_to"))

    totals_a = _category_totals(account_id, a_from, a_to)
    totals_b = _category_totals(account_id, b_from, b_to) if (b_from and b_to) else {}

    all_categories = sorted(set(totals_a.keys()) | set(totals_b.keys()))
    comparison_rows = []
    for cat in all_categories:
        va = totals_a.get(cat, 0.0)
        vb = totals_b.get(cat, 0.0)
        comparison_rows.append((cat, va, vb, va - vb))

    return render_template(
        "reports.html",
        a_from=a_from,
        a_to=a_to,
        b_from=b_from,
        b_to=b_to,
        comparison_rows=comparison_rows,
        has_b=bool(b_from and b_to),
        accounts=_accounts_for_select(),
        selected_account_id=account_id,
        currency=_currency_for(account_id),
    )


@bp.route("/monthly/<int:year>")
@login_required
def yearly_monthly(year):
    account_id = resolve_account_id(current_user, request.args.get("account_id"))

    prior_total = db.session.query(
        db.func.coalesce(db.func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.account_id == account_id,
        Transaction.date < date(year, 1, 1),
    ).scalar()
    running_balance = _initial_balance_for(account_id) + float(prior_total or 0)

    rows = []
    for m in range(1, 13):
        txs = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.account_id == account_id,
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == m,
        ).all()
        expenses = sum(-float(t.amount) for t in txs if t.amount < 0)
        income = sum(float(t.amount) for t in txs if t.amount > 0)
        running_balance += income - expenses
        rows.append({
            "month": m,
            "expenses": expenses,
            "income": income,
            "net": income - expenses,
            "ending_balance": running_balance,
        })
    return render_template(
        "reports_monthly.html",
        year=year,
        rows=rows,
        accounts=_accounts_for_select(),
        selected_account_id=account_id,
        currency=_currency_for(account_id),
    )


@bp.route("/yearly")
@login_required
def yearly():
    account_id = resolve_account_id(current_user, request.args.get("account_id"))

    years_query = (
        db.session.query(extract("year", Transaction.date))
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.account_id == account_id,
        )
        .distinct()
        .all()
    )
    years = sorted({int(y[0]) for y in years_query if y[0] is not None})
    running_balance = _initial_balance_for(account_id)
    rows = []
    for y in years:
        txs = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            Transaction.account_id == account_id,
            extract("year", Transaction.date) == y,
        ).all()
        expenses = sum(-float(t.amount) for t in txs if t.amount < 0)
        income = sum(float(t.amount) for t in txs if t.amount > 0)
        running_balance += income - expenses
        rows.append({
            "year": y,
            "expenses": expenses,
            "income": income,
            "net": income - expenses,
            "ending_balance": running_balance,
        })
    return render_template(
        "reports_yearly.html",
        rows=rows,
        accounts=_accounts_for_select(),
        selected_account_id=account_id,
        currency=_currency_for(account_id),
    )

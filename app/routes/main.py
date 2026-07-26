from datetime import date
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import Account, Transaction, RecurringRule

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def dashboard():
    accounts = Account.query.filter_by(user_id=current_user.id, active=True).all()
    recent = (
        Transaction.query.filter_by(user_id=current_user.id)
        .order_by(Transaction.date.desc(), Transaction.created_at.desc())
        .limit(10)
        .all()
    )
    upcoming_count = RecurringRule.query.filter(
        RecurringRule.user_id == current_user.id,
        RecurringRule.active.is_(True),
        RecurringRule.next_due_date <= date.today().replace(day=28),
    ).count()
    return render_template(
        "dashboard.html", accounts=accounts, recent=recent, upcoming_count=upcoming_count
    )

from datetime import date
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Account, Transaction, RecurringRule
from app.utils import month_bounds, resolve_account_id

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
    today = date.today()
    # Same scope as the monthly budget page it links to (resolve_account_id
    # always narrows to a single account there), so the count shown here
    # matches exactly what the user will see after clicking through.
    account_id = resolve_account_id(current_user, None)
    _, month_end = month_bounds(today.year, today.month)
    upcoming_count = RecurringRule.query.filter(
        RecurringRule.user_id == current_user.id,
        RecurringRule.active.is_(True),
        RecurringRule.next_due_date <= month_end,
        db.or_(RecurringRule.account_id == account_id, RecurringRule.to_account_id == account_id),
    ).count()
    return render_template(
        "dashboard.html", accounts=accounts, recent=recent, upcoming_count=upcoming_count
    )

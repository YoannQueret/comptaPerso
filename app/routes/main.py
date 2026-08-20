from datetime import date
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Account, Transaction, RecurringRule
from app.utils import month_bounds, resolve_account_id, accessible_account_ids, account_access

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def dashboard():
    ids = accessible_account_ids(current_user)
    accounts = Account.query.filter(Account.id.in_(ids), Account.active.is_(True)).all()
    # own accounts first, shared ones last, alphabetical within each group
    accounts.sort(key=lambda a: (a.user_id != current_user.id, a.name))
    recent = (
        Transaction.query.filter(Transaction.account_id.in_(ids))
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
        RecurringRule.active.is_(True),
        RecurringRule.next_due_date <= month_end,
        db.or_(RecurringRule.account_id == account_id, RecurringRule.to_account_id == account_id),
    ).count()
    write_account_ids = {
        acc.id for acc in accounts if account_access(acc, current_user) in ("owner", "write")
    }
    return render_template(
        "dashboard.html",
        accounts=accounts,
        recent=recent,
        upcoming_count=upcoming_count,
        write_account_ids=write_account_ids,
    )

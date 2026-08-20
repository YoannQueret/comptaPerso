from datetime import date
from dateutil.relativedelta import relativedelta


def advance_date(d: date, periodicity: str, interval: int = 1) -> date:
    """Return the next due date for a recurring rule's periodicity."""
    interval = max(1, int(interval or 1))
    if periodicity == "week":
        return d + relativedelta(weeks=interval)
    if periodicity == "month":
        return d + relativedelta(months=interval)
    if periodicity == "quarter":
        return d + relativedelta(months=3 * interval)
    if periodicity == "year":
        return d + relativedelta(years=interval)
    # default: monthly
    return d + relativedelta(months=interval)


def month_bounds(year: int, month: int):
    start = date(year, month, 1)
    end = start + relativedelta(months=1) - relativedelta(days=1)
    return start, end


def accessible_account_ids(user, permission=None):
    """Account ids `user` may act on: owned, plus accounts shared with them.
    Pass permission="write" to only include write-shared accounts (owned
    accounts always count, regardless of permission)."""
    from app.models import Account, AccountShare

    owned = [aid for (aid,) in Account.query.filter_by(user_id=user.id).with_entities(Account.id).all()]
    shared_q = AccountShare.query.filter_by(user_id=user.id)
    if permission == "write":
        shared_q = shared_q.filter_by(permission="write")
    shared = [aid for (aid,) in shared_q.with_entities(AccountShare.account_id).all()]
    return list(dict.fromkeys(owned + shared))


def account_access(account, user):
    """None | "owner" | "read" | "write" — user's relationship to this account."""
    if account.user_id == user.id:
        return "owner"
    from app.models import AccountShare

    share = AccountShare.query.filter_by(account_id=account.id, user_id=user.id).first()
    return share.permission if share else None


def get_accessible_account_or_404(account_id, user, permission=None):
    """Fetch `account_id` only if accessible to `user`, else abort(404). Pass
    permission="write" to require write access (owner always qualifies)."""
    from flask import abort
    from app.extensions import db
    from app.models import Account

    acc = db.session.get(Account, account_id) if account_id else None
    if not acc:
        abort(404)
    level = account_access(acc, user)
    if level is None or (permission == "write" and level == "read"):
        abort(404)
    return acc


def resolve_account_id(user, requested_account_id):
    """Return a valid, accessible account_id (owned or shared): the requested one
    if accessible, otherwise the last one selected this session, otherwise the
    default account, otherwise the first account alphabetically. Whichever
    account is resolved is remembered in the session, so navigating between
    pages without an explicit ?account_id= keeps showing the same account
    instead of resetting to the default every time."""
    from flask import session
    from app.models import Account

    account_ids = accessible_account_ids(user)

    if requested_account_id and requested_account_id in account_ids:
        session["selected_account_id"] = requested_account_id
        return requested_account_id

    remembered_id = session.get("selected_account_id")
    if remembered_id and remembered_id in account_ids:
        return remembered_id

    if user.default_account_id and user.default_account_id in account_ids:
        session["selected_account_id"] = user.default_account_id
        return user.default_account_id

    fallback = Account.query.filter(Account.id.in_(account_ids)).order_by(Account.name).first()
    if fallback:
        session["selected_account_id"] = fallback.id
        return fallback.id
    return None


def safe_next(url):
    """Only accept a same-site relative path as a post-submit redirect target."""
    if url and url.startswith("/") and not url.startswith("//"):
        return url
    return None


def ordered_categories(user_id):
    """Categories sorted: parents alphabetically, each followed by its subcategories
    (already sorted via Category.children)."""
    from app.models import Category

    roots = (
        Category.query.filter_by(user_id=user_id, parent_id=None)
        .order_by(Category.name)
        .all()
    )
    categories = []
    for root in roots:
        categories.append(root)
        categories.extend(root.children)
    return categories


def categories_by_owner(accounts):
    """{owner_id: [{id, full_name}, ...]} for every distinct owner among `accounts` —
    a shared account's transactions/rules always use the OWNER's categories, and the
    account picker can span several owners once accounts can be shared, so the
    category <select> is rebuilt client-side on account change (see category-select.js)."""
    owner_ids = {acc.user_id for acc in accounts}
    return {
        owner_id: [{"id": c.id, "full_name": c.full_name} for c in ordered_categories(owner_id)]
        for owner_id in owner_ids
    }

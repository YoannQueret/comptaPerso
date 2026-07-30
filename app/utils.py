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


def resolve_account_id(user, requested_account_id):
    """Return a valid account_id belonging to the user: the requested one if valid,
    otherwise the last one selected this session, otherwise the default account,
    otherwise the first account alphabetically. Whichever account is resolved is
    remembered in the session, so navigating between pages without an explicit
    ?account_id= keeps showing the same account instead of resetting to the
    default every time."""
    from flask import session
    from app.models import Account

    if requested_account_id:
        acc = Account.query.filter_by(id=requested_account_id, user_id=user.id).first()
        if acc:
            session["selected_account_id"] = acc.id
            return acc.id

    remembered_id = session.get("selected_account_id")
    if remembered_id:
        acc = Account.query.filter_by(id=remembered_id, user_id=user.id).first()
        if acc:
            return acc.id

    if user.default_account_id:
        acc = Account.query.filter_by(id=user.default_account_id, user_id=user.id).first()
        if acc:
            session["selected_account_id"] = acc.id
            return acc.id

    fallback = Account.query.filter_by(user_id=user.id).order_by(Account.name).first()
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

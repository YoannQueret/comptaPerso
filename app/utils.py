import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dateutil.relativedelta import relativedelta

# curated for a manageable <select>, rather than every ~600 IANA zones —
# one representative city per UTC offset/region a user is realistically in.
COMMON_TIMEZONES = [
    "UTC",
    "Europe/London",
    "Europe/Paris",
    "Europe/Zurich",
    "Europe/Berlin",
    "Europe/Madrid",
    "Europe/Rome",
    "Europe/Lisbon",
    "Europe/Athens",
    "Europe/Moscow",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Sao_Paulo",
    "Africa/Cairo",
    "Africa/Johannesburg",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Asia/Singapore",
    "Australia/Sydney",
    "Pacific/Auckland",
]


def _user_zoneinfo(user):
    tz_name = (user.timezone if user and getattr(user, "timezone", None) else "UTC")
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def to_user_timezone(dt, user):
    """Convert a naive UTC datetime (as stored throughout this app) to
    `user`'s configured display timezone. Returns None if `dt` is None."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(_user_zoneinfo(user))


def today_for_user(user):
    """Today's calendar date in `user`'s configured timezone — independent of
    the server's own timezone/locale. Matters right around midnight: if the
    server runs in UTC and the user is in Europe/Paris (ahead of UTC), their
    local day has already turned over while the server's has not yet, and
    every "today" comparison in the app (default dates, the real/current
    balance, "future transaction" highlighting, overdue rules...) must use
    the user's day, not the server's."""
    return datetime.now(timezone.utc).astimezone(_user_zoneinfo(user)).date()


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


def parse_decimal(raw):
    """Parse a user-typed amount into a Decimal, tolerating whatever a bank
    statement, a receipt, or a non-English keyboard might produce: a comma as
    decimal separator, a space/apostrophe/dot used as a thousands separator
    (e.g. Swiss "1'234.50", French "1 234,50"), a stray currency symbol.
    Raises ValueError (never decimal.InvalidOperation) if truly unparseable,
    so callers only need to catch one exception type."""
    if raw is None:
        raise ValueError("empty amount")
    s = re.sub(r"[^\d,.\-]", "", raw.strip())
    if not s:
        raise ValueError("empty amount")
    if "," in s and "." in s:
        # whichever separator appears last is the decimal point; the other
        # one(s) must be thousands separators, so drop them
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ValueError(f"invalid amount: {raw!r}")


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

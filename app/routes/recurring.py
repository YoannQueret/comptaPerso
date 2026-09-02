import uuid
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, request, flash, g, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import RecurringRule, Account, Category, Transaction, PERIODICITIES
from app.utils import (
    advance_date,
    month_bounds,
    resolve_account_id,
    ordered_categories,
    categories_by_owner,
    safe_next,
    accessible_account_ids,
    account_access,
    get_accessible_account_or_404,
    parse_decimal,
    today_for_user,
)

bp = Blueprint("recurring", __name__)


def _parse_date(s, default=None):
    if not s:
        return default
    return datetime.strptime(s, "%Y-%m-%d").date()


def _parse_budget_month(s, fallback_date):
    if s:
        return datetime.strptime(s, "%Y-%m").date().replace(day=1)
    return fallback_date.replace(day=1)


def _rule_access(rule):
    """True if current_user has write/owner access to this rule's account — for a
    transfer rule, either leg's account being write-accessible is enough (mirrors
    the "either leg" rule used for editing an already-existing transfer)."""
    if account_access(rule.account, current_user) in ("owner", "write"):
        return True
    if rule.is_transfer and rule.to_account and account_access(rule.to_account, current_user) in ("owner", "write"):
        return True
    return False


SORT_COLUMNS = {
    "name": RecurringRule.label,
    "account": Account.name,
    "category": Category.name,
    "amount": RecurringRule.amount,
    "due_date": RecurringRule.next_due_date,
}


@bp.route("/recurring")
@login_required
def list_recurring():
    sort = request.args.get("sort", "due_date")
    if sort not in SORT_COLUMNS:
        sort = "due_date"
    direction = request.args.get("dir", "asc")
    if direction not in ("asc", "desc"):
        direction = "asc"

    column = SORT_COLUMNS[sort]
    order = column.asc() if direction == "asc" else column.desc()

    ids = accessible_account_ids(current_user)
    q = RecurringRule.query.filter(
        db.or_(RecurringRule.account_id.in_(ids), RecurringRule.to_account_id.in_(ids))
    )
    q = q.join(Account, RecurringRule.account_id == Account.id)
    if sort == "category":
        q = q.outerjoin(Category, RecurringRule.category_id == Category.id)
    rules = q.order_by(order).all()

    active_accounts = Account.query.filter(
        Account.id.in_(accessible_account_ids(current_user, permission="write")),
        Account.active.is_(True),
    ).order_by(Account.name).all()
    categories_by_owner_map = categories_by_owner(active_accounts)

    preselected_account_id = resolve_account_id(current_user, None)
    write_ids = {a.id for a in active_accounts}
    if preselected_account_id not in write_ids:
        preselected_account_id = active_accounts[0].id if active_accounts else None
    initial_owner_id = next(
        (a.user_id for a in active_accounts if a.id == preselected_account_id), current_user.id
    )
    categories = ordered_categories(initial_owner_id)

    return render_template(
        "recurring.html",
        rules=rules,
        sort=sort,
        direction=direction,
        active_accounts=active_accounts,
        categories=categories,
        categories_by_owner=categories_by_owner_map,
        periodicities=PERIODICITIES,
        preselected_account_id=preselected_account_id,
        today=today_for_user(current_user),
    )


def _parse_rule_amounts(form, kind):
    """Return (amount, is_transfer, to_account_id, amount_received, category_id)
    from a recurring-rule form, given the selected kind (expense/income/transfer).
    Raises ValueError if an amount can't be parsed."""
    if kind == "transfer":
        amount = -abs(parse_decimal(form.get("amount")))
        received_raw = form.get("amount_received") or form.get("amount")
        amount_received = abs(parse_decimal(received_raw))
        return amount, True, form.get("to_account_id") or None, amount_received, None

    amount = parse_decimal(form.get("amount"))
    amount = -abs(amount) if kind == "expense" else abs(amount)
    return amount, False, None, None, form.get("category_id") or None


@bp.route("/recurring/new", methods=["GET", "POST"])
@login_required
def new_recurring():
    accounts = Account.query.filter(
        Account.id.in_(accessible_account_ids(current_user, permission="write")),
        Account.active.is_(True),
    ).order_by(Account.name).all()
    categories_by_owner_map = categories_by_owner(accounts)

    preselected_account_id = resolve_account_id(current_user, request.args.get("account_id"))
    write_ids = {a.id for a in accounts}
    if preselected_account_id not in write_ids:
        preselected_account_id = accounts[0].id if accounts else None
    initial_owner_id = next(
        (a.user_id for a in accounts if a.id == preselected_account_id), current_user.id
    )
    categories = ordered_categories(initial_owner_id)

    if request.method == "POST":
        kind = request.form["kind"]
        try:
            amount, is_transfer, to_account_id, amount_received, category_id = _parse_rule_amounts(
                request.form, kind
            )
        except ValueError:
            flash(g._("invalid_transaction_data"), "danger")
            return render_template(
                "recurring_form.html",
                rule=None,
                accounts=accounts,
                categories=categories,
                categories_by_owner=categories_by_owner_map,
                periodicities=PERIODICITIES,
                preselected_account_id=preselected_account_id,
                next_url=safe_next(request.form.get("next")),
            )

        if is_transfer and to_account_id == request.form["account_id"]:
            flash(g._("transfer_accounts_must_differ"), "danger")
            return render_template(
                "recurring_form.html",
                rule=None,
                accounts=accounts,
                categories=categories,
                categories_by_owner=categories_by_owner_map,
                periodicities=PERIODICITIES,
                preselected_account_id=preselected_account_id,
                next_url=safe_next(request.form.get("next")),
            )

        acc = get_accessible_account_or_404(request.form.get("account_id"), current_user, permission="write")
        to_account = None
        if is_transfer:
            to_account = get_accessible_account_or_404(to_account_id, current_user, permission="write")

        start = _parse_date(request.form["start_date"], today_for_user(current_user))
        rule = RecurringRule(
            user_id=acc.user_id,
            account_id=acc.id,
            category_id=category_id,
            label=request.form["label"].strip(),
            amount=amount,
            is_transfer=is_transfer,
            to_account_id=to_account.id if to_account else None,
            amount_received=amount_received,
            periodicity=request.form.get("periodicity", "month"),
            interval=int(request.form.get("interval") or 1),
            start_date=start,
            next_due_date=start,
            end_date=_parse_date(request.form.get("end_date")),
        )
        db.session.add(rule)
        db.session.commit()
        flash(g._("recurring_created"), "success")
        next_url = safe_next(request.form.get("next"))
        return redirect(next_url or url_for("recurring.list_recurring"))

    return render_template(
        "recurring_form.html",
        rule=None,
        accounts=accounts,
        categories=categories,
        categories_by_owner=categories_by_owner_map,
        periodicities=PERIODICITIES,
        preselected_account_id=preselected_account_id,
        next_url=safe_next(request.args.get("next")),
    )


@bp.route("/recurring/<rule_id>/edit", methods=["GET", "POST"])
@login_required
def edit_recurring(rule_id):
    rule = RecurringRule.query.filter_by(id=rule_id).first_or_404()
    if not _rule_access(rule):
        abort(404)

    accounts = Account.query.filter(
        Account.id.in_(accessible_account_ids(current_user, permission="write"))
    ).order_by(Account.name).all()
    categories_by_owner_map = categories_by_owner(accounts)
    categories = ordered_categories(rule.account.user_id)

    if request.method == "POST":
        kind = request.form["kind"]
        try:
            amount, is_transfer, to_account_id, amount_received, category_id = _parse_rule_amounts(
                request.form, kind
            )
        except ValueError:
            flash(g._("invalid_transaction_data"), "danger")
            return render_template(
                "recurring_form.html", rule=rule, accounts=accounts, categories=categories,
                categories_by_owner=categories_by_owner_map,
                periodicities=PERIODICITIES,
            )

        if is_transfer and to_account_id == request.form["account_id"]:
            flash(g._("transfer_accounts_must_differ"), "danger")
            return render_template(
                "recurring_form.html", rule=rule, accounts=accounts, categories=categories,
                categories_by_owner=categories_by_owner_map,
                periodicities=PERIODICITIES,
            )

        acc = get_accessible_account_or_404(request.form.get("account_id"), current_user, permission="write")
        to_account = None
        if is_transfer:
            to_account = get_accessible_account_or_404(to_account_id, current_user, permission="write")

        rule.amount = amount
        rule.is_transfer = is_transfer
        rule.to_account_id = to_account.id if to_account else None
        rule.amount_received = amount_received
        rule.account_id = acc.id
        rule.user_id = acc.user_id
        rule.category_id = category_id
        rule.label = request.form["label"].strip()
        rule.periodicity = request.form.get("periodicity", "month")
        rule.interval = int(request.form.get("interval") or 1)
        rule.next_due_date = _parse_date(request.form.get("next_due_date"), rule.next_due_date)
        rule.end_date = _parse_date(request.form.get("end_date"))
        rule.active = bool(request.form.get("active"))
        db.session.commit()
        flash(g._("recurring_updated"), "success")
        return redirect(url_for("recurring.list_recurring"))

    return render_template(
        "recurring_form.html",
        rule=rule,
        accounts=accounts,
        categories=categories,
        categories_by_owner=categories_by_owner_map,
        periodicities=PERIODICITIES,
    )


@bp.route("/recurring/<rule_id>/delete", methods=["POST"])
@login_required
def delete_recurring(rule_id):
    rule = RecurringRule.query.filter_by(id=rule_id).first_or_404()
    if not _rule_access(rule):
        abort(404)
    db.session.delete(rule)
    db.session.commit()
    flash(g._("recurring_deleted"), "success")
    return redirect(url_for("recurring.list_recurring"))


def _carryover_balance(account_id, start):
    """Budget balance just before `start`: initial balance + all transactions whose
    budget_month is before this one (not `date` — a budget-shifted transaction must
    be counted exactly once, either in the carryover or in the month's own total)."""
    ids = accessible_account_ids(current_user)
    carryover_q = db.session.query(
        db.func.coalesce(db.func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.account_id.in_(ids),
        Transaction.budget_month < start,
    )
    initial_balance_q = db.session.query(
        db.func.coalesce(db.func.sum(Account.initial_balance), 0)
    ).filter(Account.id.in_(ids))
    if account_id:
        carryover_q = carryover_q.filter(Transaction.account_id == account_id)
        initial_balance_q = initial_balance_q.filter(Account.id == account_id)
    return float(initial_balance_q.scalar() or 0) + float(carryover_q.scalar() or 0)


def _rule_pending_amount(rule, account_id):
    """Signed amount a due (not-yet-validated) rule contributes for `account_id`:
    the sent amount for its source account, the received amount when `account_id`
    is a transfer's destination — so a transfer shows as pending income on the
    account that's about to receive it, not as an expense."""
    if rule.is_transfer and account_id and rule.to_account_id == account_id:
        return float(rule.amount_received if rule.amount_received is not None else abs(rule.amount))
    return float(rule.amount)


@bp.route("/budget/<int:year>/<int:month>")
@login_required
def monthly_budget(year, month):
    start, end = month_bounds(year, month)
    account_id = resolve_account_id(current_user, request.args.get("account_id"))
    ids = accessible_account_ids(current_user)

    # occurrences due this month or overdue (not yet validated) — a transfer rule
    # is due on both its source and destination account's budget page.
    due_rules_q = RecurringRule.query.filter(
        db.or_(RecurringRule.account_id.in_(ids), RecurringRule.to_account_id.in_(ids)),
        RecurringRule.active.is_(True),
        RecurringRule.next_due_date <= end,
    )
    if account_id:
        due_rules_q = due_rules_q.filter(
            db.or_(RecurringRule.account_id == account_id, RecurringRule.to_account_id == account_id)
        )
    due_rules = due_rules_q.order_by(RecurringRule.next_due_date).all()

    validated_txs_q = Transaction.query.filter(
        Transaction.account_id.in_(ids),
        Transaction.budget_month == start,
        Transaction.recurring_rule_id.isnot(None),
    )
    if account_id:
        validated_txs_q = validated_txs_q.filter(Transaction.account_id == account_id)
    validated_txs = validated_txs_q.order_by(Transaction.date.desc()).all()

    other_txs_q = Transaction.query.filter(
        Transaction.account_id.in_(ids),
        Transaction.budget_month == start,
        Transaction.recurring_rule_id.is_(None),
    )
    if account_id:
        other_txs_q = other_txs_q.filter(Transaction.account_id == account_id)
    other_txs = other_txs_q.order_by(Transaction.date.desc()).all()

    transfer_group_ids = {t.transfer_group_id for t in other_txs if t.is_transfer}
    transfer_counterparts = {}
    if transfer_group_ids:
        legs = Transaction.query.filter(Transaction.transfer_group_id.in_(transfer_group_ids)).all()
        by_group = {}
        for leg in legs:
            by_group.setdefault(leg.transfer_group_id, []).append(leg)
        for t in other_txs:
            if t.is_transfer:
                transfer_counterparts[t.id] = next(
                    (leg for leg in by_group.get(t.transfer_group_id, []) if leg.id != t.id), None
                )

    total_expenses = sum(-float(t.amount) for t in validated_txs + other_txs if t.amount < 0)
    total_income = sum(float(t.amount) for t in validated_txs + other_txs if t.amount > 0)

    pending_amounts = [_rule_pending_amount(r, account_id) for r in due_rules]
    pending_expenses = sum(-a for a in pending_amounts if a < 0)
    pending_income = sum(a for a in pending_amounts if a > 0)

    remaining_validated = total_income - total_expenses
    remaining_forecast = (total_income + pending_income) - (total_expenses + pending_expenses)

    carryover = _carryover_balance(account_id, start)
    net_with_carryover = carryover + remaining_validated

    prev_month = start.replace(day=1) - timedelta(days=1)
    next_month_date = end + timedelta(days=1)

    accounts = Account.query.filter(Account.id.in_(ids)).order_by(Account.name).all()
    active_accounts = Account.query.filter(
        Account.id.in_(accessible_account_ids(current_user, permission="write")),
        Account.active.is_(True),
    ).order_by(Account.name).all()
    categories_by_owner_map = categories_by_owner(active_accounts)
    write_ids = {a.id for a in active_accounts}
    dialog_account_id = account_id if account_id in write_ids else (
        active_accounts[0].id if active_accounts else None
    )
    dialog_owner_id = next(
        (a.user_id for a in active_accounts if a.id == dialog_account_id), current_user.id
    )
    categories = ordered_categories(dialog_owner_id)
    can_add_here = account_id in write_ids

    return render_template(
        "budget_monthly.html",
        year=year,
        month=month,
        start=start,
        end=end,
        due_rules=due_rules,
        validated_txs=validated_txs,
        other_txs=other_txs,
        total_expenses=total_expenses,
        total_income=total_income,
        remaining_forecast=remaining_forecast,
        active_accounts=active_accounts,
        categories=categories,
        categories_by_owner=categories_by_owner_map,
        today=today_for_user(current_user),
        carryover=carryover,
        net_with_carryover=net_with_carryover,
        prev_year=prev_month.year,
        prev_month=prev_month.month,
        next_year=next_month_date.year,
        next_month=next_month_date.month,
        accounts=accounts,
        selected_account_id=account_id,
        transfer_counterparts=transfer_counterparts,
        can_add_here=can_add_here,
    )


def _rule_occurrences_in_range(rule, start, end):
    """Project a recurring rule's occurrences landing within [start, end],
    stepping forward from its actual next_due_date (which may be before
    `start`, overdue relative to today, or the displayed month itself)."""
    dates = []
    d = rule.next_due_date
    for _ in range(2000):  # safety cap, e.g. ~38 years of weekly occurrences
        if d > end:
            break
        if d >= start:
            dates.append(d)
        d = advance_date(d, rule.periodicity, rule.interval)
    return dates


@bp.route("/budget/<int:year>/<int:month>/chart-data")
@login_required
def monthly_budget_chart_data(year, month):
    start, end = month_bounds(year, month)
    account_id = resolve_account_id(current_user, request.args.get("account_id"))
    today = today_for_user(current_user)
    ids = accessible_account_ids(current_user)

    account = Account.query.filter(Account.id == account_id, Account.id.in_(ids)).first() if account_id else None

    # Charted transactions must match the same set the summary cards count for
    # this month (budget_month), not the real transaction date — otherwise a
    # budget-shifted transaction (e.g. a salary paid 26/07 but budgeted to
    # August) would silently vanish from one or the other and the chart's
    # ending balance would no longer reconcile with "net balance (with
    # carryover)" + the remaining forecast.
    txs_q = Transaction.query.filter(
        Transaction.account_id.in_(ids),
        Transaction.budget_month == start,
    )
    due_rules_q = RecurringRule.query.filter(
        db.or_(RecurringRule.account_id.in_(ids), RecurringRule.to_account_id.in_(ids)),
        RecurringRule.active.is_(True),
        RecurringRule.next_due_date <= end,
    )
    if account_id:
        txs_q = txs_q.filter(Transaction.account_id == account_id)
        due_rules_q = due_rules_q.filter(
            db.or_(RecurringRule.account_id == account_id, RecurringRule.to_account_id == account_id)
        )
    txs = txs_q.order_by(Transaction.date, Transaction.created_at).all()
    due_rules = due_rules_q.order_by(RecurringRule.next_due_date).all()

    events = [
        {
            # clamp to the displayed month for the X axis — its real date may
            # fall outside this month when budget_month was overridden
            "date": min(max(t.date, start), end),
            "amount": float(t.amount),
            "label": t.description or g._("transaction"),
            "realized": t.date <= today,
        }
        for t in txs
    ]
    for r in due_rules:
        amount = _rule_pending_amount(r, account_id)
        events += [
            {"date": d, "amount": amount, "label": r.label}
            for d in _rule_occurrences_in_range(r, start, end)
        ]
    events.sort(key=lambda e: e["date"])

    # group same-day events into one point — several transactions landing on
    # the same date would otherwise sit at the exact same X position anyway,
    # and the tooltip needs all of that day's operations together, not just
    # whichever one happened to be nearest.
    events_by_date = {}
    for event in events:
        events_by_date.setdefault(event["date"], []).append(event)

    running_balance = _carryover_balance(account_id, start)
    points = [{
        "date": (start - timedelta(days=1)).isoformat(),
        "balance": round(running_balance, 2),
        "items": [],
        "realized": True,
    }]
    for event_date in sorted(events_by_date):
        day_events = events_by_date[event_date]
        for event in day_events:
            running_balance += event["amount"]
        points.append({
            "date": event_date.isoformat(),
            "balance": round(running_balance, 2),
            "items": [{"label": e["label"], "amount": e["amount"]} for e in day_events],
            "realized": event_date <= today,
        })

    # extend the line flat to the end of the month so the X axis always spans
    # the full displayed month, even if nothing else happens after the last event
    if points[-1]["date"] != end.isoformat():
        points.append({
            "date": end.isoformat(),
            "balance": points[-1]["balance"],
            "items": [],
            "realized": end <= today,
        })

    return {
        "points": points,
        "today": today.isoformat(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "currency": account.currency if account else "",
    }


@bp.route("/budget/validate/<rule_id>", methods=["POST"])
@login_required
def validate_occurrence(rule_id):
    rule = RecurringRule.query.filter_by(id=rule_id).first_or_404()
    if not _rule_access(rule):
        abort(404)

    def _back_to_budget():
        fallback_date = _parse_date(request.form.get("date"), rule.next_due_date) or rule.next_due_date
        redirect_year = request.form.get("year", type=int) or fallback_date.year
        redirect_month = request.form.get("month", type=int) or fallback_date.month
        redirect_account_id = request.form.get("account_id") or None
        return redirect(
            url_for(
                "recurring.monthly_budget",
                year=redirect_year,
                month=redirect_month,
                account_id=redirect_account_id,
            )
        )

    try:
        occ_date = _parse_date(request.form["date"], rule.next_due_date)
        budget_month = _parse_budget_month(request.form.get("budget_month"), occ_date)
        if rule.is_transfer:
            amount_sent = abs(parse_decimal(request.form.get("amount")))
            received_raw = request.form.get("amount_received") or request.form.get("amount")
            amount_received = abs(parse_decimal(received_raw))
        else:
            amount = parse_decimal(request.form.get("amount"))
    except ValueError:
        flash(g._("invalid_transaction_data"), "danger")
        return _back_to_budget()

    if rule.is_transfer:
        group_id = str(uuid.uuid4())
        db.session.add(Transaction(
            user_id=rule.account.user_id,
            account_id=rule.account_id,
            date=occ_date,
            budget_month=budget_month,
            amount=-amount_sent,
            description=rule.label,
            is_transfer=True,
            transfer_group_id=group_id,
            recurring_rule_id=rule.id,
        ))
        db.session.add(Transaction(
            user_id=rule.to_account.user_id,
            account_id=rule.to_account_id,
            date=occ_date,
            budget_month=budget_month,
            amount=amount_received,
            description=rule.label,
            is_transfer=True,
            transfer_group_id=group_id,
            recurring_rule_id=rule.id,
        ))
    else:
        amount = -abs(amount) if rule.amount < 0 else abs(amount)
        db.session.add(Transaction(
            user_id=rule.account.user_id,
            account_id=rule.account_id,
            category_id=rule.category_id,
            date=occ_date,
            budget_month=budget_month,
            amount=amount,
            description=rule.label,
            recurring_rule_id=rule.id,
        ))

    # advance to the next due date
    rule.next_due_date = advance_date(rule.next_due_date, rule.periodicity, rule.interval)
    if rule.end_date and rule.next_due_date > rule.end_date:
        rule.active = False

    db.session.commit()
    flash(g._("occurrence_validated"), "success")

    redirect_year = request.form.get("year", type=int) or occ_date.year
    redirect_month = request.form.get("month", type=int) or occ_date.month
    redirect_account_id = request.form.get("account_id") or None
    return redirect(
        url_for(
            "recurring.monthly_budget",
            year=redirect_year,
            month=redirect_month,
            account_id=redirect_account_id,
        )
    )


@bp.route("/budget/ignore/<rule_id>", methods=["POST"])
@login_required
def ignore_occurrence(rule_id):
    rule = RecurringRule.query.filter_by(id=rule_id).first_or_404()
    if not _rule_access(rule):
        abort(404)

    rule.next_due_date = advance_date(rule.next_due_date, rule.periodicity, rule.interval)
    if rule.end_date and rule.next_due_date > rule.end_date:
        rule.active = False

    db.session.commit()
    flash(g._("occurrence_ignored"), "success")

    redirect_today = today_for_user(current_user)
    redirect_year = request.form.get("year", type=int) or redirect_today.year
    redirect_month = request.form.get("month", type=int) or redirect_today.month
    redirect_account_id = request.form.get("account_id") or None
    return redirect(
        url_for(
            "recurring.monthly_budget",
            year=redirect_year,
            month=redirect_month,
            account_id=redirect_account_id,
        )
    )


@bp.route("/budget/unvalidate/<tx_id>", methods=["POST"])
@login_required
def unvalidate_occurrence(tx_id):
    tx = (
        Transaction.query.filter_by(id=tx_id)
        .filter(Transaction.recurring_rule_id.isnot(None))
        .first_or_404()
    )
    if account_access(tx.account, current_user) not in ("owner", "write"):
        abort(404)
    rule = tx.recurring_rule
    occ_date = tx.date

    rule.next_due_date = occ_date
    rule.active = True
    if tx.is_transfer:
        Transaction.query.filter_by(transfer_group_id=tx.transfer_group_id).delete()
    else:
        db.session.delete(tx)
    db.session.commit()
    flash(g._("occurrence_reverted"), "success")

    redirect_year = request.form.get("year", type=int) or occ_date.year
    redirect_month = request.form.get("month", type=int) or occ_date.month
    redirect_account_id = request.form.get("account_id") or None
    return redirect(
        url_for(
            "recurring.monthly_budget",
            year=redirect_year,
            month=redirect_month,
            account_id=redirect_account_id,
        )
    )

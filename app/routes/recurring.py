import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, render_template, redirect, url_for, request, flash, g
from flask_login import login_required, current_user

from app.extensions import db
from app.models import RecurringRule, Account, Category, Transaction, PERIODICITIES
from app.utils import advance_date, month_bounds, resolve_account_id, ordered_categories, safe_next

bp = Blueprint("recurring", __name__)


def _parse_date(s, default=None):
    if not s:
        return default
    return datetime.strptime(s, "%Y-%m-%d").date()


def _parse_budget_month(s, fallback_date):
    if s:
        return datetime.strptime(s, "%Y-%m").date().replace(day=1)
    return fallback_date.replace(day=1)


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

    q = RecurringRule.query.filter_by(user_id=current_user.id)
    q = q.join(Account, RecurringRule.account_id == Account.id)
    if sort == "category":
        q = q.outerjoin(Category, RecurringRule.category_id == Category.id)
    rules = q.order_by(order).all()

    active_accounts = Account.query.filter_by(user_id=current_user.id, active=True).order_by(
        Account.name
    ).all()
    categories = ordered_categories(current_user.id)
    preselected_account_id = resolve_account_id(current_user, None)

    return render_template(
        "recurring.html",
        rules=rules,
        sort=sort,
        direction=direction,
        active_accounts=active_accounts,
        categories=categories,
        periodicities=PERIODICITIES,
        preselected_account_id=preselected_account_id,
        today=date.today(),
    )


def _parse_rule_amounts(form, kind):
    """Return (amount, is_transfer, to_account_id, amount_received, category_id)
    from a recurring-rule form, given the selected kind (expense/income/transfer)."""
    if kind == "transfer":
        amount = -abs(Decimal(form["amount"].replace(",", ".")))
        received_raw = form.get("amount_received") or form["amount"]
        amount_received = abs(Decimal(received_raw.replace(",", ".")))
        return amount, True, form.get("to_account_id") or None, amount_received, None

    amount = Decimal(form["amount"].replace(",", "."))
    amount = -abs(amount) if kind == "expense" else abs(amount)
    return amount, False, None, None, form.get("category_id") or None


@bp.route("/recurring/new", methods=["GET", "POST"])
@login_required
def new_recurring():
    accounts = Account.query.filter_by(user_id=current_user.id, active=True).order_by(
        Account.name
    ).all()
    categories = ordered_categories(current_user.id)

    if request.method == "POST":
        kind = request.form["kind"]
        amount, is_transfer, to_account_id, amount_received, category_id = _parse_rule_amounts(
            request.form, kind
        )

        if is_transfer and to_account_id == request.form["account_id"]:
            flash(g._("transfer_accounts_must_differ"), "danger")
            return render_template(
                "recurring_form.html",
                rule=None,
                accounts=accounts,
                categories=categories,
                periodicities=PERIODICITIES,
                preselected_account_id=resolve_account_id(current_user, request.args.get("account_id")),
                next_url=safe_next(request.form.get("next")),
            )

        start = _parse_date(request.form["start_date"], date.today())
        rule = RecurringRule(
            user_id=current_user.id,
            account_id=request.form["account_id"],
            category_id=category_id,
            label=request.form["label"].strip(),
            amount=amount,
            is_transfer=is_transfer,
            to_account_id=to_account_id,
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

    preselected_account_id = resolve_account_id(current_user, request.args.get("account_id"))
    return render_template(
        "recurring_form.html",
        rule=None,
        accounts=accounts,
        categories=categories,
        periodicities=PERIODICITIES,
        preselected_account_id=preselected_account_id,
        next_url=safe_next(request.args.get("next")),
    )


@bp.route("/recurring/<rule_id>/edit", methods=["GET", "POST"])
@login_required
def edit_recurring(rule_id):
    rule = RecurringRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.name).all()
    categories = ordered_categories(current_user.id)

    if request.method == "POST":
        kind = request.form["kind"]
        amount, is_transfer, to_account_id, amount_received, category_id = _parse_rule_amounts(
            request.form, kind
        )

        if is_transfer and to_account_id == request.form["account_id"]:
            flash(g._("transfer_accounts_must_differ"), "danger")
            return render_template(
                "recurring_form.html", rule=rule, accounts=accounts, categories=categories,
                periodicities=PERIODICITIES,
            )

        rule.amount = amount
        rule.is_transfer = is_transfer
        rule.to_account_id = to_account_id
        rule.amount_received = amount_received
        rule.account_id = request.form["account_id"]
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
        periodicities=PERIODICITIES,
    )


@bp.route("/recurring/<rule_id>/delete", methods=["POST"])
@login_required
def delete_recurring(rule_id):
    rule = RecurringRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    db.session.delete(rule)
    db.session.commit()
    flash(g._("recurring_deleted"), "success")
    return redirect(url_for("recurring.list_recurring"))


def _carryover_balance(account_id, start):
    """Budget balance just before `start`: initial balance + all transactions whose
    budget_month is before this one (not `date` — a budget-shifted transaction must
    be counted exactly once, either in the carryover or in the month's own total)."""
    carryover_q = db.session.query(
        db.func.coalesce(db.func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.budget_month < start,
    )
    initial_balance_q = db.session.query(
        db.func.coalesce(db.func.sum(Account.initial_balance), 0)
    ).filter(Account.user_id == current_user.id)
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

    # occurrences due this month or overdue (not yet validated) — a transfer rule
    # is due on both its source and destination account's budget page.
    due_rules_q = RecurringRule.query.filter(
        RecurringRule.user_id == current_user.id,
        RecurringRule.active.is_(True),
        RecurringRule.next_due_date <= end,
    )
    if account_id:
        due_rules_q = due_rules_q.filter(
            db.or_(RecurringRule.account_id == account_id, RecurringRule.to_account_id == account_id)
        )
    due_rules = due_rules_q.order_by(RecurringRule.next_due_date).all()

    validated_txs_q = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.budget_month == start,
        Transaction.recurring_rule_id.isnot(None),
    )
    if account_id:
        validated_txs_q = validated_txs_q.filter(Transaction.account_id == account_id)
    validated_txs = validated_txs_q.order_by(Transaction.date).all()

    other_txs_q = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.budget_month == start,
        Transaction.recurring_rule_id.is_(None),
    )
    if account_id:
        other_txs_q = other_txs_q.filter(Transaction.account_id == account_id)
    other_txs = other_txs_q.order_by(Transaction.date).all()

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

    accounts = Account.query.filter_by(user_id=current_user.id).order_by(Account.name).all()
    active_accounts = [a for a in accounts if a.active]
    categories = ordered_categories(current_user.id)

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
        remaining_validated=remaining_validated,
        remaining_forecast=remaining_forecast,
        active_accounts=active_accounts,
        categories=categories,
        today=date.today(),
        carryover=carryover,
        net_with_carryover=net_with_carryover,
        prev_year=prev_month.year,
        prev_month=prev_month.month,
        next_year=next_month_date.year,
        next_month=next_month_date.month,
        accounts=accounts,
        selected_account_id=account_id,
        transfer_counterparts=transfer_counterparts,
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
    today = date.today()

    account = Account.query.filter_by(id=account_id, user_id=current_user.id).first() if account_id else None

    txs_q = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start,
        Transaction.date <= end,
    )
    due_rules_q = RecurringRule.query.filter(
        RecurringRule.user_id == current_user.id,
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
        {"date": t.date, "amount": float(t.amount), "label": t.description or g._("transaction")}
        for t in txs
    ]
    for r in due_rules:
        amount = _rule_pending_amount(r, account_id)
        events += [
            {"date": d, "amount": amount, "label": r.label}
            for d in _rule_occurrences_in_range(r, start, end)
        ]
    events.sort(key=lambda e: e["date"])

    running_balance = _carryover_balance(account_id, start)
    points = [{
        "date": (start - timedelta(days=1)).isoformat(),
        "balance": round(running_balance, 2),
        "label": None,
        "realized": True,
    }]
    for event in events:
        running_balance += event["amount"]
        points.append({
            "date": event["date"].isoformat(),
            "balance": round(running_balance, 2),
            "label": event["label"],
            "realized": event["date"] <= today,
        })

    # extend the line flat to the end of the month so the X axis always spans
    # the full displayed month, even if nothing else happens after the last event
    if points[-1]["date"] != end.isoformat():
        points.append({
            "date": end.isoformat(),
            "balance": points[-1]["balance"],
            "label": None,
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
    rule = RecurringRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()
    occ_date = _parse_date(request.form["date"], rule.next_due_date)
    budget_month = _parse_budget_month(request.form.get("budget_month"), occ_date)

    if rule.is_transfer:
        amount_sent = abs(Decimal(request.form["amount"].replace(",", ".")))
        received_raw = request.form.get("amount_received") or request.form["amount"]
        amount_received = abs(Decimal(received_raw.replace(",", ".")))
        group_id = str(uuid.uuid4())
        db.session.add(Transaction(
            user_id=current_user.id,
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
            user_id=current_user.id,
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
        amount = Decimal(request.form["amount"].replace(",", "."))
        amount = -abs(amount) if rule.amount < 0 else abs(amount)
        db.session.add(Transaction(
            user_id=current_user.id,
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
    rule = RecurringRule.query.filter_by(id=rule_id, user_id=current_user.id).first_or_404()

    rule.next_due_date = advance_date(rule.next_due_date, rule.periodicity, rule.interval)
    if rule.end_date and rule.next_due_date > rule.end_date:
        rule.active = False

    db.session.commit()
    flash(g._("occurrence_ignored"), "success")

    redirect_year = request.form.get("year", type=int) or date.today().year
    redirect_month = request.form.get("month", type=int) or date.today().month
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
        Transaction.query.filter_by(id=tx_id, user_id=current_user.id)
        .filter(Transaction.recurring_rule_id.isnot(None))
        .first_or_404()
    )
    rule = tx.recurring_rule
    occ_date = tx.date

    rule.next_due_date = occ_date
    rule.active = True
    if tx.is_transfer:
        Transaction.query.filter_by(
            transfer_group_id=tx.transfer_group_id, user_id=current_user.id
        ).delete()
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

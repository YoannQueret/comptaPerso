import uuid
from datetime import datetime, date

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


def gen_uuid():
    return str(uuid.uuid4())


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    locale = db.Column(db.String(5), default="fr")
    default_account_id = db.Column(
        db.String(36),
        db.ForeignKey("accounts.id", use_alter=True, name="fk_users_default_account_id"),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_seen_at = db.Column(db.DateTime, nullable=True)
    active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)

    accounts = db.relationship(
        "Account", backref="user", cascade="all, delete-orphan", foreign_keys="Account.user_id"
    )
    default_account = db.relationship("Account", foreign_keys=[default_account_id])
    categories = db.relationship("Category", backref="user", cascade="all, delete-orphan")
    account_types = db.relationship("AccountType", backref="user", cascade="all, delete-orphan")
    currencies = db.relationship("Currency", backref="user", cascade="all, delete-orphan")
    sent_invitations = db.relationship(
        "Invitation",
        backref="invited_by",
        cascade="all, delete-orphan",
        foreign_keys="Invitation.invited_by_id",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class AccountType(db.Model):
    __tablename__ = "account_types"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)


class Currency(db.Model):
    __tablename__ = "currencies"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    code = db.Column(db.String(3), nullable=False)
    active = db.Column(db.Boolean, default=False)


class Account(db.Model):
    __tablename__ = "accounts"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    account_number = db.Column(db.String(64), nullable=True)
    account_type_id = db.Column(db.String(36), db.ForeignKey("account_types.id"), nullable=True)
    currency = db.Column(db.String(3), nullable=False, default="EUR")
    initial_balance = db.Column(db.Numeric(14, 2), default=0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    transactions = db.relationship(
        "Transaction", backref="account", cascade="all, delete-orphan", lazy="dynamic"
    )
    account_type = db.relationship("AccountType", backref="accounts")

    @property
    def balance(self):
        """Full balance including future-dated transactions."""
        total = db.session.query(db.func.coalesce(db.func.sum(Transaction.amount), 0)).filter(
            Transaction.account_id == self.id
        ).scalar()
        return float(self.initial_balance or 0) + float(total or 0)

    @property
    def current_balance(self):
        """Real balance as of today: excludes any transaction dated in the future."""
        total = db.session.query(db.func.coalesce(db.func.sum(Transaction.amount), 0)).filter(
            Transaction.account_id == self.id,
            Transaction.date <= date.today(),
        ).scalar()
        return float(self.initial_balance or 0) + float(total or 0)


CATEGORY_KINDS = ["expense", "income", "both"]


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    parent_id = db.Column(db.String(36), db.ForeignKey("categories.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(10), default="both")  # expense / income / both
    color = db.Column(db.String(7), default="#6c757d")

    children = db.relationship(
        "Category",
        backref=db.backref("parent", remote_side=[id]),
        cascade="all, delete-orphan",
        order_by="Category.name",
    )

    @property
    def full_name(self):
        if self.parent:
            return f"{self.parent.name} / {self.name}"
        return self.name


class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    account_id = db.Column(db.String(36), db.ForeignKey("accounts.id"), nullable=False, index=True)
    category_id = db.Column(db.String(36), db.ForeignKey("categories.id"), nullable=True)
    date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    # which month's budget this counts toward (always the 1st of a month); independent
    # from `date`, which stays the real bank-movement date used for account balances.
    budget_month = db.Column(db.Date, nullable=False, index=True)
    # signed amount: positive = income, negative = expense (in the account's currency)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    description = db.Column(db.String(255))
    is_transfer = db.Column(db.Boolean, default=False)
    transfer_group_id = db.Column(db.String(36), nullable=True, index=True)
    recurring_rule_id = db.Column(db.String(36), db.ForeignKey("recurring_rules.id"), nullable=True)
    attachment_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship("Category")


PERIODICITIES = ["week", "month", "quarter", "year"]


class RecurringRule(db.Model):
    __tablename__ = "recurring_rules"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    account_id = db.Column(db.String(36), db.ForeignKey("accounts.id"), nullable=False)
    category_id = db.Column(db.String(36), db.ForeignKey("categories.id"), nullable=True)
    label = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)  # signed, approximate
    periodicity = db.Column(db.String(10), default="month")
    interval = db.Column(db.Integer, default=1)  # every N periods (months, weeks...)
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    next_due_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True)
    is_transfer = db.Column(db.Boolean, default=False)
    to_account_id = db.Column(db.String(36), db.ForeignKey("accounts.id"), nullable=True)
    amount_received = db.Column(db.Numeric(14, 2), nullable=True)  # transfers only, approximate

    account = db.relationship("Account", foreign_keys=[account_id])
    to_account = db.relationship("Account", foreign_keys=[to_account_id])
    category = db.relationship("Category")
    occurrences = db.relationship("Transaction", backref="recurring_rule")


class Invitation(db.Model):
    """A log of invite emails sent by an admin. The token itself stays a
    stateless signed value (see auth.generate_invite_token) — this table only
    exists so admins can see what was sent, not to validate the token."""

    __tablename__ = "invitations"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    email = db.Column(db.String(255), nullable=False, index=True)
    invited_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    accepted_at = db.Column(db.DateTime, nullable=True)

from datetime import datetime

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, g, current_app
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.mail import send_email
from app.config import Config
from app.models import User, AccountType, Currency, Invitation
from app.translations import DEFAULT_ACCOUNT_TYPE_NAMES

bp = Blueprint("auth", __name__)

RESET_TOKEN_SALT = "password-reset"
INVITE_TOKEN_SALT = "user-invite"


def _reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=RESET_TOKEN_SALT)


def generate_reset_token(user):
    return _reset_serializer().dumps({"user_id": user.id})


def verify_reset_token(token):
    try:
        data = _reset_serializer().loads(
            token, max_age=current_app.config["PASSWORD_RESET_TOKEN_MAX_AGE"]
        )
    except (BadSignature, SignatureExpired):
        return None
    return data.get("user_id")


def _invite_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=INVITE_TOKEN_SALT)


def generate_invite_token(email):
    return _invite_serializer().dumps({"email": email})


def verify_invite_token(token):
    try:
        data = _invite_serializer().loads(
            token, max_age=current_app.config["INVITE_TOKEN_MAX_AGE"]
        )
    except (BadSignature, SignatureExpired):
        return None
    return data.get("email")


def seed_new_user_defaults(user):
    """Default AccountType/Currency rows every new user starts with, whether
    they came from self-registration or an admin invite."""
    for type_name in DEFAULT_ACCOUNT_TYPE_NAMES.get(user.locale, DEFAULT_ACCOUNT_TYPE_NAMES["fr"]):
        db.session.add(AccountType(user_id=user.id, name=type_name))
    for code in Config.DEFAULT_CURRENCIES:
        db.session.add(Currency(user_id=user.id, code=code, active=code == "EUR"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.active:
                flash(g._("auth_account_disabled"), "danger")
                return render_template("login.html")
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            login_user(user)
            return redirect(url_for("main.dashboard"))
        flash(g._("auth_invalid_credentials"), "danger")
    return render_template("login.html")


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_reset_token(user)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            send_email(
                user.email,
                g._("password_reset_email_subject"),
                g._("password_reset_email_body") % {"url": reset_url},
            )
        # Same message whether or not the address exists, so the form can't be
        # used to probe which emails are registered.
        flash(g._("password_reset_email_sent"), "success")
        return redirect(url_for("auth.login"))
    return render_template("forgot_password.html")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    user_id = verify_reset_token(token)
    user = User.query.get(user_id) if user_id else None
    if not user:
        flash(g._("password_reset_link_invalid"), "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        if len(new_password) < 6:
            flash(g._("auth_password_too_short"), "danger")
            return render_template("reset_password.html", token=token)
        if new_password != confirm_password:
            flash(g._("auth_passwords_dont_match"), "danger")
            return render_template("reset_password.html", token=token)
        user.set_password(new_password)
        db.session.commit()
        flash(g._("auth_password_updated"), "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if not current_app.config["ALLOW_REGISTRATION"]:
        flash(g._("registration_disabled"), "danger")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        if not email or not password or not name:
            flash(g._("auth_all_fields_required"), "danger")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash(g._("auth_email_already_used"), "danger")
            return render_template("register.html")
        is_first_user = User.query.count() == 0
        user = User(email=email, name=name, locale=g.locale, is_admin=is_first_user)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        seed_new_user_defaults(user)
        user.last_login_at = datetime.utcnow()
        Invitation.query.filter_by(email=email, accepted_at=None).update(
            {"accepted_at": datetime.utcnow()}
        )
        db.session.commit()
        login_user(user)
        return redirect(url_for("main.dashboard"))
    return render_template("register.html")


@bp.route("/accept-invite/<token>", methods=["GET", "POST"])
def accept_invite(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    email = verify_invite_token(token)
    if not email:
        flash(g._("invite_link_invalid"), "danger")
        return redirect(url_for("auth.login"))

    if User.query.filter_by(email=email).first():
        flash(g._("auth_email_already_used"), "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        if not name or not password:
            flash(g._("auth_all_fields_required"), "danger")
            return render_template("accept_invite.html", token=token, email=email)
        if len(password) < 6:
            flash(g._("auth_password_too_short"), "danger")
            return render_template("accept_invite.html", token=token, email=email)
        user = User(email=email, name=name, locale=g.locale, is_admin=False)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        seed_new_user_defaults(user)
        user.last_login_at = datetime.utcnow()
        Invitation.query.filter_by(email=email, accepted_at=None).update(
            {"accepted_at": datetime.utcnow()}
        )
        db.session.commit()
        login_user(user)
        return redirect(url_for("main.dashboard"))

    return render_template("accept_invite.html", token=token, email=email)


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not current_user.check_password(current_password):
            flash(g._("auth_current_password_wrong"), "danger")
            return render_template("change_password.html")
        if len(new_password) < 6:
            flash(g._("auth_password_too_short"), "danger")
            return render_template("change_password.html")
        if new_password != confirm_password:
            flash(g._("auth_passwords_dont_match"), "danger")
            return render_template("change_password.html")
        current_user.set_password(new_password)
        db.session.commit()
        flash(g._("auth_password_updated"), "success")
        return redirect(url_for("main.dashboard"))
    return render_template("change_password.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/locale/<lang>")
def set_locale(lang):
    if lang in ("fr", "en"):
        session["locale"] = lang
        if current_user.is_authenticated:
            current_user.locale = lang
            db.session.commit()
    return redirect(request.referrer or url_for("main.dashboard"))

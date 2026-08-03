from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, request, flash, g, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.mail import send_email
from app.models import User, Invitation
from app.routes.auth import generate_invite_token

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            flash(g._("admin_access_denied"), "danger")
            return redirect(url_for("main.dashboard"))
        return view(*args, **kwargs)
    return wrapped


def _active_admin_count():
    return User.query.filter_by(is_admin=True, active=True).count()


@bp.route("/")
@login_required
@admin_required
def list_users():
    users = User.query.order_by(User.created_at).all()
    return render_template("admin_users.html", users=users)


@bp.route("/invitations")
@login_required
@admin_required
def list_invitations():
    invitations = Invitation.query.order_by(Invitation.created_at.desc()).all()
    max_age = current_app.config["INVITE_TOKEN_MAX_AGE"]
    now = datetime.utcnow()
    rows = [
        {
            "invitation": inv,
            "expires_at": inv.created_at + timedelta(seconds=max_age),
            "expired": not inv.accepted_at and inv.created_at + timedelta(seconds=max_age) < now,
        }
        for inv in invitations
    ]
    return render_template("admin_invitations.html", rows=rows)


def _send_invite_email(email):
    token = generate_invite_token(email)
    invite_url = url_for("auth.accept_invite", token=token, _external=True)
    send_email(
        email,
        g._("invite_email_subject"),
        g._("invite_email_body") % {"url": invite_url, "inviter": current_user.name},
    )


@bp.route("/invite", methods=["POST"])
@login_required
@admin_required
def invite_user():
    email = request.form.get("email", "").strip().lower()
    if not email:
        flash(g._("auth_all_fields_required"), "danger")
        return redirect(url_for("admin.list_invitations"))
    if User.query.filter_by(email=email).first():
        flash(g._("auth_email_already_used"), "danger")
        return redirect(url_for("admin.list_invitations"))

    _send_invite_email(email)
    db.session.add(Invitation(email=email, invited_by_id=current_user.id))
    db.session.commit()
    flash(g._("invite_sent"), "success")
    return redirect(url_for("admin.list_invitations"))


@bp.route("/invitations/<invitation_id>/resend", methods=["POST"])
@login_required
@admin_required
def resend_invitation(invitation_id):
    invitation = Invitation.query.filter_by(id=invitation_id).first_or_404()
    if invitation.accepted_at:
        flash(g._("invite_already_accepted"), "danger")
        return redirect(url_for("admin.list_invitations"))

    _send_invite_email(invitation.email)
    # a resend issues a brand new token, so the invitation's clock restarts too
    invitation.created_at = datetime.utcnow()
    db.session.commit()
    flash(g._("invite_resent"), "success")
    return redirect(url_for("admin.list_invitations"))


@bp.route("/<user_id>/toggle-admin", methods=["POST"])
@login_required
@admin_required
def toggle_admin(user_id):
    user = User.query.filter_by(id=user_id).first_or_404()
    if user.is_admin and _active_admin_count() <= 1:
        flash(g._("admin_cannot_remove_last"), "danger")
        return redirect(url_for("admin.list_users"))
    user.is_admin = not user.is_admin
    db.session.commit()
    flash(g._("admin_role_updated"), "success")
    return redirect(url_for("admin.list_users"))


@bp.route("/<user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_active(user_id):
    if user_id == current_user.id:
        flash(g._("admin_cannot_deactivate_self"), "danger")
        return redirect(url_for("admin.list_users"))

    user = User.query.filter_by(id=user_id).first_or_404()
    if user.is_admin and user.active and _active_admin_count() <= 1:
        flash(g._("admin_cannot_remove_last"), "danger")
        return redirect(url_for("admin.list_users"))

    user.active = not user.active
    db.session.commit()
    flash(g._("admin_status_updated"), "success")
    return redirect(url_for("admin.list_users"))


@bp.route("/<user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash(g._("admin_cannot_delete_self"), "danger")
        return redirect(url_for("admin.list_users"))

    user = User.query.filter_by(id=user_id).first_or_404()
    if user.is_admin and _active_admin_count() <= 1:
        flash(g._("admin_cannot_remove_last"), "danger")
        return redirect(url_for("admin.list_users"))

    db.session.delete(user)
    db.session.commit()
    flash(g._("admin_user_deleted"), "success")
    return redirect(url_for("admin.list_users"))

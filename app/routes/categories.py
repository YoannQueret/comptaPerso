from flask import Blueprint, render_template, redirect, url_for, request, flash, g
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Category, CATEGORY_KINDS

bp = Blueprint("categories", __name__, url_prefix="/categories")


@bp.route("/")
@login_required
def list_categories():
    roots = (
        Category.query.filter_by(user_id=current_user.id, parent_id=None)
        .order_by(Category.name)
        .all()
    )
    return render_template("categories.html", roots=roots)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_category():
    parents = Category.query.filter_by(user_id=current_user.id, parent_id=None).order_by(
        Category.name
    ).all()
    if request.method == "POST":
        parent_id = request.form.get("parent_id") or None
        cat = Category(
            user_id=current_user.id,
            name=request.form["name"].strip(),
            kind=request.form.get("kind", "both"),
            color=request.form.get("color", "#6c757d"),
            parent_id=parent_id,
        )
        db.session.add(cat)
        db.session.commit()
        flash(g._("category_created"), "success")
        return redirect(url_for("categories.list_categories"))
    return render_template(
        "category_form.html", category=None, parents=parents, kinds=CATEGORY_KINDS
    )


@bp.route("/<category_id>/edit", methods=["GET", "POST"])
@login_required
def edit_category(category_id):
    cat = Category.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
    parents = (
        Category.query.filter_by(user_id=current_user.id, parent_id=None)
        .filter(Category.id != category_id)
        .order_by(Category.name)
        .all()
    )
    if request.method == "POST":
        cat.name = request.form["name"].strip()
        cat.kind = request.form.get("kind", "both")
        cat.color = request.form.get("color", "#6c757d")
        parent_id = request.form.get("parent_id") or None
        cat.parent_id = parent_id if parent_id != cat.id else None
        db.session.commit()
        flash(g._("category_updated"), "success")
        return redirect(url_for("categories.list_categories"))
    return render_template(
        "category_form.html", category=cat, parents=parents, kinds=CATEGORY_KINDS
    )


@bp.route("/<category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id):
    cat = Category.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
    db.session.delete(cat)
    db.session.commit()
    flash(g._("category_deleted"), "success")
    return redirect(url_for("categories.list_categories"))

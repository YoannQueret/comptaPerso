import glob
import logging
import os
import shutil
from datetime import datetime

from flask import Flask, session, g, render_template, redirect, url_for, flash
from flask_wtf import CSRFProtect
from flask_migrate import upgrade as migrate_upgrade

from app.config import BASE_DIR, Config
from app.extensions import db, login_manager, migrate
from app.translations import (
    get_translator,
    month_name as _month_name,
    PERIODICITY_LABEL_KEYS,
    KIND_LABEL_KEYS,
)

csrf = CSRFProtect()

logger = logging.getLogger(__name__)


def _read_version():
    try:
        with open(os.path.join(BASE_DIR, "VERSION")) as f:
            return f.read().strip()
    except OSError:
        return "dev"


APP_VERSION = _read_version()


def _backup_sqlite_database(app):
    """Copy the SQLite file into BACKUP_DIR before running any migration, keeping
    only the BACKUP_KEEP most recent backups."""
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    prefix = "sqlite:///"
    if not uri.startswith(prefix):
        return  # no file-based backup for non-SQLite engines (e.g. mariadb)

    db_path = uri[len(prefix):]
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return  # nothing to back up (first install)

    backup_dir = app.config["BACKUP_DIR"]
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{os.path.splitext(os.path.basename(db_path))[0]}_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_name)
    shutil.copy2(db_path, backup_path)
    logger.info("Database backup created: %s", backup_path)

    keep = app.config["BACKUP_KEEP"]
    existing = sorted(glob.glob(os.path.join(backup_dir, "*.db")))
    for stale in existing[:-keep] if keep > 0 else []:
        os.remove(stale)


def _ensure_database_ready(app):
    """Check at startup that the database exists and apply any pending migrations,
    so the app never runs against a stale schema."""
    with app.app_context():
        try:
            _backup_sqlite_database(app)
            migrate_upgrade()
        except Exception:
            logger.exception("Failed to update the database schema at startup")
            raise


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    if not app.config.get("SKIP_DB_UPGRADE"):
        _ensure_database_ready(app)

    app.jinja_env.filters["abs"] = abs
    app.jinja_env.filters["periodicity_label"] = (
        lambda value: g._(PERIODICITY_LABEL_KEYS.get(value, value))
    )
    app.jinja_env.filters["kind_label"] = (
        lambda value: g._(KIND_LABEL_KEYS.get(value, value))
    )

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, user_id)

    @app.before_request
    def set_locale():
        from flask_login import current_user

        locale = session.get("locale")
        if not locale:
            if current_user.is_authenticated:
                locale = current_user.locale
            else:
                locale = Config.DEFAULT_LOCALE
        g.locale = locale
        g._ = get_translator(locale)

        if current_user.is_authenticated and not current_user.active:
            from flask_login import logout_user

            logout_user()
            flash(g._("auth_account_disabled"), "danger")
            return redirect(url_for("auth.login"))

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("404.html"), 404

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from datetime import date
        return dict(_=g.get("_", get_translator(Config.DEFAULT_LOCALE)),
                    locale=g.get("locale", Config.DEFAULT_LOCALE),
                    current_user=current_user,
                    now=date.today(),
                    allow_registration=app.config["ALLOW_REGISTRATION"],
                    month_name=_month_name,
                    app_version=APP_VERSION)

    from app.routes.auth import bp as auth_bp
    from app.routes.main import bp as main_bp
    from app.routes.accounts import bp as accounts_bp
    from app.routes.account_types import bp as account_types_bp
    from app.routes.currencies import bp as currencies_bp
    from app.routes.categories import bp as categories_bp
    from app.routes.transactions import bp as transactions_bp
    from app.routes.transfers import bp as transfers_bp
    from app.routes.recurring import bp as recurring_bp
    from app.routes.reports import bp as reports_bp
    from app.routes.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(account_types_bp)
    app.register_blueprint(currencies_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(transfers_bp)
    app.register_blueprint(recurring_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reports_bp)

    return app

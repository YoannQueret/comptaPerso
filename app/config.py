import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    WTF_CSRF_ENABLED = True

    # Allows disabling self-service registration once the initial users are set up.
    ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "true").lower() in ("1", "true", "yes")

    # Port used by `python run.py` (the dev server) and by the Docker entrypoint (gunicorn).
    PORT = int(os.environ.get("PORT", "5000"))

    # Flask's debugger/reloader. Must stay disabled in production (code execution
    # via the debugger console, auto-reload). Only affects `python run.py` — the
    # Docker path always runs gunicorn, which never enables it.
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")

    DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite")  # sqlite | mariadb

    if DB_ENGINE == "mariadb":
        DB_USER = os.environ.get("DB_USER", "compta")
        DB_PASSWORD = os.environ.get("DB_PASSWORD", "compta")
        DB_HOST = os.environ.get("DB_HOST", "db")
        DB_PORT = os.environ.get("DB_PORT", "3306")
        DB_NAME = os.environ.get("DB_NAME", "comptaperso")
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
        )
    else:
        os.makedirs(DATA_DIR, exist_ok=True)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(DATA_DIR, 'compta.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Forces the browser to always revalidate static files (JS/CSS) instead of
    # trusting its own heuristic cache lifetime — otherwise a browser can keep
    # serving a stale script for a long time after a deploy, with no way to
    # know it changed short of the user manually clearing their cache.
    SEND_FILE_MAX_AGE_DEFAULT = 0

    # Allows disabling the automatic schema upgrade at startup
    # (useful for the `flask db ...` commands themselves, or for troubleshooting).
    SKIP_DB_UPGRADE = os.environ.get("SKIP_DB_UPGRADE", "").lower() in ("1", "true", "yes")

    # Automatic backup of the SQLite file before every schema upgrade at startup.
    BACKUP_DIR = os.environ.get("BACKUP_DIR", os.path.join(DATA_DIR, "backups"))
    BACKUP_KEEP = int(os.environ.get("BACKUP_KEEP", "20"))

    # Transaction attachments (receipts, etc.)
    ATTACHMENTS_DIR = os.environ.get("ATTACHMENTS_DIR", os.path.join(DATA_DIR, "attachments"))
    ALLOWED_ATTACHMENT_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "heic", "heif", "pdf"}
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB upload limit

    # SMTP settings for outgoing email (currently used for password reset links).
    # SMTP_HOST left empty disables sending; requests still succeed (no user
    # enumeration) but the email is only logged, not delivered.
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
    SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")
    MAIL_FROM = os.environ.get("MAIL_FROM", "no-reply@comptaperso.local")

    # How long a password reset link stays valid, in seconds.
    PASSWORD_RESET_TOKEN_MAX_AGE = int(os.environ.get("PASSWORD_RESET_TOKEN_MAX_AGE", "3600"))

    # How long an admin's invite link stays valid, in seconds (default 7 days).
    INVITE_TOKEN_MAX_AGE = int(os.environ.get("INVITE_TOKEN_MAX_AGE", str(7 * 24 * 3600)))

    # Default supported currencies (short list, extensible)
    DEFAULT_CURRENCIES = ["EUR", "CHF", "USD", "GBP"]

    LANGUAGES = ["fr", "en"]
    DEFAULT_LOCALE = "fr"

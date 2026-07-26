import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

logger = logging.getLogger(__name__)


def send_email(to_address, subject, body):
    """Send a plain-text email via the configured SMTP server.

    Returns True on success. If SMTP_HOST isn't configured, or sending fails,
    logs the problem and returns False without raising — callers should not
    let email delivery failures leak into user-facing errors (e.g. password
    reset must respond the same way whether or not the address exists).
    """
    cfg = current_app.config
    if not cfg.get("SMTP_HOST"):
        logger.error("SMTP_HOST is not configured; email to %s was not sent", to_address)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["MAIL_FROM"]
    msg["To"] = to_address
    msg.set_content(body)

    try:
        if cfg.get("SMTP_USE_SSL"):
            server = smtplib.SMTP_SSL(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10)
        else:
            server = smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10)
        with server:
            if cfg.get("SMTP_USE_TLS") and not cfg.get("SMTP_USE_SSL"):
                server.starttls()
            if cfg.get("SMTP_USERNAME"):
                server.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_address)
        return False

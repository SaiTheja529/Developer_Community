"""EmailSender interface with SMTP and console implementations (spec §6.7)."""

from __future__ import annotations

import html
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from pathlib import Path
from string import Template
from typing import Protocol

from app.extensions import settings as get_settings

log = logging.getLogger("devcommons.email")
TEMPLATE_DIR = Path(__file__).parent / "templates"

SUBJECTS = {
    "verify_email": "Confirm your email for $app_name",
    "reset_password": "Reset your $app_name password",
    "password_changed": "Your $app_name password was changed",
    "email_change_confirm": "Confirm your new email for $app_name",
    "email_change_notice": "Your $app_name email is being changed",
    "suspicious_signin": "Security alert: a session on $app_name was signed out",
}


class EmailSender(Protocol):
    def send(self, to: str, subject: str, text_body: str, html_body: str) -> None: ...


class ConsoleEmailSender:
    """Development/test sender. Keeps an in-memory outbox (used by tests) and logs a summary."""

    def __init__(self) -> None:
        self.outbox: list[dict] = []

    def send(self, to: str, subject: str, text_body: str, html_body: str) -> None:
        self.outbox.append({"to": to, "subject": subject, "text": text_body, "html": html_body})
        # Development convenience: print the body (it contains the verification/reset link).
        # Use EMAIL_PROVIDER=smtp to send real email.
        print(f"\n=== EMAIL (console) ===\nTo: {to}\nSubject: {subject}\n\n{text_body}\n=======================\n", flush=True)


class SmtpEmailSender:
    """Sends real email through any SMTP server (Gmail, Outlook, Brevo, Mailgun, SendGrid, Resend, ...).

    Uses only the standard library. One short-lived connection per message keeps it thread-safe under
    Gunicorn threads; auth emails are rare enough that pooling isn't worth the complexity.
    """

    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        username: str | None = None,
        password: str | None = None,
        security: str = "starttls",
        timeout: float = 15,
    ) -> None:
        self._host = host
        self._port = port
        self._from = sender
        self._username = username
        self._password = password
        self._security = security
        self._timeout = timeout

    def _build(self, to: str, subject: str, text_body: str, html_body: str) -> EmailMessage:
        msg = EmailMessage()
        # EmailMessage rejects CR/LF in header values, which blocks header injection.
        msg["From"] = self._from
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=False)
        domain = parseaddr(self._from)[1].rpartition("@")[2] or None
        msg["Message-ID"] = make_msgid(domain=domain)
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")
        return msg

    def send(self, to: str, subject: str, text_body: str, html_body: str) -> None:
        msg = self._build(to, subject, text_body, html_body)
        context = ssl.create_default_context()
        if self._security == "ssl":
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(self._host, self._port, timeout=self._timeout, context=context)
        else:
            smtp = smtplib.SMTP(self._host, self._port, timeout=self._timeout)
        with smtp:
            if self._security == "starttls":
                smtp.starttls(context=context)
            if self._username:
                smtp.login(self._username, self._password or "")
            smtp.send_message(msg)


def build_sender(settings) -> EmailSender:
    if settings.EMAIL_PROVIDER == "smtp":
        return SmtpEmailSender(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            sender=settings.EMAIL_FROM,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD.get_secret_value() if settings.SMTP_PASSWORD else None,
            security=settings.SMTP_SECURITY,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
        )
    return ConsoleEmailSender()


def _render(name: str, ctx: dict) -> tuple[str, str, str]:
    s = get_settings()
    full = {"app_name": s.APP_NAME, "frontend_url": s.FRONTEND_URL.rstrip("/"), **ctx}
    subject = Template(SUBJECTS[name]).safe_substitute(full)
    text_body = Template((TEMPLATE_DIR / f"{name}.txt").read_text(encoding="utf-8")).safe_substitute(full)
    html_ctx = {k: html.escape(str(v)) for k, v in full.items()}
    html_body = Template((TEMPLATE_DIR / f"{name}.html").read_text(encoding="utf-8")).safe_substitute(html_ctx)
    return subject, text_body, html_body


def send_template(name: str, to: str, ctx: dict) -> None:
    from flask import current_app

    sender: EmailSender = current_app.extensions["email_sender"]
    subject, text_body, html_body = _render(name, ctx)
    try:
        sender.send(to, subject, text_body, html_body)
        log.info("email_sent", extra={"template": name})
    except Exception:
        # Email failures must not break the user-facing action; they are logged for follow-up.
        log.exception("email_send_failed", extra={"template": name})

"""SMTP email sender: message building, connection security modes, and settings validation."""

import pytest
from pydantic import ValidationError

from app.auth import email_sender
from app.auth.email_sender import ConsoleEmailSender, SmtpEmailSender, build_sender
from tests.conftest import make_settings


class FakeSMTP:
    """Records what the sender does instead of opening a network connection."""

    instances: list["FakeSMTP"] = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.implicit_tls = context is not None
        self.calls: list[str] = []
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append("quit")

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(f"login:{user}:{password}")

    def send_message(self, msg):
        self.calls.append("send")
        self.sent.append(msg)


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(email_sender.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(email_sender.smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


def _sender(**kw):
    args = dict(host="smtp.example.com", port=587, sender="DevCommons <no-reply@example.com>", username="u", password="p")
    args.update(kw)
    return SmtpEmailSender(**args)


def test_starttls_login_and_multipart_message():
    _sender().send("ada@example.com", "Confirm your email", "Plain body https://x/verify", "<p>HTML body</p>")
    smtp = FakeSMTP.instances[0]
    assert (smtp.host, smtp.port, smtp.implicit_tls) == ("smtp.example.com", 587, False)
    assert smtp.calls == ["starttls", "login:u:p", "send", "quit"]
    msg = smtp.sent[0]
    assert msg["To"] == "ada@example.com"
    assert msg["From"] == "DevCommons <no-reply@example.com>"
    assert msg["Subject"] == "Confirm your email"
    assert msg["Message-ID"].endswith("@example.com>")
    assert msg["Date"]
    parts = {p.get_content_type(): p.get_content() for p in msg.iter_parts()}
    assert "https://x/verify" in parts["text/plain"]
    assert "<p>HTML body</p>" in parts["text/html"]


def test_ssl_mode_uses_implicit_tls_without_starttls():
    _sender(port=465, security="ssl").send("a@example.com", "s", "t", "<p>h</p>")
    smtp = FakeSMTP.instances[0]
    assert smtp.implicit_tls is True
    assert "starttls" not in smtp.calls


def test_no_auth_and_no_tls_for_local_server():
    _sender(username=None, password=None, security="none", port=1025).send("a@example.com", "s", "t", "<p>h</p>")
    assert FakeSMTP.instances[0].calls == ["send", "quit"]


def test_header_injection_is_rejected():
    with pytest.raises(ValueError):
        _sender().send("a@example.com\r\nBcc: victim@example.com", "s", "t", "<p>h</p>")


def test_build_sender_picks_provider():
    assert isinstance(build_sender(make_settings()), ConsoleEmailSender)
    s = make_settings(
        EMAIL_PROVIDER="smtp", SMTP_HOST="smtp.example.com", SMTP_USERNAME="u", SMTP_PASSWORD="secret"
    )
    sender = build_sender(s)
    assert isinstance(sender, SmtpEmailSender)
    assert sender._password == "secret"
    assert "secret" not in repr(s.SMTP_PASSWORD)  # SecretStr keeps it out of logs


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({}, "SMTP_HOST is required"),
        ({"SMTP_HOST": "h", "SMTP_USERNAME": "u"}, "both SMTP_USERNAME and SMTP_PASSWORD"),
        ({"SMTP_HOST": "h", "SMTP_PASSWORD": "p"}, "both SMTP_USERNAME and SMTP_PASSWORD"),
    ],
)
def test_smtp_settings_validation(overrides, message):
    with pytest.raises(ValidationError, match=message):
        make_settings(EMAIL_PROVIDER="smtp", **overrides)


def test_ses_provider_no_longer_accepted():
    with pytest.raises(ValidationError):
        make_settings(EMAIL_PROVIDER="ses")

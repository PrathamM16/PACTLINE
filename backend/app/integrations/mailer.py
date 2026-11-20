import smtplib
from email.message import EmailMessage

from app.errors import ProviderError


class SmtpMailer:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str, smtp_factory=None):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._sender = sender
        self._factory = smtp_factory

    @staticmethod
    def from_env(env):
        if not all(env.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD")):
            return None
        return SmtpMailer(env["SMTP_HOST"], int(env.get("SMTP_PORT", "587")), env["SMTP_USER"], env["SMTP_PASSWORD"], env.get("SMTP_FROM") or env["SMTP_USER"])

    def _connect(self):
        if self._factory:
            return self._factory()
        if self._port == 465:
            return smtplib.SMTP_SSL(self._host, self._port, timeout=15)
        return smtplib.SMTP(self._host, self._port, timeout=15)

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        try:
            with self._connect() as smtp:
                if self._port != 465:
                    smtp.starttls()
                smtp.login(self._user, self._password)
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            raise ProviderError(f"email delivery failed: {type(exc).__name__}")

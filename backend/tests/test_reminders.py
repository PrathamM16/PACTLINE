import unittest
from datetime import datetime, timezone

from app.errors import ProviderError
from app.integrations.mailer import SmtpMailer
from app.reminders import MAX_ATTEMPTS, deliver_due, to_utc
from app.storage import open_store

TZ = "Asia/Kolkata"
NOW = datetime(2026, 11, 21, 5, 0, tzinfo=timezone.utc)


class FakeMailer:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    def send(self, to, subject, body):
        if self.fail:
            raise ProviderError("smtp down")
        self.sent.append((to, subject, body))


class FakeSmtp:
    def __init__(self):
        self.actions = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        self.actions.append("starttls")

    def login(self, user, password):
        self.actions.append(("login", user))

    def send_message(self, message):
        self.actions.append(("send", message["To"], message["Subject"]))


def reminder(remind_at="2026-11-21T10:00:00", **overrides):
    values = {"id": "r1", "text": "Call the bank", "remind_at": remind_at, "for_person": None, "recipient_email": "a@example.com", "delivery": "pending", "attempts": 0}
    values.update(overrides)
    return values


def store_with(record):
    store = open_store("sqlite:///:memory:")
    store.put("reminder", "ws", record["id"], record)
    return store


def current(store):
    return store.get("reminder", "ws", "r1")


class TimeConversionTest(unittest.TestCase):
    def test_naive_time_is_interpreted_in_configured_zone(self):
        self.assertEqual(to_utc("2026-11-21T10:00:00", TZ), datetime(2026, 11, 21, 4, 30, tzinfo=timezone.utc))

    def test_explicit_offset_is_respected(self):
        self.assertEqual(to_utc("2026-11-21T10:00:00+00:00", TZ), datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc))


class DeliveryTest(unittest.TestCase):
    def test_due_reminder_is_sent_to_recipient(self):
        mailer = FakeMailer()
        deliver_due(store_with(reminder()), mailer, NOW, TZ)
        self.assertEqual(mailer.sent[0][0], "a@example.com")

    def test_sent_reminder_is_marked_sent(self):
        store = store_with(reminder())
        deliver_due(store, FakeMailer(), NOW, TZ)
        self.assertEqual(current(store)["delivery"], "sent")

    def test_future_reminder_is_not_sent(self):
        mailer = FakeMailer()
        deliver_due(store_with(reminder("2026-11-22T10:00:00")), mailer, NOW, TZ)
        self.assertEqual(mailer.sent, [])

    def test_future_reminder_stays_pending(self):
        store = store_with(reminder("2026-11-22T10:00:00"))
        deliver_due(store, FakeMailer(), NOW, TZ)
        self.assertEqual(current(store)["delivery"], "pending")

    def test_second_run_does_not_send_again(self):
        mailer = FakeMailer()
        store = store_with(reminder())
        deliver_due(store, mailer, NOW, TZ)
        deliver_due(store, mailer, NOW, TZ)
        self.assertEqual(len(mailer.sent), 1)

    def test_provider_failure_is_marked_failed_not_sent(self):
        store = store_with(reminder())
        deliver_due(store, FakeMailer(fail=True), NOW, TZ)
        self.assertEqual(current(store)["delivery"], "failed")

    def test_failure_message_is_recorded(self):
        store = store_with(reminder())
        deliver_due(store, FakeMailer(fail=True), NOW, TZ)
        self.assertEqual(current(store)["error"], "smtp down")

    def test_failed_reminder_is_retried_and_can_succeed(self):
        store = store_with(reminder())
        deliver_due(store, FakeMailer(fail=True), NOW, TZ)
        deliver_due(store, FakeMailer(), NOW, TZ)
        self.assertEqual(current(store)["delivery"], "sent")

    def test_attempts_are_capped(self):
        store = store_with(reminder())
        mailer = FakeMailer(fail=True)
        for _ in range(MAX_ATTEMPTS + 2):
            deliver_due(store, mailer, NOW, TZ)
        self.assertEqual(current(store)["attempts"], MAX_ATTEMPTS)

    def test_missing_recipient_is_failed_not_sent(self):
        store = store_with(reminder(recipient_email=None))
        deliver_due(store, FakeMailer(), NOW, TZ)
        self.assertEqual(current(store)["delivery"], "failed")

    def test_no_mailer_leaves_reminder_pending(self):
        store = store_with(reminder())
        deliver_due(store, None, NOW, TZ)
        self.assertEqual(current(store)["delivery"], "pending")

    def test_counts_are_reported(self):
        self.assertEqual(deliver_due(store_with(reminder()), FakeMailer(), NOW, TZ), {"sent": 1, "failed": 0})

    def test_delivery_is_audited(self):
        store = store_with(reminder())
        deliver_due(store, FakeMailer(), NOW, TZ)
        self.assertEqual(store.audit_list("ws")[0]["outcome"], "sent")


class SmtpMailerTest(unittest.TestCase):
    def setUp(self):
        self.smtp = FakeSmtp()
        self.mailer = SmtpMailer("smtp.example.com", 587, "bot", "pw", "bot@example.com", lambda: self.smtp)

    def test_starttls_is_used_on_port_587(self):
        self.mailer.send("a@example.com", "Hi", "Body")
        self.assertEqual(self.smtp.actions[0], "starttls")

    def test_message_is_sent_to_recipient_with_subject(self):
        self.mailer.send("a@example.com", "Hi", "Body")
        self.assertIn(("send", "a@example.com", "Hi"), self.smtp.actions)

    def test_smtp_error_becomes_provider_error(self):
        import smtplib

        class Broken(FakeSmtp):
            def login(self, user, password):
                raise smtplib.SMTPAuthenticationError(535, b"bad")

        mailer = SmtpMailer("h", 587, "u", "p", "s@example.com", Broken)
        with self.assertRaises(ProviderError):
            mailer.send("a@example.com", "x", "y")

    def test_provider_error_does_not_leak_password(self):
        import smtplib

        class Broken(FakeSmtp):
            def login(self, user, password):
                raise smtplib.SMTPAuthenticationError(535, b"bad pw")

        mailer = SmtpMailer("h", 587, "u", "secret-pw", "s@example.com", Broken)
        with self.assertRaises(ProviderError) as raised:
            mailer.send("a@example.com", "x", "y")
        self.assertNotIn("secret-pw", str(raised.exception))

    def test_missing_smtp_settings_mean_not_configured(self):
        self.assertIsNone(SmtpMailer.from_env({"SMTP_HOST": "h"}))

    def test_complete_smtp_settings_build_mailer(self):
        env = {"SMTP_HOST": "h", "SMTP_USER": "u", "SMTP_PASSWORD": "p"}
        self.assertIsInstance(SmtpMailer.from_env(env), SmtpMailer)


if __name__ == "__main__":
    unittest.main()

import unittest

from app.accounts import Accounts
from app.storage import open_store


def accounts():
    return Accounts(open_store("sqlite:///:memory:").db)


class RegistrationTest(unittest.TestCase):
    def test_registration_creates_owner_membership(self):
        acc = accounts()
        ids = acc.register("a@example.com", "Asha", "long-enough-pass")
        self.assertEqual(acc.role(ids["user_id"], ids["workspace_id"]), "owner")

    def test_duplicate_email_is_rejected_case_insensitively(self):
        acc = accounts()
        acc.register("a@example.com", "Asha", "long-enough-pass")
        with self.assertRaises(ValueError):
            acc.register("A@Example.com", "Other", "long-enough-pass")

    def test_short_password_is_rejected(self):
        with self.assertRaises(ValueError):
            accounts().register("a@example.com", "Asha", "short")

    def test_invalid_email_is_rejected(self):
        with self.assertRaises(ValueError):
            accounts().register("not-an-email", "Asha", "long-enough-pass")


class AuthenticationTest(unittest.TestCase):
    def setUp(self):
        self.acc = accounts()
        self.ids = self.acc.register("a@example.com", "Asha", "long-enough-pass")

    def test_correct_credentials_authenticate(self):
        self.assertEqual(self.acc.authenticate("a@example.com", "long-enough-pass")["id"], self.ids["user_id"])

    def test_wrong_password_does_not_authenticate(self):
        self.assertIsNone(self.acc.authenticate("a@example.com", "wrong-password-1"))

    def test_unknown_email_does_not_authenticate(self):
        self.assertIsNone(self.acc.authenticate("nobody@example.com", "long-enough-pass"))


class MembershipTest(unittest.TestCase):
    def setUp(self):
        self.acc = accounts()
        self.owner = self.acc.register("a@example.com", "Asha", "long-enough-pass")
        self.other = self.acc.register("b@example.com", "Ravi", "long-enough-pass")

    def test_user_has_no_role_in_foreign_workspace(self):
        self.assertIsNone(self.acc.role(self.other["user_id"], self.owner["workspace_id"]))

    def test_added_member_gets_requested_role(self):
        self.acc.add_member(self.owner["workspace_id"], self.other["user_id"], "viewer")
        self.assertEqual(self.acc.role(self.other["user_id"], self.owner["workspace_id"]), "viewer")

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(ValueError):
            self.acc.add_member(self.owner["workspace_id"], self.other["user_id"], "superadmin")

    def test_workspace_list_contains_only_own_memberships(self):
        self.assertEqual([w["id"] for w in self.acc.workspaces_for(self.other["user_id"])], [self.other["workspace_id"]])


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest

from app.accounts import Accounts
from app.storage import Database, Store, open_store


def memory_store():
    return open_store("sqlite:///:memory:")


class MigrationTest(unittest.TestCase):
    def test_first_migration_applies_version_one(self):
        db = Database("sqlite:///:memory:")
        self.assertEqual(db.migrate(), [1])

    def test_second_migration_run_applies_nothing(self):
        db = Database("sqlite:///:memory:")
        db.migrate()
        self.assertEqual(db.migrate(), [])


class RecordIsolationTest(unittest.TestCase):
    def setUp(self):
        self.store = memory_store()
        self.store.put("task", "ws-a", "t1", {"title": "a"})

    def test_owner_workspace_can_read_record(self):
        self.assertEqual(self.store.get("task", "ws-a", "t1"), {"title": "a"})

    def test_other_workspace_cannot_read_record(self):
        self.assertIsNone(self.store.get("task", "ws-b", "t1"))

    def test_other_workspace_list_is_empty(self):
        self.assertEqual(self.store.list_records("task", "ws-b"), [])

    def test_other_workspace_cannot_overwrite_record(self):
        self.store.put("task", "ws-b", "t1", {"title": "hijacked"})
        self.assertEqual(self.store.get("task", "ws-a", "t1"), {"title": "a"})

    def test_owner_can_update_record(self):
        self.store.put("task", "ws-a", "t1", {"title": "changed"})
        self.assertEqual(self.store.get("task", "ws-a", "t1"), {"title": "changed"})


class OnceKeyTest(unittest.TestCase):
    def test_first_use_wins(self):
        self.assertTrue(memory_store().once("delivery-1"))

    def test_second_use_loses(self):
        store = memory_store()
        store.once("delivery-1")
        self.assertFalse(store.once("delivery-1"))


class ToolResultCacheTest(unittest.TestCase):
    def test_same_call_id_in_other_workspace_is_not_shared(self):
        store = memory_store()
        store.save_tool_result("ws-a", "call-1", {"ok": True, "data": "secret-a"})
        self.assertIsNone(store.get_tool_result("ws-b", "call-1"))

    def test_cached_result_is_returned_to_same_workspace(self):
        store = memory_store()
        store.save_tool_result("ws-a", "call-1", {"ok": True})
        self.assertEqual(store.get_tool_result("ws-a", "call-1"), {"ok": True})


class AuditTest(unittest.TestCase):
    def test_audit_entries_are_scoped_to_workspace(self):
        store = memory_store()
        store.audit("ws-a", "u1", "createTask", "-", "succeeded")
        self.assertEqual(store.audit_list("ws-b"), [])

    def test_audit_entry_records_outcome(self):
        store = memory_store()
        store.audit("ws-a", "u1", "createTask", "-", "succeeded")
        self.assertEqual(store.audit_list("ws-a")[0]["outcome"], "succeeded")


class RestartPersistenceTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.addCleanup(os.remove, self.path)
        self.url = f"sqlite:///{self.path}"
        first = open_store(self.url)
        first.put("task", "ws-a", "t1", {"title": "survives restart"})
        Accounts(first.db).register("a@example.com", "Asha", "long-enough-pass")
        first.db.close()

    def reopen(self):
        store = open_store(self.url)
        self.addCleanup(store.db.close)
        return store

    def test_record_survives_reopening_database(self):
        self.assertEqual(self.reopen().get("task", "ws-a", "t1"), {"title": "survives restart"})

    def test_account_survives_reopening_database(self):
        reopened = self.reopen()
        self.assertIsNotNone(Accounts(reopened.db).authenticate("a@example.com", "long-enough-pass"))


if __name__ == "__main__":
    unittest.main()

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

MIGRATIONS = [
    (1, [
        "CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE workspaces (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE memberships (workspace_id TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL, PRIMARY KEY (workspace_id, user_id))",
        "CREATE TABLE records (kind TEXT NOT NULL, id TEXT NOT NULL, workspace_id TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (kind, id))",
        "CREATE INDEX idx_records_workspace_kind ON records (workspace_id, kind, created_at)",
        "CREATE TABLE tool_calls (workspace_id TEXT NOT NULL, tool_call_id TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY (workspace_id, tool_call_id))",
        "CREATE TABLE once_keys (key TEXT PRIMARY KEY, created_at TEXT NOT NULL)",
        "CREATE TABLE audit_log (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, resource TEXT NOT NULL, outcome TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE INDEX idx_audit_workspace ON audit_log (workspace_id, created_at)",
    ]),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, url: str):
        self._lock = threading.RLock()
        self._depth = 0
        self.is_postgres = url.startswith(("postgres://", "postgresql://"))
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row

            self._conn = psycopg.connect(url, row_factory=dict_row)
        else:
            path = url.removeprefix("sqlite:///") or ":memory:"
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.is_postgres else sql

    @contextmanager
    def transaction(self):
        with self._lock:
            self._depth += 1
            try:
                yield
            except Exception:
                self._depth -= 1
                if self._depth == 0:
                    self._conn.rollback()
                raise
            self._depth -= 1
            if self._depth == 0:
                self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            try:
                cursor = self._conn.execute(self._sql(sql), params)
            except Exception:
                self._conn.rollback()
                raise
            if self._depth == 0:
                self._conn.commit()
            return cursor.rowcount

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            cursor = self._conn.execute(self._sql(sql), params)
            rows = cursor.fetchall()
            if self._depth == 0:
                self._conn.commit()
            return [dict(row) for row in rows]

    def migrate(self) -> list[int]:
        self.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        applied = {row["version"] for row in self.query("SELECT version FROM schema_migrations")}
        newly_applied = []
        for version, statements in MIGRATIONS:
            if version in applied:
                continue
            with self.transaction():
                for statement in statements:
                    self.execute(statement)
                self.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (version, now_iso()))
            newly_applied.append(version)
        return newly_applied

    def close(self) -> None:
        self._conn.close()


class Store:
    def __init__(self, db: Database):
        self.db = db

    def put(self, kind: str, workspace_id: str, record_id: str, data: dict) -> None:
        self.db.execute(
            "INSERT INTO records (kind, id, workspace_id, data, created_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (kind, id) DO UPDATE SET data = excluded.data WHERE records.workspace_id = excluded.workspace_id",
            (kind, record_id, workspace_id, json.dumps(data), now_iso()),
        )

    def get(self, kind: str, workspace_id: str, record_id: str) -> dict | None:
        rows = self.db.query("SELECT data FROM records WHERE kind = ? AND id = ? AND workspace_id = ?", (kind, record_id, workspace_id))
        return json.loads(rows[0]["data"]) if rows else None

    def list_records(self, kind: str, workspace_id: str) -> "list[dict]":
        rows = self.db.query("SELECT data FROM records WHERE kind = ? AND workspace_id = ? ORDER BY created_at, id", (kind, workspace_id))
        return [json.loads(row["data"]) for row in rows]

    def list_all(self, kind: str) -> "list[tuple[str, dict]]":
        rows = self.db.query("SELECT workspace_id, data FROM records WHERE kind = ? ORDER BY created_at, id", (kind,))
        return [(row["workspace_id"], json.loads(row["data"])) for row in rows]

    def once(self, key: str) -> bool:
        changed = self.db.execute("INSERT INTO once_keys (key, created_at) VALUES (?, ?) ON CONFLICT (key) DO NOTHING", (key, now_iso()))
        return changed == 1

    def get_tool_result(self, workspace_id: str, tool_call_id: str) -> dict | None:
        rows = self.db.query("SELECT result FROM tool_calls WHERE workspace_id = ? AND tool_call_id = ?", (workspace_id, tool_call_id))
        return json.loads(rows[0]["result"]) if rows else None

    def save_tool_result(self, workspace_id: str, tool_call_id: str, result: dict) -> None:
        self.db.execute(
            "INSERT INTO tool_calls (workspace_id, tool_call_id, result) VALUES (?, ?, ?) ON CONFLICT (workspace_id, tool_call_id) DO NOTHING",
            (workspace_id, tool_call_id, json.dumps(result)),
        )

    def audit(self, workspace_id: str, actor: str, action: str, resource: str, outcome: str, detail: str = "") -> None:
        import uuid

        self.db.execute(
            "INSERT INTO audit_log (id, workspace_id, actor, action, resource, outcome, detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), workspace_id, actor, action, resource, outcome, detail[:500], now_iso()),
        )

    def audit_list(self, workspace_id: str, limit: int = 100) -> list[dict]:
        return self.db.query("SELECT actor, action, resource, outcome, detail, created_at FROM audit_log WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ?", (workspace_id, limit))


def open_store(url: str) -> Store:
    db = Database(url)
    db.migrate()
    return Store(db)

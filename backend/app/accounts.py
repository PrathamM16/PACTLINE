import uuid

from app.security import MIN_PASSWORD_LENGTH, hash_password, verify_password
from app.storage import Database, now_iso

ROLES = ("owner", "member", "viewer")
DUMMY_HASH = hash_password("not-a-real-password")


class Accounts:
    def __init__(self, db: Database):
        self._db = db

    def register(self, email: str, name: str, password: str) -> dict:
        email = email.strip().lower()
        if "@" not in email or len(email) > 254:
            raise ValueError("invalid email")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
        if not name.strip():
            raise ValueError("name is required")
        if self._db.query("SELECT id FROM users WHERE email = ?", (email,)):
            raise ValueError("email already registered")
        user_id, workspace_id = str(uuid.uuid4()), str(uuid.uuid4())
        with self._db.transaction():
            self._db.execute("INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)", (user_id, email, name.strip(), hash_password(password), now_iso()))
            self._db.execute("INSERT INTO workspaces (id, name, created_at) VALUES (?, ?, ?)", (workspace_id, f"{name.strip()}'s workspace", now_iso()))
            self._db.execute("INSERT INTO memberships (workspace_id, user_id, role) VALUES (?, ?, ?)", (workspace_id, user_id, "owner"))
        return {"user_id": user_id, "workspace_id": workspace_id}

    def authenticate(self, email: str, password: str) -> dict | None:
        rows = self._db.query("SELECT id, name, email, password_hash FROM users WHERE email = ?", (email.strip().lower(),))
        stored = rows[0]["password_hash"] if rows else DUMMY_HASH
        valid = verify_password(password, stored)
        return {"id": rows[0]["id"], "name": rows[0]["name"], "email": rows[0]["email"]} if rows and valid else None

    def profile(self, user_id: str) -> dict:
        rows = self._db.query("SELECT name, email FROM users WHERE id = ?", (user_id,))
        return {"name": rows[0]["name"], "email": rows[0]["email"]} if rows else {"name": "", "email": ""}

    def workspaces_for(self, user_id: str) -> list[dict]:
        return self._db.query("SELECT w.id AS id, w.name AS name, m.role AS role FROM memberships m JOIN workspaces w ON w.id = m.workspace_id WHERE m.user_id = ? ORDER BY w.created_at", (user_id,))

    def role(self, user_id: str, workspace_id: str) -> str | None:
        rows = self._db.query("SELECT role FROM memberships WHERE user_id = ? AND workspace_id = ?", (user_id, workspace_id))
        return rows[0]["role"] if rows else None

    def add_member(self, workspace_id: str, user_id: str, role: str) -> None:
        if role not in ROLES:
            raise ValueError("unknown role")
        self._db.execute("INSERT INTO memberships (workspace_id, user_id, role) VALUES (?, ?, ?) ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = excluded.role", (workspace_id, user_id, role))

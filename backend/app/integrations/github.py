import json
import urllib.request
import urllib.error
from typing import Callable

Transport = Callable[[str, str, dict, bytes | None], tuple[int, bytes]]


class GitHubError(Exception):
    pass


class GitHubClient:
    def __init__(self, token: str, transport: Transport):
        self.token = token
        self.transport = transport

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"https://api.github.com{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "pactline",
        }
        data = json.dumps(body).encode() if body else None
        try:
            status, payload = self.transport(method, url, headers, data)
            if status >= 400:
                raise GitHubError(f"HTTP {status}: {payload.decode(errors='replace')[:300]}")
            return json.loads(payload or b"{}")
        except Exception as e:
            raise GitHubError(str(e))

    def list_user_repos(self, per_page: int = 30) -> list[dict]:
        """List user's repositories."""
        data = self._call("GET", f"/user/repos?per_page={per_page}&sort=updated")
        return [{"name": r["name"], "full_name": r["full_name"], "url": r["html_url"], "language": r["language"], "private": r["private"]} for r in data]

    def get_repo_contents(self, owner: str, repo: str, path: str = "") -> dict:
        """Get repository file/directory contents."""
        return self._call("GET", f"/repos/{owner}/{repo}/contents/{path}")

    def create_branch(self, owner: str, repo: str, branch: str, sha: str) -> dict:
        """Create a new branch."""
        return self._call("POST", f"/repos/{owner}/{repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": sha})

    def get_default_branch_sha(self, owner: str, repo: str) -> str:
        """Get the default branch commit SHA."""
        repo_data = self._call("GET", f"/repos/{owner}/{repo}")
        default_branch = repo_data["default_branch"]
        branch_data = self._call("GET", f"/repos/{owner}/{repo}/branches/{default_branch}")
        return branch_data["commit"]["sha"]

    def create_or_update_file(self, owner: str, repo: str, path: str, content: bytes, branch: str, message: str, sha: str | None = None) -> dict:
        """Create or update a file in the repository."""
        import base64

        payload = {
            "message": message,
            "content": base64.b64encode(content).decode(),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        return self._call("PUT", f"/repos/{owner}/{repo}/contents/{path}", payload)

    def create_pull_request(self, owner: str, repo: str, title: str, head: str, base: str, body: str = "") -> dict:
        """Create a pull request."""
        return self._call("POST", f"/repos/{owner}/{repo}/pulls", {"title": title, "head": head, "base": base, "body": body})

    @staticmethod
    def from_env(env, transport: Transport):
        """Create a GitHubClient from environment variables."""
        token = env.get("GITHUB_TOKEN", "")
        if not token:
            return None
        return GitHubClient(token, transport)

import json
from typing import Callable
from urllib.parse import quote

Transport = Callable[[str, str, dict, bytes | None], tuple[int, bytes]]

STATUS_MAP = {"OK": "PASSED", "ERROR": "FAILED", "WARN": "WARNING", "NONE": "NOT_COMPUTED"}


class SonarError(Exception):
    pass


class SonarClient:
    def __init__(self, base_url: str, token: str, transport: Transport):
        self._base = base_url.rstrip("/")
        self._token = token
        self._transport = transport

    def quality_gate(self, project_key: str) -> dict:
        url = f"{self._base}/api/qualitygates/project_status?projectKey={quote(project_key)}"
        status, payload = self._transport("GET", url, {"Authorization": f"Bearer {self._token}"}, None)
        if status != 200:
            raise SonarError(f"quality gate lookup failed with HTTP {status}")
        project_status = json.loads(payload)["projectStatus"]
        failed = [c["metricKey"] for c in project_status.get("conditions", []) if c.get("status") == "ERROR"]
        return {
            "project_key": project_key,
            "gate": STATUS_MAP.get(project_status["status"], "UNKNOWN"),
            "failed_conditions": failed,
        }

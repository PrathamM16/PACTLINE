import base64
import json
from typing import Callable
from urllib.parse import quote
from xml.sax.saxutils import escape

from app.devops.pipeline import PipelineSpec

Transport = Callable[[str, str, dict, bytes | None], tuple[int, bytes]]


class JenkinsError(Exception):
    pass


def job_config_xml(spec: PipelineSpec) -> str:
    credentials = ""
    if spec.git_credentials_id:
        credentials = f"<credentialsId>{escape(spec.git_credentials_id)}</credentialsId>"
    url = escape(f"https://github.com/{spec.repository}.git")
    return (
        "<flow-definition plugin=\"workflow-job\">"
        f"<description>Managed by PACTLINE for {escape(spec.repository)}</description>"
        "<definition class=\"org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition\" plugin=\"workflow-cps\">"
        "<scm class=\"hudson.plugins.git.GitSCM\" plugin=\"git\"><configVersion>2</configVersion>"
        "<userRemoteConfigs><hudson.plugins.git.UserRemoteConfig>"
        f"<url>{url}</url>{credentials}"
        "</hudson.plugins.git.UserRemoteConfig></userRemoteConfigs>"
        f"<branches><hudson.plugins.git.BranchSpec><name>*/{escape(spec.branch)}</name></hudson.plugins.git.BranchSpec></branches>"
        "</scm><scriptPath>Jenkinsfile</scriptPath><lightweight>true</lightweight></definition>"
        "<triggers><com.cloudbees.jenkins.GitHubPushTrigger plugin=\"github\"><spec></spec>"
        "</com.cloudbees.jenkins.GitHubPushTrigger></triggers></flow-definition>"
    )


class JenkinsClient:
    def __init__(self, base_url: str, username: str, api_token: str, transport: Transport):
        self._base = base_url.rstrip("/")
        self._auth = "Basic " + base64.b64encode(f"{username}:{api_token}".encode()).decode()
        self._transport = transport

    def _call(self, method: str, path: str, headers: dict | None = None, body: bytes | None = None):
        merged = {"Authorization": self._auth, **(headers or {})}
        return self._transport(method, self._base + path, merged, body)

    def _crumb(self) -> dict:
        status, payload = self._call("GET", "/crumbIssuer/api/json")
        if status != 200:
            return {}
        data = json.loads(payload)
        return {data["crumbRequestField"]: data["crumb"]}

    def job_exists(self, job_name: str) -> bool:
        status, _ = self._call("GET", f"/job/{quote(job_name)}/api/json")
        return status == 200

    def create_job(self, job_name: str, config_xml: str) -> dict:
        headers = {"Content-Type": "application/xml", **self._crumb()}
        status, _ = self._call("POST", f"/createItem?name={quote(job_name)}", headers, config_xml.encode())
        if status not in (200, 201):
            raise JenkinsError(f"createItem failed with HTTP {status}")
        return {"created": True, "confirmed": self.job_exists(job_name)}

    def trigger_build(self, job_name: str) -> bool:
        status, _ = self._call("POST", f"/job/{quote(job_name)}/build", self._crumb())
        if status not in (200, 201):
            raise JenkinsError(f"build trigger failed with HTTP {status}")
        return True

    def build_status(self, job_name: str, build_number: int) -> dict:
        status, payload = self._call("GET", f"/job/{quote(job_name)}/{build_number}/api/json")
        if status != 200:
            raise JenkinsError(f"build lookup failed with HTTP {status}")
        data = json.loads(payload)
        return {"number": data["number"], "building": data["building"], "result": data.get("result")}

    def console_tail(self, job_name: str, build_number: int, max_chars: int = 2000) -> str:
        status, payload = self._call("GET", f"/job/{quote(job_name)}/{build_number}/consoleText")
        if status != 200:
            raise JenkinsError(f"console lookup failed with HTTP {status}")
        return payload.decode(errors="replace")[-max_chars:]

import json
import unittest

from app.devops.pipeline import PipelineSpec
from app.devops.tools import DevopsTools
from app.domain.approval import ApprovalGate
from app.domain.audit import AuditLog
from app.integrations.jenkins import JenkinsClient, JenkinsError, job_config_xml
from app.integrations.sonar import SonarClient, SonarError

SPEC = PipelineSpec("web-ci", "acme/web", "develop", "angular", "20", ("install", "build"))
CRUMB = json.dumps({"crumbRequestField": "Jenkins-Crumb", "crumb": "abc"}).encode()


class FakeTransport:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        return self.routes.get((method, url.split("//", 1)[1].split("/", 1)[1]), (404, b""))


def jenkins(routes):
    transport = FakeTransport(routes)
    return JenkinsClient("https://jenkins.example.com", "bot", "token", transport), transport


class JenkinsClientTest(unittest.TestCase):
    def test_create_job_is_confirmed_only_when_job_exists(self):
        client, _ = jenkins({("GET", "crumbIssuer/api/json"): (200, CRUMB), ("POST", "createItem?name=web-ci"): (200, b""), ("GET", "job/web-ci/api/json"): (200, b"{}")})
        self.assertEqual(client.create_job("web-ci", "<x/>"), {"created": True, "confirmed": True})

    def test_create_job_is_unconfirmed_when_lookup_fails(self):
        client, _ = jenkins({("GET", "crumbIssuer/api/json"): (200, CRUMB), ("POST", "createItem?name=web-ci"): (200, b"")})
        self.assertFalse(client.create_job("web-ci", "<x/>")["confirmed"])

    def test_create_job_failure_raises(self):
        client, _ = jenkins({("GET", "crumbIssuer/api/json"): (200, CRUMB), ("POST", "createItem?name=web-ci"): (403, b"")})
        with self.assertRaises(JenkinsError):
            client.create_job("web-ci", "<x/>")

    def test_crumb_header_is_sent_on_mutation(self):
        client, transport = jenkins({("GET", "crumbIssuer/api/json"): (200, CRUMB), ("POST", "job/web-ci/build"): (201, b"")})
        client.trigger_build("web-ci")
        self.assertEqual(transport.calls[-1][2]["Jenkins-Crumb"], "abc")

    def test_basic_auth_header_is_sent(self):
        client, transport = jenkins({("GET", "job/web-ci/api/json"): (200, b"{}")})
        client.job_exists("web-ci")
        self.assertTrue(transport.calls[0][2]["Authorization"].startswith("Basic "))

    def test_build_status_reports_result(self):
        payload = json.dumps({"number": 7, "building": False, "result": "SUCCESS"}).encode()
        client, _ = jenkins({("GET", "job/web-ci/7/api/json"): (200, payload)})
        self.assertEqual(client.build_status("web-ci", 7), {"number": 7, "building": False, "result": "SUCCESS"})

    def test_build_status_unknown_build_raises(self):
        client, _ = jenkins({})
        with self.assertRaises(JenkinsError):
            client.build_status("web-ci", 99)

    def test_console_tail_is_truncated(self):
        client, _ = jenkins({("GET", "job/web-ci/3/consoleText"): (200, b"x" * 5000)})
        self.assertEqual(len(client.console_tail("web-ci", 3, 100)), 100)

    def test_job_config_points_at_github_repository(self):
        self.assertIn("https://github.com/acme/web.git", job_config_xml(SPEC))

    def test_job_config_uses_jenkinsfile_from_scm(self):
        self.assertIn("<scriptPath>Jenkinsfile</scriptPath>", job_config_xml(SPEC))

    def test_job_config_escapes_branch_markup(self):
        spec = PipelineSpec("web-ci", "acme/web", "dev<x>", "angular", "20", ("install",))
        self.assertNotIn("<x>", job_config_xml(spec))


class SonarClientTest(unittest.TestCase):
    def sonar(self, status, body):
        transport = FakeTransport({("GET", "api/qualitygates/project_status?projectKey=acme_web"): (status, json.dumps(body).encode())})
        return SonarClient("https://sonar.example.com", "tok", transport)

    def test_error_status_maps_to_failed(self):
        client = self.sonar(200, {"projectStatus": {"status": "ERROR", "conditions": [{"metricKey": "coverage", "status": "ERROR"}]}})
        self.assertEqual(client.quality_gate("acme_web")["gate"], "FAILED")

    def test_failed_conditions_are_listed(self):
        client = self.sonar(200, {"projectStatus": {"status": "ERROR", "conditions": [{"metricKey": "coverage", "status": "ERROR"}]}})
        self.assertEqual(client.quality_gate("acme_web")["failed_conditions"], ["coverage"])

    def test_ok_status_maps_to_passed(self):
        self.assertEqual(self.sonar(200, {"projectStatus": {"status": "OK"}}).quality_gate("acme_web")["gate"], "PASSED")

    def test_none_status_is_not_reported_as_passed(self):
        self.assertEqual(self.sonar(200, {"projectStatus": {"status": "NONE"}}).quality_gate("acme_web")["gate"], "NOT_COMPUTED")

    def test_http_failure_raises(self):
        with self.assertRaises(SonarError):
            self.sonar(401, {}).quality_gate("acme_web")


class DevopsToolsTest(unittest.TestCase):
    def setUp(self):
        routes = {("GET", "crumbIssuer/api/json"): (200, CRUMB), ("POST", "createItem?name=web-ci"): (200, b""), ("GET", "job/web-ci/api/json"): (200, b"{}"), ("POST", "job/web-ci/build"): (201, b"")}
        self.client, self.transport = jenkins(routes)
        self.gate = ApprovalGate()
        self.audit = AuditLog()
        self.tools = DevopsTools(self.client, self.gate, self.audit, {"acme/web"}, {"web-ci"})

    def approved(self, tool):
        request = self.gate.request(tool, "web-ci", {}, False, "pratham")
        self.gate.decide(request.id, "pratham", True)
        return request.id

    def test_job_creation_without_approval_is_denied(self):
        request = self.gate.request("create_jenkins_job", "web-ci", {}, False, "pratham")
        self.assertFalse(self.tools.create_jenkins_job("pratham", SPEC, request.id).ok)

    def test_denied_creation_never_calls_jenkins(self):
        request = self.gate.request("create_jenkins_job", "web-ci", {}, False, "pratham")
        self.tools.create_jenkins_job("pratham", SPEC, request.id)
        self.assertEqual(self.transport.calls, [])

    def test_approved_creation_succeeds(self):
        self.assertTrue(self.tools.create_jenkins_job("pratham", SPEC, self.approved("create_jenkins_job")).ok)

    def test_non_allowlisted_repository_is_denied(self):
        tools = DevopsTools(self.client, self.gate, self.audit, set(), {"web-ci"})
        self.assertFalse(tools.create_jenkins_job("pratham", SPEC, self.approved("create_jenkins_job")).ok)

    def test_creation_is_audited(self):
        self.tools.create_jenkins_job("pratham", SPEC, self.approved("create_jenkins_job"))
        self.assertEqual(self.audit.events[-1].outcome, "confirmed")

    def test_trigger_without_approval_is_denied(self):
        request = self.gate.request("trigger_jenkins_build", "web-ci", {}, False, "pratham")
        self.assertFalse(self.tools.trigger_build("pratham", "web-ci", request.id).ok)

    def test_approved_trigger_queues_build(self):
        self.assertEqual(self.tools.trigger_build("pratham", "web-ci", self.approved("trigger_jenkins_build")).detail, "build queued")

    def test_invalid_spec_is_not_generated(self):
        bad = PipelineSpec("web-ci", "acme/web", "bad branch", "angular", "20", ("install",))
        self.assertFalse(self.tools.generate_jenkinsfile("pratham", bad).ok)

    def test_valid_spec_returns_jenkinsfile(self):
        self.assertIn("pipeline {", self.tools.generate_jenkinsfile("pratham", SPEC).data["jenkinsfile"])


if __name__ == "__main__":
    unittest.main()

"""
SonarQube Cloud API client for quality analysis and reporting.
"""

import json
from typing import Callable

Transport = Callable[[str, str, dict, bytes | None], tuple[int, bytes]]


class SonarQubeError(Exception):
    pass


class SonarQubeClient:
    def __init__(self, token: str, cloud_url: str = "https://sonarcloud.io", transport: Transport = None):
        self.token = token
        self.cloud_url = cloud_url.rstrip("/")
        self.transport = transport

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        """Call SonarQube API endpoint."""
        url = f"{self.cloud_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "pactline",
        }
        data = json.dumps(body).encode() if body else None
        
        try:
            if self.transport:
                status, payload = self.transport(method, url, headers, data)
            else:
                # Fallback to urllib if no transport provided
                import urllib.request
                import urllib.error
                req = urllib.request.Request(url, data=data, method=method, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        status, payload = r.status, r.read()
                except urllib.error.HTTPError as e:
                    status, payload = e.code, e.read()
            
            if status >= 400:
                raise SonarQubeError(f"HTTP {status}: {payload.decode(errors='replace')[:300]}")
            return json.loads(payload or b"{}")
        except Exception as e:
            raise SonarQubeError(str(e))

    def get_project_status(self, project_key: str) -> dict:
        """Get project quality gate status."""
        return self._call("GET", f"/api/qualitygates/project_status?projectKey={project_key}")

    def get_project_measures(self, project_key: str, metrics: list[str] = None) -> dict:
        """Get project quality metrics."""
        if not metrics:
            metrics = [
                "coverage",           # Code coverage percentage
                "lines_to_cover",     # Lines to cover
                "ncloc",              # Non-comment lines of code
                "complexity",         # Cyclomatic complexity
                "bugs",               # Number of bugs
                "vulnerabilities",    # Security vulnerabilities
                "code_smells",        # Code smell issues
                "duplicated_lines",   # Duplicated lines
                "tests",              # Number of tests
                "test_success_density", # Test pass rate
            ]
        
        metric_string = ",".join(metrics)
        return self._call("GET", f"/api/measures/component?component={project_key}&metricKeys={metric_string}")

    def get_quality_gate_conditions(self, project_key: str) -> dict:
        """Get quality gate conditions and their status."""
        return self._call("GET", f"/api/qualitygates/project_status?projectKey={project_key}")

    def get_project_issues(self, project_key: str, severity: str = None, limit: int = 10) -> dict:
        """Get open issues/violations for the project."""
        query = f"componentKeys={project_key}&statuses=OPEN&pageSize={limit}"
        if severity:
            query += f"&severities={severity}"
        return self._call("GET", f"/api/issues/search?{query}")

    def get_coverage_report(self, project_key: str) -> dict:
        """Get code coverage details."""
        measures = self.get_project_measures(project_key, [
            "coverage",
            "line_coverage",
            "branch_coverage",
            "lines_to_cover",
            "uncovered_lines",
        ])
        
        component = measures.get("component", {})
        measures_dict = {m["metric"]: m.get("value") for m in component.get("measures", [])}
        
        return {
            "coverage_percentage": float(measures_dict.get("coverage", 0)),
            "line_coverage": float(measures_dict.get("line_coverage", 0)),
            "branch_coverage": float(measures_dict.get("branch_coverage", 0)),
            "lines_to_cover": int(measures_dict.get("lines_to_cover", 0)),
            "uncovered_lines": int(measures_dict.get("uncovered_lines", 0)),
        }

    def get_security_report(self, project_key: str) -> dict:
        """Get security vulnerabilities report."""
        measures = self.get_project_measures(project_key, [
            "vulnerabilities",
            "security_hotspots",
            "security_hotspots_reviewed",
        ])
        
        component = measures.get("component", {})
        measures_dict = {m["metric"]: m.get("value") for m in component.get("measures", [])}
        
        issues = self.get_project_issues(project_key, severity="BLOCKER")
        security_issues = [i for i in issues.get("issues", []) if i.get("type") in ("VULNERABILITY", "SECURITY_HOTSPOT")]
        
        return {
            "vulnerabilities": int(measures_dict.get("vulnerabilities", 0)),
            "security_hotspots": int(measures_dict.get("security_hotspots", 0)),
            "hotspots_reviewed": int(measures_dict.get("security_hotspots_reviewed", 0)),
            "critical_issues": len([i for i in security_issues if i.get("severity") in ("BLOCKER", "CRITICAL")]),
        }

    def is_quality_gate_passed(self, project_key: str) -> bool:
        """Check if quality gate is passed."""
        status = self.get_project_status(project_key)
        return status.get("projectStatus", {}).get("status") == "OK"

    def get_quality_summary(self, project_key: str) -> dict:
        """Get a comprehensive quality summary for approvals."""
        try:
            status = self.get_project_status(project_key)
            measures = self.get_project_measures(project_key)
            issues = self.get_project_issues(project_key, limit=5)
            
            component = measures.get("component", {})
            measures_dict = {m["metric"]: m.get("value") for m in component.get("measures", [])}
            
            gate_status = status.get("projectStatus", {})
            gate_passed = gate_status.get("status") == "OK"
            
            conditions = gate_status.get("conditions", [])
            failed_conditions = [c for c in conditions if c.get("status") != "OK"]
            
            return {
                "project_key": project_key,
                "quality_gate_passed": gate_passed,
                "quality_gate_status": gate_status.get("status"),
                "failed_conditions": [
                    {
                        "metric": c.get("metricKey"),
                        "operator": c.get("comparator"),
                        "threshold": c.get("errorThreshold"),
                        "actual": c.get("actualValue"),
                    }
                    for c in failed_conditions
                ],
                "coverage": float(measures_dict.get("coverage", 0)),
                "ncloc": int(measures_dict.get("ncloc", 0)),
                "complexity": int(measures_dict.get("complexity", 0)),
                "bugs": int(measures_dict.get("bugs", 0)),
                "vulnerabilities": int(measures_dict.get("vulnerabilities", 0)),
                "code_smells": int(measures_dict.get("code_smells", 0)),
                "open_issues": len(issues.get("issues", [])),
                "recommendation": _quality_recommendation(gate_passed, failed_conditions),
            }
        except SonarQubeError as e:
            return {
                "error": str(e),
                "project_key": project_key,
                "quality_gate_passed": False,
                "recommendation": "Unable to fetch SonarQube analysis. Please check project key and token.",
            }

    @staticmethod
    def from_env(env, transport: Transport = None):
        """Create a SonarQubeClient from environment variables."""
        token = env.get("SONARQUBE_TOKEN", "")
        url = env.get("SONARQUBE_CLOUD_URL", "https://sonarcloud.io")
        
        if not token or not url:
            return None
        
        return SonarQubeClient(token, url, transport)


def _quality_recommendation(gate_passed: bool, failed_conditions: list) -> str:
    """Generate a recommendation based on quality gate status."""
    if gate_passed:
        return "Quality gate PASSED. This build is production-ready. Ready to merge and deploy."
    
    if not failed_conditions:
        return "Quality gate status is unclear. Review SonarQube dashboard for details."
    
    # Analyze which conditions failed
    fail_reasons = []
    for condition in failed_conditions:
        metric = condition.get("metric", "unknown")
        if metric == "coverage":
            fail_reasons.append("code coverage is below threshold")
        elif metric == "security_rating":
            fail_reasons.append("security vulnerabilities detected")
        elif metric == "reliability_rating":
            fail_reasons.append("bug threshold exceeded")
        elif metric == "sqale_rating":
            fail_reasons.append("maintainability issues found")
        else:
            fail_reasons.append(f"{metric} threshold not met")
    
    reason_text = "; ".join(fail_reasons)
    return f"Quality gate FAILED: {reason_text}. Address issues before deployment."

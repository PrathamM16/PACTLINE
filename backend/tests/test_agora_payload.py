import json
import re
import unittest

from app.domain.tools import ToolRegistry
from app.storage import open_store
from app.integrations.agora import AGENT_UID, SYSTEM_PROMPT, build_join_payload, tool_specs

SETTINGS = {
    "llm_url": "https://api.openai.com/v1/chat/completions",
    "llm_api_key": "llm-key",
    "llm_model": "model-x",
    "murf_api_key": "murf-key",
    "murf_voice_id": "Matthew",
    "murf_locale": "en-US",
    "asr_language": "en-US",
    "murf_model": "FALCON",
}
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,63}$")


def specs():
    return tool_specs("https://api.example.com/", ToolRegistry(open_store("sqlite:///:memory:")).definitions())


def payload():
    return build_join_payload("room-1", "agent-token", 42, "session-jwt", specs(), SETTINGS)


class ToolSpecTest(unittest.TestCase):
    def test_tool_count_is_within_agora_limit(self):
        self.assertLessEqual(len(specs()), 32)

    def test_tool_names_are_alphanumeric_and_unique_ignoring_case(self):
        names = [s["function"]["name"].lower() for s in specs()]
        self.assertEqual(len(set(names)), len(names))

    def test_tool_names_match_agora_rules(self):
        self.assertTrue(all(NAME_RE.match(s["function"]["name"]) for s in specs()))

    def test_no_tool_uses_reserved_prefix(self):
        self.assertFalse(any(s["function"]["name"].lower().startswith("mcp") for s in specs()))

    def test_every_tool_uses_https_post(self):
        self.assertTrue(all(s["server"]["method"] == "POST" and s["server"]["url"].startswith("https://") for s in specs()))

    def test_tool_url_has_no_double_slash_after_host(self):
        self.assertEqual(specs()[0]["server"]["url"], "https://api.example.com/tools/createTask")

    def test_every_parameter_is_required_to_avoid_unresolved_templates(self):
        self.assertTrue(all(set(s["function"]["parameters"]["required"]) == set(s["function"]["parameters"]["properties"]) for s in specs()))

    def test_body_maps_each_parameter_to_a_complete_placeholder(self):
        spec = specs()[0]
        names = spec["function"]["parameters"]["properties"]
        self.assertTrue(all(spec["server"]["body"][n] == "{{args." + n + "}}" for n in names))

    def test_authorization_header_uses_template_variable_only(self):
        self.assertEqual(specs()[0]["server"]["headers"]["Authorization"], "{{template_variables.tool_auth}}")

    def test_no_placeholder_appears_in_header_args(self):
        self.assertTrue(all("args." not in v for s in specs() for v in s["server"]["headers"].values()))


class JoinPayloadTest(unittest.TestCase):
    def test_tts_vendor_is_murf(self):
        self.assertEqual(payload()["properties"]["tts"]["vendor"], "murf")

    def test_murf_model_is_falcon(self):
        self.assertEqual(payload()["properties"]["tts"]["params"]["model"], "FALCON")

    def test_murf_endpoint_is_streaming_websocket(self):
        self.assertEqual(payload()["properties"]["tts"]["params"]["base_url"], "wss://global.api.murf.ai/v1/speech/stream-input")

    def test_rtm_and_tools_are_enabled(self):
        self.assertEqual(payload()["properties"]["advanced_features"], {"enable_rtm": True, "enable_tools": True})

    def test_data_channel_is_rtm_for_transcripts(self):
        self.assertEqual(payload()["properties"]["parameters"]["data_channel"], "rtm")

    def test_agent_uid_differs_from_user_uid(self):
        props = payload()["properties"]
        self.assertNotEqual(props["agent_rtc_uid"], props["remote_rtc_uids"][0])

    def test_agent_uid_is_string_form_of_constant(self):
        self.assertEqual(payload()["properties"]["agent_rtc_uid"], str(AGENT_UID))

    def test_tool_auth_is_the_session_token_in_template_variables(self):
        self.assertEqual(payload()["properties"]["llm"]["template_variables"], {"tool_auth": "Bearer session-jwt"})

    def test_session_token_appears_only_once_in_payload(self):
        self.assertEqual(json.dumps(payload()).count("session-jwt"), 1)

    def test_tool_bodies_carry_no_identity_fields(self):
        self.assertTrue(all("workspace_id" not in s["server"]["body"] and "user_id" not in s["server"]["body"] for s in specs()))

    def test_tool_bodies_carry_no_confirmation_flag(self):
        self.assertTrue(all("user_confirmed" not in s["server"]["body"] for s in specs()))

    def test_murf_model_is_configurable(self):
        configured = build_join_payload("room-1", "t", 42, "j", specs(), {**SETTINGS, "murf_model": "falcon-2.1"})
        self.assertEqual(configured["properties"]["tts"]["params"]["model"], "falcon-2.1")

    def test_payload_is_json_serialisable(self):
        self.assertIsInstance(json.dumps(payload()), str)

    def test_system_prompt_requires_in_app_approval_before_claiming_writes(self):
        self.assertIn("press Approve in the app", SYSTEM_PROMPT)

    def test_system_prompt_forbids_choosing_disputed_dates(self):
        self.assertIn("never choose a date yourself", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()

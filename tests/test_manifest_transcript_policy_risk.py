import json
import tempfile
import unittest
from pathlib import Path

from mcp_policy_forge.engine import analyze, merge_needs
from mcp_policy_forge.manifest import parse_manifest
from mcp_policy_forge.models import ACTION_EXECUTE, ACTION_NETWORK, ACTION_READ, ACTION_WRITE, PermissionNeed
from mcp_policy_forge.policy import decide, generated_policy_from_needs
from mcp_policy_forge.risk import risk_level, score_risks
from mcp_policy_forge.transcript import parse_transcript


class ManifestTranscriptPolicyRiskTests(unittest.TestCase):
    def test_parse_manifest_tools(self):
        tools = parse_manifest({"tools": [{"name": "repo.read_file", "description": "Read file", "inputSchema": {"properties": {"path": {"type": "string"}}}}]})
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "repo.read_file")
        self.assertIn(ACTION_READ, tools[0].inferred_actions)

    def test_parse_manifest_mcp_servers_shape(self):
        tools = parse_manifest({"mcpServers": {"fs": {"tools": [{"name": "fs.write", "description": "write file"}]}}})
        self.assertEqual(tools[0].name, "fs.write")
        self.assertIn(ACTION_WRITE, tools[0].inferred_actions)

    def test_transcript_jsonl_extracts_calls(self):
        needs = parse_transcript('{"type":"tool_call","name":"web.fetch","arguments":{"url":"https://example.com/a"}}\n')
        self.assertEqual(needs[0].tool, "web.fetch")
        self.assertIn(ACTION_NETWORK, needs[0].actions)
        self.assertEqual(needs[0].networks, ["example.com"])

    def test_transcript_openai_function_shape(self):
        text = json.dumps({"tool_calls": [{"function": {"name": "repo.read", "arguments": "{\"path\":\"README.md\"}"}}]})
        needs = parse_transcript(text)
        self.assertEqual(needs[0].tool, "repo.read")
        self.assertIn("README.md", needs[0].paths)

    def test_merge_needs_combines_actions(self):
        merged = merge_needs([
            PermissionNeed(tool="x", actions=[ACTION_READ], paths=["a"]),
            PermissionNeed(tool="x", actions=[ACTION_WRITE], paths=["b"]),
        ])
        self.assertEqual(len(merged), 1)
        self.assertEqual(set(merged[0].actions), {ACTION_READ, ACTION_WRITE})
        self.assertEqual(merged[0].paths, ["a", "b"])

    def test_generated_policy_allows_needed_action(self):
        policy = generated_policy_from_needs([PermissionNeed(tool="repo.read", actions=[ACTION_READ], paths=["README.md"])])
        self.assertEqual(decide(policy, "repo.read", action=ACTION_READ, path="README.md"), "allow")

    def test_policy_default_denies_unknown_tool(self):
        policy = generated_policy_from_needs([PermissionNeed(tool="repo.read", actions=[ACTION_READ])])
        self.assertEqual(decide(policy, "repo.write", action=ACTION_WRITE), "deny")

    def test_risk_scores_command_as_high(self):
        tools = parse_manifest({"tools": [{"name": "shell.run", "description": "Run shell command"}]})
        risks = score_risks(tools, [PermissionNeed(tool="shell.run", actions=[ACTION_EXECUTE])])
        self.assertGreaterEqual(risks[0].score, 45)
        self.assertEqual(risks[0].level, "medium")

    def test_risk_level_boundaries(self):
        self.assertEqual(risk_level(10), "low")
        self.assertEqual(risk_level(25), "medium")
        self.assertEqual(risk_level(50), "high")
        self.assertEqual(risk_level(75), "critical")

    def test_analyze_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            transcript = root / "transcript.jsonl"
            manifest.write_text(json.dumps({"tools": [{"name": "web.fetch", "description": "Fetch URL", "inputSchema": {"properties": {"url": {"type": "string"}}}}]}), encoding="utf-8")
            transcript.write_text('{"type":"tool_call","name":"web.fetch","arguments":{"url":"https://example.com"}}\n', encoding="utf-8")
            report = analyze(str(manifest), transcript_path=str(transcript), repo_root=str(root))
        self.assertEqual(report.tools[0].name, "web.fetch")
        self.assertIn(ACTION_NETWORK, report.needs[0].actions)
        self.assertEqual(report.risks[0].tool, "web.fetch")


if __name__ == "__main__":
    unittest.main()


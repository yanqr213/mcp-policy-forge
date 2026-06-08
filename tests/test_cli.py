import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from mcp_policy_forge import cli
from mcp_policy_forge.cli import EXIT_FAILED, EXIT_INVALID, EXIT_OK, should_fail
from mcp_policy_forge.models import AnalysisReport, Finding, PermissionNeed, Policy, RiskResult


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.manifest = self.root / "manifest.json"
        self.transcript = self.root / "transcript.jsonl"
        self.manifest.write_text(json.dumps({"tools": [{"name": "web.fetch", "description": "Fetch URL", "inputSchema": {"properties": {"url": {"type": "string"}}}}]}), encoding="utf-8")
        self.transcript.write_text('{"type":"tool_call","name":"web.fetch","arguments":{"url":"https://example.com"}}\n', encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def run_cli(self, argv):
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            return cli.main(argv)

    def test_generate_writes_json(self):
        out = self.root / "report.json"
        code = self.run_cli(["generate", "--manifest", str(self.manifest), "--transcript", str(self.transcript), "--out-json", str(out), "--fail-on", "never"])
        self.assertEqual(code, EXIT_OK)
        self.assertTrue(out.exists())
        self.assertIn("policy", json.loads(out.read_text(encoding="utf-8")))

    def test_generate_writes_policy(self):
        out = self.root / "policy.json"
        code = self.run_cli(["generate", "--manifest", str(self.manifest), "--out-policy", str(out), "--fail-on", "never"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("rules", json.loads(out.read_text(encoding="utf-8")))

    def test_generate_writes_markdown_and_junit(self):
        md = self.root / "report.md"
        junit = self.root / "junit.xml"
        code = self.run_cli(["generate", "--manifest", str(self.manifest), "--out-md", str(md), "--junit", str(junit), "--fail-on", "never"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("MCP Policy Forge", md.read_text(encoding="utf-8"))
        self.assertIn("<testsuite", junit.read_text(encoding="utf-8"))

    def test_check_fail_on_high_risk(self):
        code = self.run_cli(["check", "--manifest", str(self.manifest), "--transcript", str(self.transcript), "--fail-on", "medium"])
        self.assertEqual(code, EXIT_FAILED)

    def test_check_never_succeeds(self):
        code = self.run_cli(["check", "--manifest", str(self.manifest), "--transcript", str(self.transcript), "--fail-on", "never"])
        self.assertEqual(code, EXIT_OK)

    def test_validate_good_policy(self):
        policy = self.root / "policy.json"
        policy.write_text(json.dumps({"rules": [{"effect": "allow", "tools": ["x"], "actions": ["read_file"]}]}), encoding="utf-8")
        self.assertEqual(self.run_cli(["validate", "--policy", str(policy)]), EXIT_OK)

    def test_validate_bad_policy(self):
        policy = self.root / "bad-policy.json"
        policy.write_text(json.dumps({"rules": [{"effect": "maybe", "tools": ["x"], "actions": ["read_file"]}]}), encoding="utf-8")
        self.assertEqual(self.run_cli(["validate", "--policy", str(policy)]), EXIT_FAILED)

    def test_validate_missing_policy_is_invalid(self):
        self.assertEqual(self.run_cli(["validate", "--policy", str(self.root / "missing.json")]), EXIT_INVALID)

    def test_diff_writes_json(self):
        old = self.root / "old.json"
        new = self.root / "new.json"
        out = self.root / "diff.json"
        old.write_text(json.dumps({"rules": []}), encoding="utf-8")
        new.write_text(json.dumps({"rules": [{"effect": "allow", "tools": ["x"], "actions": ["read_file"]}]}), encoding="utf-8")
        self.assertEqual(self.run_cli(["diff", "--old", str(old), "--new", str(new), "--out-json", str(out)]), EXIT_OK)
        self.assertEqual(len(json.loads(out.read_text(encoding="utf-8"))["added"]), 1)

    def test_diff_writes_markdown(self):
        old = self.root / "old.json"
        new = self.root / "new.json"
        out = self.root / "diff.md"
        old.write_text(json.dumps({"rules": []}), encoding="utf-8")
        new.write_text(json.dumps({"rules": []}), encoding="utf-8")
        self.assertEqual(self.run_cli(["diff", "--old", str(old), "--new", str(new), "--out-md", str(out)]), EXIT_OK)
        self.assertIn("Policy Diff", out.read_text(encoding="utf-8"))

    def test_no_command_invalid(self):
        self.assertEqual(self.run_cli([]), EXIT_INVALID)

    def test_should_fail_violations(self):
        report = AnalysisReport(policy=Policy(), needs=[], risks=[], findings=[Finding(severity="error", code="E", message="bad")])
        self.assertTrue(should_fail(report, "violations"))

    def test_should_fail_never(self):
        report = AnalysisReport(policy=Policy(), needs=[], risks=[RiskResult(tool="x", score=100, level="critical")], findings=[])
        self.assertFalse(should_fail(report, "never"))

    def test_should_fail_threshold(self):
        report = AnalysisReport(policy=Policy(), needs=[PermissionNeed(tool="x")], risks=[RiskResult(tool="x", score=50, level="high")], findings=[])
        self.assertTrue(should_fail(report, "high"))

    def test_should_not_fail_below_threshold(self):
        report = AnalysisReport(policy=Policy(), needs=[], risks=[RiskResult(tool="x", score=24, level="low")], findings=[])
        self.assertFalse(should_fail(report, "medium"))


if __name__ == "__main__":
    unittest.main()

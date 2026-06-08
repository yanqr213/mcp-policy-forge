import tempfile
import unittest
from pathlib import Path

from mcp_policy_forge.io import InputError
from mcp_policy_forge.models import ACTION_NETWORK, ACTION_READ, ACTION_WRITE, PermissionNeed, Policy, PolicyRule
from mcp_policy_forge.policy import (
    decide,
    escapes_repo,
    evaluate_needs,
    generated_policy_from_needs,
    is_write_path,
    matches_rule,
    merge_rules,
    parse_policy,
    validate_policy,
)


class PolicyTests(unittest.TestCase):
    def test_parse_policy_rules(self):
        policy = parse_policy({"rules": [{"effect": "allow", "tools": "x", "actions": "read"}]})
        self.assertEqual(policy.rules[0].tools, ["x"])
        self.assertEqual(policy.rules[0].actions, [ACTION_READ])

    def test_parse_policy_rejects_non_object(self):
        with self.assertRaises(InputError):
            parse_policy([])

    def test_parse_policy_rejects_non_object_rule(self):
        with self.assertRaises(InputError):
            parse_policy({"rules": ["bad"]})

    def test_validate_policy_bad_effect(self):
        findings = validate_policy(Policy(rules=[PolicyRule(effect="maybe", tools=["x"], actions=[ACTION_READ])]))
        self.assertEqual(findings[0].code, "POLICY_EFFECT")

    def test_validate_policy_empty_scope_warning(self):
        findings = validate_policy(Policy(rules=[PolicyRule(effect="allow", tools=["x"])]))
        self.assertEqual(findings[0].code, "POLICY_EMPTY_SCOPE")

    def test_merge_rules_combines_scope(self):
        rules = merge_rules([
            PolicyRule(effect="allow", tools=["x"], actions=[ACTION_READ]),
            PolicyRule(effect="allow", tools=["x"], actions=[ACTION_WRITE]),
        ])
        self.assertEqual(set(rules[0].actions), {ACTION_READ, ACTION_WRITE})

    def test_deny_overrides_allow(self):
        policy = Policy(rules=[
            PolicyRule(effect="allow", tools=["x"], actions=[ACTION_READ]),
            PolicyRule(effect="deny", tools=["x"], actions=[ACTION_READ]),
        ])
        self.assertEqual(decide(policy, "x", action=ACTION_READ), "deny")

    def test_match_tool_wildcard(self):
        self.assertTrue(matches_rule(PolicyRule(effect="allow", tools=["repo.*"]), "repo.read"))

    def test_match_action_filter(self):
        self.assertFalse(matches_rule(PolicyRule(effect="allow", tools=["x"], actions=[ACTION_READ]), "x", action=ACTION_WRITE))

    def test_match_path_glob(self):
        rule = PolicyRule(effect="allow", tools=["x"], paths=["src/*.py"])
        self.assertTrue(matches_rule(rule, "x", path="src/app.py"))

    def test_match_network_glob(self):
        rule = PolicyRule(effect="allow", tools=["x"], networks=["*.example.com"])
        self.assertTrue(matches_rule(rule, "x", network="api.example.com"))

    def test_evaluate_denied_action(self):
        findings = evaluate_needs(Policy(defaults={"effect": "deny"}), [PermissionNeed(tool="x", actions=[ACTION_WRITE])])
        self.assertEqual(findings[0].code, "ACTION_DENIED")

    def test_evaluate_allowed_network(self):
        policy = Policy(rules=[PolicyRule(effect="allow", tools=["x"], actions=[ACTION_NETWORK], networks=["example.com"])])
        findings = evaluate_needs(policy, [PermissionNeed(tool="x", actions=[ACTION_NETWORK], networks=["example.com"])])
        self.assertFalse(findings)

    def test_evaluate_denied_network(self):
        policy = Policy(rules=[PolicyRule(effect="allow", tools=["x"], actions=[ACTION_NETWORK], networks=["allowed.com"])])
        findings = evaluate_needs(policy, [PermissionNeed(tool="x", actions=[ACTION_NETWORK], networks=["blocked.com"])])
        self.assertEqual(findings[0].code, "NETWORK_DENIED")

    def test_path_escape_absolute(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = str(Path(tmp).parent / "outside.txt")
            self.assertTrue(escapes_repo(outside, tmp))

    def test_path_escape_relative_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(escapes_repo("../outside.txt", tmp))

    def test_path_inside_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(escapes_repo("src/app.py", tmp))

    def test_evaluate_path_escape_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = generated_policy_from_needs([PermissionNeed(tool="x", actions=[ACTION_READ], paths=["../x"])])
            findings = evaluate_needs(policy, [PermissionNeed(tool="x", actions=[ACTION_READ], paths=["../x"])], repo_root=tmp)
            self.assertTrue(any(item.code == "PATH_ESCAPE" for item in findings))

    def test_is_write_path_true_when_only_write(self):
        self.assertTrue(is_write_path(PermissionNeed(tool="x", actions=[ACTION_WRITE]), "a"))

    def test_is_write_path_false_when_read_present(self):
        self.assertFalse(is_write_path(PermissionNeed(tool="x", actions=[ACTION_WRITE, ACTION_READ]), "a"))

    def test_generated_policy_preserves_org_rule(self):
        org = Policy(rules=[PolicyRule(effect="deny", tools=["x"], actions=[ACTION_WRITE])])
        policy = generated_policy_from_needs([PermissionNeed(tool="x", actions=[ACTION_READ])], org)
        self.assertEqual(policy.rules[0].effect, "deny")


if __name__ == "__main__":
    unittest.main()


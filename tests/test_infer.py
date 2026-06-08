import unittest

from mcp_policy_forge.infer import (
    infer_actions_from_text,
    infer_from_arguments,
    infer_from_schema,
    looks_like_network,
    looks_like_path,
    normalize_action,
    normalize_network,
    schema_literals,
)
from mcp_policy_forge.models import ACTION_EXECUTE, ACTION_NETWORK, ACTION_READ, ACTION_SECRET, ACTION_WRITE


class InferTests(unittest.TestCase):
    def test_normalize_action_aliases(self):
        self.assertEqual(normalize_action("read"), ACTION_READ)
        self.assertEqual(normalize_action("file-write"), ACTION_WRITE)
        self.assertEqual(normalize_action("exec"), ACTION_EXECUTE)

    def test_infer_read_from_text(self):
        self.assertIn(ACTION_READ, infer_actions_from_text("read a file"))

    def test_infer_write_from_text(self):
        self.assertIn(ACTION_WRITE, infer_actions_from_text("create and patch"))

    def test_infer_network_from_text(self):
        self.assertIn(ACTION_NETWORK, infer_actions_from_text("fetch url"))

    def test_infer_execute_from_text(self):
        self.assertIn(ACTION_EXECUTE, infer_actions_from_text("run command"))

    def test_infer_secret_from_text(self):
        self.assertIn(ACTION_SECRET, infer_actions_from_text("api_key token"))

    def test_looks_like_path_absolute(self):
        self.assertTrue(looks_like_path("/tmp/a.txt"))

    def test_looks_like_path_relative(self):
        self.assertTrue(looks_like_path("./src/app.py"))

    def test_looks_like_path_extension(self):
        self.assertTrue(looks_like_path("README.md"))

    def test_looks_like_path_rejects_plain_word(self):
        self.assertFalse(looks_like_path("hello"))

    def test_looks_like_path_rejects_url(self):
        self.assertFalse(looks_like_path("https://example.com/a"))

    def test_looks_like_network_url(self):
        self.assertTrue(looks_like_network("https://example.com/a"))

    def test_looks_like_network_host(self):
        self.assertTrue(looks_like_network("api.example.com"))

    def test_normalize_network_url(self):
        self.assertEqual(normalize_network("https://Example.COM/a"), "example.com")

    def test_normalize_network_host(self):
        self.assertEqual(normalize_network("Example.COM/"), "example.com")

    def test_schema_literals_from_enum(self):
        self.assertEqual(schema_literals({"enum": ["a", "b"]}), ["a", "b"])

    def test_schema_literals_from_example(self):
        self.assertEqual(schema_literals({"example": "README.md"}), ["README.md"])

    def test_infer_from_schema_path_field(self):
        actions, paths, networks, reasons = infer_from_schema({"properties": {"path": {"type": "string", "examples": ["README.md"]}}})
        self.assertIn(ACTION_READ, actions)
        self.assertIn("README.md", paths)
        self.assertTrue(reasons)

    def test_infer_from_schema_url_field(self):
        actions, paths, networks, reasons = infer_from_schema({"properties": {"url": {"type": "string", "examples": ["https://example.com/a"]}}})
        self.assertIn(ACTION_NETWORK, actions)
        self.assertIn("example.com", networks)

    def test_infer_from_schema_secret_field(self):
        actions, paths, networks, reasons = infer_from_schema({"properties": {"api_key": {"type": "string"}}})
        self.assertIn(ACTION_SECRET, actions)

    def test_infer_from_arguments_path(self):
        actions, paths, networks, reasons = infer_from_arguments({"path": "README.md"})
        self.assertIn(ACTION_READ, actions)
        self.assertEqual(paths, ["README.md"])

    def test_infer_from_arguments_output_path(self):
        actions, paths, networks, reasons = infer_from_arguments({"output_path": "dist/report.json"})
        self.assertIn(ACTION_WRITE, actions)
        self.assertEqual(paths, ["dist/report.json"])

    def test_infer_from_arguments_url(self):
        actions, paths, networks, reasons = infer_from_arguments({"url": "https://example.com/a"})
        self.assertIn(ACTION_NETWORK, actions)
        self.assertNotIn(ACTION_READ, actions)
        self.assertEqual(paths, [])
        self.assertEqual(networks, ["example.com"])

    def test_unknown_removed_when_specific_action_exists(self):
        actions, paths, networks, reasons = infer_from_schema({"properties": {"url": {"type": "string"}}})
        self.assertEqual(actions, [ACTION_NETWORK])


if __name__ == "__main__":
    unittest.main()

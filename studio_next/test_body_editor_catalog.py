"""Native editing stays native; BODY supplies host-granted tool discovery."""
import tempfile
import unittest
from studio_next.body_integration import body_catalog


class Editor:
    allowed_tools = {"get_project": "read", "update_text_clip": "write"}

    def __init__(self):
        self.calls = []

    def list_tools(self):
        return [
            {"name": "get_project", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "update_text_clip", "description": "Native edit",
             "inputSchema": {"type": "object", "required": ["clipId"], "properties": {
                 "clipId": {"type": "string"}, "text": {"anyOf": [{"type": "string"}, {"type": "null"}]}}}},
            {"name": "install_workflow_setup", "inputSchema": {"type": "object"}},
        ]

    def call(self, name, arguments, *, allowed_access):
        self.calls.append((name, arguments, allowed_access))
        return {"content": [{"type": "text", "text": "native result"}]}


class EditorCatalogTests(unittest.TestCase):
    def test_native_schema_and_arguments_survive_and_writes_are_not_replayable(self):
        editor = Editor()
        with tempfile.TemporaryDirectory() as root:
            catalog = body_catalog(root, editor_client=editor)
            tools = {tool["id"]: tool for tool in catalog.discover()}
            tool = tools["body.editor.update_text_clip"]
            self.assertEqual(tool["schema"]["properties"]["arguments"], editor.list_tools()[1]["inputSchema"])
            args = {"clipId": "native-id", "text": "Revision"}
            result = catalog.invoke(tool["id"], {"arguments": args}, {"write"})
            self.assertEqual(result["content"][0]["text"], "native result")
            self.assertEqual(editor.calls, [("update_text_clip", args, frozenset({"write"}))])
            self.assertNotIn(tool["id"], catalog.trusted_idempotent_ids())
            self.assertNotIn("body.editor.install_workflow_setup", tools)

    def test_caller_must_grant_writes_before_native_request(self):
        editor = Editor()
        with tempfile.TemporaryDirectory() as root:
            catalog = body_catalog(root, editor_client=editor)
            with self.assertRaises(PermissionError):
                catalog.invoke("body.editor.update_text_clip", {"arguments": {"clipId": "x"}})
            self.assertEqual(editor.calls, [])
            catalog.invoke("body.editor.get_project", {"arguments": {}})
            self.assertEqual(editor.calls[0][0], "get_project")

    def test_missing_granted_tool_fails_discovery(self):
        editor = Editor()
        editor.allowed_tools = {"removed_tool": "write"}
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "absent"):
                body_catalog(root, editor_client=editor)

    def test_default_catalog_does_not_claim_running_editor(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertFalse(any(tool["id"].startswith("body.editor.") for tool in body_catalog(root).discover()))


if __name__ == "__main__":
    unittest.main()

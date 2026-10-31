"""Model-neutral trusted fact frontier: exact native source tools, no edit scripts.

The test stub chooses actions, so this proves protocol/safety only. The real
Qwen3.5-2B trial #41186113669 showed 40 authored decisions but never searched
for import, despite source assets in its brief and get_assets count=0.
"""
import copy
import json
import unittest
from types import SimpleNamespace

from studio_next.native_creative_control import NativeCreativeControl
from studio_next.native_creative_audit import audit_native_journal, NativeJournalError
from studio_next.test_native_creative_control import ScriptedModel, decision
from studio_next.test_native_asset_identity import LiveCatalogSession


class HostObservedEmptyAssetSession(LiveCatalogSession):
    def __init__(self):
        super().__init__([])
        self.tools.extend([
            SimpleNamespace(name="get_project",
                            description="Read real native saved project",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="import_asset_from_path",
                            description=("Preview or import a local media path into the "
                                         "active saved project. Source assets are "
                                         "copied on confirmed apply."),
                            input_schema={"type": "object", "properties": {
                                "path": {"type": "string"},
                                "previewOnly": {"type": "boolean"}}}),
        ])

    async def call_tool(self, name, arguments):
        if name == "get_project":
            self.calls.append((name, arguments))
            response = {"mcp": {"hasProject": True},
                        "project": {"id": "source-owned-project"},
                        "assetCount": 0, "timelineCount": 1,
                        "currentTimeline": {"id": "real-timeline",
                                            "clipCount": 0, "trackCount": 2,
                                            "transitionCount": 0}}
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text=json.dumps(response))])
        return await super().call_tool(name, arguments)


class ActualHostAssetProducerFrontierTests(unittest.IsolatedAsyncioTestCase):
    def grants(self, session):
        return {t.name: ("read" if t.name in {
            "get_project", "get_assets", "get_timeline",
            "zx7_verify_native_export", "zx7_observe_verified_export_frame"}
            else "write") for t in session.tools}

    async def test_empty_native_assets_expose_actual_host_producer_not_a_script(self):
        editor = HostObservedEmptyAssetSession()
        model = ScriptedModel([
            decision("search", query="add_asset_to_timeline"),
            decision("invoke", tool="add_asset_to_timeline",
                     inputs={"assetId": "hallucinated-asset", "previewOnly": False}),
            decision("invoke", tool="import_asset_from_path",
                     inputs={"path": "/trusted/staging/original.mp4",
                             "previewOnly": False}),
        ])
        access = self.grants(editor)
        result = await NativeCreativeControl(
            editor, model, max_turns=3, catalog_mode="indexed",
            host_tool_access=access,
            host_possible_effects={
                "import_asset_from_path": ["project_asset_available"],
            }).run("Edit genuinely imported owner-licensed video")
        self.assertEqual(result["status"], "max_turns_exhausted")
        self.assertIn("import_asset_from_path",
                      model.observed[2]["selectable_native_tools"])
        self.assertEqual(model.observed[2]["last_capability_search_result"]["origin"],
                         "host_attested_missing_native_asset")
        self.assertEqual(model.observed[2]["last_rejected_native_action_feedback"][
            "validation_keyword"], "native_asset_not_imported")
        self.assertEqual([name for name, _ in editor.calls if name in (
            "add_asset_to_timeline", "import_asset_from_path")],
            ["import_asset_from_path"])
        frontier = [x for x in result["events"]
                    if x.get("kind") == "host_native_asset_capability_frontier"]
        self.assertEqual(len(frontier), 1)
        self.assertEqual(frontier[0]["result_tool_names"],
                         ["import_asset_from_path"])
        self.assertTrue(audit_native_journal(result["events"],
                           host_tool_access=access)["journal_chain_structurally_valid"])
        forged = copy.deepcopy(result["events"])
        for x in forged:
            if x.get("kind") == "host_native_asset_capability_frontier":
                x["result_tool_names"] = ["ungranted_import"]
        with self.assertRaises(NativeJournalError):
            audit_native_journal(forged, host_tool_access=access)
        self.assertFalse(result["native_editing_capability_complete"])

    async def test_no_host_producer_effect_means_no_fake_remediation_tool(self):
        editor = HostObservedEmptyAssetSession()
        model = ScriptedModel([
            decision("search", query="add_asset_to_timeline"),
            decision("invoke", tool="add_asset_to_timeline",
                     inputs={"assetId": "not-imported", "previewOnly": False}),
        ])
        access = self.grants(editor)
        result = await NativeCreativeControl(
            editor, model, max_turns=2, catalog_mode="indexed",
            host_tool_access=access, host_possible_effects={}).run(
                "Only actually granted source actions")
        self.assertFalse(any(e.get("kind") == "host_native_asset_capability_frontier"
                             for e in result["events"]))
        self.assertTrue(audit_native_journal(result["events"],
                           host_tool_access=access)["journal_chain_structurally_valid"])
        self.assertEqual([name for name, _ in editor.calls if name ==
                          "add_asset_to_timeline"], [])


if __name__ == "__main__":
    unittest.main()

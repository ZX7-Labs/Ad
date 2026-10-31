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
        self.assertEqual(result["status"], "turn_budget_exhausted")
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

    async def test_real_empty_project_suggests_discoverable_producer_before_bad_placement(self):
        # The physical Qwen run #41204331429 never attempted placement, so
        # post-rejection hints alone cannot help that failure mode. A trusted
        # post-save project READ with 0 assets/0 clips can inform the model
        # without making any producer executable before explicit search.
        editor = HostObservedEmptyAssetSession()
        editor.tools.append(SimpleNamespace(
            name="save_project",
            description="Save existing project state; no media added",
            input_schema={"type": "object", "properties": {}}))
        model = ScriptedModel([
            decision("search", query="save_project"),
            decision("invoke", tool="save_project", inputs={}),
            decision("search", query="import_asset_from_path"),
        ])
        access = self.grants(editor)
        result = await NativeCreativeControl(
            editor, model, max_turns=3, catalog_mode="indexed",
            host_tool_access=access,
            host_possible_effects={
                "import_asset_from_path": ["project_asset_available"],
            }).run("Choose how to edit the owner's original video")
        self.assertEqual(result["status"], "turn_budget_exhausted")
        fact = model.observed[2]["host_observed_potential_asset_producers"]
        self.assertEqual(fact["tool_names_for_search_only"],
                         ["import_asset_from_path"])
        self.assertTrue(fact["host_did_not_choose_or_execute_an_edit"])
        self.assertEqual(fact["observed_native_asset_count"], 0)
        self.assertNotIn("import_asset_from_path",
                         model.observed[2]["selectable_native_tools"])
        self.assertNotIn("import_asset_from_path",
                         [name for name, _ in editor.calls])
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=access)[
                "journal_chain_structurally_valid"])

    async def test_empty_state_hint_does_not_invent_a_producer_or_grant(self):
        editor = HostObservedEmptyAssetSession()
        editor.tools.append(SimpleNamespace(
            name="save_project", description="Save project",
            input_schema={"type": "object", "properties": {}}))
        model = ScriptedModel([
            decision("search", query="save_project"),
            decision("invoke", tool="save_project", inputs={}),
            decision("search", query="timeline"),
        ])
        access = self.grants(editor)
        result = await NativeCreativeControl(
            editor, model, max_turns=3, catalog_mode="indexed",
            host_tool_access=access, host_possible_effects={}).run(
                "Original video and native editing")
        self.assertNotIn("host_observed_potential_asset_producers",
                         model.observed[2])
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=access)[
                "journal_chain_structurally_valid"])

    async def test_empty_native_export_rejected_before_stateful_rpc(self):
        # Actual Qwen run #41204331429 terminated after attempting to export
        # a zero-clip project. The pinned Velorn source has an explicit
        # checkExportReadiness no-visual-clip blocker before performAction.
        editor = HostObservedEmptyAssetSession()
        editor.tools.extend([
            SimpleNamespace(name="save_project", description="Save project",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="export_timeline",
                            description="Render current visual timeline",
                            input_schema={"type": "object", "properties": {}}),
        ])
        model = ScriptedModel([
            decision("search", query="save_project"),
            decision("invoke", tool="save_project", inputs={}),
            decision("search", query="export_timeline"),
            decision("invoke", tool="export_timeline", inputs={}),
            decision("search", query="import_asset_from_path"),
        ])
        access = self.grants(editor)
        outcome = await NativeCreativeControl(
            editor, model, max_turns=5, catalog_mode="indexed",
            host_tool_access=access,
            host_possible_effects={"import_asset_from_path": [
                "project_asset_available"]},
        ).run("Original native footage must be edited before export")
        self.assertEqual(outcome["status"], "turn_budget_exhausted")
        self.assertEqual(model.observed[4]["last_rejected_native_action_feedback"][
            "validation_keyword"], "native_export_no_timeline_clips")
        self.assertNotIn("export_timeline",
                         [name for name, _ in editor.calls])
        self.assertTrue(any(event.get("validation_keyword") ==
                            "native_export_no_timeline_clips"
                            for event in outcome["events"]))
        self.assertTrue(audit_native_journal(
            outcome["events"], host_tool_access=access)[
                "journal_chain_structurally_valid"])

    async def test_nonempty_native_export_still_uses_existing_host_authority(self):
        class PhysicalClipSession(HostObservedEmptyAssetSession):
            async def call_tool(self, name, arguments):
                result = await super().call_tool(name, arguments)
                if name == "get_project":
                    snapshot = json.loads(result.content[0].text)
                    snapshot["assetCount"] = 1
                    snapshot["currentTimeline"]["clipCount"] = 1
                    result.content[0].text = json.dumps(snapshot)
                return result
        editor = PhysicalClipSession()
        editor.tools.extend([
            SimpleNamespace(name="save_project", description="Save project",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="export_timeline",
                            description="Render current visual timeline",
                            input_schema={"type": "object", "properties": {}}),
        ])
        model = ScriptedModel([
            decision("search", query="save_project"),
            decision("invoke", tool="save_project", inputs={}),
            decision("search", query="export_timeline"),
            decision("invoke", tool="export_timeline", inputs={}),
        ])
        access = self.grants(editor)
        outcome = await NativeCreativeControl(
            editor, model, max_turns=4, catalog_mode="indexed",
            host_tool_access=access,
        ).run("Native editor export after actual content")
        self.assertEqual([name for name, _ in editor.calls
                          if name == "export_timeline"], ["export_timeline"])
        self.assertFalse(any(e.get("validation_keyword") ==
                             "native_export_no_timeline_clips"
                             for e in outcome["events"]))
        self.assertTrue(audit_native_journal(
            outcome["events"], host_tool_access=access)[
                "journal_chain_structurally_valid"])

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

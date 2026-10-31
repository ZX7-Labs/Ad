"""No creative-plan scripting: native ABI and observation safety regression.

Source-reviewed preview errors can recover, while a genuine committing write
failure still requires reconciliation. Every post-write project summary is
from an independently granted Velorn get_project read, not model text.
"""
import copy
import json
import unittest
from types import SimpleNamespace

from studio_next.native_state_evidence import (
    pinned_snapshot_summary, source_reviewed_preview_is_readonly)
from studio_next.native_creative_audit import audit_native_journal, NativeJournalError
from studio_next.native_creative_control import NativeCreativeControl
from studio_next.test_native_creative_control import (
    FakeSession, ScriptedModel, decision)


def native_snapshot(*, present=True, clips=0, assets=0):
    return {
        "mcp": {"hasProject": present},
        "project": {"name": "Original native project"} if present else None,
        "currentTimeline": ({
            "id": "actual-native-timeline", "clipCount": clips,
            "trackCount": 2, "transitionCount": 0,
        } if present else None),
        "timelineCount": 1 if present else 0,
        "assetCount": assets,
    }


class SourcePreviewContracts(unittest.TestCase):
    def test_only_source_attested_preview_semantics_admit_recovery(self):
        schema = {"type": "object", "properties": {
            "previewOnly": {"type": "boolean"}}}
        for name in ("add_asset_to_timeline", "add_assets_to_timeline",
                     "add_solid_color"):
            self.assertTrue(source_reviewed_preview_is_readonly(
                name, {}, schema))
            self.assertTrue(source_reviewed_preview_is_readonly(
                name, {"previewOnly": True}, schema))
            self.assertFalse(source_reviewed_preview_is_readonly(
                name, {"previewOnly": False}, schema))
        self.assertFalse(source_reviewed_preview_is_readonly(
            "add_timeline_markers", {"previewOnly": True}, schema))
        self.assertFalse(source_reviewed_preview_is_readonly(
            "add_asset_to_timeline", {}, {"type": "object", "properties": {}}))
        self.assertFalse(source_reviewed_preview_is_readonly(
            "add_asset_to_timeline", {"previewOnly": 1}, schema))

    def test_native_project_counts_require_consistent_project_and_safe_integers(self):
        expected = pinned_snapshot_summary(native_snapshot(clips=0, assets=0))
        self.assertEqual(expected["native_project_asset_count"], 0)
        self.assertEqual(expected["current_timeline_clip_count"], 0)
        self.assertTrue(expected["snapshot_may_lag_app_state"])
        self.assertFalse(expected["creative_content_or_export_quality_approved"])
        for invalid in (
            {}, {"mcp": {"hasProject": True}, "project": None,
                 "assetCount": 0, "timelineCount": 1},
            {**native_snapshot(), "assetCount": -1},
            {**native_snapshot(), "currentTimeline": {
                "clipCount": "one", "trackCount": 2, "transitionCount": 0}},
            {**native_snapshot(present=False), "project": {"name": "contradiction"}},
        ):
            self.assertIsNone(pinned_snapshot_summary(invalid))


class ActualNativeObservationSession(FakeSession):
    def __init__(self, *, preview_error=False, state_error=False):
        super().__init__()
        self.created = False
        self.preview_error = preview_error
        self.state_error = state_error
        self.tools.extend((
            SimpleNamespace(name="get_project",
                            description="Host native project read",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="create_project",
                            description="Create original native project",
                            input_schema={"type": "object", "properties": {
                                "name": {"type": "string"}}}),
            SimpleNamespace(name="add_timeline_markers",
                            description="Native markers (not image editing)",
                            input_schema={"type": "object", "properties": {
                                "markers": {"type": "array"}}}),
            SimpleNamespace(name="add_asset_to_timeline",
                            description="Preview or place source asset",
                            input_schema={"type": "object", "properties": {
                                "previewOnly": {"type": "boolean"},
                                "assetId": {"type": "string"}}}),
        ))

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "get_project":
            if self.state_error and self.created:
                return SimpleNamespace(is_error=True, content=[
                    SimpleNamespace(type="text", text="Native project read failed")])
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text",
                                text=json.dumps(native_snapshot(
                                    present=self.created, clips=0, assets=0)))])
        if name == "create_project":
            self.created = True
        if name == "add_asset_to_timeline" and self.preview_error:
            return SimpleNamespace(is_error=True, content=[
                SimpleNamespace(type="text",
                                text="Editor source asset not imported")])
        return SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps(
                {"success": True, "native_tool": name,
                 "result": {"action": name}}))])


class NativeLoopObservationTests(unittest.IsolatedAsyncioTestCase):
    def grants(self, session):
        return {item.name: ("read" if item.name.startswith("get_") or
                item.name.startswith("zx7_") else "write") for item in session.tools}

    async def test_true_empty_native_timeline_survives_noncreative_marker_write(self):
        session = ActualNativeObservationSession()
        model = ScriptedModel([
            decision("invoke", tool="create_project", inputs={"name": "Creative source"}),
            decision("invoke", tool="add_timeline_markers",
                     inputs={"markers": [{"label": "Progress"}]}),
            decision("finish", summary="No original footage and no final export"),
        ])
        grants = self.grants(session)
        result = await NativeCreativeControl(
            session, model, host_tool_access=grants,
            max_turns=3).run("Original footage scene, export and review")
        self.assertEqual(result["status"], "model_finished_unverified")
        self.assertEqual(len([name for name, _ in session.calls
                              if name == "get_project"]), 3)
        for turn in (1, 2):
            facts = model.observed[turn][
                "latest_host_attested_native_project_progress"]
            self.assertEqual(facts["native_project_asset_count"], 0)
            self.assertEqual(facts["current_timeline_clip_count"], 0)
        self.assertEqual(model.observed[2]["last_native_result_texts"][0] and
                         json.loads(model.observed[2][
                             "last_native_result_texts"][0])["native_tool"],
                         "add_timeline_markers")
        self.assertTrue(audit_native_journal(result["events"],
                                             host_tool_access=grants)[
                                             "journal_chain_structurally_valid"])
        altered = copy.deepcopy(result["events"])
        for event in altered:
            if event.get("kind") == "host_native_state_progress_observation":
                event["host_attested_read_only"] = False
                break
        with self.assertRaises(NativeJournalError):
            audit_native_journal(altered, host_tool_access=grants)

    async def test_preview_error_does_not_become_uncertain_creative_write(self):
        session = ActualNativeObservationSession(preview_error=True)
        model = ScriptedModel([
            decision("invoke", tool="add_asset_to_timeline", inputs={
                "assetId": "not-imported", "previewOnly": True}),
            decision("finish", summary="Preview was refused; no mutation"),
        ])
        grants = self.grants(session)
        result = await NativeCreativeControl(
            session, model, host_tool_access=grants,
            max_turns=2).run("Preview imported original asset")
        self.assertEqual(result["status"], "model_finished_unverified")
        self.assertEqual(model.observed[1][
            "last_rejected_native_action_feedback"][
            "validation_keyword"], "source_reviewed_readonly_preview_error")
        self.assertTrue(any(e["kind"] == "native_source_preview_reported_error"
                            for e in result["events"]))
        self.assertFalse(any(e["kind"] == "native_tool_result" for e in result["events"]))
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=grants)[
            "journal_chain_structurally_valid"])

    async def test_committing_error_stays_terminal_even_if_same_tool(self):
        session = ActualNativeObservationSession(preview_error=True)
        model = ScriptedModel([decision("invoke",
            tool="add_asset_to_timeline", inputs={
                "assetId": "not-imported", "previewOnly": False})])
        result = await NativeCreativeControl(
            session, model, host_tool_access=self.grants(session),
            max_turns=1).run("Try actual edit")
        self.assertEqual(result["status"],
                         "native_error_requires_state_reconciliation")
        self.assertTrue(any(e["kind"] == "native_tool_reported_error"
                            for e in result["events"]))

    async def test_bad_post_write_native_state_cannot_claim_fake_progress(self):
        session = ActualNativeObservationSession(state_error=True)
        model = ScriptedModel([
            decision("invoke", tool="create_project", inputs={"name": "Original"}),
            decision("finish", summary="Cannot prove assets"),
        ])
        grants = self.grants(session)
        result = await NativeCreativeControl(session, model,
            host_tool_access=grants, max_turns=2).run("Observe native project")
        self.assertIsNone(model.observed[1][
            "latest_host_attested_native_project_progress"])
        self.assertTrue(any(e["kind"] == "host_native_state_progress_read_error"
                            for e in result["events"]))
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=grants)[
            "journal_chain_structurally_valid"])


if __name__ == "__main__":
    unittest.main()

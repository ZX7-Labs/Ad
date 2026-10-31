"""No creative-plan scripting: native ABI and observation safety regression.

Source-reviewed preview errors can recover, while a genuine committing write
failure still requires reconciliation. Every post-write project summary is
from an independently granted Velorn get_project read, not model text.
"""
import copy
import json
from pathlib import Path
import unittest
from types import SimpleNamespace

from studio_next.native_state_evidence import (
    pinned_snapshot_summary, source_reviewed_preview_is_readonly,
    pinned_direct_native_plan_preview, contradictory_nested_write_receipt,
    _PINNED_NO_IMAGE_SEQUENCE_ERROR,
    pinned_forced_image_sequence_absent_error,
    pinned_transition_missing_clips_prewrite_error,
    _PINNED_TRANSITION_CLIPS_ABSENT_ERROR)
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
                     "add_solid_color", "add_adjustment_clip"):
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

    def test_direct_pinned_plan_preview_requires_full_source_attestation(self):
        import copy
        schema = {"type": "object", "properties": {
            "previewOnly": {"type": "boolean"}}}
        for tool in ("add_asset_to_timeline", "add_assets_to_timeline",
                     "add_solid_color", "add_adjustment_clip"):
            with self.subTest(tool=tool):
                receipt = {
                    "previewOnly": True, "action": tool,
                    "plan": {"previewOnly": True, "action": tool},
                    "suggestedApplyCall": {
                        "tool": tool, "arguments": {"previewOnly": False}},
                }
                self.assertTrue(pinned_direct_native_plan_preview(
                    tool, {}, schema, receipt))
                self.assertTrue(pinned_direct_native_plan_preview(
                    tool, {"previewOnly": True}, schema, receipt))
                self.assertFalse(pinned_direct_native_plan_preview(
                    tool, {"previewOnly": False}, schema, receipt))
                self.assertFalse(pinned_direct_native_plan_preview(
                    tool, {}, {"type": "object", "properties": {}}, receipt))
                self.assertFalse(pinned_direct_native_plan_preview(
                    "delete_clips", {}, schema, receipt))
                mutations = (
                    ("success", True), ("success", False),
                    ("result", {"action": tool, "previewOnly": True}),
                    ("previewOnly", False), ("previewOnly", "true"),
                    ("action", "delete_clips"), ("plan", {}),
                    ("plan", {"action": tool, "previewOnly": False}),
                    ("plan", {"action": "delete_clips", "previewOnly": True}),
                    ("suggestedApplyCall", None),
                    ("suggestedApplyCall", {
                        "tool": "delete_clips", "arguments": {"previewOnly": False}}),
                    ("suggestedApplyCall", {
                        "tool": tool, "arguments": {"previewOnly": True}}),
                    ("error", "maybe wrote"),
                )
                for field, altered in mutations:
                    with self.subTest(field=field, altered=repr(altered)):
                        forged = copy.deepcopy(receipt)
                        forged[field] = altered
                        self.assertFalse(pinned_direct_native_plan_preview(
                            tool, {}, schema, forged))

    def test_pinned_native_editor_source_guarantees_preview_never_performs_action(self):
        # This safety exception may NOT silently survive a third-party editor
        # update that changes preview behavior. Inspect the actual vendored
        # pinned source, not a hypothetical mocked helper.
        source = (Path(__file__).resolve().parents[1] /
                  "third_party/velorn/electron/mcpServer.js")
        text = source.read_text(encoding="utf-8")
        functions = {
            "add_asset_to_timeline": ("addAssetToTimeline", "replaceClipWithAsset"),
            "add_assets_to_timeline": ("addAssetsToTimeline", "addAdjustmentClip"),
            "add_solid_color": ("addSolidColor", "addAssetsToTimeline"),
            "add_adjustment_clip": ("addAdjustmentClip", "duplicateClip"),
        }
        for name, (start, end) in functions.items():
            with self.subTest(name=name):
                definition = "async " + start + "("
                left = text.index(definition)
                right = text.index("async " + end + "(", left + len(definition))
                function = text[left:right]
                planning_failure = function.index("if (plan.error) return errorResult(plan.error)")
                preview_guard = function.index("if (args.previewOnly !== false) {")
                native_mutation = function.index("await this.performAction({")
                self.assertLess(planning_failure, preview_guard)
                self.assertLess(preview_guard, native_mutation)
                self.assertIn("return textResult({", function[preview_guard:native_mutation])
                self.assertIn("previewOnly: true", function[preview_guard:native_mutation])

    def test_exact_source_image_sequence_failure_is_nonmutating(self):
        source = Path(__file__).resolve().parents[1] / "third_party/velorn"
        renderer_source = (source / "src/services/mcpActions.js").read_text(
            encoding="utf-8")
        native_server = (source / "electron/mcpServer.js").read_text(
            encoding="utf-8")
        method_start = renderer_source.index(
            "async function handleImportAssetFromPath(")
        method_end = renderer_source.index(
            "async function handleRelinkAsset(", method_start)
        method = renderer_source[method_start:method_end]
        # Must verify *real pinned source* rather than trusting the local
        # safety exception's description. A future editor change fails tests.
        literal = _PINNED_NO_IMAGE_SEQUENCE_ERROR.removeprefix(
            "import_asset_from_path failed: ")
        self.assertIn("throw new Error('" + literal + "')", method)
        self.assertLess(
            method.index("throw new Error('" + literal + "')"),
            method.index("const imported = "))
        self.assertIn(
            "return errorResult(`${suggestedTool} failed: ${error?.message || String(error)}`)",
            native_server)
        self.assertIn(
            "this.runRendererActionTool('import_asset_from_path', args",
            native_server)

    def test_transition_missing_clips_error_is_exact_source_proven_no_write(self):
        source = (Path(__file__).resolve().parents[1] /
                  "third_party/velorn/electron/mcpServer.js")
        text = source.read_text(encoding="utf-8")
        first = text.index("async addTransition(")
        last = text.index("async updateTransition(", first)
        method = text[first:last]
        source_error = _PINNED_TRANSITION_CLIPS_ABSENT_ERROR
        self.assertIn("return errorResult('" + source_error + "')", method)
        self.assertLess(method.index("return errorResult('" + source_error + "')"),
                        method.index("await this.performAction({"))
        self.assertIn("case 'add_transition':", text)
        self.assertIn("return this.addTransition(snapshot, args)", text)
        def result(messages, error=True):
            return SimpleNamespace(is_error=error, content=[
                SimpleNamespace(type="text", text=message) for message in messages])
        exact = result([source_error])
        self.assertTrue(pinned_transition_missing_clips_prewrite_error(
            "add_transition", exact))
        for bad in (
            ("export_timeline", exact),
            ("add_transition", result([source_error], error=False)),
            ("add_transition", result([source_error, source_error])),
            ("add_transition", result(["Error: " + source_error])),
            ("add_transition", result(["Could not add transition"])),
        ):
            with self.subTest(case=bad[0], receipt=str(bad[1].content)[:90]):
                self.assertFalse(pinned_transition_missing_clips_prewrite_error(*bad))

    def test_only_exact_error_content_is_recoverable(self):
        value = _PINNED_NO_IMAGE_SEQUENCE_ERROR
        def reply(*messages, error=True):
            return SimpleNamespace(is_error=error, content=[
                SimpleNamespace(type="text", text=m) for m in messages])
        self.assertTrue(pinned_forced_image_sequence_absent_error(
            "import_asset_from_path", reply(value)))
        for name, candidate in (
            ("export_timeline", reply(value)),
            ("import_asset_from_path", reply(value, value)),
            ("import_asset_from_path", reply(value, error=False)),
            ("import_asset_from_path", reply("Error: " + value)),
            ("import_asset_from_path", reply("import_asset_from_path failed: disk full")),
        ):
            with self.subTest(tool=name):
                self.assertFalse(pinned_forced_image_sequence_absent_error(
                    name, candidate))

    def test_nested_native_renderer_ack_requires_explicit_boolean_truth(self):
        for invalid in (
            {"success": False}, {"success": 0}, {"success": "yes"},
            {"success": None}, {"success": True, "error": "failure"},
        ):
            with self.subTest(invalid=invalid):
                self.assertTrue(contradictory_nested_write_receipt(invalid))
        for valid in (None, {}, {"success": True},
                      {"success": True, "error": None}):
            with self.subTest(valid=valid):
                self.assertFalse(contradictory_nested_write_receipt(valid))

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
    def __init__(self, *, preview_error=False, state_error=False, nested_failure=False,
                 state_changes_on_third_read=False):
        super().__init__()
        self.created = False
        self.preview_error = preview_error
        self.state_error = state_error
        self.nested_failure = nested_failure
        self.state_changes_on_third_read = state_changes_on_third_read
        self.project_reads = 0
        self.tools.extend((
            SimpleNamespace(name="get_project",
                            description="Host native project read",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="create_project",
                            description="Create original native project",
                            input_schema={"type": "object", "properties": {
                                "name": {"type": "string"}}}),
            SimpleNamespace(name="save_project",
                            description="Save native project metadata",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="add_asset_to_timeline",
                            description="Preview or place source asset",
                            input_schema={"type": "object", "properties": {
                                "previewOnly": {"type": "boolean"},
                                "assetId": {"type": "string"}}}),
        ))

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "get_project":
            self.project_reads += 1
            if self.state_error and self.created:
                return SimpleNamespace(is_error=True, content=[
                    SimpleNamespace(type="text", text="Native project read failed")])
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text",
                                text=json.dumps(native_snapshot(
                                    present=self.created,
                                    clips=(2 if self.created and
                                           self.state_changes_on_third_read and
                                           self.project_reads >= 3 else 0),
                                    assets=0)))])
        if name == "create_project":
            self.created = True
        if name == "add_asset_to_timeline" and self.preview_error:
            return SimpleNamespace(is_error=True, content=[
                SimpleNamespace(type="text",
                                text="Editor source asset not imported")])
        if name == "add_asset_to_timeline" and self.nested_failure:
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text=json.dumps({
                    "success": True, "action": name,
                    "result": {"success": False, "error": "Renderer rejected write"}}))])
        return SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps(
                {"success": True, "native_tool": name,
                 "result": {"action": name}}))])


class NativeLoopObservationTests(unittest.IsolatedAsyncioTestCase):
    def grants(self, session):
        return {item.name: ("read" if item.name.startswith("get_") or
                item.name.startswith("zx7_") else "write") for item in session.tools}

    async def test_true_empty_native_timeline_survives_noncreative_project_save(self):
        session = ActualNativeObservationSession()
        model = ScriptedModel([
            decision("invoke", tool="create_project", inputs={"name": "Creative source"}),
            decision("invoke", tool="save_project", inputs={}),
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
            self.assertEqual(model.observed[turn][
                "native_project_presence_from_last_inspection"], "present")
            self.assertEqual(facts["native_project_asset_count"], 0)
            self.assertEqual(facts["current_timeline_clip_count"], 0)
        self.assertEqual(model.observed[2]["last_native_result_texts"][0] and
                         json.loads(model.observed[2][
                             "last_native_result_texts"][0])["native_tool"],
                         "save_project")
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

    async def test_newer_direct_project_read_supersedes_stale_post_write_facts(self):
        session = ActualNativeObservationSession(
            state_changes_on_third_read=True)
        model = ScriptedModel([
            decision("invoke", tool="create_project", inputs={"name": "Original"}),
            decision("invoke", tool="get_project", inputs={}),
            decision("finish", summary="A later project read superseded cached counts"),
        ])
        grants = self.grants(session)
        result = await NativeCreativeControl(
            session, model, host_tool_access=grants,
            max_turns=3).run("Independently inspect native project progress")
        self.assertEqual(model.observed[1][
            "latest_host_attested_native_project_progress"][
            "current_timeline_clip_count"], 0)
        self.assertEqual(model.observed[2][
            "latest_host_attested_native_project_progress"][
            "current_timeline_clip_count"], 2)
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=grants)[
            "journal_chain_structurally_valid"])

    async def test_real_2b_invalid_transition_ids_recover_without_write_replay(self):
        # Actual 2B run #41219493015 invented two native clip IDs and
        # received the pinned, pre-write missing-clip error. The creator must
        # be free to inspect real clips instead of ending the job uncertain.
        class PinnedTransitionSession(FakeSession):
            def __init__(self, response=None):
                super().__init__()
                self.response = response or _PINNED_TRANSITION_CLIPS_ABSENT_ERROR
                self.tools.append(SimpleNamespace(
                    name="add_transition", description="Native between-clip edit",
                    input_schema={"type": "object", "properties": {
                        "clipAId": {"type": "string"},
                        "clipBId": {"type": "string"},
                        "previewOnly": {"type": "boolean"}}}))
            async def call_tool(self, name, arguments):
                if name == "add_transition":
                    self.calls.append((name, arguments))
                    return SimpleNamespace(is_error=True, content=[
                        SimpleNamespace(type="text", text=self.response)])
                return await super().call_tool(name, arguments)
        invalid = {"clipAId": "invented-clip-0",
                   "clipBId": "invented-clip-1", "previewOnly": False}
        model = ScriptedModel([
            decision("invoke", tool="add_transition", inputs=invalid),
            decision("finish", summary="I must inspect real clips before editing"),
        ])
        session = PinnedTransitionSession()
        grants = {t.name: ("write" if t.name in (
            "add_transition", "update_text_clip") else "read")
            for t in session.tools}
        outcome = await NativeCreativeControl(
            session, model, host_tool_access=grants, max_turns=2).run(
                "Build an editable original movie")
        self.assertEqual(outcome["status"], "model_finished_unverified")
        self.assertEqual(model.observed[1]["last_rejected_native_action_feedback"][
            "validation_keyword"], "native_transition_clip_identity_absent")
        self.assertTrue(model.observed[1]["last_rejected_native_action_feedback"][
            "no_native_write_acknowledged"])
        self.assertTrue(any(e.get("kind") ==
                            "native_source_pretransition_reported_error"
                            for e in outcome["events"]))
        self.assertFalse(any(e.get("kind") == "native_tool_result" and
                             e.get("tool") == "add_transition"
                             for e in outcome["events"]))
        self.assertTrue(audit_native_journal(
            outcome["events"], host_tool_access=grants)[
                "journal_chain_structurally_valid"])
        forged = copy.deepcopy(outcome["events"])
        for event in forged:
            if event.get("kind") == "native_source_pretransition_reported_error":
                event["error_sha256"] = "f" * 64
                break
        with self.assertRaises(NativeJournalError):
            audit_native_journal(forged, host_tool_access=grants)

        bad = PinnedTransitionSession("Unrelated transition could have written")
        wrong = await NativeCreativeControl(
            bad, ScriptedModel([
                decision("invoke", tool="add_transition", inputs=invalid)
            ]), host_tool_access=grants, max_turns=1).run(
                "Do not forgive unrelated native write errors")
        self.assertEqual(wrong["status"],
                         "native_error_requires_state_reconciliation")
        self.assertEqual(wrong["events"][-1]["kind"],
                         "native_tool_reported_error")

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

    async def test_outer_success_inner_renderer_failure_cannot_mint_write_proof(self):
        session = ActualNativeObservationSession(nested_failure=True)
        model = ScriptedModel([decision("invoke",
            tool="add_asset_to_timeline", inputs={
                "assetId": "model-selected", "previewOnly": False})])
        grants = self.grants(session)
        result = await NativeCreativeControl(
            session, model, host_tool_access=grants,
            max_turns=1).run("Attempt native write")
        self.assertEqual(result["status"],
                         "native_error_requires_state_reconciliation")
        self.assertTrue(any(e["kind"] == "native_tool_uncertain_outcome"
                            for e in result["events"]))
        self.assertFalse(any(e["kind"] == "native_tool_result"
                             for e in result["events"]))
        self.assertTrue(audit_native_journal(result["events"],
                                             host_tool_access=grants)[
                                             "journal_chain_structurally_valid"])

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
        self.assertEqual(model.observed[1][
            "native_project_presence_from_last_inspection"], "unknown")
        self.assertTrue(any(e["kind"] == "host_native_state_progress_read_error"
                            for e in result["events"]))
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=grants)[
            "journal_chain_structurally_valid"])


if __name__ == "__main__":
    unittest.main()

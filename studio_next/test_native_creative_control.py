"""Host-bound tests for the model-to-real-editor decision protocol.

Scripted fake decisions here test *safety and sequencing* only: they are NOT
evidence of original creativity, live neural inference or a finished movie.
"""
import asyncio
import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from studio_next.native_creative_control import (
    NativeCreativeControl, NativeCreativeControlError,
)


class ScriptedModel:
    settings = SimpleNamespace(model_id="scripted-fixture-NOT-A-REAL-MODEL")

    def __init__(self, actions):
        self.actions = iter(actions)
        self.observed = []
        self.images_observed = []

    def decide(self, context):
        self.observed.append(context)
        return next(self.actions)

    def decide_with_images(self, context, images):
        self.images_observed.append((context, images))
        return next(self.actions)


def decision(action, **arguments):
    return {"action": action, "arguments": arguments, "reason": "chosen by test stub"}


class FakeSession:
    def __init__(self):
        self.tools = [SimpleNamespace(
            name="get_timeline", description="Read the real native project",
            input_schema={"type": "object", "properties": {"includeClips": {"type": "boolean"}}}),
            SimpleNamespace(name="update_text_clip", description="Edit native text",
                            input_schema={"type": "object", "properties": {
                                "clipId": {"type": "string"}, "text": {"type": "string"}}}),
            SimpleNamespace(name="zx7_verify_native_export", description="Independently verify final movie",
                            input_schema={"type": "object"}),
            SimpleNamespace(name="zx7_observe_verified_export_frame", description="Read verified PNG",
                            input_schema={"type": "object", "properties": {
                                "path": {"type": "string"},
                                "at_seconds": {"type": "number"}}})]
        self.calls = []
        self.raise_on_call = None
        self.custom_response = None

    async def list_tools(self):
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.raise_on_call is not None:
            raise self.raise_on_call
        if name == "zx7_verify_native_export":
            return SimpleNamespace(is_error=False, content=[SimpleNamespace(
                type="text", text=json.dumps({"physical_export_verified": True,
                     "native_export_sha256": "a"*64, "artistic_quality_approved": False}))])
        if self.custom_response is not None:
            return self.custom_response
        return SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps({
                "success": True, "native_tool": name, "editable": True}))])


class NativeCreativeControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_host_required_evidence_refuses_false_finish_and_allows_independent_correction(self):
        from studio_next.native_creative_audit import audit_native_journal
        session = FakeSession()
        grants = {tool.name: ("write" if tool.name == "update_text_clip" else "read")
                  for tool in session.tools}
        model = ScriptedModel([
            decision("finish", summary="Unjustified complete"),
            decision("invoke", tool="update_text_clip", inputs={"clipId": "one", "text": "New"}),
            decision("finish", summary="Still no export proof"),
            decision("invoke", tool="zx7_verify_native_export", inputs={}),
            decision("finish", summary="Only technical evidence is present"),
        ])
        required = ("native_write_acknowledged", "physical_export_verified")
        result = await NativeCreativeControl(
            session, model, host_tool_access=grants,
            required_evidence=required, max_turns=5).run("Make an editable original video")
        self.assertEqual(result["status"], "model_finished_unverified")
        rejected = [e for e in result["events"] if e["kind"] == "model_finish_rejected"]
        self.assertEqual(len(rejected), 2)
        self.assertEqual(rejected[0]["missing_completion_evidence"], sorted(required))
        self.assertEqual(rejected[1]["missing_completion_evidence"], ["physical_export_verified"])
        self.assertEqual([name for name, _ in session.calls],
                         ["update_text_clip", "zx7_verify_native_export"])
        self.assertEqual(model.observed[1]["missing_completion_evidence"], sorted(required))
        self.assertEqual(model.observed[3]["missing_completion_evidence"],
                         ["physical_export_verified"])
        self.assertEqual(model.observed[4]["missing_completion_evidence"], [])
        for index in range(4):
            self.assertNotIn("finish", model.observed[index]["available_actions"])
        self.assertIn("finish", model.observed[4]["available_actions"])
        self.assertTrue(audit_native_journal(result["events"],
                                             host_tool_access=grants)["journal_chain_structurally_valid"])
        self.assertFalse(result["native_editing_capability_complete"])

    async def test_stale_export_cannot_certify_a_later_native_edit(self):
        from studio_next.native_creative_audit import audit_native_journal
        png = b"\x89PNG\r\n\x1a\n" + b"bounded-fixture"
        png_hash = hashlib.sha256(png).hexdigest()
        class FrameSession(FakeSession):
            async def call_tool(self, name, arguments):
                if name == "zx7_observe_verified_export_frame":
                    self.calls.append((name, arguments))
                    return SimpleNamespace(is_error=False, content=[
                        SimpleNamespace(type="text", text=json.dumps({
                            "export_sha256": "a" * 64,
                            "png_sha256": png_hash})),
                        SimpleNamespace(type="image", mime_type="image/png",
                            data=base64.b64encode(png).decode())])
                return await super().call_tool(name, arguments)
        session = FrameSession()
        grants = {tool.name: ("write" if tool.name == "update_text_clip" else "read")
                  for tool in session.tools}
        model = ScriptedModel([
            decision("invoke", tool="update_text_clip", inputs={"clipId": "one"}),
            decision("invoke", tool="zx7_verify_native_export", inputs={}),
            decision("invoke", tool="zx7_observe_verified_export_frame", inputs={}),
            decision("finish", summary="Premature: I only observed the first export"),
            decision("invoke", tool="update_text_clip", inputs={"clipId": "one", "text": "new"}),
            decision("finish", summary="The frame was from before my latest edit"),
            decision("invoke", tool="zx7_verify_native_export", inputs={}),
            decision("invoke", tool="zx7_observe_verified_export_frame", inputs={}),
            decision("finish", summary="New verified source; still not artistic acceptance"),
        ])
        required = ("native_write_acknowledged", "physical_export_verified",
                    "post_observation_native_write_acknowledged",
                    "verified_export_frame_observed")
        result = await NativeCreativeControl(
            session, model, max_turns=9, host_tool_access=grants,
            required_evidence=required,
            host_content_revision_tools=("update_text_clip",)).run("Independent editable video")
        self.assertEqual(result["status"], "model_finished_unverified")
        refused = [e for e in result["events"] if e["kind"] == "model_finish_rejected"]
        self.assertEqual(len(refused), 2)
        self.assertEqual(refused[0]["missing_completion_evidence"], [
            "post_observation_native_write_acknowledged"])
        self.assertEqual(refused[1]["missing_completion_evidence"], [
            "physical_export_verified", "verified_export_frame_observed"])
        self.assertEqual(model.images_observed[0][0]["missing_completion_evidence"], [
            "post_observation_native_write_acknowledged"])
        self.assertEqual(model.observed[4]["missing_completion_evidence"], [
            "physical_export_verified", "verified_export_frame_observed"])
        self.assertEqual(model.images_observed[1][0]["missing_completion_evidence"], [])
        audited = audit_native_journal(
            result["events"], host_tool_access=grants,
            expected_required_evidence=required,
            host_content_revision_tools=("update_text_clip",))
        self.assertTrue(audited["host_completion_policy_independently_matched"])
        self.assertEqual(sum(e["kind"] == "native_tool_result" and
                             e.get("independently_verified_export_sha256") is not None
                             for e in result["events"]), 2)
        self.assertFalse(result["native_editing_capability_complete"])

    async def test_impossible_host_evidence_contract_fails_before_neural_inference(self):
        session = FakeSession()
        grants = {tool.name: "read" for tool in session.tools}
        model = ScriptedModel([decision("finish", summary="Wrongly finished")])
        with self.assertRaisesRegex(NativeCreativeControlError,
                                    "unsupported by granted native tools"):
            await NativeCreativeControl(
                session, model, host_tool_access=grants,
                required_evidence=("native_write_acknowledged",)).run("Original film")
        self.assertEqual(model.observed, [])
        self.assertEqual(session.calls, [])

        no_verifier = FakeSession()
        no_verifier.tools = [tool for tool in no_verifier.tools
                             if tool.name != "zx7_verify_native_export"]
        access = {tool.name: ("write" if tool.name == "update_text_clip" else "read")
                  for tool in no_verifier.tools}
        with self.assertRaisesRegex(NativeCreativeControlError,
                                    "unsupported by granted native tools"):
            await NativeCreativeControl(
                no_verifier, model, host_tool_access=access,
                required_evidence=("verified_export_frame_observed",)).run("Original film")
        self.assertEqual(no_verifier.calls, [])
        self.assertEqual(model.observed, [])

    async def test_unmet_required_evidence_cannot_be_faked_by_finish_or_bad_host_contract(self):
        session = FakeSession()
        grants = {tool.name: "read" for tool in session.tools}
        model = ScriptedModel([decision("finish", summary="False success")])
        result = await NativeCreativeControl(
            session, model, host_tool_access=grants, max_turns=1,
            required_evidence=("verified_export_frame_observed",)).run("A video")
        self.assertEqual(result["status"], "turn_budget_exhausted")
        self.assertEqual(session.calls, [])
        self.assertEqual(result["events"][-1]["kind"], "model_finish_rejected")
        with self.assertRaisesRegex(NativeCreativeControlError, "trusted host requirement"):
            NativeCreativeControl(session, model,
                                  required_evidence=("physical_export_verified",))
        with self.assertRaisesRegex(NativeCreativeControlError, "trusted host requirement"):
            NativeCreativeControl(session, model, host_tool_access=grants,
                                  required_evidence=("invented_model_claim",))

    async def test_actual_native_model_sees_and_calls_granted_tool_on_late_mcp_page(self):
        class VersionedEditor(FakeSession):
            async def list_tools(self, *, cursor=None):
                if cursor is None:
                    return {"jsonrpc": "2.0", "id": 1, "result": {
                        "resultType": "complete",
                        "tools": self.tools[:2], "nextCursor": "opaque-late-page"}}
                if cursor == "opaque-late-page":
                    return SimpleNamespace(result={
                        "resultType": "complete",
                        "tools": self.tools[2:]})
                raise AssertionError("Unexpected or fabricated MCP cursor")

        session = VersionedEditor()
        session.tools.append(SimpleNamespace(
            name="custom_native_glow", description="Apply specialized native glow",
            input_schema={"type": "object", "properties": {
                "intensity": {"type": "number"}}, "required": ["intensity"]}))
        grants = {tool.name: ("read" if tool.name == "get_timeline" else "write")
                  for tool in session.tools}
        model = ScriptedModel([
            decision("search", query="specialized glow"),
            decision("describe", tool="custom_native_glow"),
            decision("invoke", tool="custom_native_glow", inputs={"intensity": 0.42}),
            decision("finish", summary="Native host reported a tool result, not artistic approval"),
        ])
        outcome = await NativeCreativeControl(
            session, model, max_turns=4, host_tool_access=grants,
            catalog_mode="indexed").run("Create an original look in the native video editor")
        self.assertEqual(outcome["status"], "model_finished_unverified")
        self.assertEqual(session.calls, [("custom_native_glow", {"intensity": 0.42})])
        self.assertEqual(model.observed[0]["actual_granted_native_tools"], [])
        self.assertEqual(model.observed[0]["available_actions"],
                         ["search", "finish"])
        self.assertEqual(model.observed[0]["capability_overview"]["operation_count"],
                         len(session.tools))
        self.assertEqual(model.observed[1]["last_capability_search_result"]["matches"][0]
                         ["tool"], "custom_native_glow")
        self.assertEqual(model.observed[1]["available_actions"],
                         ["search", "describe", "invoke", "finish"])
        self.assertFalse(outcome["native_editing_capability_complete"])

    async def test_indexed_search_with_no_matches_advertises_no_unselectable_native_action(self):
        session = FakeSession()
        grants = {tool.name: "read" for tool in session.tools}
        model = ScriptedModel([
            decision("search", query="this_capability_has_no_matching_identity_9999"),
            decision("finish", summary="Search returned no applicable editing operation"),
        ])
        outcome = await NativeCreativeControl(
            session, model, host_tool_access=grants, catalog_mode="indexed",
            max_turns=2).run("Look for a specific original native video edit capability")
        self.assertEqual(model.observed[0]["available_actions"], ["search", "finish"])
        self.assertEqual(model.observed[1]["available_actions"], ["search", "finish"])
        self.assertEqual(model.observed[1]["selectable_native_tools"], [])
        self.assertEqual(session.calls, [])
        self.assertEqual(outcome["status"], "model_finished_unverified")
        self.assertFalse(outcome["native_editing_capability_complete"])

    async def test_compact_model_does_not_waste_turns_on_unavailable_discover(self):
        session = FakeSession()
        grants = {tool.name: "read" for tool in session.tools}
        model = ScriptedModel([decision("discover")])
        with self.assertRaisesRegex(NativeCreativeControlError,
                                    "unavailable catalog action"):
            await NativeCreativeControl(
                session, model, host_tool_access=grants, catalog_mode="indexed",
                max_turns=1).run("A native film with searchable editor tools")
        self.assertEqual(session.calls, [])
        self.assertEqual(model.observed[0]["available_actions"],
                         ["search", "finish"])

    async def test_native_model_rejects_incomplete_paged_tool_list_before_inference(self):
        class PartialEditor(FakeSession):
            async def list_tools(self, *, cursor=None):
                if cursor is None:
                    return SimpleNamespace(tools=self.tools[:2],
                                           nextCursor="opaque-pagination")
                return {"result": {"resultType": "input_required",
                                   "tools": self.tools[2:]}}
        session = PartialEditor()
        model = ScriptedModel([decision("finish", summary="Not an actual edit")])
        with self.assertRaisesRegex(ValueError, "not complete"):
            await NativeCreativeControl(
                session, model, max_turns=1).run("Inspect a real native project")
        self.assertEqual(session.calls, [])
        self.assertEqual(model.observed, [])

    async def test_model_decides_actions_no_fixed_edit_sequence_and_no_completion_claim(self):
        model = ScriptedModel([
            decision("discover"),
            decision("describe", tool="update_text_clip"),
            decision("invoke", tool="get_timeline", inputs={"includeClips": True}),
            decision("invoke", tool="update_text_clip", inputs={"clipId": "title-1", "text": "ORIGINAL"}),
            decision("finish", summary="Edited the existing native project; not independently approved"),
        ])
        session = FakeSession()
        with tempfile.TemporaryDirectory() as root:
            receipt = Path(root) / "private-events.jsonl"
            result = await NativeCreativeControl(session, model, max_turns=8,
                                                  receipt_path=receipt).run("Make a distinctive edit")
            self.assertEqual(result["status"], "model_finished_unverified")
            self.assertFalse(result["native_editing_capability_complete"])
            self.assertFalse(result["artistic_quality_independently_approved"])
            self.assertEqual([name for name, _ in session.calls], ["get_timeline", "update_text_clip"])
            self.assertEqual(session.calls[-1][1]["text"], "ORIGINAL")
            journal = [json.loads(line) for line in receipt.read_text().splitlines()]
            self.assertEqual(journal, result["events"])
            self.assertEqual([x["sequence"] for x in journal], list(range(len(journal))))
            self.assertEqual(len([x for x in journal if x["kind"] == "native_tool_submitted"]), 2)
            self.assertNotIn("Make a distinctive edit", receipt.read_text())
            self.assertNotIn("ORIGINAL", receipt.read_text())
            self.assertEqual(model.observed[-1]["last_native_result_texts"][0].count('"editable"'), 1)

    async def test_ungranted_tool_never_calls_native_editor(self):
        model = ScriptedModel([decision("invoke", tool="not-granted", inputs={})])
        session = FakeSession()
        with self.assertRaisesRegex(NativeCreativeControlError, "ungranted"):
            await NativeCreativeControl(session, model).run("A source-owned project")
        self.assertEqual(session.calls, [])

    async def test_invalid_action_and_budget_fail_closed(self):
        invalid = [
            {"action": "invoke", "arguments": {"tool": "get_timeline"}, "reason": ""},
            {"action": "install", "arguments": {}, "reason": "do bad thing"},
            {"action": "finish", "arguments": {}, "reason": "premature"},
        ]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(NativeCreativeControlError):
                await NativeCreativeControl(FakeSession(), ScriptedModel([item])).run("A video")
        outcome = await NativeCreativeControl(FakeSession(),
                    ScriptedModel([decision("discover")]), max_turns=1).run("A film")
        self.assertEqual(outcome["status"], "turn_budget_exhausted")
        self.assertFalse(outcome["native_editing_capability_complete"])

    async def test_uncertain_write_is_recorded_before_failure_no_automatic_replay(self):
        model = ScriptedModel([decision("invoke", tool="update_text_clip",
                                        inputs={"clipId": "title-1", "text": "change"})])
        session = FakeSession()
        session.raise_on_call = TimeoutError("Remote write outcome is unknown")
        with tempfile.TemporaryDirectory() as root:
            receipt = Path(root) / "private.jsonl"
            with self.assertRaises(TimeoutError):
                await NativeCreativeControl(session, model, receipt_path=receipt).run("A film")
            events = [json.loads(line) for line in receipt.read_text().splitlines()]
            self.assertEqual(events[-2]["kind"], "native_tool_submitted")
            self.assertEqual(events[-1]["kind"], "native_tool_uncertain_outcome")
            self.assertEqual(len(session.calls), 1)
            with self.assertRaises(FileExistsError):
                await NativeCreativeControl(FakeSession(), ScriptedModel([]),
                    receipt_path=receipt).run("Never overwrite receipts")

    async def test_actual_source_bound_frame_reaches_visual_model_only_if_hash_matches(self):
        png = b"\x89PNG\r\n\x1a\n" + b"fixture"
        sha = hashlib.sha256(png).hexdigest()
        export = "a" * 64
        session = FakeSession()
        session.custom_response = SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps({
                "export_sha256": export, "png_sha256": sha})),
            SimpleNamespace(type="image", mime_type="image/png",
                            data=base64.b64encode(png).decode())])
        model = ScriptedModel([
            decision("invoke", tool="zx7_verify_native_export", inputs={"path": "/bound/movie.mp4"}),
            decision("invoke", tool="zx7_observe_verified_export_frame",
                     inputs={"path": "/bound/movie.mp4", "at_seconds": 1}),
            decision("finish", summary="Still an unverified review"),
        ])
        result = await NativeCreativeControl(session, model).run("Review an actual source edit")
        self.assertEqual(len(model.images_observed), 1)
        self.assertEqual(model.images_observed[0][1], [("image/png", png)])
        self.assertEqual(model.images_observed[0][0]["observed_picture_sha256"], [sha])
        self.assertFalse(result["artistic_quality_independently_approved"])
        observed = [ev for ev in result["events"] if ev["kind"] == "native_tool_result"]
        self.assertEqual(observed[0]["independently_verified_export_sha256"], export)
        self.assertEqual(observed[1]["observed_export_sha256"], export)
        self.assertNotIn(base64.b64encode(png).decode(), json.dumps(result))
        model2 = ScriptedModel([
            decision("invoke", tool="zx7_verify_native_export", inputs={"path": "/bound/movie.mp4"}),
            decision("invoke", tool="zx7_observe_verified_export_frame", inputs={})])
        session.custom_response.content[0].text = json.dumps({
            "export_sha256": export, "png_sha256": "0" * 64})
        with self.assertRaisesRegex(NativeCreativeControlError, "SHA-bound"):
            await NativeCreativeControl(session, model2).run("Review a corrupted frame")

    async def test_arbitrary_native_tool_cannot_impersonate_physical_sensors(self):
        png = b"\x89PNG\r\n\x1a\n" + b"fixture"
        session = FakeSession()
        session.custom_response = SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps({
                "export_sha256": "a"*64, "png_sha256": hashlib.sha256(png).hexdigest()})),
            SimpleNamespace(type="image", mime_type="image/png",
                            data=base64.b64encode(png).decode())])
        model = ScriptedModel([
            decision("invoke", tool="get_timeline", inputs={})])
        with self.assertRaisesRegex(NativeCreativeControlError, "Untrusted tool supplied image"):
            await NativeCreativeControl(session, model).run("Review an untrusted native image")
        session2 = FakeSession()
        session2.custom_response = session.custom_response
        model2 = ScriptedModel([
            decision("invoke", tool="zx7_observe_verified_export_frame", inputs={})])
        with self.assertRaisesRegex(NativeCreativeControlError, "No earlier independently verified export"):
            await NativeCreativeControl(session2, model2).run("Review unverified output")

    async def test_error_results_do_not_become_trusted_success(self):
        session = FakeSession()
        session.custom_response = SimpleNamespace(is_error=True, content=[
            SimpleNamespace(type="text", text="Missing native asset")])
        model = ScriptedModel([
            decision("invoke", tool="get_timeline", inputs={}),
            decision("invoke", tool="update_text_clip", inputs={"clipId": "must-not-write"})])
        with tempfile.TemporaryDirectory() as root:
            receipt = Path(root) / "model-failure.jsonl"
            result = await NativeCreativeControl(session, model, receipt_path=receipt).run("Test error")
            self.assertEqual(result["status"], "native_error_requires_state_reconciliation")
            self.assertEqual(result["events"][-1]["kind"], "native_tool_reported_error")
            self.assertTrue(result["events"][-1]["must_reconcile_native_state"])
            self.assertEqual(len(session.calls), 1)
            self.assertNotIn("Missing native asset", receipt.read_text())
            self.assertIn("error_sha256", receipt.read_text())
        self.assertFalse(result["native_editing_capability_complete"])

    async def test_audio_content_without_proof_not_silently_translated_to_language(self):
        session = FakeSession()
        session.custom_response = SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="audio", mime_type="audio/wav",
                            data=base64.b64encode(b"RIFF").decode())])
        model = ScriptedModel([decision("invoke", tool="get_timeline", inputs={})])
        with self.assertRaisesRegex(NativeCreativeControlError, "out of budget"):
            await NativeCreativeControl(session, model).run("Listen to my mix")

    async def test_controller_is_single_use_so_verified_export_proof_cannot_leak(self):
        session = FakeSession()
        model = ScriptedModel([
            decision("invoke", tool="zx7_verify_native_export",
                     inputs={"path": "/host/test.mp4"}),
            decision("finish", summary="Fixture ended, not independently reviewed")])
        controller = NativeCreativeControl(session, model, max_turns=2)
        first = await controller.run("First source-bound model session")
        self.assertEqual(first["status"], "model_finished_unverified")
        self.assertTrue(controller._verified_exports)
        with self.assertRaisesRegex(NativeCreativeControlError, "single-use"):
            await controller.run("Second session may not inherit first export proof")
        self.assertEqual(len([c for c in session.calls if c[0] == "zx7_verify_native_export"]), 1)

    async def test_real_monotonic_timing_and_untrusted_token_reports_are_distinguished(self):
        model = ScriptedModel([
            decision("invoke", tool="get_timeline", inputs={"includeClips": True}),
            decision("finish", summary="Time measured, aesthetic judgment remains unproven"),
        ])
        # Deliberately supply an implausible BOOL value: bool is an int
        # subclass and must never be treated as a truthful token count.
        model.last_call_usage = {"prompt_tokens": 11, "completion_tokens": True,
                                 "total_tokens": -1}
        outcome = await NativeCreativeControl(FakeSession(), model, max_turns=3).run(
            "Use local native editing tools and record bounded timing")
        self.assertGreaterEqual(outcome["measured_model_wall_ms_total"], 0)
        self.assertGreaterEqual(outcome["measured_native_mcp_wall_ms_total"], 0)
        self.assertFalse(outcome["token_usage_independently_verified"])
        submitted = next(x for x in outcome["events"]
                         if x["kind"] == "native_tool_submitted")
        self.assertEqual(submitted["local_server_reported_token_usage"],
                         {"prompt_tokens": 11})
        self.assertGreaterEqual(submitted["measured_model_wall_ms"], 0)
        result = next(x for x in outcome["events"]
                      if x["kind"] == "native_tool_result")
        self.assertGreaterEqual(result["measured_native_mcp_wall_ms"], 0)
        finished = outcome["events"][-1]
        self.assertEqual(finished["kind"], "model_finished")
        self.assertFalse(outcome["native_editing_capability_complete"])

    async def test_semantically_invalid_model_actions_leave_terminal_failure_before_rpc(self):
        invalid = [
            decision("finish", summary=""),
            decision("finish", summary="private value", unexpected=True),
            decision("discover", unexpected=True),
            decision("describe", tool="not_granted"),
            decision("describe", tool=[]),
            decision("invoke", tool="not_granted", inputs={}),
            decision("invoke", tool="get_timeline", inputs=[]),
        ]
        from studio_next.native_creative_audit import audit_native_journal
        for action in invalid:
            with self.subTest(action=action), tempfile.TemporaryDirectory() as root:
                journal = Path(root) / "invalid-model-action.jsonl"
                session = FakeSession()
                controller = NativeCreativeControl(session, ScriptedModel([action]), receipt_path=journal)
                with self.assertRaises(NativeCreativeControlError):
                    await controller.run("Native action validation fixture")
                events = [json.loads(line) for line in journal.read_text().splitlines()]
                self.assertEqual([event["kind"] for event in events],
                                 ["session_started", "model_decision_failed"])
                self.assertEqual(session.calls, [])
                audit = audit_native_journal(events, host_tool_access={"get_timeline": "read"})
                self.assertEqual(audit["model_reported_end_state"], "model_decision_failed")
                self.assertNotIn("private value", journal.read_text())

    async def test_failing_local_model_gets_terminal_trace_without_leaking_error_text(self):
        class BrokenLocalModel(ScriptedModel):
            def decide(self, context):
                raise RuntimeError("private media path and secret must NOT be logged")
        with tempfile.TemporaryDirectory() as root:
            journal = Path(root) / "inference-failed.jsonl"
            with self.assertRaisesRegex(RuntimeError, "private media path"):
                await NativeCreativeControl(FakeSession(), BrokenLocalModel([]),
                                            receipt_path=journal).run("Review my film")
            raw = journal.read_text()
            events = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual([e["kind"] for e in events],
                             ["session_started", "model_decision_failed"])
            self.assertEqual(events[-1]["error_type"], "RuntimeError")
            self.assertTrue(events[-1]["no_automatic_retry"])
            self.assertGreaterEqual(events[-1]["measured_model_wall_ms"], 0)
            self.assertNotIn("private media path", raw)
            self.assertNotIn("Review my film", raw)
            from studio_next.native_creative_audit import audit_native_journal
            audit = audit_native_journal(events, host_tool_access={"get_timeline": "read"})
            self.assertEqual(audit["model_reported_end_state"], "model_decision_failed")
            self.assertFalse(audit["video_editing_capability_complete"])

    async def test_nonexistent_or_duplicate_native_tool_descriptors_refused(self):
        session = FakeSession()
        session.tools.append(session.tools[0])
        with self.assertRaisesRegex(NativeCreativeControlError, "duplicate"):
            await NativeCreativeControl(session, ScriptedModel([])).run("A film")
        with self.assertRaisesRegex(NativeCreativeControlError, "finite turn"):
            NativeCreativeControl(FakeSession(), ScriptedModel([]), max_turns=0)


    async def test_multiple_native_text_parts_cannot_bypass_total_evidence_budget(self):
        for blocks in (
            [SimpleNamespace(type="text", text="a" * 35000),
             SimpleNamespace(type="text", text="b" * 35000)],
            [SimpleNamespace(type="text", text="a") for _ in range(65)],
            [SimpleNamespace(type="text", text="界" * 21000),
             SimpleNamespace(type="text", text="a" * 1001)],
        ):
            with self.subTest(part_count=len(blocks)), tempfile.TemporaryDirectory() as root:
                session = FakeSession()
                session.custom_response = SimpleNamespace(is_error=False, content=blocks)
                journal = Path(root) / "native-budget.jsonl"
                controller = NativeCreativeControl(session, ScriptedModel([
                    decision("invoke", tool="get_timeline", inputs={}),
                ]), receipt_path=journal)
                with self.assertRaisesRegex(NativeCreativeControlError, "too many content blocks|text evidence"):
                    await controller.run("Inspect native media without unbounded context")
                events = [json.loads(line) for line in journal.read_text().splitlines()]
                self.assertEqual(events[-1]["kind"], "native_observation_rejected")
                self.assertEqual(len(session.calls), 1)
                self.assertNotIn("a" * 1000, journal.read_text())

    async def test_bounded_native_text_parts_still_reach_the_model(self):
        session = FakeSession()
        session.custom_response = SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text="a" * 32000),
            SimpleNamespace(type="text", text="b" * 32000),
        ])
        model = ScriptedModel([
            decision("invoke", tool="get_timeline", inputs={}),
            decision("finish", summary="Observed bounded native text"),
        ])
        outcome = await NativeCreativeControl(session, model, max_turns=2).run(
            "Read a bounded native timeline")
        self.assertEqual(outcome["status"], "model_finished_unverified")
        self.assertEqual(sum(len(s.encode("utf-8"))
                             for s in model.observed[-1]["last_native_result_texts"]), 64000)
        self.assertEqual(len(session.calls), 1)


    async def test_private_model_intent_and_summary_are_hashed_not_journaled(self):
        private = "PRIVATE-BRIEF-PATH-AND-SECRET-DO-NOT-PERSIST"
        session = FakeSession()
        model = ScriptedModel([
            {"action": "invoke", "arguments": {"tool": "get_timeline", "inputs": {}},
             "reason": private},
            {"action": "finish", "arguments": {"summary": private},
             "reason": "done"},
        ])
        with tempfile.TemporaryDirectory() as root:
            journal = Path(root) / "private-proof.jsonl"
            outcome = await NativeCreativeControl(session, model, max_turns=2,
                                                   receipt_path=journal).run("Private test")
            raw = journal.read_text()
            self.assertNotIn(private, raw)
            events = [json.loads(line) for line in raw.splitlines()]
            submitted = next(x for x in events if x["kind"] == "native_tool_submitted")
            terminal = events[-1]
            self.assertEqual(submitted["model_reason_sha256"],
                             hashlib.sha256(private.encode()).hexdigest())
            self.assertEqual(submitted["model_reason_utf8_bytes"], len(private.encode()))
            self.assertNotIn("model_reason", submitted)
            self.assertEqual(terminal["summary_sha256"],
                             hashlib.sha256(private.encode()).hexdigest())
            self.assertEqual(terminal["summary_utf8_bytes"], len(private.encode()))
            self.assertNotIn("summary", terminal)
            self.assertNotIn(private, json.dumps(outcome["events"]))
            from studio_next.native_creative_audit import audit_native_journal
            audit = audit_native_journal(events, host_tool_access={"get_timeline": "read"})
            self.assertTrue(audit["journal_chain_structurally_valid"])
            self.assertFalse(audit["video_editing_capability_complete"])


    async def test_native_error_text_is_bounded_without_replaying_uncertain_write(self):
        oversize = [
            [SimpleNamespace(type="text", text="PRIVATE-ERROR-SECRET-" * 7000)],
            [SimpleNamespace(type="text", text="x" * 35000),
             SimpleNamespace(type="text", text="y" * 35000)],
            [SimpleNamespace(type="text", text="short") for _ in range(65)],
        ]
        for blocks in oversize:
            with self.subTest(parts=len(blocks)), tempfile.TemporaryDirectory() as root:
                session = FakeSession()
                session.custom_response = SimpleNamespace(is_error=True, content=blocks)
                model = ScriptedModel([
                    decision("invoke", tool="update_text_clip", inputs={"clipId": "possibly-mutated"}),
                    decision("invoke", tool="update_text_clip", inputs={"clipId": "must-never-replay"}),
                ])
                path = Path(root) / "redacted-error.jsonl"
                outcome = await NativeCreativeControl(session, model, max_turns=2,
                                                       receipt_path=path).run("A private native project")
                self.assertEqual(outcome["status"], "native_error_requires_state_reconciliation")
                self.assertEqual(len(session.calls), 1)
                terminal = outcome["events"][-1]
                self.assertEqual(terminal["kind"], "native_tool_reported_error")
                self.assertIsNone(terminal["error_sha256"])
                self.assertTrue(terminal["error_text_exceeded_evidence_budget"])
                self.assertTrue(terminal["must_reconcile_native_state"])
                self.assertNotIn("PRIVATE-ERROR-SECRET-", path.read_text())
                from studio_next.native_creative_audit import audit_native_journal
                verified = audit_native_journal(outcome["events"],
                                                host_tool_access={"update_text_clip": "write"})
                self.assertEqual(verified["model_reported_end_state"], "native_tool_reported_error")
                self.assertFalse(verified["video_editing_capability_complete"])

    async def test_small_native_errors_keep_complete_hash_without_raw_error(self):
        session = FakeSession()
        error = ["secret-a", "secret-b"]
        session.custom_response = SimpleNamespace(is_error=True, content=[
            SimpleNamespace(type="text", text=value) for value in error])
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "errors.jsonl"
            controller = NativeCreativeControl(session, ScriptedModel([
                decision("invoke", tool="get_timeline", inputs={})]), receipt_path=path)
            result = await controller.run("Bounded error proof")
            receipt = result["events"][-1]
            self.assertFalse(receipt["error_text_exceeded_evidence_budget"])
            self.assertEqual(receipt["error_sha256"], hashlib.sha256(
                json.dumps(error, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")).encode()).hexdigest())
            self.assertNotIn("secret-a", path.read_text())
            self.assertNotIn("secret-b", path.read_text())


    async def test_real_host_tool_descriptions_help_model_without_creative_templates(self):
        from studio_next.native_creative_control import _native_tool_hints
        session = FakeSession()
        # The host supplies every name/description; the adapter invents none.
        session.tools[0].description = "  Read   the native" + chr(10) + " project   state "
        session.tools[1].description = "N" * 100_000
        model = ScriptedModel([
            decision("discover"),
            decision("describe", tool="get_timeline"),
            decision("finish", summary="Tool selection remains model-controlled"),
        ])
        outcome = await NativeCreativeControl(session, model, max_turns=3).run(
            "Creative brief without hardcoded steps")
        initial = model.observed[0]
        after_discovery = model.observed[1]
        final = model.observed[2]
        self.assertEqual(initial["actual_granted_native_tools"],
                         [tool.name for tool in session.tools])
        hints = initial["host_declared_tool_hints"]
        self.assertEqual(hints, _native_tool_hints(session.tools))
        self.assertEqual(hints[0]["description"], "Read the native project state")
        self.assertGreater(len(hints[1]["description"]), 0)
        self.assertLessEqual(len(hints[1]["description"]), 80)
        self.assertEqual(hints, after_discovery["host_declared_tool_hints"])
        self.assertNotIn("host_declared_tool_hints", final)
        self.assertEqual(session.calls, [])
        self.assertEqual(outcome["status"], "model_finished_unverified")

    async def test_tool_hints_bounded_in_aggregate_with_real_host_names_retained(self):
        from studio_next.native_creative_control import _native_tool_hints
        session = FakeSession()
        session.tools = [
            SimpleNamespace(name=f"native_action_{i}", description="界" * 1000,
                            input_schema={"type": "object"})
            for i in range(120)
        ]
        hints = _native_tool_hints(session.tools)
        self.assertLessEqual(sum(len(x["description"].encode("utf-8")) for x in hints), 12_000)
        model = ScriptedModel([decision("finish", summary="No chosen edit")])
        outcome = await NativeCreativeControl(session, model, max_turns=1).run(
            "Discover every editor tool identity")
        self.assertEqual(len(model.observed[0]["actual_granted_native_tools"]), 120)
        self.assertEqual(model.observed[0]["host_declared_tool_hints"], hints)
        self.assertFalse(outcome["native_editing_capability_complete"])


    async def test_invalid_native_arguments_corrected_by_model_before_editor_dispatch(self):
        model = ScriptedModel([
            decision("invoke", tool="update_text_clip", inputs={"clipId": 42}),
            decision("describe", tool="update_text_clip"),
            decision("invoke", tool="update_text_clip", inputs={"clipId": "model-chosen-id"}),
            decision("finish", summary="Native schema correction tested, no aesthetic claim"),
        ])
        session = FakeSession()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "preflight.jsonl"
            result = await NativeCreativeControl(session, model, max_turns=4,
                                                  receipt_path=path).run("Repair native text")
            self.assertEqual(result["status"], "model_finished_unverified")
            self.assertEqual(session.calls, [
                ("update_text_clip", {"clipId": "model-chosen-id"})])
            self.assertEqual([e["kind"] for e in result["events"]], [
                "session_started", "model_action_rejected", "native_tool_schema",
                "native_tool_submitted", "native_tool_result", "model_finished"])
            rejected = result["events"][1]
            self.assertEqual(rejected["validation_keyword"], "type")
            self.assertEqual(rejected["schema_location"], "properties/clipId/type")
            self.assertTrue(rejected["no_native_dispatch"])
            self.assertNotIn('"inputs":', json.dumps(rejected))
            self.assertEqual(model.observed[1]["latest_events"][-1]["kind"],
                             "model_action_rejected")
            from studio_next.native_creative_audit import audit_native_journal
            audit = audit_native_journal(result["events"],
                                         host_tool_access={"update_text_clip": "write",
                                                           "get_timeline": "read",
                                                           "zx7_verify_native_export": "read",
                                                           "zx7_observe_verified_export_frame": "read"})
            self.assertEqual(audit["recorded_native_write_result_count"], 1)
            self.assertFalse(audit["video_editing_capability_complete"])

    async def test_preflight_exhaustion_never_executes_invalid_native_write(self):
        attempts = [decision("invoke", tool="update_text_clip", inputs={"clipId": False})
                    for _ in range(4)]
        session = FakeSession()
        result = await NativeCreativeControl(session, ScriptedModel(attempts),
                                             max_turns=4).run("A safe native text revision")
        self.assertEqual(result["status"], "turn_budget_exhausted")
        self.assertEqual(session.calls, [])
        self.assertEqual(len([e for e in result["events"]
                             if e["kind"] == "model_action_rejected"]), 4)
        self.assertFalse(result["native_editing_capability_complete"])


    async def test_actual_native_observation_survives_metadata_and_invalid_proposals(self):
        session = FakeSession()
        model = ScriptedModel([
            decision("invoke", tool="get_timeline", inputs={"includeClips": True}),
            decision("discover"),
            decision("describe", tool="update_text_clip"),
            decision("invoke", tool="update_text_clip", inputs={"clipId": 404}),
            decision("invoke", tool="update_text_clip", inputs={"clipId": "editable-model-choice"}),
            decision("finish", summary="Native observation continuity checked"),
        ])
        outcome = await NativeCreativeControl(session, model, max_turns=6).run(
            "Inspect state and independently choose an edit")
        self.assertEqual(outcome["status"], "model_finished_unverified")
        self.assertEqual([name for name, _ in session.calls], [
            "get_timeline", "update_text_clip"])
        native_observed = model.observed[1]["last_native_result_texts"]
        self.assertTrue(native_observed)
        for turn in (2, 3, 4):
            with self.subTest(turn=turn):
                self.assertEqual(model.observed[turn]["last_native_result_texts"],
                                 native_observed)
                self.assertEqual(model.observed[turn]["successful_native_tool_results"], 1)
        self.assertEqual(model.observed[3]["described_native_tools"], ["update_text_clip"])
        self.assertIn("update_text_clip", model.observed[5]["last_native_result_texts"][0])
        self.assertEqual(model.observed[5]["successful_native_tool_results"], 2)
        self.assertEqual(len([e for e in outcome["events"]
                             if e["kind"] == "model_action_rejected"]), 1)
        self.assertFalse(outcome["artistic_quality_independently_approved"])


    async def test_host_preview_plan_never_mints_a_native_write_proof(self):
        from studio_next.native_creative_audit import audit_native_journal, NativeJournalError
        session = FakeSession()
        session.tools.append(SimpleNamespace(
            name="create_project", description="Create or preview a project",
            input_schema={"type": "object", "properties": {
                "name": {"type": "string"}, "previewOnly": {"type": "boolean"}}}))
        grants = {t.name: ("write" if t.name == "create_project" else "read")
                  for t in session.tools}
        async def native_call(name, inputs):
            session.calls.append((name, inputs))
            if name == "create_project" and inputs.get("previewOnly", True):
                receipt = {"success": False, "action": "create_project",
                           "result": {"previewOnly": True,
                                      "plan": {"name": inputs["name"]}},
                           "suggestedApplyCall": {"tool": "create_project",
                                                  "arguments": {"name": inputs["name"],
                                                                "previewOnly": False}}}
            else:
                receipt = {"success": True, "action": name, "result": {"created": True}}
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text=json.dumps(receipt))])
        session.call_tool = native_call
        model = ScriptedModel([
            decision("invoke", tool="create_project", inputs={"name": "Owned short"}),
            decision("finish", summary="A preview is NOT an actual project"),
            decision("invoke", tool="create_project",
                     inputs={"name": "Owned short", "previewOnly": False}),
            decision("finish", summary="Native project applied; no movie delivered"),
        ])
        result = await NativeCreativeControl(
            session, model, max_turns=4, host_tool_access=grants,
            required_evidence=("native_write_acknowledged",)).run("Create original editable work")
        kinds = [e["kind"] for e in result["events"]]
        self.assertEqual(kinds.count("native_tool_preview"), 1)
        self.assertEqual(kinds.count("native_tool_result"), 1)
        self.assertEqual(kinds.count("model_finish_rejected"), 1)
        self.assertEqual(result["status"], "model_finished_unverified")
        self.assertEqual(model.observed[1]["missing_completion_evidence"],
                         ["native_write_acknowledged"])
        self.assertEqual(model.observed[3]["missing_completion_evidence"], [])
        self.assertEqual([c[0] for c in session.calls], ["create_project", "create_project"])
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=grants)["journal_chain_structurally_valid"])
        forged = [dict(e) for e in result["events"]]
        event = next(e for e in forged if e["kind"] == "native_tool_preview")
        event["host_reported_preview_only"] = False
        with self.assertRaisesRegex(NativeJournalError, "forged"):
            audit_native_journal(forged, host_tool_access=grants)

    async def test_actual_project_open_write_is_followed_by_independent_read_once(self):
        from studio_next.native_creative_audit import audit_native_journal
        session = FakeSession()
        session.tools += [
            SimpleNamespace(name="get_project", description="Host project identity",
                            input_schema={"type": "object", "properties": {},
                                          "additionalProperties": False}),
            SimpleNamespace(name="create_project", description="Create editable native project",
                            input_schema={"type": "object", "properties": {
                                "name": {"type": "string"},
                                "previewOnly": {"type": "boolean"}}}),
        ]
        read_count = 0
        async def native_call(name, arguments):
            nonlocal read_count
            session.calls.append((name, arguments))
            if name == "get_project":
                read_count += 1
                payload = ({"project": None, "mcp": {"hasProject": False}}
                           if read_count == 1 else
                           {"project": {"id": "real-native-project"}, "mcp": {"hasProject": True}})
                return SimpleNamespace(is_error=False, content=[
                    SimpleNamespace(type="text", text=json.dumps(payload))])
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text=json.dumps({"success": True}))])
        session.call_tool = native_call
        grants = {t.name: ("write" if t.name == "create_project" else "read")
                  for t in session.tools}
        model = ScriptedModel([
            decision("invoke", tool="create_project",
                     inputs={"name": "Independent owned work", "previewOnly": False}),
            decision("finish", summary="Project state is host-verified, not an artistic pass"),
        ])
        result = await NativeCreativeControl(
            session, model, max_turns=2, catalog_mode="indexed",
            host_tool_access=grants,
            host_possible_effects={"create_project": ["project_open"]}).run(
                "Create a genuine editable native movie project")
        self.assertEqual([name for name, _ in session.calls],
                         ["get_project", "create_project", "get_project"])
        self.assertEqual([c["native_project_presence_from_last_inspection"]
                          for c in model.observed], ["absent", "present"])
        self.assertIn("real-native-project",
                      model.observed[1]["last_native_result_texts"][0])
        reviews = [e for e in result["events"]
                   if e["kind"] == "host_project_post_write_observation"]
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["project_presence"], "present")
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=grants)["journal_chain_structurally_valid"])
        forged = [dict(x) for x in result["events"]]
        forged[reviews[0]["sequence"]]["triggered_by_native_tool"] = "get_project"
        from studio_next.native_creative_audit import NativeJournalError
        with self.assertRaisesRegex(NativeJournalError, "read-after-write"):
            audit_native_journal(forged, host_tool_access=grants)
        self.assertFalse(result["native_editing_capability_complete"])

    async def test_post_write_project_read_error_does_not_fabricate_presence_or_retry_write(self):
        from studio_next.native_creative_audit import audit_native_journal
        session = FakeSession()
        session.tools += [
            SimpleNamespace(name="get_project", description="Project status",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="create_project", description="Create project",
                            input_schema={"type": "object", "properties": {
                                "name": {"type": "string"}}}),
        ]
        n = 0
        async def native_call(name, args):
            nonlocal n
            session.calls.append((name, args))
            if name == "get_project":
                n += 1
                if n == 1:
                    return SimpleNamespace(is_error=False, content=[
                        SimpleNamespace(type="text", text=json.dumps({
                            "project": None, "mcp": {"hasProject": False}}))])
                return SimpleNamespace(is_error=True, content=[
                    SimpleNamespace(type="text", text="Native read failed")])
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text='{"success":true}')])
        session.call_tool = native_call
        grants = {t.name: ("write" if t.name == "create_project" else "read")
                  for t in session.tools}
        model = ScriptedModel([
            decision("invoke", tool="create_project", inputs={"name": "Owned work"}),
            decision("finish", summary="Read error does not imply an open project"),
        ])
        result = await NativeCreativeControl(
            session, model, catalog_mode="indexed", host_tool_access=grants,
            host_possible_effects={"create_project": ["project_open"]},
            max_turns=2).run("Create editable work with verified presence")
        self.assertEqual(sum(name == "create_project" for name, _ in session.calls), 1)
        self.assertEqual(model.observed[1]["native_project_presence_from_last_inspection"],
                         "unknown")
        self.assertIn("host_project_post_write_error",
                      [e["kind"] for e in result["events"]])
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=grants)["journal_chain_structurally_valid"])

    async def test_native_project_presence_is_observed_not_inferred_from_model_words(self):
        session = FakeSession()
        session.tools.append(SimpleNamespace(name="get_project", description="Real native project",
                                             input_schema={"type": "object", "additionalProperties": False}))
        observed_null = json.dumps({"project": None, "mcp": {"hasProject": False}})
        observed_present = json.dumps({"project": {"id": "native-1"}, "mcp": {"hasProject": True}})
        observed_state = [observed_null, observed_present]
        async def native_call(name, arguments):
            session.calls.append((name, arguments))
            if name == "get_project":
                return SimpleNamespace(is_error=False, content=[
                    SimpleNamespace(type="text", text=observed_state.pop(0))])
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text=json.dumps({"success": True}))])
        session.call_tool = native_call
        model = ScriptedModel([
            decision("invoke", tool="get_project", inputs={}),
            decision("discover"),
            decision("invoke", tool="get_project", inputs={}),
            decision("finish", summary="Only source evidence determines project presence"),
        ])
        result = await NativeCreativeControl(session, model, max_turns=4).run(
            "Inspect the actual editable project without inventing state")
        self.assertEqual([c["native_project_presence_from_last_inspection"]
                          for c in model.observed],
                         ["unknown", "absent", "absent", "present"])
        self.assertEqual(result["status"], "model_finished_unverified")
        self.assertEqual(len(session.calls), 2)
        self.assertFalse(result["native_editing_capability_complete"])

    async def test_native_project_presence_invalidated_after_other_real_operation(self):
        session = FakeSession()
        session.tools.append(SimpleNamespace(name="get_project", description="Native project state",
                                             input_schema={"type": "object", "additionalProperties": False}))
        session.custom_response = SimpleNamespace(is_error=False, content=[SimpleNamespace(
            type="text", text=json.dumps({"project": None, "mcp": {"hasProject": False}}))])
        model = ScriptedModel([
            decision("invoke", tool="get_project", inputs={}),
            decision("invoke", tool="update_text_clip", inputs={"clipId": "model-edit"}),
            decision("finish", summary="A write invalidated the old project snapshot"),
        ])
        result = await NativeCreativeControl(session, model, max_turns=3).run(
            "Inspect then change native state")
        self.assertEqual(model.observed[1]["native_project_presence_from_last_inspection"], "absent")
        self.assertEqual(model.observed[2]["native_project_presence_from_last_inspection"], "unknown")
        self.assertEqual([x[0] for x in session.calls], ["get_project", "update_text_clip"])
        self.assertFalse(result["artistic_quality_independently_approved"])

    async def test_missing_project_field_cannot_be_misreported_as_absent(self):
        session = FakeSession()
        session.tools.append(SimpleNamespace(name="get_project", description="Native project",
                                             input_schema={"type": "object", "additionalProperties": False}))
        session.custom_response = SimpleNamespace(is_error=False, content=[SimpleNamespace(
            type="text", text=json.dumps({"mcp": {"hasProject": False}}))])
        model = ScriptedModel([
            decision("invoke", tool="get_project", inputs={}),
            decision("finish", summary="Missing project field is not evidence of no project"),
        ])
        await NativeCreativeControl(session, model, max_turns=2).run("Check project truth")
        self.assertEqual(model.observed[1]["native_project_presence_from_last_inspection"],
                         "unknown")

    async def test_contradictory_native_project_snapshot_is_not_treated_as_fact(self):
        session = FakeSession()
        session.tools.append(SimpleNamespace(name="get_project", description="Native project",
                                             input_schema={"type": "object", "additionalProperties": False}))
        session.custom_response = SimpleNamespace(is_error=False, content=[SimpleNamespace(
            type="text", text=json.dumps({"project": None, "mcp": {"hasProject": True}}))])
        model = ScriptedModel([
            decision("invoke", tool="get_project", inputs={}),
            decision("finish", summary="Contradiction is unknown"),
        ])
        await NativeCreativeControl(session, model, max_turns=2).run("Inspect project truth")
        self.assertEqual(model.observed[1]["native_project_presence_from_last_inspection"],
                         "unknown")


    async def test_model_window_compacts_redundant_catalogs_not_real_observations(self):
        from studio_next.native_creative_control import _model_event_window
        giant_tool_names = [f"real_host_tool_{i:04d}" for i in range(130)]
        events = [{"kind": "discovered", "turn": i, "sequence": i,
                   "tools": giant_tool_names, "measured_model_wall_ms": 30000}
                  for i in range(5)]
        events += [
            {"kind": "native_tool_schema", "turn": 5, "tool": "old_tool",
             "description": "old", "input_schema": {"type": "object", "padding": "x" * 1500}},
            {"kind": "native_tool_schema", "turn": 6, "tool": "new_tool",
             "description": "new", "input_schema": {"type": "object", "properties": {
                 "nativeField": {"type": "string"}}}},
            {"kind": "model_action_rejected", "turn": 7, "tool": "new_tool",
             "validation_keyword": "required", "schema_location": "required",
             "no_native_dispatch": True, "inputs_sha256": "a" * 64},
        ]
        before = json.dumps(events, sort_keys=True)
        window = _model_event_window(events)
        self.assertEqual(len(window), 8)
        self.assertTrue(all(x["native_tool_count"] == 130 for x in window[:5]))
        self.assertNotIn("tools", window[0])
        self.assertNotIn("input_schema", window[5])
        self.assertTrue(window[5]["schema_available_by_describe"])
        self.assertEqual(window[6]["input_schema"], events[6]["input_schema"])
        self.assertTrue(window[-1]["no_native_dispatch"])
        self.assertEqual(window[-1]["schema_location"], "required")
        self.assertNotIn("inputs_sha256", window[-1])
        self.assertLess(len(json.dumps(window).encode()), len(before.encode()) // 4)
        self.assertEqual(before, json.dumps(events, sort_keys=True))  # durable trace untouched

    async def test_model_window_preserves_verified_export_identity_and_native_result(self):
        from studio_next.native_creative_control import _model_event_window
        events = [
            {"kind": "native_tool_result", "turn": 2,
             "tool": "zx7_verify_native_export",
             "independently_verified_export_sha256": "a" * 64,
             "human_or_artistic_quality_approved": False},
            {"kind": "native_tool_result", "turn": 3,
             "tool": "zx7_observe_verified_export_frame",
             "observed_export_sha256": "a" * 64,
             "image_sha256": ["b" * 64],
             "human_or_artistic_quality_approved": False},
        ]
        window = _model_event_window(events)
        self.assertEqual(window[0]["independently_verified_export_sha256"], "a" * 64)
        self.assertEqual(window[1]["observed_export_sha256"], "a" * 64)
        self.assertEqual(window[1]["image_sha256"], ["b" * 64])
        self.assertNotIn("human_or_artistic_quality_approved", window[1])

    async def test_real_native_observation_still_reaches_model_with_compact_history(self):
        session = FakeSession()
        model = ScriptedModel([
            decision("discover"),
            decision("invoke", tool="get_timeline", inputs={}),
            decision("describe", tool="update_text_clip"),
            decision("finish", summary="Observed actual native result"),
        ])
        result = await NativeCreativeControl(session, model, max_turns=4).run(
            "Inspect an editor and choose project work")
        self.assertEqual(result["status"], "model_finished_unverified")
        self.assertTrue(model.observed[2]["last_native_result_texts"])
        self.assertEqual(model.observed[2]["latest_events"][0]["kind"], "session_started")
        self.assertNotIn("tools", model.observed[2]["latest_events"][1])
        self.assertEqual(model.observed[3]["latest_events"][-1]["input_schema"],
                         session.tools[1].input_schema)
        self.assertEqual(len(session.calls), 1)


    async def test_undeclared_native_top_level_model_inputs_never_reach_editor(self):
        session = FakeSession()
        # Real pinned open_project uses projectPath, projectName, previewOnly,
        # and the upstream schema omits additionalProperties and required.
        session.tools.append(SimpleNamespace(name="open_project",
            description="Open an existing native project",
            input_schema={"type": "object", "properties": {
                "projectPath": {"type": "string"},
                "projectName": {"type": "string"},
                "previewOnly": {"type": "boolean"}}}))
        model = ScriptedModel([
            decision("invoke", tool="open_project",
                     inputs={"project_name": "invented alias", "folder": "/invented"}),
            decision("describe", tool="open_project"),
            decision("invoke", tool="open_project",
                     inputs={"projectName": "real recent project", "previewOnly": True}),
            decision("finish", summary="Only native-declared fields dispatched"),
        ])
        result = await NativeCreativeControl(session, model, max_turns=4).run(
            "Safely open an existing native video project")
        self.assertEqual(result["status"], "model_finished_unverified")
        self.assertEqual(session.calls, [("open_project",
            {"projectName": "real recent project", "previewOnly": True})])
        self.assertEqual(result["events"][1]["kind"], "model_action_rejected")
        self.assertEqual(result["events"][1]["validation_keyword"], "additionalProperties")
        self.assertTrue(result["events"][1]["no_native_dispatch"])
        self.assertEqual(model.observed[0]["host_declared_tool_hints"][-1]
                         ["declared_parameter_names_sample"],
                         ["projectPath", "projectName", "previewOnly"])
        self.assertFalse(result["native_editing_capability_complete"])

    async def test_deliberately_unrestricted_artistic_schema_stays_expressive(self):
        session = FakeSession()
        session.tools.append(SimpleNamespace(name="native_style",
            description="Artist-directed native parameter graph",
            input_schema={"type": "object", "properties": {
                "node": {"type": "string"},
                "parameters": {"type": "object", "additionalProperties": True}},
                "additionalProperties": True}))
        model = ScriptedModel([
            decision("invoke", tool="native_style",
                     inputs={"node": "model-node",
                             "parameters": {"shaders": {"custom": [0.1, 0.75]}},
                             "extension": {"customArtistField": 9}}),
            decision("finish", summary="Permissive native extension accepted"),
        ])
        result = await NativeCreativeControl(session, model, max_turns=2).run(
            "Model chooses its own expressive parameters")
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0][1]["extension"]["customArtistField"], 9)
        self.assertEqual(result["status"], "model_finished_unverified")


    async def test_native_affordance_envelope_has_exact_12kb_budget_and_fair_late_tool_sampling(self):
        from studio_next.native_creative_control import _native_tool_hints
        tools = [
            SimpleNamespace(name=f"tool_{i:03d}", description="D" * 5000,
                            input_schema={"type": "object", "properties": {
                                "nativeFirst": {"type": "string"},
                                "nativeSecond": {"type": "number"},
                                "nativeThird": {"type": "boolean"}}})
            for i in range(80)
        ]
        hints = _native_tool_hints(tools)
        self.assertEqual(len(hints), 80)
        encoded = json.dumps(hints, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")
        self.assertLessEqual(len(encoded), 12_000)
        self.assertTrue(hints[0]["declared_parameter_names_sample"])
        self.assertTrue(hints[-1]["declared_parameter_names_sample"])
        self.assertEqual(hints[-1]["declared_parameter_names_sample"][0], "nativeFirst")
        self.assertTrue(all(len(item["description"]) <= 80 for item in hints))
        self.assertNotIn("nativeFirst", tools[0].description)



    async def test_host_attested_read_failure_allows_independent_model_correction(self):
        from studio_next.native_creative_audit import audit_native_journal
        session = FakeSession()
        access = {x.name: "read" for x in session.tools}
        access["update_text_clip"] = "write"
        failed_once = [True]
        async def native_tool(name, inputs):
            session.calls.append((name, inputs))
            if name == "get_timeline" and failed_once[0]:
                failed_once[0] = False
                return SimpleNamespace(is_error=True, content=[
                    SimpleNamespace(type="text", text="Private source not yet open")])
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text='{"success":true}')])
        session.call_tool = native_tool
        model = ScriptedModel([
            decision("invoke", tool="get_timeline", inputs={}),
            decision("describe", tool="get_timeline"),
            decision("invoke", tool="get_timeline", inputs={"includeClips": True}),
            decision("finish", summary="Read corrected without editing any file"),
        ])
        with tempfile.TemporaryDirectory() as root:
            receipt = Path(root) / "read-recovery.jsonl"
            result = await NativeCreativeControl(session, model, max_turns=4,
                receipt_path=receipt, host_tool_access=access).run("Inspect actual state")
            self.assertEqual(result["status"], "model_finished_unverified")
            self.assertEqual(len(session.calls), 2)
            failure = result["events"][2]
            self.assertEqual(failure["kind"], "native_read_tool_reported_error")
            self.assertTrue(failure["host_attested_read_only"])
            self.assertTrue(failure["no_successful_native_observation"])
            self.assertEqual(model.observed[1]["latest_events"][-1]["kind"],
                             "native_read_tool_reported_error")
            self.assertNotIn("Private source", receipt.read_text())
            self.assertTrue(audit_native_journal(
                result["events"], host_tool_access=access)["journal_chain_structurally_valid"])
            self.assertEqual(len([x for x in result["events"] if x["kind"] == "native_tool_result"]), 1)
            self.assertFalse(result["native_editing_capability_complete"])

    async def test_unknown_or_write_failure_still_terminates_even_with_host_grants(self):
        for access_mode in ("read", "write"):
            session = FakeSession()
            session.custom_response = SimpleNamespace(is_error=True, content=[
                SimpleNamespace(type="text", text="Uncertain private native outcome")])
            access = {x.name: "read" for x in session.tools}
            access["update_text_clip"] = "write"
            model = ScriptedModel([
                decision("invoke", tool="update_text_clip", inputs={"clipId": "original"}),
                decision("finish", summary="Should never reach this state"),
            ])
            with self.subTest(access_mode=access_mode):
                grants = access if access_mode == "write" else None
                result = await NativeCreativeControl(session, model,
                        host_tool_access=grants, max_turns=2).run("Guard native writes")
                self.assertEqual(result["status"], "native_error_requires_state_reconciliation")
                self.assertEqual(len(session.calls), 1)
                self.assertTrue(result["events"][-1]["must_reconcile_native_state"])

    async def test_trusted_read_grants_must_cover_exact_discovered_tools(self):
        session = FakeSession()
        with self.assertRaisesRegex(NativeCreativeControlError, "match"):
            await NativeCreativeControl(session, ScriptedModel([
                decision("finish", summary="No native actions")]),
                host_tool_access={"get_timeline": "read"}).run("No grant escalation")
        self.assertEqual(session.calls, [])


    async def test_actual_host_schema_is_provided_after_preflight_without_second_metadata_turn(self):
        session = FakeSession()
        model = ScriptedModel([
            decision("invoke", tool="update_text_clip", inputs={"clipId": 12}),
            decision("invoke", tool="update_text_clip", inputs={"clipId": "model-chosen"}),
            decision("finish", summary="Corrected native input against discovered ABI"),
        ])
        result = await NativeCreativeControl(session, model, max_turns=3).run(
            "Model chooses its own native text update")
        first = model.observed[0]["last_rejected_native_action_feedback"]
        second = model.observed[1]["last_rejected_native_action_feedback"]
        third = model.observed[2]["last_rejected_native_action_feedback"]
        self.assertIsNone(first)
        self.assertEqual(second["tool"], "update_text_clip")
        self.assertEqual(second["validation_keyword"], "type")
        self.assertTrue(second["no_native_dispatch"])
        self.assertEqual(second["actual_host_input_schema"]["properties"]
                         ["clipId"]["type"], "string")
        self.assertIsNone(third)
        self.assertEqual(session.calls, [("update_text_clip", {"clipId": "model-chosen"})])
        self.assertNotIn("actual_host_input_schema", json.dumps(result["events"]))
        self.assertFalse(result["artistic_quality_independently_approved"])

    async def test_oversized_actual_schema_not_replayed_to_model(self):
        session = FakeSession()
        session.tools.append(SimpleNamespace(name="huge_native",
             description="Native customizable geometry",
             input_schema={"type": "object", "properties": {
                 "artistValues": {"type": "string", "description": "A" * 30000}}}))
        model = ScriptedModel([
            decision("invoke", tool="huge_native", inputs={"artistValues": 123}),
            decision("finish", summary="Cannot infer large schema from undersized context"),
        ])
        outcome = await NativeCreativeControl(session, model, max_turns=2).run("An original edit")
        next_feedback = model.observed[1]["last_rejected_native_action_feedback"]
        self.assertTrue(next_feedback["request_schema_with_describe"])
        self.assertNotIn("actual_host_input_schema", next_feedback)
        self.assertEqual(session.calls, [])
        self.assertFalse(outcome["native_editing_capability_complete"])


    async def test_untrusted_model_adapter_cannot_mutate_validator_or_receipts(self):
        class MutatingModel(ScriptedModel):
            def decide(self, ctx):
                if ctx.get("last_rejected_native_action_feedback"):
                    ctx["last_rejected_native_action_feedback"]["actual_host_input_schema"][
                        "properties"]["clipId"]["type"] = "number"
                    for event in ctx["latest_events"]:
                        if event.get("kind") == "native_tool_schema":
                            event["input_schema"]["properties"]["clipId"]["type"] = "number"
                return super().decide(ctx)
        session = FakeSession()
        model = MutatingModel([
            decision("describe", tool="update_text_clip"),
            decision("invoke", tool="update_text_clip", inputs={"clipId": 42}),
            decision("invoke", tool="update_text_clip", inputs={"clipId": 73}),
            decision("finish", summary="An untrusted adapter cannot rewrite editor ABI"),
        ])
        with tempfile.TemporaryDirectory() as root:
            receipt = Path(root) / "immutable-host-schema.jsonl"
            outcome = await NativeCreativeControl(session, model, max_turns=4,
                receipt_path=receipt).run("Preserve native host ABI and journal")
            self.assertEqual(session.calls, [])
            self.assertEqual(len([e for e in outcome["events"]
                                 if e["kind"] == "model_action_rejected"]), 2)
            schema_receipt = next(e for e in outcome["events"]
                                  if e["kind"] == "native_tool_schema")
            self.assertEqual(schema_receipt["input_schema"]["properties"]
                             ["clipId"]["type"], "string")
            self.assertEqual(json.loads(receipt.read_text().splitlines()[1])[
                "input_schema"]["properties"]["clipId"]["type"], "string")
            self.assertEqual(outcome["status"], "model_finished_unverified")


    async def test_trusted_host_project_sensing_precedes_first_model_decision(self):
        session = FakeSession()
        session.tools.append(SimpleNamespace(name="get_project",
             description="Real native project state",
             input_schema={"type": "object", "additionalProperties": False}))
        session.custom_response = SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps({
                "project": None, "mcp": {"hasProject": False}}))])
        access = {x.name: ("write" if x.name == "update_text_clip" else "read")
                  for x in session.tools}
        model = ScriptedModel([decision("finish", summary="Only inspected project truth")])
        with tempfile.TemporaryDirectory() as root:
            receipt = Path(root) / "host-bootstrap.jsonl"
            result = await NativeCreativeControl(session, model, max_turns=1,
                 host_tool_access=access, receipt_path=receipt).run("Independent creative project")
            self.assertEqual(session.calls, [("get_project", {})])
            self.assertEqual(model.observed[0]["native_project_presence_from_last_inspection"],
                             "absent")
            self.assertEqual(model.observed[0]["latest_events"][1]["kind"],
                             "host_project_bootstrap_observation")
            self.assertEqual(result["events"][1]["kind"], "host_project_bootstrap_observation")
            self.assertTrue(result["events"][1]["no_model_selected_mutation"])
            from studio_next.native_creative_audit import audit_native_journal
            audit = audit_native_journal(result["events"], host_tool_access=access)
            self.assertTrue(audit["journal_chain_structurally_valid"])
            self.assertEqual(audit["recorded_native_write_result_count"], 0)
            self.assertFalse(audit["video_editing_capability_complete"])

    async def test_bootstrap_no_read_grant_does_not_invent_state_or_call_editor(self):
        session = FakeSession()
        session.tools.append(SimpleNamespace(name="get_project",
             description="Project state", input_schema={"type": "object"}))
        grants = {x.name: ("write" if x.name in ("get_project", "update_text_clip")
                          else "read") for x in session.tools}
        model = ScriptedModel([decision("finish", summary="No automatic write-granted sensing")])
        result = await NativeCreativeControl(session, model, max_turns=1,
            host_tool_access=grants).run("A video project")
        self.assertEqual(session.calls, [])
        self.assertEqual(model.observed[0]["native_project_presence_from_last_inspection"],
                         "unknown")
        self.assertEqual(result["events"][1]["kind"], "model_finished")

    async def test_host_project_sensing_error_is_never_a_successful_observation(self):
        session = FakeSession()
        session.tools.append(SimpleNamespace(name="get_project",
            description="Native current project", input_schema={"type": "object"}))
        session.custom_response = SimpleNamespace(is_error=True, content=[
            SimpleNamespace(type="text", text="Private filesystem location is absent")])
        grants = {x.name: ("write" if x.name == "update_text_clip" else "read")
                  for x in session.tools}
        model = ScriptedModel([decision("finish", summary="Not a successful inspection")])
        result = await NativeCreativeControl(session, model, max_turns=1,
            host_tool_access=grants).run("Inspect project")
        self.assertEqual(result["events"][1]["kind"], "host_project_bootstrap_error")
        self.assertEqual(model.observed[0]["native_project_presence_from_last_inspection"], "unknown")
        self.assertNotIn("Private filesystem", json.dumps(result["events"]))
        self.assertFalse(result["native_editing_capability_complete"])


    async def test_bootstrap_receipt_write_failure_is_never_hidden_as_read_failure(self):
        from unittest.mock import patch
        session = FakeSession()
        session.tools.append(SimpleNamespace(name="get_project",
             description="Trusted native project snapshot",
             input_schema={"type": "object", "additionalProperties": False}))
        session.custom_response = SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps({
                "project": None, "mcp": {"hasProject": False}}))])
        grants = {x.name: ("write" if x.name == "update_text_clip" else "read")
                  for x in session.tools}
        model = ScriptedModel([decision("finish", summary="Must not run after audit failure")])
        original_append = NativeCreativeControl._append
        def reject_bootstrap_write(self, event):
            if event.get("kind") == "host_project_bootstrap_observation":
                raise OSError("Receipt fsync failed")
            return original_append(self, event)
        with patch.object(NativeCreativeControl, "_append", reject_bootstrap_write):
            with self.assertRaisesRegex(OSError, "Receipt fsync failed"):
                await NativeCreativeControl(session, model, max_turns=1,
                    host_tool_access=grants).run("No model activity without evidence")
        self.assertEqual(session.calls, [("get_project", {})])
        self.assertEqual(model.observed, [])

    async def test_indexed_capabilities_are_discovered_instead_of_dumping_120_tools(self):
        from studio_next.native_creative_audit import audit_native_journal
        session = FakeSession()
        for idx in range(120):
            session.tools.append(SimpleNamespace(
                name=f"future_extension_{idx:03d}",
                description="Unrelated native future animation parameter",
                input_schema={"type": "object"}))
        grants = {tool.name: ("write" if tool.name == "update_text_clip" else "read")
                  for tool in session.tools}
        model = ScriptedModel([
            decision("search", query="edit text", limit=3),
            decision("describe", tool="update_text_clip"),
            decision("invoke", tool="update_text_clip",
                     inputs={"clipId": "title-chosen-by-model", "text": "Original"}),
            decision("finish", summary="Control protocol exercised; no quality certification")
        ])
        with tempfile.TemporaryDirectory() as root:
            receipt = Path(root) / "fabric-ledger.jsonl"
            result = await NativeCreativeControl(session, model, max_turns=4,
                catalog_mode="indexed", host_tool_access=grants, receipt_path=receipt
            ).run("Make an original title")
            self.assertEqual(model.observed[0]["actual_granted_native_tools"], [])
            self.assertTrue(model.observed[0]["compact_tool_catalog"])
            self.assertNotIn("host_declared_tool_hints", model.observed[0])
            self.assertEqual(model.observed[0]["capability_overview"]["operation_count"],
                             len(session.tools))
            search = model.observed[1]["last_capability_search_result"]
            self.assertEqual(search["matches"][0]["tool"], "update_text_clip")
            self.assertEqual(search["matches"][0]["access"], "write")
            self.assertEqual(search["matches"][0]["parameters_sample"],
                             ["clipId", "text"])
            self.assertEqual([name for name, _ in session.calls], ["update_text_clip"])
            self.assertEqual(result["events"][1]["kind"], "capability_searched")
            self.assertNotIn("edit text", receipt.read_text())
            self.assertTrue(audit_native_journal(
                result["events"], host_tool_access=grants)["journal_chain_structurally_valid"])
            self.assertFalse(result["native_editing_capability_complete"])

    async def test_indexed_brain_cannot_invoke_invented_or_ungranted_tools(self):
        session = FakeSession()
        grants = {tool.name: "read" for tool in session.tools}
        for cmd in (decision("invoke", tool="does_not_exist", inputs={}),
                    decision("describe", tool="fake_tool")):
            with self.subTest(command=cmd), self.assertRaises(NativeCreativeControlError):
                await NativeCreativeControl(session, ScriptedModel([cmd]),
                    catalog_mode="indexed", host_tool_access=grants).run(
                    "No hallucinated BODY operations")
        self.assertEqual(session.calls, [])
        with self.assertRaisesRegex(NativeCreativeControlError, "requires trusted"):
            NativeCreativeControl(session, ScriptedModel([decision("search", query="movie")]),
                                  catalog_mode="indexed")

    async def test_real_2b_hallucinated_invoke_search_is_rejected_before_native_dispatch(self):
        session = FakeSession()
        grants = {x.name: ("write" if x.name == "update_text_clip" else "read")
                  for x in session.tools}
        model = ScriptedModel([
            decision("search", query="native text"),
            decision("invoke", tool="search", inputs={"query": "native edit", "limit": 10}),
        ])
        with self.assertRaisesRegex(NativeCreativeControlError, "ungranted|unsearched"):
            await NativeCreativeControl(session, model, catalog_mode="indexed",
                host_tool_access=grants, max_turns=2).run("Only exact returned editors exist")
        self.assertEqual(session.calls, [])
        self.assertNotIn("search", model.observed[1]["selectable_native_tools"])
        self.assertLessEqual(len(model.observed[1]["selectable_native_tools"]), 8)

    async def test_indexed_search_is_private_metadata_not_editor_execution(self):
        session = FakeSession()
        grants = {x.name: "read" for x in session.tools}
        model = ScriptedModel([
            decision("search", query="magical nonexisting world manipulation"),
            decision("finish", summary="No unsupported tool was invented")
        ])
        result = await NativeCreativeControl(session, model, max_turns=2,
            catalog_mode="indexed", host_tool_access=grants).run("An original film")
        self.assertFalse(model.observed[1]["last_capability_search_result"]["matches"])
        self.assertEqual(session.calls, [])
        self.assertEqual(result["events"][1]["result_tool_names"], [])
        self.assertFalse(result["native_editing_capability_complete"])



    async def test_host_observed_missing_project_preloads_real_native_possibilities(self):
        from studio_next.native_creative_audit import audit_native_journal
        session = FakeSession()
        session.tools += [
            SimpleNamespace(name="get_project", description="Inspect editable native project",
                            input_schema={"type": "object"}),
            SimpleNamespace(name="create_project", description="Create native editable project",
                            input_schema={"type": "object", "properties": {
                                "name": {"type": "string"}}}),
            SimpleNamespace(name="open_project", description="Open existing native project",
                            input_schema={"type": "object", "properties": {
                                "projectName": {"type": "string"}}}),
            SimpleNamespace(name="import_asset_from_path",
                            description="Import footage to current project",
                            input_schema={"type": "object", "properties": {
                                "path": {"type": "string"}}}),
        ]
        session.custom_response = SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps({
                "project": None, "mcp": {"hasProject": False}}))])
        grants = {x.name: ("read" if x.name in ("get_project", "get_timeline")
                         else "write") for x in session.tools}
        model = ScriptedModel([
            decision("describe", tool="create_project"),
            decision("finish", summary="Real options known; art still model-selected"),
        ])
        result = await NativeCreativeControl(
            session, model, max_turns=2, catalog_mode="indexed",
            host_tool_access=grants,
            host_preconditions={"import_asset_from_path": ["project_open"]},
            host_possible_effects={
                "create_project": ["project_open"],
                "open_project": ["project_open"],
            }).run("A source-owned film")
        initial = model.observed[0]
        self.assertEqual(initial["native_project_presence_from_last_inspection"], "absent")
        self.assertEqual(set(initial["selectable_native_tools"]),
                         {"create_project", "open_project"})
        self.assertEqual(set(x["tool"] for x in initial[
            "last_capability_search_result"]["matches"]),
            {"create_project", "open_project"})
        self.assertEqual(session.calls, [("get_project", {})])
        self.assertEqual(result["events"][2]["kind"], "host_capability_frontier")
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=grants)["journal_chain_structurally_valid"])
        self.assertFalse(result["native_editing_capability_complete"])

    async def test_unknown_project_state_does_not_grant_invented_affordances(self):
        session = FakeSession()
        session.tools += [
            SimpleNamespace(name="get_project", description="Project state",
                            input_schema={"type": "object"}),
            SimpleNamespace(name="create_project", description="Create project",
                            input_schema={"type": "object"}),
        ]
        session.custom_response = SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps({
                "mcp": {"hasProject": False}}))])
        grants = {x.name: ("read" if x.name == "get_project" else "write")
                  for x in session.tools}
        model = ScriptedModel([decision("finish", summary="Unknown state")])
        result = await NativeCreativeControl(session, model, max_turns=1,
            catalog_mode="indexed", host_tool_access=grants,
            host_possible_effects={"create_project": ["project_open"]}).run("Video")
        self.assertEqual(model.observed[0]["selectable_native_tools"], [])
        self.assertNotIn("host_capability_frontier",
                         [e["kind"] for e in result["events"]])


    async def test_wrong_order_import_is_rejected_without_stateful_editor_rpc(self):
        from studio_next.native_creative_audit import audit_native_journal
        session = FakeSession()
        session.tools += [
            SimpleNamespace(name="get_project", description="Read native project",
                            input_schema={"type": "object"}),
            SimpleNamespace(name="create_project", description="Create native project",
                            input_schema={"type": "object", "properties": {
                                "name": {"type": "string"}}}),
            SimpleNamespace(name="import_asset_from_path",
                            description="Import asset to an open project",
                            input_schema={"type": "object", "properties": {
                                "path": {"type": "string"}}}),
        ]
        session.custom_response = SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="text", text=json.dumps({
                "project": None, "mcp": {"hasProject": False}}))])
        grants = {x.name: ("read" if x.name in ("get_project", "get_timeline")
                          else "write") for x in session.tools}
        model = ScriptedModel([
            decision("search", query="import asset"),
            decision("invoke", tool="import_asset_from_path",
                     inputs={"path": "/authorized/source.mp4"}),
            decision("finish", summary="No mutation without an actual project"),
        ])
        result = await NativeCreativeControl(session, model,
            catalog_mode="indexed", host_tool_access=grants, max_turns=3,
            host_preconditions={"import_asset_from_path": ["project_open"]},
            host_possible_effects={"create_project": ["project_open"]}).run(
                "Create an independently authored video")
        self.assertEqual(session.calls, [("get_project", {})])
        invalid = [e for e in result["events"] if e["kind"] == "model_action_rejected"]
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0]["validation_keyword"], "host_precondition")
        self.assertEqual(invalid[0]["schema_location"], "project_open")
        self.assertTrue(invalid[0]["no_native_dispatch"])
        self.assertEqual(model.observed[-1]["last_rejected_native_action_feedback"]
                         ["missing_machine_facts"], ["project_open"])
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=grants)["journal_chain_structurally_valid"])
        self.assertFalse(result["native_editing_capability_complete"])


    async def test_ambiguous_application_write_receipts_cannot_mint_completion_proof(self):
        """A successful MCP transport is not proof the editor applied an edit."""
        from studio_next.native_creative_audit import audit_native_journal
        invalid_responses = (
            json.dumps({"result": {"created": True}}),  # Missing explicit success
            json.dumps({"success": None}),
            json.dumps({"success": "true"}),
            json.dumps({"success": 1}),  # Must reject bool-like JSON integers
            json.dumps({"success": True, "result": {"previewOnly": True}}),
            json.dumps({"success": True, "result": {"previewOnly": None}}),
            '{"success":true,"success":false}',  # Duplicate receipt keys
            "not-json-at-all",
        )
        for text in invalid_responses:
            with self.subTest(response=text):
                session = FakeSession()
                session.custom_response = SimpleNamespace(
                    is_error=False, content=[SimpleNamespace(type="text", text=text)])
                grants = {tool.name: ("write" if tool.name == "update_text_clip" else "read")
                          for tool in session.tools}
                model = ScriptedModel([
                    decision("invoke", tool="update_text_clip",
                             inputs={"clipId": "one", "text": "Changed"}),
                ])
                required = ("native_write_acknowledged",)
                outcome = await NativeCreativeControl(
                    session, model, max_turns=1, host_tool_access=grants,
                    required_evidence=required).run("Create one editable original revision")
                self.assertEqual(outcome["status"], "native_error_requires_state_reconciliation")
                self.assertEqual([name for name, _ in session.calls], ["update_text_clip"])
                self.assertEqual(outcome["events"][-1]["kind"], "native_tool_uncertain_outcome")
                self.assertTrue(outcome["events"][-1]["must_reconcile_native_state"])
                self.assertTrue(outcome["events"][-1]["no_automatic_retry"])
                self.assertNotIn(text, json.dumps(outcome["events"]))
                proof = audit_native_journal(
                    outcome["events"], host_tool_access=grants,
                    expected_required_evidence=required)
                self.assertEqual(proof["recorded_native_write_result_count"], 0)
                self.assertFalse(outcome["native_editing_capability_complete"])

    async def test_explicit_application_success_still_grants_write_proof(self):
        from studio_next.native_creative_audit import audit_native_journal
        session = FakeSession()
        session.custom_response = SimpleNamespace(
            is_error=False, content=[SimpleNamespace(type="text", text=json.dumps({
                "success": True, "result": {"previewOnly": False, "editable": True}}))])
        grants = {tool.name: ("write" if tool.name == "update_text_clip" else "read")
                  for tool in session.tools}
        model = ScriptedModel([
            decision("invoke", tool="update_text_clip",
                     inputs={"clipId": "one", "text": "Changed"}),
            decision("finish", summary="One confirmed native edit, not a certified movie"),
        ])
        outcome = await NativeCreativeControl(
            session, model, max_turns=2, host_tool_access=grants,
            required_evidence=("native_write_acknowledged",)).run("Edit original title")
        self.assertEqual(outcome["status"], "model_finished_unverified")
        self.assertEqual(sum(x["kind"] == "native_tool_result" for x in outcome["events"]), 1)
        self.assertEqual(model.observed[1]["missing_completion_evidence"], [])
        self.assertEqual(audit_native_journal(
            outcome["events"], host_tool_access=grants)["recorded_native_write_result_count"], 1)

    async def test_read_observations_do_not_require_mutation_receipts(self):
        session = FakeSession()
        session.custom_response = SimpleNamespace(
            is_error=False, content=[SimpleNamespace(type="text", text='{"timeline":[]}')])
        grants = {tool.name: ("write" if tool.name == "update_text_clip" else "read")
                  for tool in session.tools}
        model = ScriptedModel([
            decision("invoke", tool="get_timeline", inputs={}),
            decision("finish", summary="Read only, no creative success asserted"),
        ])
        outcome = await NativeCreativeControl(session, model, max_turns=2,
            host_tool_access=grants).run("Inspect the real timeline")
        self.assertEqual(outcome["status"], "model_finished_unverified")
        self.assertEqual([x[0] for x in session.calls], ["get_timeline"])


    async def test_trial_single_project_policy_blocks_repeated_model_create(self):
        """Actual saved project beats the small model's repeated create guesses."""
        from studio_next.native_creative_audit import audit_native_journal
        session = FakeSession()
        session.tools += [
            SimpleNamespace(name="get_project", description="Inspect actual project identity",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="create_project", description="Create native project",
                            input_schema={"type": "object", "properties": {
                                "name": {"type": "string"},
                                "previewOnly": {"type": "boolean"}}}),
        ]
        create_count = 0
        async def native(name, inputs):
            nonlocal create_count
            session.calls.append((name, inputs))
            if name == "get_project":
                payload = {"project": {"id": "actual-native"} if create_count else None,
                           "mcp": {"hasProject": bool(create_count)}}
            elif name == "create_project":
                create_count += 1
                payload = {"success": True, "result": {"previewOnly": False}}
            else:
                payload = {"timeline": [], "real_project": bool(create_count)}
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text=json.dumps(payload))])
        session.call_tool = native
        grants = {t.name: ("write" if t.name == "create_project" else "read")
                  for t in session.tools}
        model = ScriptedModel([
            decision("invoke", tool="create_project",
                     inputs={"name": "One native movie", "previewOnly": False}),
            decision("search", query="create_project", limit=1),
            decision("invoke", tool="create_project",
                     inputs={"name": "Duplicated movie", "previewOnly": False}),
            decision("search", query="get_timeline", limit=1),
            decision("invoke", tool="get_timeline", inputs={}),
            decision("finish", summary="Only one native project; not an artistic pass"),
        ])
        result = await NativeCreativeControl(
            session, model, max_turns=6, host_tool_access=grants,
            catalog_mode="indexed",
            host_possible_effects={"create_project": ["project_open"]},
            host_once_after_acknowledged_write=("create_project",)).run(
                "Build one original editable video")
        self.assertEqual(create_count, 1)
        self.assertEqual(result["status"], "model_finished_unverified")
        self.assertEqual(model.observed[1]["selectable_native_tools"], [])
        self.assertEqual(model.observed[1]["native_project_presence_from_last_inspection"],
                         "present")
        self.assertNotIn("host_granted_search_terms",
                         model.observed[0]["capability_overview"])
        self.assertIn("timeline",
                      model.observed[1]["capability_overview"]["host_granted_search_terms"])
        self.assertLess(len(json.dumps(model.observed[1]["capability_overview"])), 950)
        # Re-searching the exhausted write returns no executable result, even
        # though the original host operation still exists in the catalog.
        filtered = model.observed[2]["last_capability_search_result"]
        self.assertEqual(filtered["matches"], [])
        self.assertEqual(filtered["already_acknowledged_host_once_tools"],
                         ["create_project"])
        self.assertTrue(filtered["host_requires_new_capability_query"])
        self.assertEqual(model.observed[2]["selectable_native_tools"], [])
        self.assertEqual(model.observed[3]["last_rejected_native_action_feedback"]
                         ["validation_keyword"], "host_single_write")
        self.assertEqual([name for name, _ in session.calls],
                         ["get_project", "create_project", "get_project", "get_timeline"])
        self.assertEqual(sum(e["kind"] == "native_tool_result" and
                             e.get("tool") == "create_project" for e in result["events"]), 1)
        self.assertTrue(audit_native_journal(result["events"],
            host_tool_access=grants)["journal_chain_structurally_valid"])

    async def test_preview_does_not_exhaust_single_project_policy(self):
        session = FakeSession()
        session.tools += [
            SimpleNamespace(name="create_project", description="Create or preview",
                            input_schema={"type": "object", "properties": {
                                "name": {"type": "string"}, "previewOnly": {"type": "boolean"}}}),
        ]
        async def native(name, args):
            session.calls.append((name, args))
            preview = args.get("previewOnly", True)
            payload = {"success": not preview, "result": {"previewOnly": preview}}
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text=json.dumps(payload))])
        session.call_tool = native
        grants = {tool.name: ("write" if tool.name == "create_project" else "read")
                  for tool in session.tools}
        model = ScriptedModel([
            decision("search", query="create_project", limit=1),
            decision("invoke", tool="create_project",
                     inputs={"name": "Proposal", "previewOnly": True}),
            decision("invoke", tool="create_project",
                     inputs={"name": "Applied", "previewOnly": False}),
            decision("finish", summary="Native project, not full video"),
        ])
        result = await NativeCreativeControl(session, model, max_turns=4,
            catalog_mode="indexed", host_tool_access=grants,
            host_once_after_acknowledged_write=("create_project",)).run(
                "Create an editable project from a real model choice")
        self.assertEqual(result["status"], "model_finished_unverified")
        self.assertEqual([name for name, _ in session.calls],
                         ["create_project", "create_project"])
        self.assertEqual(sum(e["kind"] == "native_tool_preview" for e in result["events"]), 1)
        self.assertEqual(sum(e["kind"] == "native_tool_result" for e in result["events"]), 1)

    async def test_host_one_write_policy_requires_only_granted_write_tools(self):
        session = FakeSession()
        for bad in (("get_timeline",), ("unknown",), ("update_text_clip", "update_text_clip")):
            with self.subTest(policy=bad), self.assertRaises(NativeCreativeControlError):
                NativeCreativeControl(session, ScriptedModel([]),
                    host_tool_access={"get_timeline": "read",
                                      "update_text_clip": "write"},
                    host_once_after_acknowledged_write=bad)


    async def test_lagging_native_project_snapshot_converges_using_read_only_reconciliation(self):
        from studio_next.native_creative_audit import audit_native_journal
        session = FakeSession()
        session.tools += [
            SimpleNamespace(name="get_project", description="Real host project",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="create_project", description="Create real project",
                            input_schema={"type": "object", "properties": {
                                "name": {"type": "string"}, "previewOnly": {"type": "boolean"}}}),
        ]
        reads = 0
        async def native(name, args):
            nonlocal reads
            session.calls.append((name, args))
            if name == "get_project":
                reads += 1
                present = reads >= 3  # bootstrap absent, first post-write stale
                payload = {"mcp": {"hasProject": present},
                           "project": {"id": "real-after-snapshot-lag"} if present else None}
            else:
                payload = {"success": True, "result": {"previewOnly": False}}
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text=json.dumps(payload))])
        session.call_tool = native
        grants = {t.name: ("write" if t.name == "create_project" else "read")
                  for t in session.tools}
        model = ScriptedModel([
            decision("invoke", tool="create_project",
                     inputs={"name": "Trusted original", "previewOnly": False}),
            decision("finish", summary="One native project, not a completed film")])
        result = await NativeCreativeControl(
            session, model, max_turns=2, catalog_mode="indexed",
            host_tool_access=grants,
            host_once_after_acknowledged_write=("create_project",),
            host_possible_effects={"create_project": ["project_open"]}).run(
                "Create one editable original project")
        self.assertEqual(result["status"], "model_finished_unverified")
        self.assertEqual([c[0] for c in session.calls],
                         ["get_project", "create_project", "get_project", "get_project"])
        self.assertEqual([x["native_project_presence_from_last_inspection"]
                          for x in model.observed], ["absent", "present"])
        self.assertIsNone(model.observed[1]["last_host_project_write_reconciliation"])
        inspections = [e for e in result["events"] if e["kind"] ==
                       "host_project_post_write_observation"]
        self.assertEqual([(e["read_attempt"], e["project_presence"])
                          for e in inspections], [(1, "absent"), (2, "present")])
        self.assertTrue(audit_native_journal(
            result["events"], host_tool_access=grants)["journal_chain_structurally_valid"])

    async def test_two_contradictory_project_reads_never_establish_false_absence(self):
        from studio_next.native_creative_audit import audit_native_journal, NativeJournalError
        session = FakeSession()
        session.tools += [
            SimpleNamespace(name="get_project", description="Native project identity",
                            input_schema={"type": "object", "properties": {}}),
            SimpleNamespace(name="create_project", description="Create native project",
                            input_schema={"type": "object", "properties": {"name": {"type": "string"}}}),
        ]
        async def native(name, args):
            session.calls.append((name, args))
            payload = ({"project": None, "mcp": {"hasProject": False}}
                       if name == "get_project" else
                       {"success": True, "result": {"previewOnly": False}})
            return SimpleNamespace(is_error=False, content=[
                SimpleNamespace(type="text", text=json.dumps(payload))])
        session.call_tool = native
        grants = {t.name: ("write" if t.name == "create_project" else "read")
                  for t in session.tools}
        model = ScriptedModel([
            decision("invoke", tool="create_project", inputs={"name": "Once"}),
            decision("finish", summary="No unverified project state inferred"),
        ])
        outcome = await NativeCreativeControl(
            session, model, max_turns=2, host_tool_access=grants,
            catalog_mode="indexed",
            host_once_after_acknowledged_write=("create_project",),
            host_possible_effects={"create_project": ["project_open"]}).run(
                "Produce an editable original project")
        self.assertEqual([c[0] for c in session.calls],
                         ["get_project", "create_project", "get_project", "get_project"])
        self.assertEqual(model.observed[1]["native_project_presence_from_last_inspection"],
                         "unknown")
        warning = model.observed[1]["last_host_project_write_reconciliation"]
        self.assertTrue(warning["project_state_unknown"])
        self.assertTrue(warning["must_inspect_native_project"])
        self.assertEqual(outcome["events"][-2]["kind"],
                         "host_project_post_write_inconsistent")
        self.assertTrue(audit_native_journal(
            outcome["events"], host_tool_access=grants)["journal_chain_structurally_valid"])
        tampered = [dict(e) for e in outcome["events"]]
        second = next(i for i,e in enumerate(tampered)
                      if e.get("read_attempt") == 2)
        tampered[second]["read_attempt"] = 3
        with self.assertRaises(NativeJournalError):
            audit_native_journal(tampered, host_tool_access=grants)


if __name__ == "__main__":
    unittest.main()

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
                            input_schema={"type": "object", "properties": {"clipId": {"type": "string"}}}),
            SimpleNamespace(name="zx7_verify_native_export", description="Independently verify final movie",
                            input_schema={"type": "object"}),
            SimpleNamespace(name="zx7_observe_verified_export_frame", description="Read verified PNG",
                            input_schema={"type": "object", "properties": {"at_seconds": {"type": "number"}}})]
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
        self.assertEqual(len(hints[1]["description"]), 160)
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


if __name__ == "__main__":
    unittest.main()

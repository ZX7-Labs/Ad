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
            decision("invoke", tool="zx7_observe_verified_export_frame",
                     inputs={"path": "/bound/movie.mp4", "at_seconds": 1}),
            decision("finish", summary="Still an unverified review"),
        ])
        result = await NativeCreativeControl(session, model).run("Review an actual source edit")
        self.assertEqual(len(model.images_observed), 1)
        self.assertEqual(model.images_observed[0][1], [("image/png", png)])
        self.assertEqual(model.images_observed[0][0]["observed_picture_sha256"], [sha])
        self.assertFalse(result["artistic_quality_independently_approved"])
        self.assertNotIn(base64.b64encode(png).decode(), json.dumps(result))
        model2 = ScriptedModel([
            decision("invoke", tool="zx7_observe_verified_export_frame", inputs={})])
        session.custom_response.content[0].text = json.dumps({
            "export_sha256": export, "png_sha256": "0" * 64})
        with self.assertRaisesRegex(NativeCreativeControlError, "SHA-bound"):
            await NativeCreativeControl(session, model2).run("Review a corrupted frame")

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

    async def test_audio_content_not_silently_translated_to_language_or_approved(self):
        session = FakeSession()
        session.custom_response = SimpleNamespace(is_error=False, content=[
            SimpleNamespace(type="audio", data=base64.b64encode(b"RIFF").decode())])
        model = ScriptedModel([decision("invoke", tool="get_timeline", inputs={})])
        with self.assertRaisesRegex(NativeCreativeControlError, "audio-capable"):
            await NativeCreativeControl(session, model).run("Listen to my mix")

    async def test_nonexistent_or_duplicate_native_tool_descriptors_refused(self):
        session = FakeSession()
        session.tools.append(session.tools[0])
        with self.assertRaisesRegex(NativeCreativeControlError, "duplicate"):
            await NativeCreativeControl(session, ScriptedModel([])).run("A film")
        with self.assertRaisesRegex(NativeCreativeControlError, "finite turn"):
            NativeCreativeControl(FakeSession(), ScriptedModel([]), max_turns=0)


if __name__ == "__main__":
    unittest.main()

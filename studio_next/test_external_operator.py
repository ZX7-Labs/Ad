"""Technical external-operator handshake tests, not an AI quality certificate."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

from studio_next.external_operator import (
    ExternalOperatorError, ExternalOperatorModel, PROTOCOL, reply, _write_private,
)
from studio_next.native_creative_control import NativeCreativeControl
from studio_next.test_native_creative_control import FakeSession


class ExternalOperatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "private"
        self.root.mkdir(mode=0o700)
        os.chmod(self.root, 0o700)

    def model(self, timeout=2):
        return ExternalOperatorModel(self.root, system_prompt="Host controls grants",
                                     timeout_seconds=timeout, poll_seconds=0.01)

    def answer(self, model, turn, action, change=None):
        path = model.session_dir / f"request-{turn:04d}.json"
        for _ in range(190):
            if path.exists():
                break
            time.sleep(0.01)
        self.assertTrue(path.exists(), "No real request published")
        raw = path.read_bytes()
        request = json.loads(raw)
        decision = model.session_dir / f"decision-{turn:04d}.json"
        decision.write_text(json.dumps(action))
        os.chmod(decision, 0o600)
        if change is None:
            reply(model.session_dir, turn, decision)
        else:
            body = {"protocol": PROTOCOL, "session_id": model.session_id,
                    "turn": turn, "nonce": request["nonce"],
                    "request_sha256": hashlib.sha256(raw).hexdigest(),
                    "decision": action}
            body.update(change)
            _write_private(model.session_dir / f"response-{turn:04d}.json",
                           json.dumps(body).encode())
        return request

    def run_turn(self, model, action, *, method="decide", media=None, change=None):
        result = {}
        def work():
            try:
                model_method = getattr(model, method)
                result["decision"] = (model_method({"host_context": "actual"})
                                      if media is None else
                                      model_method({"host_context": "actual"}, media))
            except Exception as exc:
                result["error"] = exc
        thread = threading.Thread(target=work)
        thread.start()
        request = self.answer(model, 1, action, change)
        thread.join(3)
        self.assertFalse(thread.is_alive())
        return request, result

    def test_decision_round_trip_and_private_session(self):
        model = self.model()
        decision = {"action": "search", "arguments": {"query": "import"},
                    "reason": "model-chosen"}
        request, result = self.run_turn(model, decision)
        self.assertEqual(result["decision"], decision)
        self.assertEqual(request["session_id"], model.session_id)
        self.assertEqual(request["context"], {"host_context": "actual"})
        self.assertEqual(request["media"], [])
        self.assertFalse(json.loads((model.session_dir / "session.json").read_text())[
            "model_identity_verified"])
        second = self.model()
        self.assertNotEqual(model.session_id, second.session_id)
        self.assertFalse((second.session_dir / "request-0001.json").exists())

    def test_stale_replayed_cross_session_or_invalid_binding_rejected(self):
        decision = {"action": "finish", "arguments": {"summary": "not approved"},
                    "reason": "end"}
        for change in ({"request_sha256": "0"*64}, {"turn": 999},
                       {"nonce": "stale"}, {"session_id": "wrong"}):
            with self.subTest(change=change):
                _, result = self.run_turn(self.model(), decision, change=change)
                self.assertIsInstance(result.get("error"), ExternalOperatorError)
                self.assertNotIn("decision", result)

    def test_timeout_and_world_readable_mailbox_fail_closed(self):
        with self.assertRaisesRegex(ExternalOperatorError, "timed out"):
            self.model(timeout=0.12).decide({"no": "operation"})
        os.chmod(self.root, 0o755)
        with self.assertRaisesRegex(ExternalOperatorError, "private"):
            self.model()

    def test_real_image_and_audio_files_are_sha_bound_not_text_proxies(self):
        png = b"\x89PNG\r\n\x1a\n" + b"pixels"*12
        wav = b"RIFF" + b"\x00"*4 + b"WAVE" + b"audio"*12
        for kind, mime, data, method in (
            ("image", "image/png", png, "decide_with_images"),
            ("audio", "audio/wav", wav, "decide_with_audio"),
        ):
            with self.subTest(kind=kind):
                model = self.model()
                request, result = self.run_turn(model, {"action": "search",
                    "arguments": {"query": "native"}, "reason": "chosen"},
                    method=method, media=[(mime, data)])
                self.assertIn("decision", result)
                item = request["media"][0]
                self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(item["kind"], kind)
                self.assertEqual((model.session_dir / item["file"]).read_bytes(), data)

    def test_wrong_media_or_duplicate_reply_never_enters_editor(self):
        model = self.model()
        with self.assertRaises(ExternalOperatorError):
            model.decide_with_images({}, [("image/png", b"wrong")])
        with self.assertRaises(ExternalOperatorError):
            model.decide_with_audio({}, [("audio/wav", b"wrong")])
        request = {"protocol": PROTOCOL, "session_id": model.session_id,
                   "turn": 1, "nonce": "abc", "context": {}, "media": []}
        raw = model.session_dir / "request-0001.json"
        raw.write_text(json.dumps(request))
        os.chmod(raw, 0o600)
        decision_file = model.session_dir / "decision.json"
        decision_file.write_text('{"action":"search","arguments":{"query":"edit"},"reason":"chosen"}')
        os.chmod(decision_file, 0o600)
        reply(model.session_dir, 1, decision_file)
        with self.assertRaisesRegex(ExternalOperatorError, "overwrite"):
            reply(model.session_dir, 1, decision_file)

    def test_existing_native_controller_accepts_operator_seat_without_bypassing_host(self):
        editor = FakeSession()
        model = self.model()
        outcome = {}
        def work():
            try:
                outcome["run"] = asyncio.run(NativeCreativeControl(
                    editor, model, max_turns=2).run("Owner brief"))
            except Exception as exc:
                outcome["error"] = exc
        thread = threading.Thread(target=work)
        thread.start()
        self.answer(model, 1, {"action": "invoke", "arguments": {
            "tool": "get_timeline", "inputs": {}},
            "reason": "Independent native inspection"})
        self.answer(model, 2, {"action": "finish", "arguments": {
            "summary": "Only inspected. No edit, export or quality acceptance."},
            "reason": "Stop the protocol fixture"})
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome, outcome)
        self.assertEqual(editor.calls, [("get_timeline", {})])
        self.assertEqual(outcome["run"]["status"], "model_finished_unverified")
        self.assertFalse(outcome["run"]["native_editing_capability_complete"])


if __name__ == "__main__":
    unittest.main()

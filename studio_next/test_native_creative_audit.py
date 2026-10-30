"""Adversarial technical trace tests, not a neural-creativity benchmark."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from studio_next.native_creative_audit import (
    NativeJournalError, audit_native_journal, read_native_journal,
)


A = "a" * 64
B = "b" * 64
C = "c" * 64
HOST = {
    "export_timeline": "write",
    "update_text_clip": "write",
    "get_timeline": "read",
    "zx7_verify_native_export": "read",
    "zx7_observe_verified_export_frame": "read",
    "zx7_observe_verified_export_audio": "read",
}


def trace():
    events = []
    def add(kind, **kw):
        events.append({"sequence": len(events), "kind": kind, **kw})
    def call(tool, n):
        add("native_tool_submitted", tool=tool, turn=n,
            inputs_sha256=hashlib.sha256(f"tool-{n}".encode()).hexdigest(),
            model_reason=f"Independent model requested tool at turn {n}",
            uncertain_write_do_not_replay=True)
    def result(tool, n, **kw):
        fields = dict(tool=tool, turn=n, text_sha256=[C],
                      image_sha256=[], audio_sha256=None,
                      independently_verified_export_sha256=None, observed_export_sha256=None,
                      human_or_artistic_quality_approved=False)
        fields.update(kw)
        add("native_tool_result", **fields)
    # Build a real-shaped transcript with *fixture bytes only*. It cannot
    # certify actual model intelligence or physical media quality.
    add("session_started", brief_sha256=A,
        model_id_reported="scripted-fixture-NOT-NEURAL",
        neural_autonomy_or_artistic_quality_verified=False)
    call("get_timeline", 0); result("get_timeline", 0)
    call("update_text_clip", 1); result("update_text_clip", 1)
    call("export_timeline", 2); result("export_timeline", 2)
    call("zx7_verify_native_export", 3)
    result("zx7_verify_native_export", 3,
           independently_verified_export_sha256=A)
    call("zx7_observe_verified_export_frame", 4)
    result("zx7_observe_verified_export_frame", 4,
           image_sha256=[C], observed_export_sha256=A)
    call("update_text_clip", 5); result("update_text_clip", 5)
    call("export_timeline", 6); result("export_timeline", 6)
    call("zx7_verify_native_export", 7)
    result("zx7_verify_native_export", 7,
           independently_verified_export_sha256=B)
    call("zx7_observe_verified_export_frame", 8)
    result("zx7_observe_verified_export_frame", 8,
           image_sha256=[C], observed_export_sha256=B)
    add("model_finished", turn=9, summary="I revised it",
        creative_quality_independently_approved=False)
    return events


class NativeCreativeAuditTests(unittest.TestCase):
    def test_honest_technical_custody_without_fake_artistic_claim(self):
        evidence = audit_native_journal(trace(), host_tool_access=HOST)
        self.assertTrue(evidence["journal_chain_structurally_valid"])
        self.assertEqual(evidence["recorded_native_write_result_count"], 4)
        self.assertEqual(evidence["export_digests_independently_reported_by_native_host"], [A, B])
        self.assertEqual(evidence["observed_verified_export_digests"], [A, B])
        self.assertGreater(evidence["model_selected_writes_after_first_verified_observation"], 0)
        self.assertFalse(evidence["physical_media_bytes_redecoded_by_this_audit"])
        self.assertFalse(evidence["real_neural_model_weights_or_inference_independently_attested"])
        self.assertFalse(evidence["human_or_artistic_quality_approved"])
        self.assertFalse(evidence["video_editing_capability_complete"])

    def test_forgery_and_unbound_proofs_fail_closed(self):
        variants = []
        variants.append(lambda x: x[0].update(brief_sha256="bad"))
        variants.append(lambda x: x[5].update(sequence=1))
        variants.append(lambda x: x[10].update(observed_export_sha256=B))
        variants.append(lambda x: x[10].update(tool="get_timeline"))
        variants.append(lambda x: x[10].update(human_or_artistic_quality_approved=True))
        variants.append(lambda x: x[10].update(image_sha256=[]))
        variants.append(lambda x: x[10].update(image_sha256=["invalid"]))
        variants.append(lambda x: x[6].update(independently_verified_export_sha256="c"*64))
        variants.append(lambda x: x[7].update(tool="ungranted_media_reader"))
        variants.append(lambda x: x[11].update(inputs_sha256="0"*63))
        variants.append(lambda x: x[-1].update(creative_quality_independently_approved=True))
        for change in variants:
            events=trace()
            change(events)
            with self.subTest(change=str(change)), self.assertRaises(NativeJournalError):
                audit_native_journal(events, host_tool_access=HOST)

    def test_broken_write_history_never_silently_reports_completion(self):
        events = trace()
        with self.assertRaisesRegex(NativeJournalError, "outcome"):
            audit_native_journal(events[:-1] + [{"sequence": len(events)-1,
                "kind": "native_tool_submitted", "tool": "update_text_clip", "turn": 9,
                "inputs_sha256": A, "model_reason": "lost write"}],
                host_tool_access=HOST)
        events = trace()
        pos = next(i for i, event in enumerate(events)
                   if event["kind"] == "native_tool_result" and event["tool"] == "update_text_clip")
        events[pos] = {"sequence": pos, "kind": "native_tool_reported_error",
                       "tool": "update_text_clip", "turn": 1,
                       "must_reconcile_native_state": True}
        with self.assertRaisesRegex(NativeJournalError, "followed by unsafe"):
            audit_native_journal(events, host_tool_access=HOST)
        events = trace()
        events[-1].update(kind="model_finished",
                          creative_quality_independently_approved=True)
        with self.assertRaises(NativeJournalError):
            audit_native_journal(events, host_tool_access=HOST)

    def test_sensor_roles_are_host_grants_not_a_model_imitation(self):
        events=trace()
        with self.assertRaisesRegex(NativeJournalError, "host grant"):
            audit_native_journal(events, host_tool_access={
                k:v for k,v in HOST.items() if k != "zx7_verify_native_export"})
        events=trace()
        obs=next(e for e in events if e["kind"] == "native_tool_result"
                 and e["tool"] == "zx7_observe_verified_export_frame")
        obs["audio_sha256"]=A
        with self.assertRaisesRegex(NativeJournalError, "audio"):
            audit_native_journal(events, host_tool_access=HOST)

    def test_model_inference_failure_is_terminal_and_cannot_be_forged_as_completion(self):
        events = [
            {"kind": "session_started", "sequence": 0, "brief_sha256": A},
            {"kind": "model_decision_failed", "sequence": 1, "turn": 0,
             "measured_model_wall_ms": 2.1, "error_type": "TimeoutError",
             "no_automatic_retry": True,
             "creative_quality_independently_approved": False},
        ]
        evidence = audit_native_journal(events, host_tool_access=HOST)
        self.assertEqual(evidence["model_reported_end_state"], "model_decision_failed")
        self.assertFalse(evidence["video_editing_capability_complete"])
        for corrupt in (
            {"no_automatic_retry": False},
            {"measured_model_wall_ms": -1},
            {"measured_model_wall_ms": float("inf")},
            {"measured_model_wall_ms": True},
            {"creative_quality_independently_approved": True},
        ):
            broken = copy.deepcopy(events)
            broken[-1].update(corrupt)
            with self.subTest(corrupt=corrupt), self.assertRaises(NativeJournalError):
                audit_native_journal(broken, host_tool_access=HOST)
        extended = copy.deepcopy(events)
        extended.append({"kind": "model_finished", "sequence": 2, "turn": 1,
                         "summary": "fake completion",
                         "creative_quality_independently_approved": False})
        with self.assertRaises(NativeJournalError):
            audit_native_journal(extended, host_tool_access=HOST)

    def test_a_real_jsonl_file_cannot_be_swapped_by_symlink_or_forged_keys(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            source=root/"verified.jsonl"
            source.write_text("".join(json.dumps(ev,sort_keys=True)+"\n" for ev in trace()))
            self.assertEqual(read_native_journal(source), trace())
            redirected=root/"alias.jsonl"
            redirected.symlink_to(source)
            with self.assertRaisesRegex(NativeJournalError,"symlink"):
                read_native_journal(redirected)
            source.write_bytes(b'{"sequence":0,"sequence":1,"kind":"session_started"}\n')
            with self.assertRaisesRegex(NativeJournalError,"Duplicate"):
                read_native_journal(source)
            source.write_bytes(b'{"sequence":0,"kind":"session_started","v":NaN}\n')
            with self.assertRaisesRegex(NativeJournalError,"Nonfinite"):
                read_native_journal(source)
            source.write_bytes(b'{"sequence":0,"kind":"session_started","v":1e999}\n')
            with self.assertRaisesRegex(NativeJournalError,"Overflowed"):
                read_native_journal(source)
            source.write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(NativeJournalError,"UTF-8"):
                read_native_journal(source)


    def test_new_private_intent_receipts_and_legacy_proofs_are_both_checked(self):
        events = trace()
        for event in events:
            if event["kind"] == "native_tool_submitted":
                reason = event.pop("model_reason")
                event["model_reason_sha256"] = hashlib.sha256(reason.encode()).hexdigest()
                event["model_reason_utf8_bytes"] = len(reason.encode())
            if event["kind"] == "model_finished":
                summary = event.pop("summary")
                event["summary_sha256"] = hashlib.sha256(summary.encode()).hexdigest()
                event["summary_utf8_bytes"] = len(summary.encode())
        accepted = audit_native_journal(events, host_tool_access=HOST)
        self.assertTrue(accepted["journal_chain_structurally_valid"])
        # Ambiguous old+new envelopes must not become an escape hatch.
        modifications = [
            (1, {"model_reason": "private leak"}),
            (1, {"model_reason_utf8_bytes": True}),
            (1, {"model_reason_sha256": "invalid"}),
            (1, {"model_reason_utf8_bytes": -1}),
            (-1, {"summary": "private leak"}),
            (-1, {"summary_utf8_bytes": True}),
            (-1, {"summary_sha256": "bad"}),
            (-1, {"summary_utf8_bytes": 0}),
        ]
        for index, change in modifications:
            with self.subTest(index=index, change=change):
                broken = copy.deepcopy(events)
                broken[index].update(change)
                with self.assertRaises(NativeJournalError):
                    audit_native_journal(broken, host_tool_access=HOST)


if __name__ == "__main__":
    unittest.main()

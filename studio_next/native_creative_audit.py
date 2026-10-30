"""Independently audit the *technical* model-to-native-editor journal.

The audit is deliberately not an evaluator of creativity or model identity:
a passing journal only proves internal ordering and source-bound custody fields
under the host-issued MCP protocol. No manually fabricated model responses are
transformed into evidence of independent neural intelligence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_OBSERVERS = frozenset({
    "zx7_observe_verified_export_frame",
    "zx7_observe_verified_export_samples",
    "zx7_observe_verified_export_audio",
    "zx7_observe_verified_export_audio_timeline",
})
_FRAME_OBSERVERS = frozenset({
    "zx7_observe_verified_export_frame",
    "zx7_observe_verified_export_samples",
})
_EXPORT = "zx7_verify_native_export"
_AUDIO = "zx7_observe_verified_export_audio"
_CRITICAL_END = frozenset({
    "native_tool_reported_error", "native_tool_uncertain_outcome",
    "native_observation_rejected", "model_finished",
    "model_decision_failed",
})


class NativeJournalError(ValueError):
    """Untrusted or incomplete native session ledger cannot be certified."""


def _sha(value):
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _strict_json(value):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise NativeJournalError("Duplicate journal JSON key")
            result[key] = item
        return result
    def finite_float(raw):
        value = float(raw)
        if not math.isfinite(value):
            raise NativeJournalError("Overflowed journal number")
        return value
    def reject_constant(_):
        raise NativeJournalError("Nonfinite journal number")
    try:
        return json.loads(value, object_pairs_hook=unique, parse_float=finite_float,
                          parse_constant=reject_constant)
    except NativeJournalError:
        # Preserve specific evidence of duplicate or nonfinite source fields.
        raise
    except (ValueError, RecursionError, UnicodeDecodeError) as exc:
        raise NativeJournalError("Invalid journal JSON") from exc


def read_native_journal(path: Path):
    """Read immutable private JSONL within a strict budget; never follow a symlink."""
    path = Path(path)
    if path.is_symlink():
        raise NativeJournalError("Journal cannot be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise NativeJournalError("Journal could not be opened as a regular file") from exc
    try:
        source_stat = os.fstat(fd)
        if (not stat.S_ISREG(source_stat.st_mode) or
                source_stat.st_size > 16 * 1024 * 1024):
            raise NativeJournalError("Journal must be a bounded regular file")
        with os.fdopen(fd, "rb", closefd=False) as source:
            raw = source.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise NativeJournalError("Journal grew past the audit limit")
    finally:
        os.close(fd)
    lines = raw.splitlines()
    if not lines or len(lines) > 1024 or any(not line or len(line) > 128 * 1024
                                              for line in lines):
        raise NativeJournalError("Journal exceeds audit limits or has empty records")
    try:
        events = [_strict_json(line.decode("utf-8")) for line in lines]
    except UnicodeDecodeError as exc:
        raise NativeJournalError("Journal is not UTF-8") from exc
    return events


def audit_native_journal(events, *, host_tool_access):
    """Check every transition and trace real export-to-observation identity.

    host_tool_access comes from the trusted owner grants, not from model text.
    A technically coherent journal is *not* proof of a real neural model, genuine
    edits or human-approved audiovisual quality: independent artifact/weight
    witnesses are a separate acceptance stage.
    """
    if (not isinstance(events, list) or not 1 <= len(events) <= 1024 or
            not isinstance(host_tool_access, dict) or
            any(not isinstance(k, str) or v not in ("read", "write")
                for k, v in host_tool_access.items())):
        raise NativeJournalError("Invalid event sequence or host access inventory")
    if not isinstance(events[0], dict) or events[0].get("kind") != "session_started":
        raise NativeJournalError("Journal lacks a session identity")
    pending = None
    verified = set()
    observed = {}
    writes = []
    observed_then_written = []
    finished = False
    terminal = None
    for i, event in enumerate(events):
        if not isinstance(event, dict) or type(event.get("sequence")) is not int or event["sequence"] != i:
            raise NativeJournalError("Journal event sequence is broken")
        kind = event.get("kind")
        if not isinstance(kind, str):
            raise NativeJournalError("Journal event kind missing")
        if finished:
            raise NativeJournalError("Unexpected events after a terminal outcome")
        if kind == "session_started":
            if i != 0 or not _sha(event.get("brief_sha256")):
                raise NativeJournalError("Duplicate or unbound creative session")
            continue
        if i == 0:
            continue
        if kind == "model_decision_failed":
            duration = event.get("measured_model_wall_ms")
            if (pending is not None or i != len(events) - 1 or
                    event.get("no_automatic_retry") is not True or
                    event.get("creative_quality_independently_approved") is not False or
                    not isinstance(event.get("error_type"), str) or
                    not event["error_type"] or
                    type(duration) not in (int, float) or
                    not math.isfinite(duration) or duration < 0):
                raise NativeJournalError("Model inference failure has invalid terminal evidence")
            terminal = kind
            finished = True
            continue
        if kind in ("discovered", "native_tool_schema"):
            if pending is not None:
                raise NativeJournalError("Tool catalog interleaved with unfinished native operation")
            continue
        if kind == "model_action_rejected":
            # Input-schema preflight rejected a model proposal BEFORE any RPC.
            # This is safe to correct, unlike an unknown native write result.
            # Never count preflight rejection as an editor operation.
            if (pending is not None or
                    event.get("tool") not in host_tool_access or
                    not _sha(event.get("inputs_sha256")) or
                    event.get("no_native_dispatch") is not True or
                    not isinstance(event.get("validation_keyword"), str) or
                    not 1 <= len(event["validation_keyword"]) <= 64 or
                    (event.get("schema_location") is not None and
                     (not isinstance(event["schema_location"], str) or
                      len(event["schema_location"]) > 512))):
                raise NativeJournalError("Model preflight rejection lacks proof of no native dispatch")
            continue
        if kind == "native_tool_submitted":
            if pending is not None:
                raise NativeJournalError("Second tool submitted before native outcome")
            tool = event.get("tool")
            # Historic receipts carry a plaintext reason. New receipts carry
            # a digest and exact byte length, so model-authored text (which
            # might quote private briefs/assets) does not leak into journals.
            old_reason = event.get("model_reason")
            private_reason = event.get("model_reason_sha256")
            private_len = event.get("model_reason_utf8_bytes")
            legacy = (isinstance(old_reason, str) and bool(old_reason.strip()) and
                      private_reason is None and private_len is None)
            hashed = (_sha(private_reason) and type(private_len) is int and
                      1 <= private_len <= 262144 and old_reason is None)
            if (not isinstance(tool, str) or tool not in host_tool_access or
                    not _sha(event.get("inputs_sha256")) or not (legacy or hashed)):
                raise NativeJournalError("Native operation lacks model intent or host grant")
            pending = (event.get("turn"), tool, host_tool_access[tool])
            continue
        if kind in ("native_tool_result", "native_tool_reported_error",
                    "native_tool_uncertain_outcome", "native_observation_rejected",
                    "native_read_tool_reported_error"):
            if pending is None or (event.get("turn"), event.get("tool")) != pending[:2]:
                raise NativeJournalError("Native outcome does not match a submitted call")
            turn, tool, access = pending
            pending = None
            if kind == "native_read_tool_reported_error":
                # This branch is only valid for a host-attested READ. Failed
                # reads are not positive native evidence and grant no ability
                # to advance artistic/export/source-completion counters.
                digest = event.get("error_sha256")
                flag = event.get("error_text_exceeded_evidence_budget")
                if (access != "read" or
                        event.get("host_attested_read_only") is not True or
                        event.get("no_successful_native_observation") is not True or
                        type(flag) is not bool or
                        ((digest is None) != flag) or
                        (digest is not None and not _sha(digest))):
                    raise NativeJournalError("Untrusted or malformed recoverable read failure")
                continue
            if kind == "native_tool_result":
                if event.get("human_or_artistic_quality_approved") is not False:
                    raise NativeJournalError("Technical tool output cannot assert artistic approval")
                if (not isinstance(event.get("text_sha256"), list) or
                        any(not _sha(d) for d in event["text_sha256"]) or
                        not isinstance(event.get("image_sha256"), list) or
                        any(not _sha(d) for d in event["image_sha256"])):
                    raise NativeJournalError("Native data has malformed source checksums")
                new_sha = event.get("independently_verified_export_sha256")
                seen_sha = event.get("observed_export_sha256")
                if new_sha is not None:
                    if tool != _EXPORT or not _sha(new_sha):
                        raise NativeJournalError("Fake physical export verification attribution")
                    verified.add(new_sha)
                if seen_sha is not None:
                    if tool not in _OBSERVERS or not _sha(seen_sha) or seen_sha not in verified:
                        raise NativeJournalError("Unverified exported media was observed")
                    observed.setdefault(seen_sha, set()).add(tool)
                if tool == _EXPORT and new_sha is None:
                    raise NativeJournalError("No physical export proof on successful verification")
                if tool in _OBSERVERS and seen_sha is None:
                    raise NativeJournalError("Native A/V observation lacks export provenance")
                if bool(event.get("image_sha256")) != (tool in _FRAME_OBSERVERS):
                    raise NativeJournalError("Native visual evidence mismatches sensor identity")
                audio_sha = event.get("audio_sha256")
                if audio_sha is not None:
                    if tool != _AUDIO or not _sha(audio_sha):
                        raise NativeJournalError("Unknown tool forged an audio recording")
                if tool == _AUDIO and audio_sha is None:
                    raise NativeJournalError("Native WAV is absent")
                if access == "write":
                    writes.append((i, tool))
                    if observed:
                        observed_then_written.append((i, tool))
            else:
                if access == "write" and kind == "native_observation_rejected":
                    # A rejected result might follow a completed write; cannot
                    # assume it was rolled back. Always terminate.
                    pass
                if not event.get("must_reconcile_native_state"):
                    raise NativeJournalError("Failed operation lacks reconciliation warning")
                if i != len(events) - 1:
                    raise NativeJournalError("Native error was followed by unsafe operations")
                terminal = kind
                finished = True
            continue
        if kind == "model_finished":
            if pending is not None:
                raise NativeJournalError("Model finished with an unresolved native write")
            # Preserve old valid journal compatibility, but require new
            # private-summary receipts to have a real SHA and length, never
            # a mixture that hides an unexamined raw-text leakage.
            old_summary = event.get("summary")
            private_sha = event.get("summary_sha256")
            private_len = event.get("summary_utf8_bytes")
            legacy = (isinstance(old_summary, str) and bool(old_summary.strip()) and
                      private_sha is None and private_len is None)
            hashed = (_sha(private_sha) and type(private_len) is int and
                      1 <= private_len <= 262144 and old_summary is None)
            if (event.get("creative_quality_independently_approved") is not False or
                    i != len(events) - 1 or not (legacy or hashed)):
                raise NativeJournalError("Model statement cannot approve artistic quality")
            terminal = kind
            finished = True
            continue
        raise NativeJournalError("Unknown or unreviewed native journal event")

    if pending is not None:
        raise NativeJournalError("Native outcome absent; the last write may have occurred")
    return {
        "schema": 1,
        "journal_chain_structurally_valid": True,
        "event_count": len(events),
        "recorded_native_write_result_count": len(writes),
        "export_digests_independently_reported_by_native_host": sorted(verified),
        "observed_verified_export_digests": sorted(observed),
        "model_selected_writes_after_first_verified_observation": len(observed_then_written),
        "model_reported_end_state": terminal or "turn_budget_without_explicit_finish",
        "real_neural_model_weights_or_inference_independently_attested": False,
        "physical_media_bytes_redecoded_by_this_audit": False,
        "source_rights_independently_verified": False,
        "video_editing_capability_complete": False,
        "human_or_artistic_quality_approved": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--host-editor-config", type=Path, required=True)
    args = p.parse_args()
    from .body_editor_policy import load_editor_config
    # The SAME real policy loader that launches the editor validates grants
    # and roots. Extra ZX7 sensor names are inserted ONLY when the actual
    # host config enabled them and the read capability was owner-granted.
    config = load_editor_config(args.host_editor_config)
    grants = dict(config.allowed_tools)
    if config.verify_native_exports and "read" in config.allowed_access:
        extras = {_EXPORT, *_OBSERVERS}
        if any(name in grants for name in extras):
            raise NativeJournalError("Namespaced BODY sensors collide with native grants")
        grants.update({name: "read" for name in extras})
    outcome = audit_native_journal(read_native_journal(args.journal),
                                   host_tool_access=grants)
    print(json.dumps(outcome, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

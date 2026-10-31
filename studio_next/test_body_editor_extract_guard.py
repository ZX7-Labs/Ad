"""Source-grounded regressions for lossy native edit protection."""
import copy
import json
import unittest

from studio_next.body_editor_client import EditorAccessError
from studio_next.body_editor_extract_guard import (
    read_complete_timeline, assert_plain_source_in_full_timeline,
    preflight_non_destructive_native_extract,
)


def clip(identity="a", **changes):
    result = {
        "id": identity, "name": identity, "type": "video", "assetId": "source",
        "trackId": "v1", "startTime": 0, "duration": 12, "trimStart": 0,
        "trimEnd": 12, "sourceDuration": 12, "speed": 1, "enabled": True,
        "labelColor": "", "trackMatte": "none", "lockMode": None,
        "syncLock": None, "transform": {"opacity": 100}, "effects": [],
        "textProperties": None, "shapeProperties": None, "titleAnimation": None,
        "keyframes": {}, "metadata": {"addedByMcp": True},
        "captionScope": None, "overlayKind": None, "text": "",
    }
    result.update(changes)
    return result


class FakeNative:
    def __init__(self, clips=None):
        self.clips = clips if clips is not None else [clip()]
        self.allowed_tools = {"get_timeline": "read", "extract_range": "write"}
        self.calls = []
        self.truncated = False
        self.warnings = []
        self.boundaries = {"splitAtStart": [{"id": "a"}], "splitAtEnd": [{"id": "a"}]}
        self.transitions = []

    def call(self, name, arguments, *, allowed_access):
        self.calls.append((name, copy.deepcopy(arguments)))
        if name == "get_timeline":
            data = {"clips": copy.deepcopy(self.clips), "clipCount": len(self.clips),
                    "fps": getattr(self, "fps", 24), "trackCount": 1,
                    "clipLimitApplied": self.truncated,
                    "tracks": [{"id": "v1", "locked": getattr(self, "locked", False)}],
                    "transitions": self.transitions}
        elif name == "extract_range":
            if arguments.get("previewOnly") is not True:
                raise AssertionError("Safety preflight dispatched a real edit")
            data = {"previewOnly": True, "plan": self.boundaries,
                    "warnings": self.warnings}
        else:
            raise AssertionError("Unexpected native operation")
        return {"isError": False, "content": [
            {"type": "text", "text": json.dumps(data)}]}


class NativeExtractLossGuardTests(unittest.TestCase):
    def check(self, client, args=None, access=frozenset({"read", "write"})):
        return preflight_non_destructive_native_extract(
            client, args if args is not None else {
                "startSeconds": 3, "endSeconds": 7, "previewOnly": False},
            allowed_access=access)

    def test_plain_source_boundary_is_source_inspected_without_mutation(self):
        client = FakeNative()
        result = self.check(client)
        self.assertEqual(result["preflighted_source_boundary_ids"], ["a", "a"])
        self.assertFalse(result["native_mutation_performed"])
        self.assertEqual([name for name, _ in client.calls],
                         ["get_timeline", "extract_range"])

    def test_unreported_inspector_effects_do_not_bypass_full_state(self):
        for state in (
            {"effects": [{"id": "blur"}]},
            {"keyframes": {"opacity": [{"time": 0, "value": 0}]}},
            {"trackMatte": "track-2"},
            {"textProperties": {"text": "authored"}},
            {"titleAnimation": {"preset": "intro"}},
            {"speed": 1.4},
            {"metadata": {"unreviewedPlugin": "data"}},
        ):
            with self.subTest(state=state):
                native = FakeNative([clip(**state)])
                with self.assertRaisesRegex(EditorAccessError, "discard editable clip state"):
                    self.check(native)
                self.assertTrue(all(args.get("previewOnly", True)
                                    for name, args in native.calls if name == "extract_range"))

    def test_undefined_optional_creative_fields_are_omitted_by_pinned_native_json(self):
        # Velorn safeClone(undefined) stays undefined; JSON.stringify drops that
        # optional key rather than writing null. Ordinary clips remain editable.
        for state in ("missing_effects", "missing_keyframes", "both"):
            native = FakeNative()
            if state in ("missing_effects", "both"):
                native.clips[0].pop("effects")
            if state in ("missing_keyframes", "both"):
                native.clips[0].pop("keyframes")
            with self.subTest(state=state):
                self.assertEqual(self.check(native)["preflighted_source_boundary_ids"],
                                 ["a", "a"])
                self.assertEqual([name for name, _ in native.calls],
                                 ["get_timeline", "extract_range"])

    def test_incomplete_or_truncated_required_native_state_never_authorizes_mutation(self):
        for state in ("missing_type", "missing_time", "unknown", "truncated"):
            native = FakeNative()
            if state == "missing_type":
                native.clips[0].pop("type")
            elif state == "missing_time":
                native.clips[0].pop("duration")
            elif state == "unknown":
                native.clips[0]["futureCreativeState"] = []
            else:
                native.truncated = True
            with self.subTest(state=state), self.assertRaises(EditorAccessError):
                self.check(native)
            self.assertEqual([name for name, _ in native.calls], ["get_timeline"])

    def test_stale_native_preview_must_match_independent_frame_boundary_plan(self):
        native = FakeNative()
        native.boundaries["splitAtStart"] = []
        with self.assertRaisesRegex(EditorAccessError, "disagree"):
            self.check(native)
        self.assertEqual([name for name, _ in native.calls],
                         ["get_timeline", "extract_range"])

    def test_locked_tracks_and_invalid_frame_rate_cannot_authorize_extract(self):
        for state in ("invalid_fps", "locked_track"):
            native = FakeNative()
            native.fps = 0 if state == "invalid_fps" else 24
            native.locked = state == "locked_track"
            with self.subTest(state=state), self.assertRaises(EditorAccessError):
                self.check(native)

    def test_boundary_missing_or_warned_plans_fail_closed(self):
        for alteration in ("bad_id", "warning", "transition", "scoped"):
            native = FakeNative()
            kwargs = {"startSeconds": 2, "endSeconds": 4, "previewOnly": False}
            if alteration == "bad_id":
                native.boundaries["splitAtStart"] = [{"id": "not-in-timeline"}]
            if alteration == "warning":
                native.warnings = ["Markers will not be shifted"]
            if alteration == "transition":
                native.transitions = [{"id": "transition"}]
            if alteration == "scoped":
                kwargs["trackIds"] = ["v1"]
            with self.subTest(alteration=alteration), self.assertRaises(EditorAccessError):
                self.check(native, kwargs)
            self.assertTrue(all(args.get("previewOnly", True)
                                for name, args in native.calls if name == "extract_range"))

    def test_no_track_access_no_read_grant_and_bad_times_are_safe(self):
        for args in ({"startSeconds": 4, "endSeconds": 3},
                     {"startSeconds": float("inf"), "endSeconds": 6},
                     {"startSeconds": "3", "endSeconds": 5}):
            with self.subTest(args=args), self.assertRaises(EditorAccessError):
                self.check(FakeNative(), args)
        with self.assertRaisesRegex(EditorAccessError, "host-granted"):
            self.check(FakeNative(), access=frozenset({"write"}))
        native = FakeNative()
        native.allowed_tools.pop("get_timeline")
        with self.assertRaisesRegex(EditorAccessError, "host-granted"):
            self.check(native)

    def test_full_snapshot_is_only_source_for_creative_state(self):
        native = FakeNative([clip(keyframes={"opacity": [1]})])
        with self.assertRaisesRegex(EditorAccessError, "authored keyframes"):
            assert_plain_source_in_full_timeline(
                native, "a", allowed_access={"read", "write"})
        self.assertEqual([name for name, _ in native.calls], ["get_timeline"])


if __name__ == "__main__":
    unittest.main()

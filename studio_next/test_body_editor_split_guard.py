"""Fail-closed, source-led tests for the pinned native NLE's known lossy razor."""
import copy
import json
import unittest

from studio_next.body_editor_client import EditorAccessError
from studio_next.body_editor_split_guard import (
    _native_json, _unsafe_features, preflight_non_destructive_native_split,
)


def plain(identity="clip-1", typ="video", start=0, duration=12):
    return {"id": identity, "type": typ, "trackId": "video-1",
            "startTime": start, "duration": duration,
            "assetId": "source", "name": "source", "url": "file:///source",
            "speed": 1, "reverse": False, "sourceTimeScale": 1,
            "frameSampling": "frame", "compositeLowerLayers": "auto",
            "metadata": {"addedByMcp": True, "sourceTool": "add_asset_to_timeline"},
            "transform": {"opacity": 100, "scaleX": 100}}


class NativeReadClient:
    def __init__(self, clips=None, *, direct=False):
        self.clips = clips if clips is not None else [plain()]
        self.direct = direct
        self.allowed_tools = {"get_timeline": "read", "inspect_clip": "read", "split_clip": "write"}
        self.calls = []
        self.truncate = False

    def call(self, name, arguments, *, allowed_access):
        self.calls.append((name, copy.deepcopy(arguments), frozenset(allowed_access)))
        if name not in self.allowed_tools:
            raise EditorAccessError("No permission to observe real native state")
        if name == "get_timeline":
            payload = {"clips": [
                {"id": c["id"], "type": c["type"],
                 "startTime": c["startTime"], "duration": c["duration"]}
                for c in self.clips], "clipLimitApplied": False}
            value = {**payload, "timeline": "Artist timeline"} if self.direct else {"timeline": payload}
        elif name == "inspect_clip":
            found = next(c for c in self.clips if c["id"] == arguments["clipId"])
            value = {"clip": found}
        else:
            raise AssertionError("Guard must never call the write tool")
        if self.truncate:
            value = {"truncated": True, "preview": "..."}
        return {"content": [{"type": "text", "text": json.dumps(value)}], "isError": False}


class NativeSplitGuardTests(unittest.TestCase):
    def check(self, client, args=None, access=frozenset({"read", "write"})):
        return preflight_non_destructive_native_split(
            client, args if args is not None else {
                "clipId": "clip-1", "timeSeconds": 6, "previewOnly": False},
            allowed_access=access)

    def test_plain_actual_source_can_still_be_split(self):
        client = NativeReadClient()
        result = self.check(client)
        self.assertEqual(result["preflighted_plain_source_clips"], ["clip-1"])
        self.assertFalse(result["professional_lossless_split_proven"])
        self.assertEqual([x[0] for x in client.calls], ["inspect_clip"])
        self.assertEqual(client.clips[0]["duration"], 12)

    def test_actual_native_direct_clip_list_and_timeline_name_are_read_correctly(self):
        # Native standalone read tools may include a summary/name alongside
        # top-level clips; that must not be mistaken for a nested timeline.
        client = NativeReadClient(direct=True)
        result = self.check(client, {"timeSeconds": 6})
        self.assertEqual(result["preflighted_plain_source_clips"], ["clip-1"])
        self.assertEqual([x[0] for x in client.calls], ["get_timeline", "inspect_clip"])

    def test_realistic_saved_animated_title_refused_without_any_write(self):
        title = plain(typ="text")
        title["textProperties"] = {"text": "ORIGINAL TITLE", "fontSize": 28}
        title["keyframes"] = {"opacity": [
            {"time": 0, "value": 0}, {"time": 1, "value": 100}]}
        client = NativeReadClient([title])
        with self.assertRaisesRegex(EditorAccessError, "discard editable clip state"):
            self.check(client)
        self.assertEqual([x[0] for x in client.calls], ["inspect_clip"])
        self.assertEqual(client.clips[0]["keyframes"], title["keyframes"])

    def test_enhanced_source_edits_are_not_silently_discarded(self):
        variants = [
            {"keyframes": {"opacity": [{"time": 0, "value": 50}]}},
            {"effects": [{"id": "my-native-effect"}]},
            {"speed": 1.5}, {"reverse": True},
            {"sourceTimeScale": 1.01},
            {"frameSampling": "blend"}, {"shapeMask": {"points": []}},
            {"audioInserts": [{"id": "eq"}]},
            {"trackMatte": {"trackId": "track-2"}},
            {"metadata": {"unreviewedPlugin": "effect-data"}},
            {"blendMode": "screen"},
            {"compositeLowerLayers": "never"},
        ]
        for change in variants:
            with self.subTest(change=change):
                source = {**plain(), **change}
                client = NativeReadClient([source])
                with self.assertRaises(EditorAccessError):
                    self.check(client)
                self.assertNotIn("split_clip", [n for n, _, _ in client.calls])
                self.assertEqual(client.clips[0], source)

    def test_audio_gain_and_fades_are_preserved_by_refusal(self):
        for key, value in [("gainDb", -6), ("fadeIn", 1.5), ("fadeOut", .4)]:
            with self.subTest(key=key):
                clip = plain(typ="audio")
                clip[key] = value
                with self.assertRaisesRegex(EditorAccessError, "audio dynamics"):
                    self.check(NativeReadClient([clip]))

    def test_multiple_clip_targets_and_implicit_ranges_are_all_inspected(self):
        a, b = plain("a", start=0), plain("b", start=5)
        c = NativeReadClient([a, b])
        result = self.check(c, {"clipIds": ["a", "b"], "timeSeconds": 6})
        self.assertEqual(result["preflighted_plain_source_clips"], ["a", "b"])
        result = self.check(c, {"timeSeconds": 6})
        self.assertEqual(result["preflighted_plain_source_clips"], ["a", "b"])
        modified = {**b, "keyframes": {"opacity": [1]}}
        with self.assertRaisesRegex(EditorAccessError, "discard"):
            self.check(NativeReadClient([a, modified]), {"timeSeconds": 6})

    def test_unknown_read_capability_missing_targets_and_bad_time_fail_closed(self):
        scenarios = [
            ({"clipId": "missing", "timeSeconds": 1}, "does not exist"),
            ({"timeSeconds": -3}, "time"),
            ({"timeSeconds": float("nan")}, "time"),
            ({}, "time"),
            ({"clipIds": ["clip-1", "clip-1"], "timeSeconds": 3}, "uniquely"),
        ]
        for arguments, message in scenarios:
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(EditorAccessError, message):
                    self.check(NativeReadClient(), arguments)
        with self.assertRaisesRegex(EditorAccessError, "host-granted read"):
            self.check(NativeReadClient(), access=frozenset({"write"}))
        client = NativeReadClient()
        client.allowed_tools.pop("inspect_clip")
        with self.assertRaisesRegex(EditorAccessError, "host-granted read"):
            self.check(client)

    def test_truncated_or_corrupt_native_observations_are_not_accepted(self):
        client = NativeReadClient()
        client.truncate = True
        with self.assertRaisesRegex(EditorAccessError, "truncated"):
            self.check(client)
        with self.assertRaises(EditorAccessError):
            _native_json({"content": [{"type": "text", "text": "{bad"}]}, "get_timeline")
        with self.assertRaises(EditorAccessError):
            _native_json({"content": [{"type": "image", "data": "bad"}]}, "inspect_clip")
        for invalid in ('{"clip":{"id":"a","id":"b"}}',
                        '{"clip":{"id":"a","startTime":NaN}}',
                        '{"clip":{"id":"a","duration":1e999}}'):
            with self.subTest(raw=invalid), self.assertRaises(EditorAccessError):
                _native_json({"content": [{"type": "text", "text": invalid}]}, "inspect_clip")
        self.assertTrue(_unsafe_features(plain(typ="adjustment")))


if __name__ == "__main__":
    unittest.main()

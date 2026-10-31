"""Source-attested guard for native range extracts and razor boundary edits.

Pinned Velorn's inspect_clip omits effects/keyframes, although get_timeline
includes them. Range extract internally splits clips and can discard those
creative properties. Only loss-free plain-source cuts may be sent to native
write RPCs. This is not an OS sandbox or protection for raw upstream MCP.
"""
from __future__ import annotations

import math

from .body_editor_client import EditorAccessError
from .body_editor_split_guard import _native_json, _unsafe_features

# Pinned src/services/mcpSnapshot.js sanitizeClip fields. Any novel property
# is unsafe until a source audit determines whether the razor preserves it.
_SNAPSHOT_KEYS = frozenset((
    "id", "name", "type", "assetId", "trackId", "startTime", "duration",
    "trimStart", "trimEnd", "sourceDuration", "speed", "enabled", "labelColor",
    "trackMatte", "lockMode", "syncLock", "transform", "effects",
    "textProperties", "shapeProperties", "titleAnimation", "keyframes",
    "metadata", "captionScope", "overlayKind", "text",
))
_PLAIN_KEYS = frozenset((
    "id", "name", "type", "assetId", "trackId", "startTime", "duration",
    "trimStart", "trimEnd", "sourceDuration", "speed", "enabled", "labelColor",
    "transform", "metadata",
))
_CREATIVE_KEYS = (
    "effects", "keyframes", "textProperties", "shapeProperties",
    "titleAnimation", "captionScope", "overlayKind", "text",
)


def read_complete_timeline(client, *, allowed_access):
    if ("read" not in allowed_access or
            client.allowed_tools.get("get_timeline") != "read"):
        raise EditorAccessError("Loss-aware edit requires host-granted full timeline read")
    response = _native_json(client.call(
        "get_timeline",
        {"includeClips": True, "includeTransitions": True, "limit": 1000},
        allowed_access=allowed_access), "get_timeline")
    timeline = response if isinstance(response.get("clips"), list) else response.get("timeline")
    if (not isinstance(timeline, dict) or
            not isinstance(timeline.get("clips"), list) or
            timeline.get("clipLimitApplied") is not False or
            type(timeline.get("clipCount")) is not int or
            timeline["clipCount"] != len(timeline["clips"])):
        raise EditorAccessError("Loss-aware edit requires complete untruncated clip snapshot")
    # In pinned Velorn sanitizeClip, safeClone(undefined) returns undefined.
    # JSON serialization then omits unused effects/keyframes properties.
    # Absence of those OPTIONAL fields on the source-sanitized full clip is
    # therefore an authentic empty state, not an unparsed summary. Unknown
    # properties and incomplete clip inventories remain fail-closed.
    ids = set()
    for clip in timeline["clips"]:
        if (not isinstance(clip, dict) or
                not isinstance(clip.get("id"), str) or not clip["id"] or
                clip["id"] in ids or
                not _SNAPSHOT_KEYS.issuperset(clip) or
                "type" not in clip or
                type(clip.get("startTime")) not in (float, int) or
                type(clip.get("duration")) not in (float, int) or
                not math.isfinite(clip["startTime"]) or
                not math.isfinite(clip["duration"]) or clip["duration"] <= 0):
            raise EditorAccessError("Loss-aware edit cannot inspect complete clip creative state")
        ids.add(clip["id"])
    return timeline


def assert_plain_source_in_full_timeline(client, clip_id, *, allowed_access,
                                         timeline=None):
    if timeline is None:
        timeline = read_complete_timeline(client, allowed_access=allowed_access)
    clip = next((item for item in timeline["clips"] if item["id"] == clip_id), None)
    if clip is None:
        raise EditorAccessError("Loss-aware edit clip missing from native timeline")
    # The renderer publishes these keys in the complete timeline snapshot, not
    # in inspect_clip. Unknown or nonempty creative state is never assumed safe.
    reasons = []
    for key in _CREATIVE_KEYS:
        if clip.get(key) not in (None, "", [], {}):
            reasons.append("authored " + key)
    if clip.get("trackMatte") not in (None, "none"):
        reasons.append("track matte")
    if clip.get("lockMode") not in (None, "", False):
        reasons.append("lock mode")
    if clip.get("syncLock") not in (None, False, [], {}):
        reasons.append("sync lock")
    # Reuse the existing pinned-source conservative checks, but do not mistake
    # *known empty* snapshot-only fields for unreviewed source state.
    reasons += _unsafe_features({key: value for key, value in clip.items()
                                if key in _PLAIN_KEYS})
    if reasons:
        raise EditorAccessError(
            "Native cut refused to discard editable clip state on " +
            clip_id + ": " + "; ".join(reasons))
    return clip


def _expected_boundary_ids(timeline, start_seconds, end_seconds):
    """Recompute the pinned editor's frame-snapped range boundary selection.

    If actual preview and independently inspected project disagree, never
    dispatch the write; debounced native state may not have converged.
    """
    fps = timeline.get("fps")
    if type(fps) not in (int, float) or not math.isfinite(fps) or fps <= 0:
        raise EditorAccessError("Native extract requires verified timeline frame rate")
    half_frame = 0.5 / fps
    start = math.floor(start_seconds * fps + 0.5) / fps
    end = math.floor(end_seconds * fps + 0.5) / fps
    if end - start < 1.0 / fps - 1e-10:
        raise EditorAccessError("Native extract range does not cover a full frame")
    tracks = timeline["tracks"]
    if (type(timeline.get("trackCount")) is not int or
            timeline["trackCount"] != len(tracks) or
            any(not isinstance(t, dict) or not isinstance(t.get("id"), str)
                or not t["id"] or t.get("locked") is True for t in tracks) or
            len({t["id"] for t in tracks}) != len(tracks)):
        raise EditorAccessError("Native extract requires complete unlocked track inventory")
    active = {t["id"] for t in tracks}
    boundaries = {"splitAtStart": [], "splitAtEnd": []}
    for clip in timeline["clips"]:
        if clip.get("trackId") not in active:
            raise EditorAccessError("Native extract has a clip outside inspected tracks")
        left, right = clip["startTime"], clip["startTime"] + clip["duration"]
        if right <= start + half_frame:
            continue
        if clip.get("syncLock") not in (None, False, [], {}):
            raise EditorAccessError("Native extract has synchronization-locked clip")
        if left < start - half_frame and right > start + half_frame:
            boundaries["splitAtStart"].append(clip["id"])
        if left < end - half_frame and right > end + half_frame:
            boundaries["splitAtEnd"].append(clip["id"])
    return boundaries


def preflight_non_destructive_native_extract(client, arguments, *, allowed_access):
    if not isinstance(arguments, dict):
        raise EditorAccessError("Native extract requires object arguments")
    if arguments.get("trackIds") is not None:
        # The pinned removeClip can delete linked A/V outside requested tracks.
        raise EditorAccessError("Scoped native extract can remove linked clips outside selected tracks")
    for key in ("startSeconds", "endSeconds"):
        value = arguments.get(key)
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
            raise EditorAccessError("Native extract needs finite nonnegative boundary times")
    if not arguments["startSeconds"] < arguments["endSeconds"]:
        raise EditorAccessError("Native extract requires a positive range")
    timeline = read_complete_timeline(client, allowed_access=allowed_access)
    if not isinstance(timeline.get("tracks"), list):
        raise EditorAccessError("Native extract requires a complete track snapshot")
    if timeline.get("transitions") not in (None, []):
        raise EditorAccessError("Native extract cannot guarantee transition preservation")
    # Actual native preview determines frame-snapped boundary targets. Preview
    # may not mutate. Never silently act on warnings (markers/links/locks).
    preview = _native_json(client.call(
        "extract_range", {**arguments, "previewOnly": True},
        allowed_access=allowed_access), "extract_range preview")
    plan = preview.get("plan")
    if (preview.get("previewOnly") is not True or
            preview.get("warnings") not in ([], None) or
            not isinstance(plan, dict) or
            not isinstance(plan.get("splitAtStart"), list) or
            not isinstance(plan.get("splitAtEnd"), list)):
        raise EditorAccessError("Native extract preview is incomplete or warns of side effects")
    expected = _expected_boundary_ids(
        timeline, arguments["startSeconds"], arguments["endSeconds"])
    checked = []
    for key in ("splitAtStart", "splitAtEnd"):
        candidate_ids = []
        for item in plan[key]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise EditorAccessError("Native extract preview has invalid split target")
            candidate_ids.append(item["id"])
        if sorted(candidate_ids) != sorted(expected[key]):
            raise EditorAccessError(
                "Native extract preview and observed source timeline disagree on " + key)
        for identity in candidate_ids:
            assert_plain_source_in_full_timeline(
                client, identity, allowed_access=allowed_access, timeline=timeline)
            checked.append(identity)
    return {"preflighted_source_boundary_ids": checked,
            "native_mutation_performed": False,
            "all_native_preservation_verified": False}

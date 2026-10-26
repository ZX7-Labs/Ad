"""Director-authored frame-exact reversible NLE revisions over owned original footage.

All edit commands are data, not shell instructions. The old plan, each physical
MediaVault source and earlier movie are immutable. The edited plan remains
directly consumable by body.sequence_cuts, including independent original
sound at every revised cut. No creative defaults or claimed complete NLE.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .body_sequence_cuts import plan_verified_sequence, render_verified_sequence
from .media_vault import sha256_file
from .precision_retime import _source_timebase


def _exact_int(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Editorial " + label + " requires a bounded exact integer")
    return value


def _idx(op, field, clips, *, middle=False):
    index = _exact_int(op[field], field, 0, len(clips)-1)
    if middle and not 0 < index < len(clips)-1:
        raise ValueError("Slide requires original shots on both sides")
    return index


def _bounds(clips, source_lengths):
    for clip in clips:
        if not isinstance(clip, dict) or set(clip) != {
                "source", "asset_id", "attestation_id",
                "first_frame", "end_frame", "audio"}:
            raise ValueError("Edited shot has altered original custody or audio contract")
        length = source_lengths.get(clip["asset_id"])
        if type(length) is not int or length <= 0:
            raise ValueError("Missing physically measured original frame capacity")
        a = clip["first_frame"]
        b = clip["end_frame"]
        if type(a) is not int or type(b) is not int or not 0 <= a < b <= length:
            raise ValueError("Editorial edit exceeded original decoded frame range")


def apply_editorial_operations(plan, decision, source_lengths):
    """Return a wholly new strict sequence plan; never mutate an argument.

    roll: positive delta moves the boundary right within both original clips.
    slip: positive delta moves the chosen source window later, same duration.
    slide: positive delta extends left neighbour, moves right neighbour's in.
    ripple_trim: delta shifts exactly the selected source in/out; duration shifts.
    split: offset divides a source range into two independently editable shots.
    reorder: moves an entire source window without modifying the source time.
    """
    if not isinstance(plan, dict) or set(plan) != {"frame_rate","frame_size","clips"}:
        raise ValueError("Editorial revision needs an original exact-frame cut plan")
    if not isinstance(decision, dict) or set(decision) != {"operations"} or (
            not isinstance(decision["operations"], list) or
            not 1 <= len(decision["operations"]) <= 64):
        raise ValueError("Director must author one to 64 exact editorial operations")
    if not isinstance(source_lengths, dict):
        raise ValueError("Original source frame extents are required")
    revised = copy.deepcopy(plan)
    clips = revised["clips"]
    if not isinstance(clips, list) or not clips:
        raise ValueError("Original timeline has no shots")
    _bounds(clips, source_lengths)
    history = []
    for raw in decision["operations"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("kind"), str):
            raise ValueError("Unrecognized editorial instruction")
        kind = raw["kind"]
        shapes = {
            "roll": {"kind","at","delta"},
            "slip": {"kind","clip","delta"},
            "slide": {"kind","clip","delta"},
            "ripple_trim": {"kind","clip","edge","delta"},
            "split": {"kind","clip","offset"},
            "reorder": {"kind","clip","to"},
        }
        if kind not in shapes or set(raw) != shapes[kind]:
            raise ValueError("Unsupported or incomplete editor operation")
        before = sum(c["end_frame"]-c["first_frame"] for c in clips)
        if kind == "roll":
            at = _exact_int(raw["at"], "cut boundary", 0, len(clips)-2)
            delta = _exact_int(raw["delta"], "cut displacement", -2000000, 2000000)
            if not delta: raise ValueError("Zero-frame edit is not a revision")
            clips[at]["end_frame"] += delta
            clips[at+1]["first_frame"] += delta
        elif kind == "slip":
            i = _idx(raw, "clip", clips)
            delta = _exact_int(raw["delta"], "slip", -2000000, 2000000)
            if not delta: raise ValueError("Zero-frame edit is not a revision")
            clips[i]["first_frame"] += delta
            clips[i]["end_frame"] += delta
        elif kind == "slide":
            i = _idx(raw, "clip", clips, middle=True)
            delta = _exact_int(raw["delta"], "slide", -2000000, 2000000)
            if not delta: raise ValueError("Zero-frame edit is not a revision")
            clips[i-1]["end_frame"] += delta
            clips[i+1]["first_frame"] += delta
        elif kind == "ripple_trim":
            i = _idx(raw, "clip", clips)
            delta = _exact_int(raw["delta"], "trim", -2000000, 2000000)
            if raw["edge"] not in ("in","out") or not delta:
                raise ValueError("Ripple trim needs actual authored in/out frame move")
            clips[i]["first_frame" if raw["edge"]=="in" else "end_frame"] += delta
        elif kind == "split":
            i = _idx(raw, "clip", clips)
            offset = _exact_int(raw["offset"], "split offset", 1, 2000000)
            shot = clips[i]
            split_at = shot["first_frame"]+offset
            if split_at >= shot["end_frame"]:
                raise ValueError("Split must produce two nonempty original shots")
            right = copy.deepcopy(shot)
            right["first_frame"] = split_at
            shot["end_frame"] = split_at
            clips.insert(i+1, right)
        elif kind == "reorder":
            i = _idx(raw, "clip", clips)
            dest = _exact_int(raw["to"], "reorder target", 0, len(clips)-1)
            if i == dest: raise ValueError("Zero-frame edit is not a revision")
            clips.insert(dest, clips.pop(i))
        if len(clips) > 128:
            raise ValueError("Native revision exceeds maximum source shot count")
        _bounds(clips, source_lengths)
        after = sum(c["end_frame"]-c["first_frame"] for c in clips)
        if kind in ("roll","slip","slide","split","reorder") and before != after:
            raise AssertionError("Non-ripple editorial edit changed total film time")
        history.append({"operation":kind,"frames_before":before,"frames_after":after})
    return revised, history


def _canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",",":"))+"\n").encode("utf-8")


def render_editorial_revision(plan_file, operation_file, workspace, vault_root, output):
    """Use physical rights checks, immutable plan readback and proven MP4 encoding.

    A named SHA256 revision JSON survives for subsequent operations; publication
    of its actual encoded movie is performed by the BODY atomic media publisher.
    """
    root = Path(workspace).resolve()
    original = Path(plan_file).resolve()
    instruction = Path(operation_file).resolve()
    movie = Path(output).resolve()
    if (any(not p.is_relative_to(root) or not p.is_file()
            for p in (original,instruction)) or
            not movie.is_relative_to(root) or movie.exists() or
            movie.suffix.lower() != ".mp4" or
            original == instruction or movie in (original,instruction)):
        raise ValueError("Revision input and new movie must belong to the owner workspace")
    old_hash = sha256_file(original)
    command_hash = sha256_file(instruction)
    plan = json.loads(original.read_text(encoding="utf-8"))
    instructions = json.loads(instruction.read_text(encoding="utf-8"))
    if sha256_file(original) != old_hash or sha256_file(instruction) != command_hash:
        raise ValueError("Author's edit input changed during initial validation")
    physical = plan_verified_sequence(plan,root,vault_root)
    original_frames = {}
    for clip in physical["clips"]:
        if clip["asset_id"] not in original_frames:
            original_frames[clip["asset_id"]] = _source_timebase(clip["source"])[1]
    revised, steps = apply_editorial_operations(plan,instructions,original_frames)
    after = plan_verified_sequence(revised,root,vault_root)
    revision_bytes = _canonical(revised)
    revision_sha = hashlib.sha256(revision_bytes).hexdigest()

    # Store the reproducible EDIT DECISION before publishing the film. This
    # content-addressed plan does not claim that rendering has succeeded.
    directory = root/".zx7-timeline-revisions"
    if directory.is_symlink():
        raise ValueError("Linked revision storage is not trusted")
    directory.mkdir(parents=True,exist_ok=True)
    revision = directory/(revision_sha+".json")
    if revision.exists():
        if revision.is_symlink() or revision.read_bytes() != revision_bytes:
            raise ValueError("Existing immutable timeline revision was modified")
    else:
        try:
            fd = os.open(revision,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:
            if revision.is_symlink() or revision.read_bytes() != revision_bytes:
                raise ValueError("Conflicting simultaneous director revision")
        else:
            with os.fdopen(fd,"wb") as handle:
                handle.write(revision_bytes)
                handle.flush()
                os.fsync(handle.fileno())

    def verify_editor_decision_before_publication():
        # Called immediately before the low-level verified renderer's
        # exclusive os.link publication, AFTER full picture/audio decode.
        if sha256_file(original) != old_hash or sha256_file(instruction) != command_hash:
            raise ValueError("Director plan or editorial decisions changed during render")
        if any(sha256_file(path)!=digest for path,digest in physical["originals"].items()):
            raise ValueError("Original media bytes changed while revising")
        if (directory.is_symlink() or revision.is_symlink() or
                not revision.is_file() or revision.read_bytes()!=revision_bytes):
            raise ValueError("Immutable timeline revision changed before film publication")

    transient = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=root, prefix=".zx7-nle-",
                                         suffix=".json", delete=False) as handle:
            transient = Path(handle.name)
            handle.write(revision_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        verify_editor_decision_before_publication()
        result = render_verified_sequence(
            transient,root,vault_root,movie,
            pre_publish_guard=verify_editor_decision_before_publication)
        return {**result,"revision_plan":str(revision.relative_to(root)),
                "revision_plan_sha256":revision_sha,
                "prior_plan_sha256":old_hash,
                "director_operation_sha256":command_hash,
                "operations":steps,
                "reversible_original_media":True}
    finally:
        # Only clean our private temp source: never remove another producer's
        # approved movie if we lose an atomic destination publication race.
        if transient is not None:
            transient.unlink(missing_ok=True)

"""Exact, source-attested native MLT revision comparison for creative review.

This is *timeline state evidence*, NOT a pixel-equivalence, sound-quality or
aesthetic judgment. Both original projects must be physically available,
strictly allowlisted, rights-attested, and independently rebuilt without loss.
No source file, native project or prior revision is ever modified here.

Uses a boundary-sweep over actual source clip intervals. It never unrolls an
hour-long timeline into millions of frames or silently normalizes timebases.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

from .body_mlt_roundtrip import recover_original_mlt_plan
from .media_vault import sha256_file


def _project(root, file):
    path=Path(file)
    if not path.is_absolute():
        path=root/path
    path=path.absolute()
    if (path.suffix.lower()!=".mlt" or not path.is_file()
            or path.is_symlink() or not path.is_relative_to(root)
            or not path.resolve().is_relative_to(root)):
        raise ValueError("Native review accepts only a physical workspace-owned original .mlt")
    return path


def _clip_intervals(clips):
    result=[]
    for clip in clips:
        start=clip["position_frame"]
        end=start+clip["end_frame"]-clip["first_frame"]
        if not (0<=start<end<=1000000):
            raise ValueError("An original source has an unrepresentable frame interval")
        result.append((start,end,clip))
    return result


def _source_at(intervals,frame):
    for start,end,clip in intervals:
        if start<=frame<end:
            return (clip["asset_id"],clip["attestation_id"],
                    clip["first_frame"]+frame-start)
    return None


def _source_identity(item):
    if item is None:
        return None
    digest,attestation,source_frame=item
    return {"asset_id":digest,"attestation_id":attestation,
            "first_source_frame":source_frame}


def _track_control(track,kind):
    if track is None:
        return None
    if kind=="picture":
        return {key:copy.deepcopy(track[key])
            for key in ("blend_mode","opacity","opacity_keyframes")
            if key in track}
    return {key:copy.deepcopy(track[key])
        for key in ("gain_db","gain_keyframes","pan","pan_keyframes")
        if key in track}


def _track_changes(original,updated,kind,index,old_frames,new_frames):
    before=_clip_intervals(original["clips"]) if original else []
    after=_clip_intervals(updated["clips"]) if updated else []
    stop=max(old_frames,new_frames)
    boundaries={0,stop,old_frames,new_frames}
    for left,right,_ in before+after:
        boundaries.add(left)
        boundaries.add(right)
    points=sorted(boundaries)
    altered=[]
    surviving=0
    for left,right in zip(points,points[1:]):
        if left==right:
            continue
        b=_source_at(before,left) if left<old_frames else None
        a=_source_at(after,left) if left<new_frames else None
        if (b is None and a is None) or (
            b is not None and a is not None and b==a):
            if b is not None:
                surviving+=right-left
            continue
        if b is None:kind_of_change="inserted_original_source"
        elif a is None:kind_of_change="removed_original_source"
        elif b[:2]==a[:2]:kind_of_change="repositioned_original_source_frame"
        else:kind_of_change="original_source_replaced_or_relinked"
        altered.append({
            "start_frame":left,"end_frame_exclusive":right,
            "duration_frames":right-left,"type":kind_of_change,
            "before":_source_identity(b),
            "after":_source_identity(a)})
    # Razor/split/rejoin can change the editable graph without moving a
    # single decoded frame. Report this separately from source-pixel deltas.
    old_clips=copy.deepcopy(original["clips"]) if original else None
    new_clips=copy.deepcopy(updated["clips"]) if updated else None
    editorial_partition_delta=(None if old_clips==new_clips else {
        "before":old_clips,"after":new_clips})
    old_control=_track_control(original,kind)
    new_control=_track_control(updated,kind)
    controls=None
    if old_control!=new_control:
        controls={"before":old_control,"after":new_control}
    return {"kind":kind,"track_index":index,
            "source_frame_spans":altered,
            "unchanged_original_source_frames":surviving,
            "native_track_controls":controls,
            "native_clip_partition_delta":editorial_partition_delta}


def _bounded_review_view(full,focus):
    """Select only requested semantic evidence, never fabricate proof.

    Summary never includes source filenames/clip payloads or all frames.
    The Brain can ask for one precise picture/sound track when the summary
    points to a change, then ask for an explicit full export if warranted.
    Model-visible result is proportional to the exact review query.
    """
    if not isinstance(focus,str) or not re.fullmatch(
            r"(?:summary|all|picture:[0-7]|sound:[0-3])",focus):
        raise ValueError("Native review focus must be summary, all or one real track")
    header={key:value for key,value in full.items()
            if key not in ("picture_changes","sound_changes")}
    header["query_focus"]=focus
    def brief(items):
        result=[]
        for track in items:
            spans=track["source_frame_spans"]
            result.append({
                "track_index":track["track_index"],
                "changed_source_intervals":len(spans),
                "changed_original_source_frames":sum(
                    row["duration_frames"] for row in spans),
                "native_clip_partitions_changed":
                    track["native_clip_partition_delta"] is not None,
                "authored_effect_controls_changed":
                    track["native_track_controls"] is not None})
        return result
    header["picture_change_summaries"]=brief(full["picture_changes"])
    header["sound_change_summaries"]=brief(full["sound_changes"])
    if focus=="summary":
        return header
    if focus=="all":
        return {**header,"picture_changes":full["picture_changes"],
                "sound_changes":full["sound_changes"]}
    kind,text=focus.split(":")
    index=int(text)
    size=max(full[kind+"_track_count_before"],
             full[kind+"_track_count_after"])
    if index>=size:
        raise ValueError("Requested native track does not exist in either owner project")
    label="picture_changes" if kind=="picture" else "sound_changes"
    header["selected_track"]={
        "kind":kind,"track_index":index,
        "change":next((value for value in full[label]
                       if value["track_index"]==index),None)}
    return header


def compare_owned_mlt_projects(before_edit,after_edit,workspace,vault_root,*,focus="summary"):
    """Read-only review of every picture/sound source address and effect state.

    Returns the exact finite semantic difference, not a creatively selected
    conclusion. Unverifiable rights, unsupported native edits or changed frame
    rates are rejected. The editor can ask its model what SHOULD change next.
    """
    root=Path(workspace).resolve()
    prior=_project(root,before_edit)
    later=_project(root,after_edit)
    sha_before=sha256_file(prior)
    sha_after=sha256_file(later)
    original=recover_original_mlt_plan(prior,root,vault_root)
    revised=recover_original_mlt_plan(later,root,vault_root)
    if (original["source_mlt_sha256"]!=sha_before or
            revised["source_mlt_sha256"]!=sha_after):
        raise ValueError("Source-authenticated native editor file changed during review")

    first=original["plan"]
    second=revised["plan"]
    if first["frame_rate"]!=second["frame_rate"]:
        raise ValueError(
            "Native edit comparison cannot silently resample different rational frame rates")
    # A change in output frame size affects the picture even when all original
    # source frames match: it must be reported separately.
    canvas_changed=(first["frame_size"]!=second["frame_size"])
    picture=[]
    sound=[]
    for kind,key,target in (("picture","tracks",picture),
                            ("sound","audio_tracks",sound)):
        lhs=first.get(key,[])
        rhs=second.get(key,[])
        for index in range(max(len(lhs),len(rhs))):
            report=_track_changes(
                lhs[index] if index<len(lhs) else None,
                rhs[index] if index<len(rhs) else None,
                kind,index,original["frames"],revised["frames"])
            if (report["source_frame_spans"] or
                    report["native_track_controls"] is not None or
                    report["native_clip_partition_delta"] is not None):
                target.append(report)
    if sha256_file(prior)!=sha_before or sha256_file(later)!=sha_after:
        raise ValueError("Native original or revised timeline changed during comparison")
    audio_order_changed=(original["legacy_audio_bus_order_requires_migration"]!=
                         revised["legacy_audio_bus_order_requires_migration"])
    changed=bool(canvas_changed or audio_order_changed or original["frames"]!=revised["frames"] or
                 picture or sound)
    return _bounded_review_view({
        "workspace_root":str(root),
        "media_vault_root":str(Path(vault_root).resolve()),
        "before_edit_path":str(prior),
        "after_edit_path":str(later),
        "before_mlt_sha256":sha_before,
        "after_mlt_sha256":sha_after,
        "frame_rate":copy.deepcopy(first["frame_rate"]),
        "before_frames":original["frames"],
        "after_frames":revised["frames"],
        "before_frame_size":copy.deepcopy(first["frame_size"]),
        "after_frame_size":copy.deepcopy(second["frame_size"]),
        "frame_size_changed":canvas_changed,
        "native_audio_execution_order_changed":audio_order_changed,
        "picture_track_count_before":len(first["tracks"]),
        "picture_track_count_after":len(second["tracks"]),
        "sound_track_count_before":len(first.get("audio_tracks",[])),
        "sound_track_count_after":len(second.get("audio_tracks",[])),
        "picture_changes":picture,"sound_changes":sound,
        "structural_changes_verified":changed,
        "exact_source_rights_and_native_roundtrips_rechecked":True,
        "decoded_pixel_or_audio_equivalence_proven":False,
        "creative_or_professional_quality_approved":False,
    },focus)

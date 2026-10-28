"""Model-directed native NLE roll/slip/slide source-window algebra.

Pure, reversible transformations of signed frame offsets; no clip is cloned,
inferred, silently retimed or re-licensed. Every original-source identity stays
attached to the exact clip. Existing MLT media vault preflight and native
roundtrip verify physically available source handles and legal rights afterward.

Effect automation is intentionally LOCKED TO ABSOLUTE FILM TIME, not secretly
moved with a source clip. The director must explicitly author that policy.
"""
from __future__ import annotations

import copy


def _integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum<=value<=maximum:
        raise ValueError("Native editor "+label+" requires an exact frame integer")
    return value


def _clip_stop(clip):
    return clip["position_frame"]+clip["end_frame"]-clip["first_frame"]


def _targets(targets,size,label):
    if not isinstance(targets,list) or len(targets)>size:
        raise ValueError("Local edit needs explicit "+label+" track+clip targets")
    result=[]
    prev=-1
    for t in targets:
        if not isinstance(t,dict) or set(t)!={"track","clip"}:
            raise ValueError("Native edit target must name a track and a clip")
        track=_integer(t["track"],label+" track",0,size-1)
        clip=_integer(t["clip"],label+" clip",0,127)
        if track<=prev:
            raise ValueError("Local editor track targets must be unique and sorted")
        prev=track
        result.append((track,clip))
    return result


def _local_one(track,kind,index,delta):
    clips=track["clips"]
    if index>=len(clips):
        raise ValueError("Selected editor clip is absent from original timeline")
    if kind=="slip":
        selected=clips[index]
        source_first=selected["first_frame"]+delta
        source_end=selected["end_frame"]+delta
        if not 0<=source_first<source_end<=1_000_000:
            raise ValueError("Slip moves original source clip outside legal frame range")
        selected["first_frame"]=source_first
        selected["end_frame"]=source_end
        return {"clip":index,"source_offset_frames":delta,
                "timeline_duration_preserved":True}
    if kind=="roll":
        if index+1>=len(clips):
            raise ValueError("Roll requires the exact adjacent right original clip")
        left,right=clips[index:index+2]
        if _clip_stop(left)!=right["position_frame"]:
            raise ValueError("Roll requires an existing source-owned cut with no gap")
        left_end=left["end_frame"]+delta
        right_first=right["first_frame"]+delta
        if (not left["first_frame"]<left_end<=1_000_000 or
                not 0<=right_first<right["end_frame"] or
                not 0<=right["position_frame"]+delta<=1_000_000):
            raise ValueError("Roll cannot erase an original clip or invent source frames")
        left["end_frame"]=left_end
        right["first_frame"]=right_first
        right["position_frame"]+=delta
        return {"left_clip":index,"right_clip":index+1,
                "boundary_delta_frames":delta,
                "total_timeline_duration_preserved":True}
    if kind=="slide":
        if not 0<index<len(clips)-1:
            raise ValueError("Slide requires the original left and right neighbours")
        left,selected,right=clips[index-1:index+2]
        if (_clip_stop(left)!=selected["position_frame"] or
                _clip_stop(selected)!=right["position_frame"]):
            raise ValueError("Slide needs a contiguous original three-clip interval")
        left_end=left["end_frame"]+delta
        right_first=right["first_frame"]+delta
        selected_pos=selected["position_frame"]+delta
        right_pos=right["position_frame"]+delta
        if (not left["first_frame"]<left_end<=1_000_000 or
                not 0<=right_first<right["end_frame"] or
                not 0<=selected_pos<=1_000_000 or
                not 0<=right_pos<=1_000_000):
            raise ValueError("Slide exceeds original source or would erase a clip")
        left["end_frame"]=left_end
        selected["position_frame"]=selected_pos
        right["first_frame"]=right_first
        right["position_frame"]=right_pos
        return {"selected_clip":index,"left_clip":index-1,
                "right_clip":index+1,
                "source_window_preserved":True,
                "total_timeline_duration_preserved":True}
    raise ValueError("Unknown original NLE source-window operation")


def apply_local_window_action(plan,action):
    """One operator-authored relative change across explicit picture/sound clips.

    Return a NEW plan. Owner source facts, prior revisions, keyframe positions,
    clip ordering, codec, and original source media must remain immutable.
    """
    if not isinstance(action,dict) or action.get("kind") not in (
            "roll","slip","slide") or set(action)!={
            "kind","delta_frames","picture_targets","audio_targets","automation"}:
        raise ValueError("Local editor instruction has no recognized typed operation")
    if action["automation"]!="lock_to_timeline":
        raise ValueError("Native source movement requires an explicit effects timeline-lock policy")
    delta=_integer(action["delta_frames"],"signed displacement",-1000000,1000000)
    if not delta:
        raise ValueError("Zero-frame source-window edit changes no film")
    if (not isinstance(plan,dict) or
            not isinstance(plan.get("tracks"),list) or
            not isinstance(plan.get("audio_tracks",[]),list)):
        raise ValueError("Native editing requires a complete original source plan")
    picture=_targets(action["picture_targets"],len(plan["tracks"]),"picture")
    audio=_targets(action["audio_targets"],len(plan.get("audio_tracks",[])),"sound")
    if not picture and not audio:
        raise ValueError("Local editor action has no authorized source window")
    original=copy.deepcopy(plan)
    revised=copy.deepcopy(plan)
    evidence=[]
    for key,targets in (("tracks",picture),("audio_tracks",audio)):
        for track,index in targets:
            before=original[key][track]
            after=revised[key][track]
            outcome=_local_one(after,action["kind"],index,delta)
            for field in ("opacity","opacity_keyframes","gain_db","gain_keyframes",
                          "pan","pan_keyframes","blend_mode"):
                if before.get(field)!=after.get(field):
                    raise AssertionError("Timeline-locked native track effect was changed")
            if len(after["clips"])!=len(before["clips"]):
                raise AssertionError("Native window editor silently deleted a source clip")
            for old,edited in zip(before["clips"],after["clips"]):
                for field in ("source","asset_id","attestation_id","audio"):
                    if field in old and old[field]!=edited[field]:
                        raise AssertionError("Original source media and rights were substituted")
            evidence.append({"domain":"picture" if key=="tracks" else "sound",
                "track":track,**outcome})
    if revised==plan:
        raise ValueError("Source window edit did not change the original film")
    return revised,{"kind":action["kind"],"delta_frames":delta,
        "effects_automation_policy":"lock_to_timeline",
        "edited_source_windows":evidence,
        "trusted_original_sources_must_be_physically_rechecked":True,
        "independent_release_or_artist_certification":False}

"""Atomic, model-directed native NLE source placement with no hidden ripple.

A placement is an authored change in the canonical editable source graph, NOT
a file relocation, clip duplication, inferred dissolve, or new rights claim.
One transaction may move picture and sound clips simultaneously between
existing native tracks; all target geometry and the effect policy are explicit.

This module is pure: the upstream native MLT revision publisher revalidates the
complete plan, source custody, real source clocks, exact XML roundtrip, prior
immutable project and physical renderer afterwards.
"""
from __future__ import annotations

import copy


def _exact(value,label,limit):
    if type(value) is not int or not 0<=value<=limit:
        raise ValueError("Source placement "+label+" must be an exact bounded integer")
    return value


def _end(clip):
    first=clip.get("first_frame")
    last=clip.get("end_frame")
    pos=clip.get("position_frame")
    if (type(first) is not int or type(last) is not int
            or type(pos) is not int or not 0<=first<last
            or not 0<=pos or last>1000000):
        raise ValueError("Source placement requires measured nonempty source frame windows")
    stop=pos+last-first
    if stop>1000000:
        raise ValueError("Native source placement exceeds exact frame budget")
    return stop


def _validate_track(track,*,allow_empty=False):
    clips=track.get("clips") if isinstance(track,dict) else None
    if not isinstance(clips,list) or len(clips)>128 or (not allow_empty and not clips):
        raise ValueError("Source placement cannot erase or overflow a native track")
    end=-1
    for clip in clips:
        if not isinstance(clip,dict):
            raise ValueError("Native track contains an unverified source clip")
        now=_end(clip)
        if clip["position_frame"]<end:
            raise ValueError("Director placements would overlap original source-owned clips")
        end=now


def apply_native_source_placements(plan,action):
    """Move many independently authorized picture/sound clips as ONE transaction.

    Every source index refers to the untouched input revision (not a changing
    loop index). Destination positions refer to the final timeline. No edit
    can delete original media, alter an in/out source window, overlap the
    destination track, silently retime effects or create a new native track.
    """
    if (not isinstance(action,dict) or
            set(action)!={"kind","placements","effects"} or
            action.get("kind")!="place" or
            action.get("effects")!="inherit_destination_track_at_film_time"):
        raise ValueError("Source placement needs director-authored target and track-effect policy")
    records=action["placements"]
    if not isinstance(records,list) or not 1<=len(records)<=256:
        raise ValueError("Placement batch size is outside native host budget")
    if (not isinstance(plan,dict) or
            not isinstance(plan.get("tracks"),list) or
            not isinstance(plan.get("audio_tracks",[]),list)):
        raise ValueError("Source placement requires complete original native film")
    revised=copy.deepcopy(plan)
    source=copy.deepcopy(plan)
    selected=set()
    remove={"tracks":{},"audio_tracks":{}}
    insert={"tracks":{},"audio_tracks":{}}
    evidence=[]
    for item in records:
        if not isinstance(item,dict) or set(item)!={
                "domain","from_track","clip","to_track","at_frame"}:
            raise ValueError("Native clip placement contains unapproved fields")
        key={"picture":"tracks","sound":"audio_tracks"}.get(item["domain"])
        if key is None:
            raise ValueError("Native placement domain is neither picture nor sound")
        n=len(source.get(key,[]))
        if n<1:
            raise ValueError("No original native track in chosen media domain")
        fi=_exact(item["from_track"],"source track",n-1)
        ti=_exact(item["to_track"],"destination track",n-1)
        clips=source[key][fi].get("clips",[])
        if not isinstance(clips,list) or not clips or len(clips)>128:
            raise ValueError("Original source clip list is unavailable")
        ci=_exact(item["clip"],"source clip index",len(clips)-1)
        when=_exact(item["at_frame"],"destination frame",1000000)
        name=(key,fi,ci)
        if name in selected:
            raise ValueError("Director cannot move the same original clip twice")
        selected.add(name)
        clip=copy.deepcopy(clips[ci])
        span=_end(clip)-clip["position_frame"]
        if when+span>1000000:
            raise ValueError("Original source clip would exceed native film budget")
        if fi==ti and when==clip["position_frame"]:
            raise ValueError("Original source clip placement would change nothing")
        clip["position_frame"]=when
        remove[key].setdefault(fi,set()).add(ci)
        insert[key].setdefault(ti,[]).append(clip)
        evidence.append({"domain":item["domain"],
            "from_track":fi,"original_clip":ci,
            "to_track":ti,"prior_position":clips[ci]["position_frame"],
            "new_position":when,
            "unchanged_source_first":clip["first_frame"],
            "unchanged_source_end":clip["end_frame"],
            "asset_id":clip["asset_id"]})

    for key in ("tracks","audio_tracks"):
        # Inputs may describe any subset of tracks in any author order.
        # Validate only final state so legal simultaneous swaps do not
        # collide or spuriously fail mid-transaction.
        for i,track in enumerate(revised.get(key,[])):
            prior=source[key][i]["clips"]
            moved=remove[key].get(i,set())
            track["clips"]=[copy.deepcopy(c) for ci,c in enumerate(prior)
                            if ci not in moved]+insert[key].get(i,[])
            track["clips"].sort(key=lambda c:c["position_frame"])
            _validate_track(track,allow_empty=key=="tracks" and i>0)
            for k,v in source[key][i].items():
                if k!="clips" and track.get(k)!=v:
                    raise AssertionError("Native track effect policy was violated")
    if revised==plan:
        raise ValueError("Director-authored placement did not modify the native project")
    return revised,{"kind":"place","placements":evidence,
        "native_picture_and_sound_positions_are_explicit":True,
        "destination_track_effects_stay_at_original_film_time":True,
        "source_windows_and_rights_unchanged":True,
        "full_native_and_physical_reverification_required":True,
        "professional_or_artistic_quality_certified":False}

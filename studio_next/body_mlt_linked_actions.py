"""Typed, source-exact multi-track NLE razor and ripple algebra.

This operates on an already source-attested native MLT plan, not on raw MLT
services. No artistic shot duration, selection, transition, effect or style is
chosen here. All editor actions, group membership, time and direction come
from the director's structured decision. Source media remain immutable.

The existing native editor must independently verify the transformed plan,
recover its rebuilt XML losslessly and decode the resulting physical output.
"""
from __future__ import annotations

import copy
import math

from .body_mlt_local_edits import apply_local_window_action


def _int(value, name, lower=0, upper=1_000_000):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError("Linked NLE "+name+" requires an exact bounded frame integer")
    return value


def _tracks(choice, size, label):
    if not isinstance(choice,list) or len(choice)>size:
        raise ValueError("Linked NLE "+label+" must be explicit track indices")
    values=[]
    for index in choice:
        _int(index,label+" index",0,size-1)
        if index in values:
            raise ValueError("Linked NLE contains duplicate target "+label)
        values.append(index)
    if values != sorted(values):
        raise ValueError("Linked NLE target tracks must be in canonical order")
    return values


def _duration(clip):
    return clip["end_frame"]-clip["first_frame"]


def _film_length(plan):
    return max((c["position_frame"]+_duration(c)
                for track in plan["tracks"] for c in track["clips"]),default=0)


def _piece(clip, old_start, old_end, new_start):
    """A pixel/sample source slice, never invented or resampled material."""
    start=clip["position_frame"]
    first=clip["first_frame"]+(old_start-start)
    result=dict(clip)
    result["position_frame"]=new_start
    result["first_frame"]=first
    result["end_frame"]=first+(old_end-old_start)
    if old_end<=old_start or result["end_frame"]>clip["end_frame"]:
        raise ValueError("Linked NLE attempted an invalid source-media slice")
    return result


def _slice_track(clips,kind,at,amount=0):
    revised=[]
    changed=False
    retains_after=False
    end=at+amount
    for clip in clips:
        if not isinstance(clip,dict):
            raise ValueError("Linked NLE requires verified source clips")
        start=clip["position_frame"]
        stop=start+_duration(clip)
        if kind=="blade":
            if start<at<stop:
                revised.append(_piece(clip,start,at,start))
                revised.append(_piece(clip,at,stop,at))
                changed=True
            else:
                revised.append(dict(clip))
        elif kind=="ripple_insert":
            if stop<=at:
                revised.append(dict(clip))
            elif start>=at:
                revised.append(_piece(clip,start,stop,start+amount))
                changed=True
                retains_after=True
            else:
                revised.append(_piece(clip,start,at,start))
                revised.append(_piece(clip,at,stop,at+amount))
                changed=True
                retains_after=True
        elif kind=="ripple_delete":
            if stop<=at:
                revised.append(dict(clip))
            elif start>=end:
                revised.append(_piece(clip,start,stop,start-amount))
                changed=True
                retains_after=True
            else:
                changed=True
                if start<at:
                    revised.append(_piece(clip,start,min(at,stop),start))
                if stop>end:
                    revised.append(_piece(clip,max(end,start),stop,
                                          max(end,start)-amount))
                    retains_after=True
        else:
            raise ValueError("Unrecognized native NLE time-domain operation")
    return revised,changed,retains_after


def _sample(keys,at,field):
    if at<=keys[0]["frame"]:
        return keys[0][field]
    for before,after in zip(keys,keys[1:]):
        if at<=after["frame"]:
            start=before["frame"]
            blend=(at-start)/(after["frame"]-start)
            return before[field]+(after[field]-before[field])*blend
    return keys[-1][field]


def _canonical_generated(value,errors):
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError("Native editor effect control is not finite")
    # The current independently verified native MLT bridge emits precisely
    # twelve significant decimal figures. Preserve exact source values and
    # record only the interpolation rounding forced by this backend; do not
    # advertise scene-linear/high-precision acceptance from MLT alone.
    result=float(format(float(value),".12g"))
    errors.append(abs(float(value)-result))
    return result


def _bound(keys,frame,field,errors):
    return {"frame":frame,field:_canonical_generated(_sample(keys,frame,field),errors)}


def _rekey(keys,kind,at,amount,field,retains_after,errors):
    if not keys:
        return keys
    if kind=="blade":
        return keys
    if (not isinstance(keys,list) or len(keys)>128 or
            any(not isinstance(k,dict) or set(k)!={"frame",field}
                for k in keys)):
        raise ValueError("Linked NLE has unrepresentable original animation")
    before=[dict(k) for k in keys if k["frame"]<at]
    if kind=="ripple_insert":
        after=[{**k,"frame":k["frame"]+amount} for k in keys if k["frame"]>=at]
        if at==0:
            return [_bound(keys,0,field,errors)]+after
        if not after:
            # Last original value holds over the added blank, and there was
            # no future key that could alter the preceding interpolation.
            return before
        if before[-1]["frame"]!=at-1:
            before.append(_bound(keys,at-1,field,errors))
        if keys and not any(k["frame"]==at for k in keys):
            # This later timeline frame must carry the ORIGINAL boundary
            # value at source time `at`, not the value from `at+amount`.
            # Otherwise a ripple insert silently changes opacity/sound.
            boundary=_bound(keys,at,field,errors)
            boundary["frame"]=at+amount
            after.insert(0,boundary)
        return before+after
    end=at+amount
    after=[{**k,"frame":k["frame"]-amount} for k in keys if k["frame"]>=end]
    if at==0:
        if not after or after[0]["frame"]!=0:
            # Surviving first source frame was originally at `end`, but
            # now lies at native timeline frame zero.
            boundary=_bound(keys,end,field,errors)
            boundary["frame"]=0
            after.insert(0,boundary)
        return after
    if before and before[-1]["frame"]!=at-1:
        before.append(_bound(keys,at-1,field,errors))
    if retains_after and (not after or after[0]["frame"]!=at):
        # The first preserved post-cut source-frame value is sampled at
        # ORIGINAL frame `end`, then moved to revised timeline frame `at`.
        boundary=_bound(keys,end,field,errors)
        boundary["frame"]=at
        after.insert(0,boundary)
    return before+after


def apply_linked_editor_actions(plan,decision):
    """Pure, fail-closed transformation over a verified editable MLT project.

    Returns a new plan and evidence; never writes to owner files. The native
    export, import, source-custody, duration and actual-decoder gates are run
    afterward by the established transaction publisher.
    """
    if (not isinstance(plan,dict) or
            set(plan)-{"frame_rate","frame_size","tracks","audio_tracks"} or
            not {"frame_rate","frame_size","tracks"}.issubset(plan)):
        raise ValueError("Linked NLE needs the complete original project")
    if (not isinstance(decision,dict) or set(decision)!={"edits"} or
            not isinstance(decision["edits"],list) or
            not 1<=len(decision["edits"])<=128):
        raise ValueError("Linked NLE must receive explicit director-authored edits")
    result=copy.deepcopy(plan)
    records=[]
    max_precision_loss=0.0
    for action in decision["edits"]:
        if not isinstance(action,dict) or action.get("kind") not in (
                "blade","ripple_insert","ripple_delete","roll","slip","slide"):
            raise ValueError("Unsupported linked native editor operation")
        kind=action["kind"]
        if kind in ("roll","slip","slide"):
            result,window_evidence=apply_local_window_action(result,action)
            records.append(window_evidence)
            continue
        required={"kind","frame","picture_tracks","audio_tracks"}
        if kind!="blade":
            required|={"frames","automation"}
        if set(action)!=required:
            raise ValueError("Native editor action has missing or untrusted controls")
        picture=_tracks(action["picture_tracks"],len(result["tracks"]),"picture")
        sound=_tracks(action["audio_tracks"],len(result.get("audio_tracks",[])),"sound")
        if not picture and not sound:
            raise ValueError("Linked edit cannot have an empty selected group")
        total=_film_length(result)
        if total<=0:
            raise ValueError("Native film has no picture frames")
        at=_int(action["frame"],"edit position",0,total-1)
        if kind=="blade" and at==0:
            raise ValueError("Razor requires a real nonzero source boundary")
        amount=0
        if kind!="blade":
            if action["automation"]!="preserve_source_frame_values":
                raise ValueError("No implicit policy may retime an artist's effects")
            amount=_int(action["frames"],"duration",1,1000000)
            if kind=="ripple_delete" and at+amount>total:
                raise ValueError("Ripple deletion exceeds actual picture duration")
        touched=0
        operation_errors=[]
        for key,selection in (("tracks",picture),("audio_tracks",sound)):
            for idx in selection:
                track=result[key][idx]
                clips,changed,retains_after=_slice_track(
                    track["clips"],kind,at,amount)
                if not changed:
                    continue
                touched+=1
                if not clips:
                    raise ValueError("An editorial action would erase an entire native track")
                if len(clips)>128:
                    raise ValueError("Native clip budget exceeded by exact linked edit")
                track["clips"]=clips
                if kind!="blade":
                    controls=(("opacity","opacity_keyframes",1),) if (
                        key=="tracks") else (
                        ("gain_db","gain_keyframes",0),
                        ("pan","pan_keyframes",0.5))
                    for field,prop,default in controls:
                        if prop not in track:
                            continue
                        preserved=_rekey(track[prop],kind,at,amount,field,
                                         retains_after,operation_errors)
                        if len(preserved)==1:
                            # An entire automation curve can collapse into
                            # one physical value; preserve it as a scalar
                            # only if it is not the renderer's true identity.
                            value=preserved[0][field]
                            del track[prop]
                            if value!=default:
                                track[field]=value
                        else:
                            track[prop]=preserved
        if not touched:
            raise ValueError("Linked edit did not change a source-attested native shot")
        errors=max(operation_errors,default=0.0)
        max_precision_loss=max(max_precision_loss,errors)
        records.append({"kind":kind,"at_frame":at,"frames":amount,
                        "picture_tracks":picture,"audio_tracks":sound,
                        "source_frame_spans_preserved":kind!="ripple_delete",
                        "interpolation_rounding_max_absolute":errors})
    return result,{"operations":records,
        "largest_interpolated_key_rounding":max_precision_loss,
        "native_renderer_precision_and_artistic_fidelity_approved":False}

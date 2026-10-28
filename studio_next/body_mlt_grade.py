"""Typed, fully reversible source-grade control on the native film clock.

This deliberately exposes the installed MLT lift_gamma_gain engine's nine RGB
color-wheel controls instead of prescribing a look or allowing native plugin
properties from model text. It is display-referred grading on attested BT.709
footage, not a scene-linear, ACES or HDR color-management pipeline.

Reference: https://www.mltframework.org/plugins/FilterLift_gamma_gain/
"""
from __future__ import annotations

import math

GRADE_FIELDS=tuple(f"{kind}_{channel}" for kind in ("lift","gamma","gain")
                   for channel in ("r","g","b"))
GRADE_NATIVE_FIELDS={"track","mlt_service",*GRADE_FIELDS}


def _grade_number(field,value):
    if field not in GRADE_FIELDS or type(value) not in (int,float):
        raise ValueError("Native RGB grade requires exact typed controls")
    try:finite=math.isfinite(value)
    except OverflowError:finite=False
    if not finite:
        raise ValueError("Native grade cannot contain NaN or infinite channel levels")
    low=0 if field.startswith("lift_") else 0.01
    high=5
    if not low<=value<=high:
        raise ValueError("Native grade level exceeds the explicitly supported color-wheel range")
    numeric=float(value)
    if numeric==0:return "0"
    formatted=format(numeric,".12g")
    return formatted if float(formatted)==numeric else repr(numeric)


def encode_grade(grade,frames):
    """Nine artist-authored channel curves, without scripts or implicit looks."""
    if not isinstance(grade,dict) or set(grade)!={"keyframes"}:
        raise ValueError("Native grade must contain only its exact film-frame keyframes")
    keys=grade["keyframes"]
    if not isinstance(keys,list) or not 1<=len(keys)<=128:
        raise ValueError("Native grade needs 1..128 explicit RGB keys")
    if type(frames) is not int or frames<1 or frames>1_000_000:
        raise ValueError("Native grade requires an exact bounded film clock")
    curves={field:[] for field in GRADE_FIELDS}
    previous=-1
    for key in keys:
        if not isinstance(key,dict) or set(key)!={"frame",*GRADE_FIELDS}:
            raise ValueError("Native grade key must contain all nine RGB lift/gamma/gain values")
        frame=key["frame"]
        if (type(frame) is not int or frame<0 or frame>=frames
                or frame<=previous or previous==-1 and frame!=0):
            raise ValueError("Native grade keyframes must start at zero and strictly increase")
        for field in GRADE_FIELDS:
            curves[field].append(str(frame)+"="+_grade_number(field,key[field]))
        previous=frame
    return {"mlt_service":"lift_gamma_gain",
            **{name:";".join(parts) for name,parts in curves.items()}}


def decode_grade(properties,frames):
    """Reject duplicate, unknown, noncanonical and expression-valued XML."""
    if (not isinstance(properties,dict) or set(properties)!=GRADE_NATIVE_FIELDS
            or properties.get("mlt_service")!="lift_gamma_gain"
            or not isinstance(properties.get("track"),str)):
        raise ValueError("Unapproved native RGB grading filter properties")
    tracks=[properties[field].split(";") if isinstance(properties[field],str) else []
            for field in GRADE_FIELDS]
    if not 1<=len(tracks[0])<=128 or any(len(t)!=len(tracks[0]) for t in tracks):
        raise ValueError("Native RGB grading channels differ in their frame clocks")
    keys=[]
    try:
        for i in range(len(tracks[0])):
            one={}
            frame=None
            for field,values in zip(GRADE_FIELDS,tracks):
                parts=values[i].split("=")
                if len(parts)!=2 or not parts[0].isdigit() or (
                        frame is not None and str(frame)!=parts[0]):
                    raise ValueError("Native RGB grade contains noncanonical keyframe syntax")
                frame=int(parts[0])
                one[field]=float(parts[1])
            keys.append({"frame":frame,**one})
        grade={"keyframes":keys}
        expected={"track":properties["track"],**encode_grade(grade,frames)}
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError("Native RGB grading cannot be reconstructed safely") from exc
    if expected!=properties:
        raise ValueError("Native RGB grading cannot roundtrip without loss")
    return grade


def rekey_grade(grade,kind,at,amount,retains_after,errors):
    """Keep all nine artist-authored channels on the surviving film frames."""
    from .body_mlt_transform import rekey_geometry
    return rekey_geometry(grade,GRADE_FIELDS,kind,at,amount,retains_after,errors)

"""Director-authored native video-tone controls, not preset grading.

MLT's installed frei0r.contrast0r and frei0r.saturat0r filters each accept
animated parameter "0" in [0,1]. Native neutral levels: contrast=0.5,
saturation=0.125. The director selects both curves AND their relative order.
Reference: https://mltframework.org/plugins/FilterFrei0r-contrast0r/
           https://mltframework.org/plugins/FilterFrei0r-saturat0r/
The controls operate on verified display-referred BT.709 source frames.
They are not HDR/ACES/scene-linear color-management substitutes.
"""
from __future__ import annotations

import math

TONE_NAMES=("contrast","saturation")
TONE_SERVICES={
    "contrast":"frei0r.contrast0r",
    "saturation":"frei0r.saturat0r",
}
TONE_SERVICE_NAMES=frozenset(TONE_SERVICES.values())
TONE_NATIVE_FIELDS={"track","mlt_service","0"}


def _number(value):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:
        raise ValueError("Native tone requires a finite director-authored level in [0,1]")
    numeric=float(value)
    if numeric==0:return "0"
    shortened=format(numeric,".12g")
    return shortened if float(shortened)==numeric else repr(numeric)


def encode_tone(tone,frames):
    """Return native filters in exactly the model's requested visual order."""
    if not isinstance(tone,dict) or set(tone)!={"order","keyframes"}:
        raise ValueError("Native tone requires an explicit effect order and film-frame keys")
    order=tone["order"]
    if (not isinstance(order,list) or len(order)!=2 or
            set(order)!=set(TONE_NAMES) or
            any(type(item) is not str for item in order)):
        raise ValueError("Both native tone effects must appear once, in director-selected order")
    keys=tone["keyframes"]
    if (not isinstance(keys,list) or not 1<=len(keys)<=128 or
            type(frames) is not int or not 1<=frames<=1_000_000):
        raise ValueError("Tone automation requires a bounded original movie frame clock")
    records={name:[] for name in TONE_NAMES}
    previous=-1
    for key in keys:
        if not isinstance(key,dict) or set(key)!={"frame",*TONE_NAMES}:
            raise ValueError("Every tone key must explicitly author contrast and saturation")
        frame=key["frame"]
        if (type(frame) is not int or not 0<=frame<frames or
                frame<=previous or previous==-1 and frame!=0):
            raise ValueError("Tone keys must start at film frame zero and strictly increase")
        for name in TONE_NAMES:
            records[name].append(f"{frame}="+_number(key[name]))
        previous=frame
    return [{"mlt_service":TONE_SERVICES[name],"0":";".join(records[name])}
            for name in order]


def decode_tone_service(properties,frames):
    """Parse one allowlisted native Frei0r service, rejecting MLT expressions."""
    if (not isinstance(properties,dict) or set(properties)!=TONE_NATIVE_FIELDS or
            properties["mlt_service"] not in TONE_SERVICE_NAMES or
            properties["track"] not in tuple(str(i) for i in range(8)) or
            not isinstance(properties["0"],str) or len(properties["0"])>8192):
        raise ValueError("Untrusted or oversized native source-tone filter properties")
    keys=[]
    try:
        for piece in properties["0"].split(";"):
            parts=piece.split("=")
            if len(parts)!=2 or not parts[0].isdigit():
                raise ValueError("Unapproved native tone animation syntax")
            frame=int(parts[0]);level=float(parts[1])
            keys.append((frame,level))
        if not 1<=len(keys)<=128 or keys[0][0]!=0 or any(
                b[0]<=a[0] or b[0]>=frames for a,b in zip(keys,keys[1:])):
            raise ValueError("Native tone frames are not a monotone film clock")
        if any(f"{frame}="+_number(value)!=piece for (
                frame,value),piece in zip(keys,properties["0"].split(";"))):
            raise ValueError("Original tone filter is not canonical")
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError("Native tone expression cannot roundtrip to exact safe levels") from exc
    if keys[-1][0]>=frames:
        raise ValueError("Tone effect exceeds original picture frame clock")
    name=next(name for name,service in TONE_SERVICES.items()
              if service==properties["mlt_service"])
    return name,keys


def decode_tone(filters,frames):
    """Recover two original effects and their selected order without loss."""
    if not isinstance(filters,list) or len(filters)!=2:
        raise ValueError("Native tone graph lost one of the original effects")
    decoded=[decode_tone_service(props,frames) for props in filters]
    if (set(name for name,_ in decoded)!=set(TONE_NAMES) or
            [frame for frame,_ in decoded[0][1]]!=[
                frame for frame,_ in decoded[1][1]] or
            any(props["track"]!=filters[0]["track"] for props in filters)):
        raise ValueError("Native tone filters have duplicate names, tracks or unrelated time clocks")
    values={name:dict(keys) for name,keys in decoded}
    tone={"order":[name for name,_ in decoded],
          "keyframes":[{"frame":frame,
                        **{name:values[name][frame] for name in TONE_NAMES}}
                       for frame,_ in decoded[0][1]]}
    expected=[{"track":filters[0]["track"],**row}
              for row in encode_tone(tone,frames)]
    if expected!=filters:
        raise ValueError("Native tone order or numeric precision cannot roundtrip")
    return tone


def rekey_tone(tone,kind,at,amount,retains_after,errors):
    """Preserve both independent controls over all surviving source frames."""
    from .body_mlt_transform import rekey_geometry
    return rekey_geometry(tone,TONE_NAMES,kind,at,amount,retains_after,errors)

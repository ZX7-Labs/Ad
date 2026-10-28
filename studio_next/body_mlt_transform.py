"""Typed, reversible native layer geometry on the authored film-frame clock.

MLT 7.22's Qt filter applies a rectangle, centered rotation and fit/distort
through QTransform. The background is fixed transparent, never a producer URL.
https://github.com/mltframework/mlt/blob/v7.22.0/src/modules/qt/filter_qtblend.cpp
https://www.mltframework.org/plugins/FilterQtblend/

The source picture is fitted or distorted into a pixel rectangle, centered
inside it, then rotated around its center. Keys interpolate linearly in film
frames and hold after the last key. Geometry precedes layer compositing.
This bridge covers upper picture layers; the bottom remains the opaque
source backing. It does not claim masks, perspective or color management.
"""
from __future__ import annotations

import math


TRANSFORM_FIELDS=("x","y","width","height","rotation_degrees")
TRANSFORM_NATIVE_CONSTANTS={
    "mlt_service":"qtblend", "background_color":"0",
    "compositing":"0", "rotate_center":"1",
}
TRANSFORM_NATIVE_FIELDS=set(TRANSFORM_NATIVE_CONSTANTS)|{
    "track","distort","rect","rotation"}


def _number(value,field):
    try:finite=type(value) in (int,float) and math.isfinite(value)
    except OverflowError:finite=False
    if not finite:
        raise ValueError("Native transform needs finite typed pixel/angle numbers")
    low,high={"x":(-32768,32768),"y":(-32768,32768),
              "width":(0,16384),"height":(0,16384),
              "rotation_degrees":(-36000,36000)}[field]
    if not low<=value<=high or field in ("width","height") and value<=0:
        raise ValueError("Native transform exceeds explicit geometry host budget")
    numeric=float(value)
    if numeric==0:return "0"
    historical=format(numeric,".12g")
    return historical if float(historical)==numeric else repr(numeric)


def encode_transform(transform,frames):
    """No native expressions, URLs, plugins, implicit aspect or inferred keys."""
    if (not isinstance(transform,dict) or set(transform)!={"aspect","keyframes"}
            or transform["aspect"] not in ("preserve","distort")):
        raise ValueError("Native transform requires an explicit aspect policy and keyframes")
    keys=transform["keyframes"]
    if not isinstance(keys,list) or not 1<=len(keys)<=128:
        raise ValueError("Native transform needs 1..128 authored film-frame keys")
    rect=[];rotation=[];previous=-1
    for key in keys:
        if not isinstance(key,dict) or set(key)!={"frame",*TRANSFORM_FIELDS}:
            raise ValueError("Native transform key needs frame, rectangle and rotation only")
        frame=key["frame"]
        if (type(frame) is not int or not 0<=frame<frames or
                frame<=previous or previous==-1 and frame!=0):
            raise ValueError("Native transform keys must begin at zero and strictly increase")
        values={field:_number(key[field],field) for field in TRANSFORM_FIELDS}
        if key["width"]*key["height"]>67108864:
            raise ValueError("Native transform exceeds decoded image-area host budget")
        prefix=str(frame)+"="
        rect.append(prefix+" ".join(values[f] for f in TRANSFORM_FIELDS[:4])+" 1")
        rotation.append(prefix+values["rotation_degrees"])
        previous=frame
    # Opposing width/height ramps can have a larger area BETWEEN legal keys.
    # Bound the quadratic's interior maximum as well as its endpoints.
    for first,last in zip(keys,keys[1:]):
        w,h=first["width"],first["height"]
        dw,dh=last["width"]-w,last["height"]-h
        if dw*dh<0:
            t=-(w*dh+h*dw)/(2*dw*dh)
            if 0<t<1 and (w+t*dw)*(h+t*dh)>67108864:
                raise ValueError("Native transform interpolated image-area exceeds host budget")
    return {**TRANSFORM_NATIVE_CONSTANTS,
            "distort":"1" if transform["aspect"]=="distort" else "0",
            "rect":";".join(rect),
            "rotation":";".join(rotation)}


def decode_transform(properties,frames):
    """Accept only an exact canonical rebuild of this typed native geometry."""
    if (set(properties)!=TRANSFORM_NATIVE_FIELDS or
            any(properties[k]!=v for k,v in TRANSFORM_NATIVE_CONSTANTS.items())
            or properties["distort"] not in ("0","1")):
        raise ValueError("Native transform contains unapproved executable properties")
    rect=properties["rect"];rotation=properties["rotation"]
    if (not isinstance(rect,str) or not isinstance(rotation,str) or
            len(rect)>32768 or len(rotation)>8192):
        raise ValueError("Native transform animation exceeds verification budget")
    rectangles=rect.split(";");rotations=rotation.split(";")
    if not 1<=len(rectangles)<=128 or len(rectangles)!=len(rotations):
        raise ValueError("Native transform animation clocks differ")
    keys=[]
    try:
        for rectangle,angle in zip(rectangles,rotations):
            frame,coords=rectangle.split("=")
            rframe,degrees=angle.split("=")
            values=coords.split(" ")
            if frame!=rframe or not frame.isdigit() or values[-1]!="1" or len(values)!=5:
                raise ValueError("Native transform rectangle/rotation clock is not canonical")
            keys.append({"frame":int(frame),
                         **dict(zip(TRANSFORM_FIELDS[:4],map(float,values[:4]))),
                         "rotation_degrees":float(degrees)})
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError("Native transform contains unsupported animation syntax") from exc
    transform={"aspect":"distort" if properties["distort"]=="1" else "preserve",
               "keyframes":keys}
    expected=encode_transform(transform,frames)
    if any(properties[k]!=v for k,v in expected.items()):
        raise ValueError("Native transform cannot roundtrip without creative loss")
    return transform


def rekey_transform(transform,kind,at,amount,retains_after,errors):
    """Preserve all five geometry values at every surviving source frame."""
    from .body_mlt_linked_actions import _rekey
    keys=transform["keyframes"]
    curves=[]
    for field in TRANSFORM_FIELDS:
        curve=[{"frame":k["frame"],field:k[field]} for k in keys]
        curves.append(_rekey(curve,kind,at,amount,field,retains_after,errors))
    if any([k["frame"] for k in c]!=[k["frame"] for k in curves[0]] for c in curves):
        raise ValueError("Native transform edit separated rectangle and rotation clocks")
    merged=[{"frame":curves[0][i]["frame"],
             **{f:curves[j][i][f] for j,f in enumerate(TRANSFORM_FIELDS)}}
            for i in range(len(curves[0]))]
    return {"aspect":transform["aspect"],"keyframes":merged}

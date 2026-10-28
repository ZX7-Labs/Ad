"""Typed, reversible native layer geometry on the authored film-frame clock.

MLT 7.22's Qt filter applies a rectangle, centered rotation and fit/distort
through QTransform. The background is fixed transparent, never a producer URL.
https://github.com/mltframework/mlt/blob/v7.22.0/src/modules/qt/filter_qtblend.cpp
https://github.com/mltframework/mlt/blob/v7.22.0/src/modules/qt/filter_qtcrop.cpp
https://www.mltframework.org/plugins/FilterQtblend/

The source picture is fitted or distorted into a pixel rectangle, centered
inside it, then rotated around its center. Keys interpolate linearly in film
frames and hold after the last key. Geometry precedes layer compositing.
Upper picture layers also accept an independently animated source-space
rounded-rectangle alpha window before geometry. The bottom remains the opaque
source backing. This is not arbitrary roto, perspective or color management.
"""
from __future__ import annotations

import math


TRANSFORM_FIELDS=("x","y","width","height","rotation_degrees")
MASK_FIELDS=("x","y","width","height","rounding")
MASK_NATIVE_CONSTANTS={"mlt_service":"qtcrop","color":"#00000000","circle":"0"}
MASK_NATIVE_FIELDS=set(MASK_NATIVE_CONSTANTS)|{"track","rect","radius"}
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
              "rotation_degrees":(-36000,36000),"rounding":(0,1)}[field]
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
    rect,rotation=_encode_geometry_keys(transform,frames,TRANSFORM_FIELDS)
    return {**TRANSFORM_NATIVE_CONSTANTS,
            "distort":"1" if transform["aspect"]=="distort" else "0",
            "rect":rect,"rotation":rotation}


def encode_mask(mask,frames):
    """An alpha window in original source-canvas pixels; no opaque filler."""
    if not isinstance(mask,dict) or set(mask)!={"keyframes"}:
        raise ValueError("Native mask requires only authored source-canvas keyframes")
    rect,radius=_encode_geometry_keys(mask,frames,MASK_FIELDS)
    return {**MASK_NATIVE_CONSTANTS,"rect":rect,"radius":radius}


def _encode_geometry_keys(control,frames,fields):
    keys=control["keyframes"]
    if not isinstance(keys,list) or not 1<=len(keys)<=128:
        raise ValueError("Native transform needs 1..128 authored film-frame keys")
    rect=[];rotation=[];previous=-1
    for key in keys:
        if not isinstance(key,dict) or set(key)!={"frame",*fields}:
            raise ValueError("Native geometry key has an unsupported field set")
        frame=key["frame"]
        if (type(frame) is not int or not 0<=frame<frames or
                frame<=previous or previous==-1 and frame!=0):
            raise ValueError("Native transform keys must begin at zero and strictly increase")
        values={field:_number(key[field],field) for field in fields}
        if key["width"]*key["height"]>67108864:
            raise ValueError("Native transform exceeds decoded image-area host budget")
        prefix=str(frame)+"="
        rect.append(prefix+" ".join(values[f] for f in fields[:4])+" 1")
        rotation.append(prefix+values[fields[-1]])
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
    return ";".join(rect),";".join(rotation)


def decode_transform(properties,frames):
    """Accept only an exact canonical rebuild of this typed native geometry."""
    if (set(properties)!=TRANSFORM_NATIVE_FIELDS or
            any(properties[k]!=v for k,v in TRANSFORM_NATIVE_CONSTANTS.items())
            or properties["distort"] not in ("0","1")):
        raise ValueError("Native transform contains unapproved executable properties")
    keys=_decode_geometry_keys(properties["rect"],properties["rotation"],TRANSFORM_FIELDS)
    transform={"aspect":"distort" if properties["distort"]=="1" else "preserve",
               "keyframes":keys}
    expected=encode_transform(transform,frames)
    if any(properties[k]!=v for k,v in expected.items()):
        raise ValueError("Native transform cannot roundtrip without creative loss")
    return transform


def decode_mask(properties,frames):
    if (set(properties)!=MASK_NATIVE_FIELDS or
            any(properties[k]!=v for k,v in MASK_NATIVE_CONSTANTS.items())):
        raise ValueError("Native mask contains unapproved executable properties")
    mask={"keyframes":_decode_geometry_keys(properties["rect"],properties["radius"],MASK_FIELDS)}
    if any(properties[k]!=v for k,v in encode_mask(mask,frames).items()):
        raise ValueError("Native mask cannot roundtrip without creative loss")
    return mask


def _decode_geometry_keys(rect,rotation,fields):
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
                         **dict(zip(fields[:4],map(float,values[:4]))),
                         fields[-1]:float(degrees)})
    except (TypeError,ValueError,OverflowError) as exc:
        raise ValueError("Native transform contains unsupported animation syntax") from exc
    return keys


def rekey_transform(transform,kind,at,amount,retains_after,errors):
    """Preserve all five geometry values at every surviving source frame."""
    return rekey_geometry(transform,TRANSFORM_FIELDS,kind,at,amount,retains_after,errors)


def rekey_geometry(control,fields,kind,at,amount,retains_after,errors):
    from .body_mlt_linked_actions import _rekey
    keys=control["keyframes"]
    curves=[]
    for field in fields:
        curve=[{"frame":k["frame"],field:k[field]} for k in keys]
        curves.append(_rekey(curve,kind,at,amount,field,retains_after,errors))
    if any([k["frame"] for k in c]!=[k["frame"] for k in curves[0]] for c in curves):
        raise ValueError("Native transform edit separated rectangle and rotation clocks")
    merged=[{"frame":curves[0][i]["frame"],
             **{f:curves[j][i][f] for j,f in enumerate(fields)}}
            for i in range(len(curves[0]))]
    return {**control,"keyframes":merged}

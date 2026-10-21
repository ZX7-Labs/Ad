"""Strict Film IR -> existing procedural motion_studio project compiler.

This is an *execution bridge*, not a creativity engine. It accepts only fully
described, cleared original 2D/2.5D artwork. It MUST NOT fabricate absent images,
shots, camera geometry, brand evidence, speech or rights.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from .film_ir import validate_film_ir

TOOL_ID = "motion_studio.composite"
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$")
_FONT_NAME = re.compile(r"^[\w .,:=-]{1,140}$",re.UNICODE)
_DRAWABLES = frozenset({"rect", "ellipse", "line", "polygon", "text"})
_MOTION = frozenset({"x", "y", "scale", "scale_x", "scale_y", "angle", "opacity", "reveal", "blur"})
_EASE = frozenset({"linear", "smooth", "in", "out", "spring"})


class UnsupportedMotionPlan(ValueError):
    """A film plan cannot be implemented with this particular actual renderer."""


def _require(condition, message):
    if not condition:
        raise UnsupportedMotionPlan(message)


def _number(v, name, lo=-1e6, hi=1e6):
    _require(not isinstance(v, bool) and isinstance(v, (int, float))
             and math.isfinite(v) and lo <= v <= hi, name + " must be finite/in range")
    return v


def _xy(v, name):
    _require(isinstance(v, (tuple, list)) and len(v) == 2, name + " needs [x,y]")
    return [_number(x, name + " coordinate") for x in v]


def _color(v, name):
    _require(isinstance(v, str) and bool(_COLOR.fullmatch(v)), name + " needs #RRGGBB or #RRGGBBAA")
    return v


def _artwork(asset, shot_key):
    spec = asset.get("artwork")
    _require(isinstance(spec, dict), shot_key + " lacks drawable artwork; no invented graphic fallback")
    _require(set(spec) <= {"size", "items"}, "Unsupported artwork properties")
    size = _xy(spec.get("size"), shot_key + ".size")
    for dimension in size:
        _number(dimension, shot_key + ".size", 1, 4096)
    items = spec.get("items")
    _require(isinstance(items, list) and len(items) > 0, shot_key + " needs drawable items")
    _require(len(items) <= 300, "Too many items for limited CPU renderer")
    clean = []
    for idx, item in enumerate(items):
        label = f"{shot_key}.items[{idx}]"
        _require(isinstance(item, dict), label + " must be object")
        kind = item.get("type")
        _require(kind in _DRAWABLES, label + " requires a supported 2D drawable")
        allowed = {"type", "fill", "stroke", "width"}
        if kind in ("rect", "ellipse"):
            allowed |= {"box", "radius"} if kind == "rect" else {"box"}
        if kind in ("line", "polygon"):
            allowed |= {"points"}
        if kind == "text":
            allowed |= {"text", "at", "size", "font", "align", "leading"}
        _require(set(item) <= allowed, label + " has unsupported drawing fields")
        if "fill" in item:
            _color(item["fill"], label + ".fill")
        if "stroke" in item:
            _color(item["stroke"], label + ".stroke")
        if "width" in item:
            _number(item["width"], label + ".width", 0.1, 64)
        if kind in ("rect", "ellipse"):
            b = item.get("box")
            _require(isinstance(b, list) and len(b) == 4, label + " box needs four numbers")
            coords = [_number(x, label + ".box") for x in b]
            _require(coords[0] <= coords[2] and coords[1] <= coords[3], label + " inverted box")
        if kind == "rect" and "radius" in item:
            _number(item["radius"], label + ".radius", 0, 1024)
        if kind in ("line", "polygon"):
            pts = item.get("points")
            _require(isinstance(pts, list) and len(pts) >= (2 if kind == "line" else 3)
                     and len(pts) <= 200, label + " needs defined points")
            for pt in pts: _xy(pt, label + ".point")
        if kind == "text":
            _require(isinstance(item.get("text"), str) and 0 < len(item["text"]) <= 500,
                     label + " requires explicitly authored text")
            _xy(item.get("at"), label + ".at")
            _number(item.get("size"), label + ".size", 2, 256)
            _require(isinstance(item.get("font","sans"),str) and
                     _FONT_NAME.fullmatch(item.get("font","sans")) is not None,
                     label + " font must be a specific installed family name or generic")
            _require(item.get("align", "left") in ("left", "center", "right"),
                     label + " unsupported alignment")
            if "leading" in item: _number(item["leading"], label + ".leading", 0.5, 3)
        clean.append(item)
    return {"size": size, "items": clean}


def _layer(layer, ids, sid, duration):
    _require(isinstance(layer, dict), sid + " layer must be object")
    allowed = {"asset", "x", "y", "scale", "scale_x", "scale_y", "angle",
               "opacity", "blur", "reveal", "in", "out", "shadow", "animate"}
    _require(set(layer) <= allowed, sid + " has unsupported layer operation")
    _require(layer.get("asset") in ids, sid + " layer references undefined art")
    for field in ("x", "y", "angle", "blur", "in", "out"):
        if field in layer: _number(layer[field], sid + "." + field, 0 if field in ("blur","in","out") else -10000, 10000)
    for field in ("scale", "scale_x", "scale_y"):
        if field in layer: _number(layer[field], sid + "." + field, 0.01, 30)
    for field in ("opacity", "reveal"):
        if field in layer: _number(layer[field], sid + "." + field, 0, 1)
    if "in" in layer and "out" in layer: _require(layer["in"] <= layer["out"], sid + " layer has inverted active interval")
    shadow = layer.get("shadow")
    if shadow is not None:
        _require(isinstance(shadow, dict) and set(shadow) <= {"alpha","blur","dx","dy"},
                 sid + " shadow invalid")
        for k,v in shadow.items(): _number(v, sid + ".shadow." + k, 0 if k in ("blur","alpha") else -500, 1 if k == "alpha" else 500)
    tracks = layer.get("animate", {})
    _require(isinstance(tracks, dict) and set(tracks) <= _MOTION, sid + " unknown keyframe property")
    for prop, track in tracks.items():
        _require(isinstance(track, list) and bool(track), sid + " empty keyframe track")
        prev = -1.
        for frame in track:
            _require(isinstance(frame, list) and 2 <= len(frame) <= 3, sid + " invalid keyframe")
            at = _number(frame[0], sid + ".at", 0, duration)
            _require(at > prev, sid + " keyframes not strictly increasing")
            prev = at
            if prop in ("opacity", "reveal"):
                _number(frame[1], sid + "." + prop, 0, 1)
            elif prop in ("scale", "scale_x", "scale_y"):
                _number(frame[1], sid + "." + prop, 0.01, 30)
            elif prop == "blur":
                _number(frame[1], sid + "." + prop, 0, 200)
            else:
                _number(frame[1], sid + "." + prop, -10000, 10000)
            if len(frame) == 3:
                _require(frame[2] in _EASE, sid + " unknown easing")
    return layer


def compile_motion_project(ir, *, fact_ids=frozenset()):
    """Return renderer JSON, or fail closed. Does not render, or approve a story."""
    _require(isinstance(ir, dict), "Film IR must be an object")
    _require(isinstance(fact_ids, (set, frozenset)) and
             all(isinstance(x, str) for x in fact_ids), "Caller-owned fact IDs required")
    check = validate_film_ir(ir, installed_tool_ids={TOOL_ID}, fact_ids=fact_ids)
    _require(check.render_ready, "Film IR not render-ready: " + "; ".join(check.errors + check.warnings))
    meta = ir["project"]
    _require(isinstance(meta, dict), "Project metadata missing")
    _require(isinstance(meta.get("title"), str) and meta["title"].strip(), "Explicit title required")
    _require(isinstance(meta.get("background"), str), "Director must select background")
    _color(meta["background"], "project.background")
    width = _number(meta.get("width"), "project.width", 320, 2160)
    height = _number(meta.get("height"), "project.height", 320, 4096)
    _require(isinstance(width,int) and isinstance(height,int), "Integer canvas dimensions required")
    voice = meta.get("voice")
    _require(voice in ("M3", "F2", "no_voice"), "Director must choose installed voice or meaningful silence")
    graph = ir["tool_graph"]
    _require(len(graph) == 1 and graph[0]["tool_id"] == TOOL_ID and graph[0].get("inputs", {}) == {},
             "Motion adapter supports exactly one explicit static composite invocation, no arbitrary commands")
    assets = {}
    for a in ir["assets"]:
        aid=a["id"]
        _require(a.get("rights") in ("generated_original", "appropriately_licensed"),
                 aid + " only inline cleared drawings supported, not footage or external assets")
        _require(a.get("location") == "inline://"+aid, aid + " location must be owned inline graphic")
        assets[aid] = _artwork(a, aid)
    scenes=[]
    for s in ir["shots"]:
        sid=s["id"]
        duration=_number(s.get("duration_seconds"), sid+".duration", 0.5, 60)
        _require(isinstance(s.get("narration"),str), sid+" needs explicit spoken text or empty silence")
        if voice=="no_voice":
            _require(not s["narration"].strip(), "no_voice cannot synthesize spoken script")
        _require("layers" in s and isinstance(s["layers"],list) and s["layers"],
                 sid+" needs deliberately authored drawable layers")
        drawn={l.get("asset") for l in s["layers"] if isinstance(l,dict)}
        _require(drawn == set(s.get("asset_refs",[])), sid+" declared assets must match rendered assets")
        clean_layers=[_layer(l, assets, sid, duration) for l in s["layers"]]
        _require(len(clean_layers) <= 100, sid+" exceeds motion renderer layer budget")
        cues=s.get("cues", [])
        _require(isinstance(cues,list), sid+" cues must be a list")
        for cue in cues:
            _require(isinstance(cue,dict) and cue.get("type") in ("ink","paper","tap"),
                     sid+" unsupported audio cue")
            _require(set(cue) <= {"type","at","seconds","gain","hz"}, sid+" invalid audio cue fields")
            _number(cue.get("at"),sid+" cue time",0,duration)
            _number(cue.get("seconds",.18),sid+" cue length",.01,duration)
            _require(cue["at"]+cue.get("seconds",.18) <= duration, sid+" cue exceeds shot")
            if "gain" in cue:_number(cue["gain"],sid+" gain",0,1)
            if "hz" in cue:_number(cue["hz"],sid+" frequency",30,12000)
        scenes.append({"id":sid, "min_seconds":duration, "narration":s["narration"],
                       "layers":clean_layers, "cues":cues,
                       "tail":0, "voice_delay":0})
    score=meta.get("score",[])
    _require(isinstance(score,list), "Score must be list")
    total=sum(s["min_seconds"] for s in scenes)
    for note in score:
        _require(isinstance(note,dict) and set(note) <= {"at","seconds","midi","gain","decay"},
                 "Score contains unsupported note")
        _number(note.get("at"),"note time",0,total)
        _number(note.get("seconds",1.3),"note seconds",.01,total)
        _number(note.get("midi"),"note pitch",0,127)
        for f in ("gain","decay"):
            if f in note:_number(note[f],"note "+f,0,10)
    return {"title":meta["title"],"direction_source":"Compiled from explicit, rights-checked Film IR; artistic approval NOT implied",
            "width":width,"height":height,"background":meta["background"],
            "grid":32,"grid_color":meta["background"],"voice":voice,
            "assets":assets,"scenes":scenes,"score":score}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--fact-ids",nargs="*",default=[])
    args=parser.parse_args()
    ir=json.loads(args.ir.read_text(encoding="utf-8"))
    compiled=compile_motion_project(ir,fact_ids=frozenset(args.fact_ids))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(compiled,ensure_ascii=False,indent=2),encoding="utf-8")
    print("COMPILED",args.out,"shots",len(compiled["scenes"]))


if __name__=="__main__":
    main()

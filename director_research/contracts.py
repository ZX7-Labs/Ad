"""Explicit contracts for the grounded Director experiment; no rendering claims."""
import copy
import math
import re

from jsonschema import Draft202012Validator


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1}
STRINGS = {"type": "array", "items": TEXT}
CONCEPT = obj({key: TEXT for key in (
    "concept", "audience_insight", "hook", "visual_motif", "why_this_concept")})
DESIGN = obj({
    **{key: TEXT for key in ("typography", "camera_language", "lighting", "use_3d",
                            "music", "sound_design", "voice_direction")},
    "palette": {"type": "array", "items": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"},
                "minItems": 2, "maxItems": 5},
    "voice": {"type": "string", "enum": ["M3", "F2"]}})
CAPABILITIES = {
    "typography": "Text drawing and wrapping: src/film_v3.py:textlines",
    "vector_shapes": "Original simple lines, circles and rectangles: Pillow drawing",
    "layered_transform": "Translate, scale, rotate, soft shadow: src/film_v3.py:place",
    "cuts_and_fades": "Simple cut or opacity transition; no material morph simulation",
    "procedural_audio": "Synthetic tones/cut accents: src/film_v3.py:music",
}
CLIP = obj({
    **{key: TEXT for key in ("narration", "emotion", "on_screen", "composition", "camera",
                            "motion", "light", "transition", "sfx", "music", "asset")},
    "role": {"type": "string", "enum": ["hook", "context", "problem", "reveal",
                                         "demonstration", "proof", "payoff", "cta"]},
    "seconds": {"type": "number", "minimum": 1.5, "maximum": 12},
    "technique": {"type": "string", "enum": ["2d", "2.5d"]},
    "representation": {"type": "string", "enum": ["metaphor", "text_only"]},
    "fact_ids": {"type": "array", "items": TEXT, "minItems": 1},
    "capabilities": {"type": "array", "items": {"type": "string", "enum": list(CAPABILITIES)},
                     "minItems": 1},
    "factual_basis": TEXT,
})
# Captions are literal short copy, not a second composition-description field.
# Constrain generation before spending further critic/repair calls on this error.
CLIP["properties"]["on_screen"] = {
    "type": "string", "minLength": 1, "maxLength": 70,
    "pattern": r"^[^ \t\n\r]+( [^ \t\n\r]+){0,5}$",
    "description": "Exact on-screen caption, at most six words. No artwork or staging instructions."}
SCENES = obj({"clips": {"type": "array", "items": CLIP, "minItems": 3, "maxItems": 10}})
BUNDLE = obj({"creative": CONCEPT, "design": DESIGN, "scenes": SCENES})
# Detect known failure modes throughout the plan, including visual instructions.
# These are tripwires, not a semantic verifier; the separate reviewer sees all fields.
UNSUPPORTED = re.compile(
    r"\b(fluid simulation|liquid simulation|water simulation|photorealistic|"
    r"real footage|product screenshot|live.action|rigged character|volumetric|"
    r"ray.trac(?:ed|ing)|blender|3d mesh)\b", re.I)
INVENTED_UI = re.compile(
    r"\b(?:click(?:s|ing)?|press(?:es|ing)?|tap(?:s|ping)?)\b.{0,45}\b(?:button|organize)\b|"
    r"\b(?:button|cursor|dashboard|drag.and.drop|auto.organiz\w*)\b", re.I)
PROMISE = re.compile(
    r"(?<!\w)(?:100%|\d+(?:\.\d+)?%|#1|guaranteed|clinically proven|fastest|"
    r"free forever|zero risk|\d+[xX] faster|cures?|automatically|instantly|one.click)(?!\w)", re.I)


def schema_errors(value, schema):
    return ["/".join(map(str, e.absolute_path)) + ": " + e.message
            for e in Draft202012Validator(schema).iter_errors(value)]


def evidence(brief):
    """Only caller-supplied facts enter the ledger. An LLM never writes evidence."""
    for key in ("product", "audience", "benefit", "cta"):
        if not isinstance(brief.get(key), str) or not brief[key].strip():
            raise ValueError("Missing brief field: " + key)
    duration = brief.get("duration_seconds", 24)
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 12 <= duration <= 90:
        raise ValueError("duration_seconds must be a finite number between 12 and 90")
    values = [brief["product"], brief["benefit"], brief["cta"]]
    if brief.get("tagline"):
        values.append(brief["tagline"])
    facts = brief.get("facts", [])
    if not isinstance(facts, list) or any(not isinstance(f, str) or not f.strip() for f in facts):
        raise ValueError("facts must contain nonempty caller-supplied strings")
    values.extend(facts)
    return [{"id": f"fact_{i+1}", "text": value, "source": "owner_reported_unverified"}
            for i, value in enumerate(values)]


def schedule(scenes, target):
    """Preserve the director's chosen rhythm when feasible, without changing words."""
    out = copy.deepcopy(scenes)
    clips = out.get("clips", [])
    if not clips or schema_errors(out, SCENES):
        return out
    original = [float(c["seconds"]) for c in clips]
    if abs(sum(original) - target) <= 0.05:
        return out
    times = [round(t * target / sum(original), 2) for t in original]
    times[-1] = round(target - sum(times[:-1]), 2)
    if all(1.5 <= t <= 12 for t in times):
        for clip, seconds in zip(clips, times):
            clip["seconds"] = seconds
    return out


def audit_bundle(bundle, brief, ledger):
    errors = schema_errors(bundle, BUNDLE)
    if errors:
        return {"passed": False, "hard_errors": errors, "render_ready": False}
    clips = bundle["scenes"]["clips"]
    known = {x["id"] for x in ledger}
    supplied = " ".join(x["text"] for x in ledger).casefold()
    total = sum(c["seconds"] for c in clips)
    if abs(total - brief.get("duration_seconds", 24)) > 0.05:
        errors.append("Shot durations do not equal requested duration")
    if clips[0]["role"] != "hook":
        errors.append("The opening lacks an intentional hook")
    if clips[-1]["role"] not in ("payoff", "cta"):
        errors.append("The ending lacks a payoff or call to action")
    final_copy = (clips[-1]["narration"] + " " + clips[-1]["on_screen"]).casefold()
    if brief["cta"].casefold() not in final_copy:
        errors.append("The final shot must include the supplied CTA verbatim")
    for index, clip in enumerate(clips, 1):
        if set(clip["fact_ids"]) - known:
            errors.append(f"Shot {index}: invented evidence reference")
        words = len(re.findall(r"\b[\w'-]+\b", clip["narration"]))
        if words / clip["seconds"] > 2.8:
            errors.append(f"Shot {index}: narration exceeds 2.8 words/second")
        if len(clip["on_screen"].split()) > max(3, int(clip["seconds"] * 2.5)):
            errors.append(f"Shot {index}: on-screen words lack reading time")
        if clip["technique"] == "2.5d" and "layered_transform" not in clip["capabilities"]:
            errors.append(f"Shot {index}: 2.5D lacks a layered-transform execution strategy")
    # Inspect concept, art, captions, assets and motion as well as narration.
    for path, rendered in text_fields(bundle):
        for pattern, label in ((UNSUPPORTED, "unavailable production technique"),
                               (INVENTED_UI, "unprovided product UI")):
            # Audience psychology is not an execution instruction. A team wanting
            # a metaphorical "pause button" does not invent a product interface.
            # Concept and actual scene instructions remain checked for fake UI.
            if pattern is INVENTED_UI and path == "/creative/audience_insight":
                continue
            for match in pattern.finditer(rendered):
                if pattern is UNSUPPORTED and production_exclusion(rendered, match):
                    continue
                errors.append(f"{path}: {label}: {match.group(0)}")
    # A single click in an audio cue is not a one-click product claim. Inspect
    # audience-facing copy/imagery rather than treating all production notes as facts.
    claim_surfaces = [("creative/" + key, value, True)
                      for key, value in bundle["creative"].items()]
    for index, clip in enumerate(clips):
        for key in ("narration", "on_screen", "composition", "asset"):
            claim_surfaces.append((f"scenes/clips/{index}/{key}", clip[key],
                                   key not in ("narration", "on_screen")))
    for path, surface, visual_note in claim_surfaces:
        for match in PROMISE.finditer(surface):
            if visual_note and (production_percentage(surface, match)
                                or production_timing(surface, match)):
                continue
            if match.group(0).casefold() not in supplied:
                errors.append(path + ": unsupported promise: " + match.group(0))
    return {"passed": not errors, "hard_errors": list(dict.fromkeys(errors)),
            "duration_seconds": round(total, 2), "shot_count": len(clips),
            "verified_claims": False, "render_ready": False,
            "limitations": ["Lexical tripwires do not prove semantic truth or visual feasibility",
                            "No arbitrary scene renderer is connected; this is a production proposal"]}


def text_fields(value, path=""):
    """Yield string leaves with JSON-pointer locations for precise diagnostics."""
    if isinstance(value, dict):
        for key, item in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            yield from text_fields(item, path + "/" + escaped)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from text_fields(item, path + "/" + str(index))
    elif isinstance(value, str):
        yield path, value


def production_exclusion(text, match):
    """Recognize a narrow, explicit exclusion instead of requesting the effect."""
    before = text[max(0, match.start()-70):match.start()]
    return bool(re.search(r"\b(?:no|without|avoid|never use|exclude|excluding|not|"
                          r"rather than|instead of)\s+(?:any\s+|using\s+|the\s+)?$", before, re.I)
                or re.search(r"\bmore effective\b[^.;]{0,60}\bthan\s*$", before, re.I))


def production_percentage(text, match):
    """A transform percentage is an editor instruction, not an ad assertion.

    Only skip an explicit adjacent scale/opacity/etc parameter in visual notes.
    Spoken/caption percentages are checked unconditionally by the caller.
    """
    if not match.group(0).endswith("%"):
        return False
    parameters = r"(?:scale|opacity|zoom|width|height|spacing|rotation|size)"
    before = text[max(0, match.start()-40):match.start()]
    after = text[match.end():match.end()+24]
    return bool(re.search(r"\b" + parameters + r"\s*(?:(?:to|at|by|of)\s+|[:=]\s*)?$", before, re.I)
                or re.match(r"\s+" + parameters + r"\b", after, re.I))


def production_timing(text, match):
    """An instantaneous cut/appearance is editing, not product performance.

    Only an adjacent animation verb qualifies, only in production prose. Literal
    narration and captions are never exempt. Semantic claims still need review.
    """
    if match.group(0).casefold() != "instantly":
        return False
    verbs = (r"(?:cuts?|fades?|freezes?|appears?|disappears?|snaps?|stops?|"
             r"re-forms?|transitions?|rotates?|scales?)")
    before = text[max(0, match.start()-32):match.start()]
    after = text[match.end():match.end()+24]
    return bool(re.search(r"\b" + verbs + r"\s+$", before, re.I)
                or re.match(r"\s+" + verbs + r"\b", after, re.I))

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
SCENES = obj({"clips": {"type": "array", "items": CLIP, "minItems": 3, "maxItems": 10}})
BUNDLE = obj({"creative": CONCEPT, "design": DESIGN, "scenes": SCENES})
REVIEW = obj({
    "approved": {"type": "boolean"},
    "score_out_of_10": {"type": "number", "minimum": 0, "maximum": 10},
    "factual_support": {"type": "boolean"}, "execution_realistic": {"type": "boolean"},
    "strongest_moment": TEXT, "problems": STRINGS, "recommended_repairs": STRINGS,
})

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
    for section, value in bundle.items():
        rendered = json_text(value)
        for pattern, label in ((UNSUPPORTED, "unavailable production technique"),
                               (INVENTED_UI, "unprovided product UI")):
            for match in pattern.finditer(rendered):
                errors.append(f"{section}: {label}: {match.group(0)}")
    # A single click in an audio cue is not a one-click product claim. Inspect
    # audience-facing copy/imagery rather than treating all production notes as facts.
    claim_surfaces = [json_text(bundle["creative"])] + [
        json_text({key: clip[key] for key in ("narration", "on_screen", "composition", "asset")})
        for clip in clips]
    for surface in claim_surfaces:
        for match in PROMISE.finditer(surface):
            if match.group(0).casefold() not in supplied:
                errors.append("unsupported promise: " + match.group(0))
    return {"passed": not errors, "hard_errors": list(dict.fromkeys(errors)),
            "duration_seconds": round(total, 2), "shot_count": len(clips),
            "verified_claims": False, "render_ready": False,
            "limitations": ["Lexical tripwires do not prove semantic truth or visual feasibility",
                            "No arbitrary scene renderer is connected; this is a production proposal"]}


def json_text(value):
    import json
    return json.dumps(value, ensure_ascii=False)


def review_passes(review):
    return (not schema_errors(review, REVIEW) and review["approved"] is True
            and review["score_out_of_10"] >= 8 and review["factual_support"] is True
            and review["execution_realistic"] is True and not review["problems"])

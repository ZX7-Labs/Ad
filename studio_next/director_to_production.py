"""Bridge ONE freely imagined film to production without authoring the art in code.

The same local artistic model first composes free-form original direction and
then translates its own source into discrete *production* decisions. The source
is a protected immutable artifact; scene count, length, genre, imagery, voice,
camera, 2D/3D/live medium all originate from the model's real direction.
Renderer availability is reported separately, never silently replacing art.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from .open_creative import FreeformFilmBrain, preserve_original_direction
from .creative_tool_registry import creative_tool_inventory
from .generative_video_providers import discover_local_generators
from .production_handoff import author_production, author_delivery
from .providers import LocalCreativeModel, LocalModelSettings

EDITORIAL_TRANSLATION = """You are the same expert filmmaking intelligence,
acting as the continuity editor translating YOUR original artistic vision into
an editable and executable film production handoff.

Read your ENTIRE original original prose, the real factual evidence and the
audience's needs. Maintain the distinctive original story, causal changes,
look, characters, emotion and last image. Do not invent a different concept.
Decide exact original shots and individual durations if they weren't already
specified; choose them artistically, with no maximum scene count or preset
format or style. For each shot provide its specific purpose, observable image,
true camera and object action, editorial transition, sound purpose and
actual spoken narration (empty text when genuinely silent).

The engineering contract is necessary because the renderers cannot consume
poetry, but the schema is NOT an artistic template. Film content should retain
its source vision, even if current tools cannot achieve the scene. Never
replace real live action, complex 3D, VFX, characters or assets with slides
to make current tooling happy. Actual medium feasibility gets decided LATER.

Return one JSON object with the complete director-approved story and only
these technical keys:
{"title":"your own original title",
"creative_intent":"exact source artistic objective",
"story":"complete causally connected story",
"voice":{"choice":"M3|F2|no_voice","why":"why appropriate"},
"scenes":[
 {"id":"unique safe filename-like shot identifier",
  "purpose":"specific dramatic function",
  "duration_seconds":6.0,
  "visual":"original observable shot composition, world and authored imagery",
  "motion":"actual actor/camera motion, spatial staging and timing",
  "edit":"motivated transition and continuity",
  "audio":"sound design and music events",
  "narration":"actual spoken line, or empty for silence",
  "fact_refs":["only exact keys in the owner fact ledger"],
  "assets_needed":["specific rights-cleared / missing media needs"]}
],
"unresolved_production_needs":["genuine missing resources"]}.
The sample 6.0 seconds is an example of a number field, NOT a target shot duration.
Create as many scenes and choose as many different media as the film demands.
Narration must not appear if choice is no_voice. Use only owner-verified facts.
No fabricated product footage, real customer quotes, real physical attributes,
unverified rights or invented demonstrations. Fictional interpretation can
remain fiction when clear. Do not supply renderer shell code or claim an MP4.
Return JSON only. No Markdown."""


def validate_translation(treatment, facts):
    """Check only technical provenance, not aesthetics or fixed filmmaking rules."""
    if not isinstance(treatment,dict) or not isinstance(facts,dict):
        raise ValueError("Director's treatment and original owner facts required")
    for name in ("title","creative_intent","story"):
        if not isinstance(treatment.get(name),str) or not treatment[name].strip():
            raise ValueError("Director did not deliver "+name)
    voice=treatment.get("voice")
    if not isinstance(voice,dict) or voice.get("choice") not in ("M3","F2","no_voice"):
        raise ValueError("Missing approved narrator choice or intentional silence")
    if not isinstance(voice.get("why"),str) or not voice["why"].strip():
        raise ValueError("Voice artistic rationale required")
    scenes=treatment.get("scenes")
    if not isinstance(scenes,list) or not scenes:
        raise ValueError("Director must author actual scene progression")
    if not isinstance(treatment.get("unresolved_production_needs"),list):
        raise ValueError("Original scene asset ledger required")
    seen=set()
    for scene in scenes:
        if not isinstance(scene,dict):
            raise ValueError("Invalid authored scene")
        identifier=scene.get("id")
        if (not isinstance(identifier,str) or not identifier or
            not all(c.isalnum() or c in "-_." for c in identifier) or
            identifier in (".","..") or identifier in seen):
            raise ValueError("Unsafe/duplicate scene ID")
        seen.add(identifier)
        for key in ("purpose","visual","motion","edit","audio"):
            if not isinstance(scene.get(key),str) or not scene[key].strip():
                raise ValueError("Director's shot missing "+key)
        if not isinstance(scene.get("narration"),str):
            raise ValueError("Director's deliberate dialogue/silence missing")
        seconds=scene.get("duration_seconds")
        if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or (
            not math.isfinite(seconds) or seconds<=0):
            raise ValueError("No model-selected finite shot duration")
        refs=scene.get("fact_refs")
        if not isinstance(refs,list) or any(not isinstance(ref,str) or ref not in facts for ref in refs):
            raise ValueError("Invented owner fact reference")
        assets=scene.get("assets_needed")
        if not isinstance(assets,list) or any(not isinstance(x,str) for x in assets):
            raise ValueError("Assets/rights provenance missing")
    if voice["choice"]=="no_voice" and any(s["narration"].strip() for s in scenes):
        raise ValueError("Director cannot silently discard spoken dialogue")
    return {"scenes":len(scenes),"duration_seconds":sum(x["duration_seconds"] for x in scenes),
            "format_preselected":False,"media_preselected":False,
            "artistic_quality_approved":False}


def handoff_single_brain(brief, brain, translation_model, production_model, 
                         delivery_model, output_dir):
    """One model ID may perform different film roles, without separate personas."""
    if not isinstance(brief,dict) or not isinstance(brief.get("facts"),dict):
        raise ValueError("Owner's factual brief required")
    ids=[getattr(getattr(x,"settings",None),"model_id",None) for x in
         (brain,translation_model,production_model,delivery_model)]
    if any(x is not None and x!=ids[0] for x in ids):
        raise ValueError("Single cohesive film brain model required")
    out=Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    # Preserve the exact authority that creative direction and final rendering share.
    # This is factual provenance, NEVER an authored art or shot template.
    (out/"owner-factual-brief.json").write_text(
        json.dumps(brief,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    tools=creative_tool_inventory()
    tools["generative_video_models"]=discover_local_generators()
    (out/"actual-creative-tools.json").write_text(
        json.dumps(tools,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # The ONE director gets the real tools but retains full artistic autonomy.
    # A missing installer never makes an ambitious scene turn into a card.
    creative_context=dict(brief,local_creative_tools=tools)
    preserve_original_direction(creative_context,brain,out/"original-vision")
    original=(out/"original-vision"/"director-original.txt").read_text(encoding="utf-8")
    source_digest=hashlib.sha256(original.encode("utf-8")).hexdigest()
    try:
        proposed=translation_model.decide(
            {"owner":brief,"original_cinematic_direction":original,
             "locally_verified_creative_tools":tools,
             "instruction":"Preserve original artistic meaning; return production editorial structure only. "
             "Use the model's independent art direction, not the tool list as a creative limit."})
        (out/"director-translation-raw.json").write_text(json.dumps(proposed,
            ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        verified=validate_translation(proposed,brief["facts"])
        (out/"director-translation.json").write_text(
            json.dumps(proposed,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        designs=author_production(proposed,brief["facts"],production_model,out/"designs",
                                  tool_inventory=tools)
        result={"model_id":ids[0],"original_vision_sha256":source_digest,
                "original_vision_preserved":True,"translation_validated":verified,
                "production":designs,"film_rendered":False,
                "filmmaking_quality_approved":False}
        try:
            fmt=author_delivery(proposed,brief,delivery_model,out/"designs"/"delivery.json")
            result["delivery"]=fmt
        except (TypeError,ValueError,KeyError) as exc:
            result["delivery_error"]=type(exc).__name__+": "+str(exc)
        result["ready_for_possible_render"]=bool(designs["all_designs_executable"]
                                                and "delivery" in result)
    except (ValueError,KeyError,TypeError) as exc:
        result={"model_id":ids[0],"original_vision_sha256":source_digest,
            "original_vision_preserved":True,
            "translation_rejected":type(exc).__name__+": "+str(exc),
            "film_rendered":False,"ready_for_possible_render":False,
            "filmmaking_quality_approved":False}
    (out/"handoff-result.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--brief",type=Path,required=True)
    p.add_argument("--model",required=True)
    p.add_argument("--api",default="http://127.0.0.1:8085")
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    brief=json.loads(args.brief.read_text(encoding="utf-8"))
    brain=FreeformFilmBrain(LocalModelSettings(
        base_url=args.api,model_id=args.model,timeout_seconds=1800))
    editorial=LocalCreativeModel(LocalModelSettings(
        base_url=args.api,model_id=args.model,timeout_seconds=1800,
        sampling={"temperature":.35,"top_p":.9,"max_tokens":5200}),
        system_prompt=EDITORIAL_TRANSLATION)
    from .production_handoff import PRODUCTION_SYSTEM,DELIVERY_SYSTEM
    production=LocalCreativeModel(LocalModelSettings(
        base_url=args.api,model_id=args.model,timeout_seconds=1800,
        sampling={"temperature":.3,"top_p":.9,"max_tokens":3600}),
        system_prompt=PRODUCTION_SYSTEM)
    delivery=LocalCreativeModel(LocalModelSettings(
        base_url=args.api,model_id=args.model,timeout_seconds=1800,
        sampling={"temperature":.25,"top_p":.85,"max_tokens":600}),
        system_prompt=DELIVERY_SYSTEM)
    result=handoff_single_brain(brief,brain,editorial,production,delivery,args.out)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    main()

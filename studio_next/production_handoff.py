"""Turn independently authored model cinematography into runnable scene specifications.

A director chooses the film first. One art-production decision is requested for
each of its shots, with full story context, adjacent shots, verified fact IDs,
rights, and installed capability descriptions. This is not a preset storyboard.
The director may request capabilities we don't yet have; that request is retained
as unresolved rather than becoming a card animation.

This module does NOT claim human-level creativity or finished video.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .blender_scene import validate_blender_shot
from .motion_bridge import compile_motion_project
from .providers import LocalCreativeModel, LocalModelSettings
from .creative_tool_registry import creative_tool_inventory
from .visual_engine_hub import resolve_visual_engine

PRODUCTION_SYSTEM = """You are the production designer and technical cinematographer of a real original film.
You are executing an ALREADY AUTHORED creative treatment, not pitching new concepts.
Preserve its exact narrative purpose, selected visual medium, story causality,
scene order, actual text, facts, music intent, transitions, continuity and voice.
DO NOT shrink an intended 3D/live-action shot to a flat motion-card because one
tool is easier to use. Do not invent licensed assets, product photos or facts.
The installed providers offered to you are per-shot capabilities, NOT restrictions
on the studio's imagination. If the design requires unavailable capability,
return a gap and keep the desired look intact.
Choose ONE result for the CURRENT shot:
- engine 'blender3d': submit a fully specified 'scene_job' conforming to Blender
  3D scene schema: shot_id,width,height,fps,frames,camera,world,materials,objects,lights.
  True meshes, materials, light rig and camera are your choices. Use only defined
  legal primitive types or explicitly authored meshes. Real 3D is preferred only
  when editorially motivated; never mandatory.
- engine 'motion2d': submit a 'scene_job' conforming to Film IR with project,assets,
  shots,tool_graph. Assets must be original inline vector artwork. Each shot needs
  original exact narration, purpose, duration_seconds, asset_refs, fact_refs,
  layers. Keep scene graph consistent; do not impose a standard aesthetic.
- Any VERIFIED registered local video production provider may be chosen.
  The actual tool inventory describes video diffusion and other resources.
  Do NOT use a provider merely because it has a famous name or weights exist.
  Engine 'comfy_video' is valid ONLY if a local compatible GPU, licensed model
  bytes, and an approved local workflow are actually configured. Its scene_job
  has model_id, prompt (specific original acting/film visual), negative_prompt
  (empty allowed), width, height, frames, fps, seed. Each is independently
  chosen to implement the director's approved timing and creative purpose.
  Additional installed engine plugins are discovered at runtime, not a fixed
  creative list. Generated images/footage must be physically proven later.
- engine 'unresolved': return desired_capabilities, production_gap and precise
  reason if actual imagery, real actor footage, photoreal assets, specialist
  engines, natural language fonts, sound, or geometry cannot be produced.
  Do not silently substitute.
Return one JSON object, never Markdown:
{"shot_id":"same scene ID","engine":"installed_approved_engine_id or unresolved",
 "creative_rationale":"WHY this method communicates THIS shot",
 "continuity":"specific connecting visual/sound action","scene_job":{},
 "desired_capabilities":[],"production_gap":""}
Set scene_job={} on unresolved. Model output is untrusted until independently
validated; never put shell commands, URLs or claimed completed files in it."""

_ALLOWED_ENGINES = frozenset({"blender3d", "motion2d", "unresolved"})


def _string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Missing " + label)
    return value


def _scenes(treatment):
    if not isinstance(treatment, dict):
        raise ValueError("A genuine complete film treatment is needed")
    scenes=treatment.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("No authored scenes in treatment")
    ids=[]
    for index,s in enumerate(scenes):
        if not isinstance(s,dict):
            raise ValueError("Malformed scene "+str(index))
        ident=_string(s.get("id"), "scene ID")
        if ident in ids:raise ValueError("Repeated scene ID")
        ids.append(ident)
        _string(s.get("purpose",s.get("story_purpose")),"purpose")
    return scenes


def _duration(shot):
    x=shot.get("duration_seconds",shot.get("seconds"))
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not (0<x<float("inf")):
        raise ValueError("Unclear director-selected duration")
    return x


def validate_visual_design(scene, design, facts):
    """No fabricated story text, unsupported operation or silent visual downgrade."""
    if not isinstance(design, dict) or not isinstance(scene,dict):
        raise TypeError("Model result and authored shot must be objects")
    if set(design)!={"shot_id","engine","creative_rationale","continuity",
                    "scene_job","desired_capabilities","production_gap"}:
        raise ValueError("Incomplete or unexpected design fields")
    sid=scene["id"]
    if design["shot_id"]!=sid:
        raise ValueError("Design must be for current unchanged shot")
    engine=design["engine"]
    external=resolve_visual_engine(engine) if engine not in _ALLOWED_ENGINES else None
    if engine not in _ALLOWED_ENGINES and external is None:
        raise ValueError("Engine must be routed by an installed adapter")
    _string(design["creative_rationale"],"why this technique fits story")
    _string(design["continuity"],"shot continuity")
    if not isinstance(design["desired_capabilities"],list) or not all(
        isinstance(v,str) and v.strip() for v in design["desired_capabilities"]):
        raise ValueError("Invalid capability requirements")
    if not isinstance(design["scene_job"],dict):
        raise ValueError("Concrete scene job required")
    if engine=="unresolved":
        _string(design["production_gap"],"honest missing production capability")
        if design["scene_job"] or not design["desired_capabilities"]:
            raise ValueError("Unavailable capability cannot claim finished assets")
        return {"executable":False, "engine":engine, "reason":design["production_gap"]}
    if design["production_gap"]:
        raise ValueError("Design cannot simultaneously be executable and blocked")
    if external is not None:
        # Technical provider handles its own true installation/capability check.
        proof=external.validate(scene,design,facts)
        if not isinstance(proof,dict) or proof.get("engine")!=engine or proof.get("executable") is not True:
            raise ValueError("External video engine did not prove usable capability")
        return proof
    if engine=="blender3d":
        job=design["scene_job"]
        if job.get("shot_id")!=sid:
            raise ValueError("3D render ID not equal to authored scene")
        validate_blender_shot(job)
        delta=abs(job["frames"]/job["fps"]-_duration(scene))
        if delta>1.0/job["fps"]+1e-5:
            raise ValueError("Production model cannot rewrite cinematic shot duration")
        if scene.get("narration"):
            # The 3D renderer is picture-only. Narration is NOT discarded:
            # actual audio attachment must be handled by installed timeline adapter.
            return {"executable":True,"engine":engine,"audio_required":True}
        return {"executable":True,"engine":engine,"audio_required":False}
    plan=design["scene_job"]
    project=compile_motion_project(plan,fact_ids=frozenset(facts))
    if len(plan["shots"])!=1 or plan["shots"][0].get("id")!=sid:
        raise ValueError("One production job may only own the exact current shot")
    shot=plan["shots"][0]
    if shot.get("narration")!=scene.get("narration", ""):
        raise ValueError("Do not rewrite or discard director-approved dialogue")
    if abs(shot.get("duration_seconds",0)-_duration(scene))>1e-5:
        raise ValueError("Do not alter director-chosen timing")
    known=scene.get("fact_refs",scene.get("factual_basis",[]))
    referenced=shot.get("fact_refs",[])
    if any(x not in facts for x in referenced):
        raise ValueError("Production job refers to unverified facts")
    if known and all(x in facts for x in known) and set(referenced)!=set(known):
        raise ValueError("Production cannot remove actual asserted fact citations")
    return {"executable":True,"engine":engine,
            "audio_required":bool(scene.get("narration")),"project":project}


def author_production(treatment, facts, model, output_dir, *, tool_inventory=None):
    """Per-scene model design, no prewritten scene graph or template choice.

    Never silently discards a scene; every defect is an auditable unresolved shot.
    No paid tools are invoked; the model interface is localhost-only.
    """
    scenes=_scenes(treatment)
    # Registered video diffusion is a physical tool, not a fictional asset.
    # Discover once per directing pass, and do not advertise GPU-less tools.
    from .generative_video_providers import discover_local_generators
    import os
    runtime=discover_local_generators(
        comfy_endpoint=os.getenv("ZX7_COMFY_API"),
        deployed_root=os.getenv("ZX7_VIDEO_DEPLOYMENTS","models/creative-video"))
    enabled_video=[x["id"] for x in runtime["video_generation_options"]
                   if x["ready_for_independent_execution_trial"]]
    if not isinstance(facts,dict) or not all(isinstance(k,str) for k in facts):
        raise TypeError("Owner-controlled facts required")
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    results=[]
    for index,scene in enumerate(scenes):
        context={
            "film":{k:v for k,v in treatment.items() if k!="scenes"},
            "all_shots":[{"id":s["id"],"purpose":s.get("purpose",s.get("story_purpose")),
                          "visual":s.get("visual"),"camera_and_edit":s.get("camera_and_edit"),
                          "seconds":_duration(s)} for s in scenes],
            "current_shot":scene,
            "owner_facts":facts,
            "previous_scene":scenes[index-1] if index else None,
            "next_scene":scenes[index+1] if index+1<len(scenes) else None,
            "installed_engines":{
                "blender3d":"actual Blender 3D camera, original meshes, materials, lighting; CPU",
                "motion2d":"actual procedural 2D/2.5D compositor for explicit rights-cleared vector artwork",
                "unresolved":"preserve intent when tools/assets are unavailable",
                **({"comfy_video":"Genuine licensed local video diffusion: "+", ".join(enabled_video)}
                    if enabled_video else {}),
            },
            "available_creative_tool_inventory":tool_inventory if tool_inventory is not None else
                creative_tool_inventory(),
            "tool_policy":"Installed tools are real capabilities, not visual presets; "
               "propose missing skills as production gaps, never invent completed files.",
            "instruction":"Do not choose a medium to fit the installed engines. "
            "Choose the artistic medium and mark unavailable needs honestly.",
        }
        raw=model.decide(context)
        evidence={"scene_id":scene["id"],"model_response":raw}
        try:
            audit=validate_visual_design(scene,raw,facts)
            evidence["verification"]=audit
        except (TypeError,ValueError,KeyError,OverflowError) as exc:
            evidence["verification"]={"executable":False,"reason":type(exc).__name__+": "+str(exc)}
        payload=json.dumps(evidence,ensure_ascii=False,indent=2,allow_nan=False)
        evidence["sha256"]=hashlib.sha256(payload.encode()).hexdigest()
        path=output_dir/f"design-{index+1:03d}.json"
        path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        results.append({"scene_id":scene["id"],"file":path.name,
                        "executable":evidence["verification"]["executable"],
                        "reason":evidence["verification"].get("reason",""),
                        "engine":evidence["verification"].get("engine","invalid")})
    manifest={"film_title":treatment.get("title",treatment.get("film_title")),
              "original_scene_ids":[s["id"] for s in scenes],
              "designs":results,
              "all_designs_executable":all(x["executable"] for x in results),
              "claim":"Model-authored designs validated, NOT rendered film or professional quality"}
    (output_dir/"production-manifest.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return manifest


DELIVERY_SYSTEM = """You are the final-format and performance director of an original film.
Determine exhibition geometry, export frame rate, framing treatment,
background in any letterboxed shots, and narrator based on actual audience,
script, story, distribution context and resource capabilities.
NEVER force vertical, short runtime, preset voice, default music or identical pacing.
Do not select a voice contrary to an already specified treatment; if the film
actually has narrated shots, 'no_voice' is NOT allowed.
For now, installed narrator identities are M3 and F2; choose purposefully.
Export shape and fps must be positive integers; working CPU render resources
are bounded and huge settings may not be presently possible.
Return JSON only:
{"format":{"width":1080,"height":1920,"fps":24,"framing":"fit",
"background":"#101010"},"voice":"M3","reason":"real editorial justification"}.
These numbers are an EXAMPLE JSON SHAPE, not mandatory artistic defaults.
"""


def author_delivery(treatment, brief, model, out):
    """Model-selected film-wide delivery; no default portrait preset."""
    from .execute_film import validate_delivery
    raw=model.decide({"treatment":treatment,"owner":brief,
       "instruction":"Make an original appropriate film-wide delivery decision. "
       "Do not change selected speech/voice or story."})
    out=Path(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    (out.parent/"delivery-raw.json").write_text(
        json.dumps(raw,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    try:
        verified=validate_delivery(raw,treatment)
    except (ValueError,KeyError,TypeError) as exc:
        (out.parent/"delivery-failure.json").write_text(json.dumps(
            {"reason":type(exc).__name__+": "+str(exc)},indent=2))
        raise
    out.write_text(json.dumps(verified,ensure_ascii=False,indent=2)+"\n",
                   encoding="utf-8")
    return verified


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--treatment",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--api",default="http://127.0.0.1:8085")
    parser.add_argument("--model",required=True)
    a=parser.parse_args()
    original=json.loads(a.treatment.read_text(encoding="utf-8"))
    treatment=original.get("treatment",original)
    facts=original.get("brief",{}).get("facts",{}) if "brief" in original else {}
    model=LocalCreativeModel(LocalModelSettings(base_url=a.api,model_id=a.model,
        timeout_seconds=1200,sampling={"temperature":.35,"max_tokens":2600,"top_p":.93}),
        system_prompt=PRODUCTION_SYSTEM)
    result=author_production(treatment,facts,model,a.out)
    delivery_model=LocalCreativeModel(LocalModelSettings(base_url=a.api,model_id=a.model,
        timeout_seconds=1200,sampling={"temperature":.25,"max_tokens":500,"top_p":.9}),
        system_prompt=DELIVERY_SYSTEM)
    try:
        result["delivery"]=author_delivery(treatment,original.get("brief",{}),
            delivery_model,a.out/"delivery.json")
    except (ValueError,TypeError,KeyError) as exc:
        result["delivery_error"]=str(exc)
    (a.out/"production-manifest.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()

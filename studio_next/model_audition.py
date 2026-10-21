"""Film-direction *model audition* independent of the old 4B repair treadmill.

The model makes its own narrative, image, camera, edit, music, timing, voice and
genre decisions for an owner brief. Validation only checks data boundaries,
rights/fact identifiers and whether a useful creative proposal was returned.
This does NOT convert a structured answer or passing test into quality approval.

An art/film critic must actually inspect the result. Prompts intentionally do
not specify number of shots, genre, aspect ratio, medium, script formula or
runtime. The number of scenes is *not* a benchmark score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from .providers import LocalCreativeModel, LocalModelSettings


CREATIVE_SYSTEM = """You are the creative intelligence of an ambitious original
filmmaking studio. You are not a template generator or a machine that fills an
advertising-form schema. Direct an actual film that a discerning human editor
would respect. Think cinematically: why this subject, why now, why this specific
idea, what the audience sees and feels, what changes, what each cut means.

Create genuinely ORIGINAL subject-specific visual ideas with real causal logic,
memorable staging, emotionally natural spoken dialogue if appropriate, rigorous
sound design, film grammar, visual continuity and physical editorial rhythm.
Choose the story type, length, number of scenes, aspect ratio, duration of every
scene, voice (or meaningful silence), camera, 2D/3D/actual-footage medium, music
and sound for THIS brief. Nothing is limited to five scenes, 15 seconds,
cards, marketing conventions, or 2D.

Only statements given in owner_facts may be presented as real product, history,
technical or competitor facts. For a fictional/metaphorical story make the
fiction plain rather than misleading a viewer as demonstrated truth. A listed
fact ID must exist in owner_facts. Never invent customer testimonials, observed
failures, specifications, photographs, interfaces or licensed footage. If media
is missing, preserve the creative direction and explicitly note its production
dependency; do not downgrade artistic direction to the installed engine.

Write the film's complete storyboard as a JSON object with:
title, creative_intent, viewer_experience, central_mechanism,
visual_and_sound_language, exhibition, voice_decision,
shots, unresolved_production_needs.
Shots must be an ordered array of ORIGINAL, independently motivated scenes,
each with id, dramatic_purpose, duration_seconds, visual, camera_and_motion,
edit_and_continuity, sound_and_performance, spoken_words, factual_basis,
assets_needed. Every field except duration_seconds, factual_basis,
unresolved_production_needs and assets_needed is human-readable text.
duration_seconds is a positive number freely chosen by YOU, factual_basis is
a list of original owner_fact keys, and asset lists are free-form strings.
The film may contain any artistically necessary number of scenes.
Return valid JSON and no markdown. Do NOT append a critic's fictitious review
or claim that any footage was actually rendered."""


def verify_artistic_sample(sample, brief):
    """Validate provenance/shape without hardcoding creative aesthetic decisions."""
    if not isinstance(sample,dict) or not isinstance(brief,dict):
        raise ValueError("Original film and brief must be objects")
    needed={"title","creative_intent","viewer_experience","central_mechanism",
            "visual_and_sound_language","exhibition","voice_decision","shots",
            "unresolved_production_needs"}
    if not needed.issubset(sample):
        raise ValueError("Creative film output is incomplete")
    for key in needed-{"shots","unresolved_production_needs"}:
        if not isinstance(sample[key],str) or not sample[key].strip():
            raise ValueError("Film requires meaningful "+key)
    scenes=sample["shots"]
    if not isinstance(scenes,list) or not scenes:
        raise ValueError("Creative director did not provide any actual scenes")
    fact_ids=set(brief.get("facts",{}))
    seen=set()
    for scene in scenes:
        required={"id","dramatic_purpose","duration_seconds","visual",
                  "camera_and_motion","edit_and_continuity",
                  "sound_and_performance","spoken_words",
                  "factual_basis","assets_needed"}
        if not isinstance(scene,dict) or not required.issubset(scene):
            raise ValueError("A film scene was not fully directed")
        for key in required-{"duration_seconds","factual_basis","assets_needed"}:
            if not isinstance(scene[key],str) or (key!="spoken_words" and not scene[key].strip()):
                raise ValueError("Scene has missing authored "+key)
        sid=scene["id"]
        if sid in seen:
            raise ValueError("Duplicate scene ID")
        seen.add(sid)
        sec=scene["duration_seconds"]
        if isinstance(sec,bool) or not isinstance(sec,(int,float)) or not math.isfinite(sec) or sec<=0:
            raise ValueError("Director did not choose a valid scene duration")
        refs=scene["factual_basis"]
        if not isinstance(refs,list) or any(not isinstance(x,str) or x not in fact_ids for x in refs):
            raise ValueError("Unknown owner factual citation")
        assets=scene["assets_needed"]
        if not isinstance(assets,list) or any(not isinstance(x,str) or not x.strip() for x in assets):
            raise ValueError("Unknown rights/production dependency")
    if not isinstance(sample["unresolved_production_needs"],list) or any(
        not isinstance(x,str) or not x.strip() for x in sample["unresolved_production_needs"]):
        raise ValueError("Production needs must be stated without invented media")
    return {"parseable":True, "scene_count":len(scenes),
            "director_duration_seconds":round(sum(x["duration_seconds"] for x in scenes),3),
            "factual_reference_ids_valid":True,
            "original_model_quality_tested":False,
            "claim":"Structured model proposal only; not a finished film, independent reasoning or human creative approval"}


def run_audition(brief_paths, model, root):
    if not brief_paths:
        raise ValueError("Need actual dissimilar creative briefs")
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    results=[]
    for index,path in enumerate(brief_paths,1):
        path=Path(path)
        brief=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(brief.get("facts"),dict) or not isinstance(brief.get("request"),str):
            raise ValueError("Brief needs owner-supplied factual ledger and natural language task")
        target=root/f"brief-{index:02d}"
        target.mkdir(exist_ok=True)
        context={"owner_request":brief["request"],"owner_facts":brief["facts"],
                 "preferences":brief.get("preferences",{}),
                 "available_voices":brief.get("available_voices",["M3","F2"]),
                 "asset_rights":brief.get("asset_rights",{}),
                 "creative_instruction":"You decide; never fit the film into a canned ad/lesson pattern"}
        fingerprint=hashlib.sha256(json.dumps(context,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        record={"source_brief":str(path),"brief_sha256":fingerprint,
                "status":"attempting_model"}
        (target/"context.json").write_text(json.dumps(context,indent=2,ensure_ascii=False)+"\n")
        try:
            raw=model.decide(context)
            (target/"original-model-sample.json").write_text(json.dumps(raw,ensure_ascii=False,indent=2)+"\n")
            record["checks"]=verify_artistic_sample(raw,brief)
            record["status"]="awaiting_independent_creative_assessment"
        except Exception as e:
            record["status"]="rejected_model_output"
            record["failure"]=type(e).__name__+": "+str(e)
            # Keep next brief independent; do not turn one weak result into
            # a globally hardcoded substitution for all production.
        (target/"status.json").write_text(json.dumps(record,indent=2,ensure_ascii=False)+"\n")
        results.append(record)
        print("AUDITION",json.dumps({"brief":str(path),"status":record["status"],
                "checks":record.get("checks"),"failure":record.get("failure")},
                ensure_ascii=False),flush=True)
    manifest={"samples":results,"model_or_provider":getattr(getattr(model,"settings",None),"model_id","injected"),
              "no_model_promoted":True,
              "claim":"Human review is needed for originality, artistic continuity, film truth and potential improvement"}
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--brief",type=Path,action="append",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--model",required=True)
    p.add_argument("--api",default="http://127.0.0.1:8085")
    a=p.parse_args()
    model=LocalCreativeModel(LocalModelSettings(base_url=a.api,model_id=a.model,
        timeout_seconds=1800,sampling={"temperature":.78,"top_p":.95,
                                       "max_tokens":3000}),system_prompt=CREATIVE_SYSTEM)
    manifest=run_audition(a.brief,model,a.out)
    print("MODEL AUDITION COMPLETE; CREATIVE QUALITY UNAPPROVED",
          json.dumps(manifest,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()

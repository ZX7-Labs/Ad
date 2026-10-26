#!/usr/bin/env python3
"""One honest creative-quality experiment, NOT a template video generator.

Tests whether a real local language model can devise distinct, subject-specific
stories in unrelated genres, choose an original one, expand it into a film
treatment and reject weak writing. No MP4 is implied by a finished screenplay.
"""
from __future__ import annotations
import argparse
import json
import re
import time
from pathlib import Path
from studio_next.providers import LocalCreativeModel, LocalModelSettings

PITCHES = """You are a bold but discerning film writer and creative director.
Here is an owner's ordinary-language request and a factual/rights ledger.
You are NOT a code assistant, marketing template filler or narrator reading a list of services.
THINK VISUALLY. Explore more than one FUNDAMENTALLY DIFFERENT narrative approach to this exact request.
A real emotion, problem, action, discovery, paradox, physical metaphor or perspective
should anchor each approach. Respond differently to an educational Short versus
a film versus product advertising. A product ad must make the real product useful
in an emotionally intelligible way without promising fictional results.
Do not invent facts, features, reviews, prices, photos, UI or statistics. Invent
fictional staging where it will not be mistaken for product evidence.
NO FORMULA requiring a certain number of shots, runtime, CTA or 3D.
Return JSON: {"pitches":[{"name":"short working title",
"central_idea":"concrete, unique one-sentence premise",
"audience_feeling":"specific intended response",
"memorable_image":"visual that belongs to THIS concept and is feasible with listed assets/tools",
"story_turn":"what changes, how the viewer discovers it",
"truth_boundary":"facts not known / deliberately not claimed",
"production_approach":"what tools might accomplish it, including honest gaps"}]}.
Pitch count here is for a COMPETITIVE EXPERIMENT, not a product limit.
At least 2 meaningfully different pitches. No JSON markdown."""

CHOOSE = """You are an exacting story editor evaluating UNFINISHED pitches, not the author.
Choose the best viable idea for this actual audience and intent, not just the flashiest adjectives.
Assess specificity, insight, originality, audience engagement, dramatic progression,
fact truthfulness and possible production. You must distinguish the ideas, not rubber-stamp.
Do not invent a third concept, do not add claims.
Return JSON: {"selected_index":0,
"why":"concrete rationale versus other pitch","risk":"strongest unresolved risk",
"criticisms":["specific weakness, not generic praise"],
"challenge_for_writer":"one surgical requirement for the finished film"}.
The index is zero-based. No markdown."""

WRITE = """You are the HEAD WRITER AND VISUAL DIRECTOR of an ambitious independent studio.
Build a film treatment with natural SPOKEN language, distinctive scenes and cinematic staging.
Write a complete coherent narrative based on the SELECTED concept and its real brief.
Your creative objective is to make viewers care — not to advertise your own sophistication.
Avoid forced enthusiasm, buzzword blocks, generic corporate claims, lists of services,
the usual 'imagine a world' and 'unlock the power' scripts and repeated taglines.
Choose the film duration, shot count, pacing, voice (among AVAILABLE options), kind of
visuals, music, typography, camera, sound and transitions independently.
Storyboard every shot with a specific physical/visual action. Detail film sound as precisely
as images. Good storytelling can choose live action, licensed footage, motion graphics,
3D, animation or combinations, but mark UNAVAILABLE resources honestly and suggest
a production provider or ask for an asset if required. Never pretend a concept rendered.
Choose any supplied installed voice identity, or deliberate silence. No singing/copyrighted media.
Product claims MUST come from the supplied owner facts and not from invented UI or outcomes.
For nonfiction, no invented events or research facts.
Return JSON: {"film_title":"distinctive",
"creative_thesis":"one sentence",
"reason_for_format":"why this medium and pacing",
"duration_seconds":number,
"voice_direction":"who speaks, why, emotion, cadence without fixed speed",
"music_direction":"concrete scene-responsive sonic idea; can use silence",
"visual_language":"design, light, recurring motifs and camera grammar",
"scenes":[{"id":"unique identifier","seconds":number,
"story_purpose":"why this scene exists and what changes",
"narration":"ACTUAL memorable natural spoken lines OR empty string when intentional silence",
"visual":"original filmable composition and action, not an abstract theme",
"camera_and_edit":"specific framing, motion, cut or transition",
"sound":"deliberate sound and music development",
"assets_and_tools":["requested capability, not made-up installed status"],
"factual_basis":["owner fact id OR explicitly imaginary metaphor"]}],
"unresolved_production_needs":["missing assets/services/rights"]}.
No fixed shot count or duration. Do not put markdown or notes outside JSON."""

JUDGE = """You are a senior independent story critic examining the actual screenplay.
You have the owner's facts and the completed film proposal. Rate honestly whether
a human viewer would want to watch rather than switch away.
Review specificity to subject, real narrative progression, naturalness of every
spoken sentence, originality, truthfulness, emotional logic, shot-to-shot visual
continuity, scene timing, motivated production choices and feasibility.
Identify exact problematic lines or shots if weak. Do not call merely structured JSON
"production-grade". Do not silently approve missing essential assets.
Return JSON: {"approved":false,"score_out_of_10":6,
"strongest_scene_id":"specific id or empty",
"reasons":["concrete evidence, not empty praise"],
"defects":[{"scene_id":"id/overall","excerpt":"exact faulty words from draft",
"problem":"why it fails","repair":"specific corrective direction"}],
"execution_status":"requires_assets|technically_possible|unverified"}.
If truly good, approved may be true; if not, refuse. No markdown."""

GENERIC = re.compile(r"\b(?:unlock your potential|seamless experience|take it to the next level|"
                     r"revolutionize your world|imagine a world where|game[\s-]changer|"
                     r"power of innovation|in today's fast-paced world)\b",re.I)

def _strings(value):
    return isinstance(value,str) and bool(value.strip())

def validate_script(treatment, facts):
    errors=[];warnings=[]
    if not isinstance(treatment,dict):return ["Not JSON treatment"],warnings
    for key in ("film_title","creative_thesis","visual_language","voice_direction","music_direction"):
        if not _strings(treatment.get(key)):
            errors.append("Missing "+key)
    scenes=treatment.get("scenes")
    if not isinstance(scenes,list) or not scenes:
        return errors+["No scenes at all"],warnings
    all_ids=set();total=0.0;spoken=[]
    for index,scene in enumerate(scenes,1):
        if not isinstance(scene,dict):
            errors.append(f"Scene {index} malformed");continue
        id_=scene.get("id")
        if not _strings(id_) or id_ in all_ids:
            errors.append(f"Scene {index} missing or repeated id")
        else:all_ids.add(id_)
        for key in ("story_purpose","visual","camera_and_edit","sound"):
            if not _strings(scene.get(key)):
                errors.append(f"Scene {index} lacks {key}")
        narration=scene.get("narration")
        if not isinstance(narration,str):
            errors.append(f"Scene {index} narration not supplied")
            narration=""
        if narration.strip():spoken.append(narration.strip())
        try:
            d=float(scene.get("seconds"))
            if d<=0 or not (d<float("inf")):raise ValueError("invalid duration")
            total+=d
            speed=len(narration.split())/d
            # Only egregious physically rushed speech is blocked. DO NOT fix voice speed.
            if speed>4.5:errors.append(f"Scene {index} impossible spoken density: {speed:.1f} words/s")
            if speed>3.1:warnings.append(f"Scene {index} rapid narration: {speed:.1f} words/s")
        except (TypeError,ValueError,OverflowError):
            errors.append(f"Scene {index} invalid duration")
        refs=scene.get("factual_basis",[])
        if not isinstance(refs,list):
            errors.append(f"Scene {index} factual_basis must be list")
        elif any(not isinstance(ref,str) for ref in refs):
            errors.append(f"Scene {index} malformed fact reference")
        elif any(ref not in facts and not ref.startswith("metaphor:") for ref in refs):
            errors.append(f"Scene {index} cites an unprovided fact")
        requested=scene.get("assets_and_tools",[])
        if not isinstance(requested,list) or any(not isinstance(x,str) for x in requested):
            errors.append(f"Scene {index} tools must be names not executable commands")
    if len(spoken)>1 and len(set(x.casefold() for x in spoken))!=len(spoken):
        errors.append("Repeated spoken lines in multiple scenes")
    if GENERIC.search(" ".join(spoken)):
        warnings.append("Formulaic marketing phrasing present in narration")
    try:
        target=float(treatment.get("duration_seconds"))
        if not 0<target<float("inf") or abs(target-total)>max(0.5,total*.02):
            errors.append(f"Timeline incompatible: declared={target:g}s, clips={total:g}s")
    except (TypeError,ValueError,OverflowError):
        errors.append("Invalid film duration")
    if not spoken:
        warnings.append("Film has no narration: only correct if visual/music storytelling intentional")
    return errors,warnings

def _write(path, data):
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix(target.suffix+".tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(target)

def _prose(brief,result):
    parts=["# Creative Directing — Authentic Model Trial",
           "This is a model-generated PREPRODUCTION screenplay, not a video or a quality certificate.",
           "## User request",str(brief["request"]),
           "## Chosen idea",str(result["selection"].get("why")),
           "## Complete film treatment",
           f"**Title:** {result['treatment'].get('film_title')}",
           f"**Premise:** {result['treatment'].get('creative_thesis')}",
           f"**Visual language:** {result['treatment'].get('visual_language')}",
           f"**Voice direction:** {result['treatment'].get('voice_direction')}",
           f"**Music:** {result['treatment'].get('music_direction')}"]
    for i,shot in enumerate(result["treatment"].get("scenes",[]),1):
        parts.extend([
            f"### Scene {i}: {shot.get('id')}, {shot.get('seconds')} seconds",
            "**Why it exists:** "+str(shot.get("story_purpose")),
            "**Spoken:** "+str(shot.get("narration")),
            "**What happens on screen:** "+str(shot.get("visual")),
            "**Camera and editing:** "+str(shot.get("camera_and_edit")),
            "**Sound:** "+str(shot.get("sound")),
            "**Suggested media/tools:** "+str(shot.get("assets_and_tools")),
            "**Source:** "+str(shot.get("factual_basis"))])
    parts.extend(["## Critic review",json.dumps(result.get("review",{}),ensure_ascii=False,indent=2),
                  "## Technical/creative warnings",json.dumps(result.get("warnings",[]),ensure_ascii=False,indent=2),
                  "## Status",result["state"],"This experiment did not render an MP4."])
    return "\n\n".join(parts)+"\n"

def trial(model,brief,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    trace=[]
    def stage(name,prompt,data):
        tic=time.monotonic()
        print("START",name,flush=True)
        result=model._invoke(prompt,data)
        trace.append({"name":name,"seconds":round(time.monotonic()-tic,1),"json_bytes":len(json.dumps(result))})
        _write(out/(name+".json"),result)
        print("FINISH",name,trace[-1],flush=True)
        return result
    facts=brief.get("facts",{})
    if not _strings(brief.get("request")) or not isinstance(facts,dict):
        raise ValueError("Expected natural request and source fact map")
    try:
        ideas=stage("01_concepts",PITCHES,{"request":brief["request"],"facts":facts,
                                       "assets":brief.get("available_assets",[]),
                                       "rights":brief.get("rights",{})})
        candidates=ideas.get("pitches",[])
        if not isinstance(candidates,list) or len(candidates)<2:
            raise ValueError("Model failed to offer genuinely competing creative pitches")
        selector=stage("02_selection",CHOOSE,{"brief":brief,"candidates":candidates})
        choice=selector.get("selected_index")
        if isinstance(choice,bool) or not isinstance(choice,int) or not 0<=choice<len(candidates):
            raise ValueError("Invalid independent creative choice")
        treatment=stage("03_screenplay",WRITE,
            {"brief":brief,"selected":candidates[choice],
             "creative_challenge":selector.get("challenge_for_writer"),
             "available_voice_identities":brief.get("available_voices",[]),
             "available_production_capabilities":brief.get("capability_catalog",[]),
             "unavailable_tools_must_be_labelled":True})
        errors,warnings=validate_script(treatment,facts)
        review=stage("04_critic",JUDGE,{"brief":brief,"film":treatment,"hard_errors":errors,
                                       "warnings":warnings})
        if not isinstance(review.get("approved"),bool):
            errors.append("Critic did not give a boolean approval")
        passed=not errors and review.get("approved") and not review.get("defects")
        result={"state":"review_ready" if passed else "needs_critical_revision",
                "request":brief["request"],"choices":ideas,"selection":selector,
                "treatment":treatment,"hard_errors":errors,"warnings":warnings,
                "review":review,"stage_performance":trace,
                "claim":"Written experimental treatment only; no video rendered."}
        _write(out/"result.json",result)
        (out/"storyboard.md").write_text(_prose(brief,result),encoding="utf-8")
        print("RESULT",json.dumps({"state":result["state"],"errors":errors,
                                   "critic_approved":review.get("approved"),"stage_performance":trace}),
              flush=True)
        return result
    except Exception as exc:
        _write(out/"failure.json",{"type":type(exc).__name__,"error":str(exc),
                                  "trace":trace,"not_approved":True})
        print("FAILURE",str(exc),flush=True)
        raise

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--brief",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--server",default="http://127.0.0.1:8085")
    p.add_argument("--model",default="director")
    p.add_argument("--max-tokens",type=int,default=2700)
    a=p.parse_args()
    if a.max_tokens<400:raise ValueError("Model output limit too low for film treatment")
    cfg=LocalModelSettings(base_url=a.server,model_id=a.model,
                           timeout_seconds=900,
                           sampling={"temperature":0.62,"top_p":0.9,"max_tokens":a.max_tokens,
                                     "chat_template_kwargs":{"enable_thinking":False}})
    return trial(LocalCreativeModel(cfg),json.loads(a.brief.read_text(encoding="utf-8")),a.out)

if __name__=="__main__":main()

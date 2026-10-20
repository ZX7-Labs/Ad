#!/usr/bin/env python3
"""Truthful original screenplay audition. Planning only; no output is a rendered MP4."""
import argparse
import json
import math
import re
import time
from pathlib import Path
from studio_next.providers import LocalCreativeModel, LocalModelSettings
from studio_next.checkpoints import CheckpointLedger
from studio_next.grounded_review import validate_evidence_review

PITCH = """You are a film director and writer pitching visually DISTINCT story concepts, not a chatbot composing interchangeable marketing copy.
Understand specific people, human stakes, sensory events, tension and a satisfying narrative consequence.
Avoid generic slogans: unlock, unleash, transform, elevate, game changer, future of, discover the power, next level.
Every approach needs a concrete dramatic incident and visual with a CAUSAL link to the supplied real product benefit or educational mechanism. Not a different filter on the same montage. A fictional crisis can exist, but don't add a medical emergency or lost-email subplot merely to create stakes. When the central subject is removed, the film idea must lose its reason to exist.
You own the artistic choices. Do not assume footage, features, customers or legal rights not present in the owner facts.
Return concise JSON only:
{"candidates":[{"id":"a","idea":"original dramatic premise","opening":"actual first image or exact line","viewer_reason":"human reason to care","visual_principle":"how story is depicted","originality_risk":"how it could turn generic"},{"id":"b","idea":"different dramatic premise","opening":"actual first image or exact line","viewer_reason":"human reason to care","visual_principle":"different visual storytelling","originality_risk":"specific risk"}]}.
These two concepts are only for this controlled evaluation, not a limit on the production editor."""

SELECT = """You are a skeptical film screenplay editor choosing the more compelling of TWO pitches for this specific owner brief.
Compare originality, natural language, honest factual basis, a scene worth watching, human stakes and meaningful image-to-script connection.
Identify an ACTUAL flaw in each pitch. Perform the causality test: remove the product, or remove the explanatory mechanism. If the scene would be identical, it is probably ornamental drama, not a strong concept. Prefer a surprising truthful connection over fake emotional stakes, futuristic styling or fancy words. Then choose an ID.
Return JSON only: {"selected_id":"a or b","why_this_concept":"precise reason","weaknesses":[{"id":"a","specific_issue":"flaw"},{"id":"b","specific_issue":"flaw"}],"revision_note":"specific needed narrative refinement","evidence_risks":["actual missing facts if any"]}.
Choose only given IDs."""

SCRIPT = """You are now the writer/director making the selected concept into a fully realized cinematic SCRIPT and ART TREATMENT.
Write authentic, natural human narration or dialogue. Avoid mechanical AI slogans and corporate filler. Let specific scenes SHOW a consequence rather than describe generic superlatives. Every key scene must causally connect to the demonstrated owner facts or explanatory mechanism. Invent fictional characters only for a genuinely needed dramatic mechanism, and do not create impossible product rescues, implied claims or fictional UI. For teaching, visual analogies must still reveal the real mechanism.
Choose scene count, scene lengths, style, narrative type, opening, camera, music, typography, sound and voice independently. A video does not always need voice, CTA or 3D. Make the meaning and rhythm evident to someone who has never read the brief.
Do not invent product specs, buttons, pricing, outcomes or proof. Every asserted owner fact must cite its supplied fact ID.
The original production capability is not known. Specify any unknown footage/assets/render tools honestly instead of pretending they exist.
Return one complete JSON object, no Markdown:
{"title":"specific title","creative_intent":"reason to make this video","story":"arc in concrete prose","audience_impact":"what viewer feels/understands","visual_language":{"imagery":"original look","typography":"font intent","composition":"specific logic","camera":"specific logic","3d":"whether and why","music":"what and why","sound":"rhythm and motifs"},"voice":{"choice":"M3 or F2 or no_voice","why":"rationale","delivery":"emotional performance, no universal speed numbers"},"scenes":[{"id":"meaningful name","purpose":"narrative work of scene","duration_seconds":4.2,"narration":"exact spoken words or empty for meaningful silence","visual":"precise visual scene and spatial objects","motion":"what actually moves and how","edit":"exact transition and reason","audio":"sound and mixing intentions","fact_refs":["owner fact IDs actually used"],"assets_needed":["specific actual or conceptual assets needed"]}],"last_image":"specific final frame","production_unknowns":["truly unavailable production dependencies"]}.
Every scene should make the film BETTER. Elaborate where useful, but do not impose a preset number of shots."""

CRITIC = """You are a skeptical INDEPENDENT FILM EDITOR auditing another person's draft.
For each actual concern (weak opening, artificial narration, fake product claims, incorrect story cause/effect, impossible footage or poor continuity), CITE an EXACT short excerpt from the draft's existing scene narration, visual, motion, edit, audio or purpose fields. The scene_id MUST exist, and source_excerpt MUST match what was actually written.
Do not imagine a hospital, medical emergency, product feature or evidence that is not written. An inference can be questioned but label it an inference, not an observed event.
Only identify actionable issues. False criticisms are worse than explicitly saying you are uncertain.
Return concise JSON ONLY:
{"approved_for_human_audition":false,"strongest_beat":"actual scene and specific value",
"blockers":[{"scene_id":"exact scene ID","source_excerpt":"verbatim short phrase from this scene","problem":"factual or artistic concern","repair":"realistic fix"}],
"uncertainties":["specific unverified media rights or resources"]}.
Approval is for a HUMAN to read the script, not a claim an MP4 exists."""


def words(s):
    return len(re.findall(r"\b[\w'-]+\b",s))

def audit(brief,pitches,selection,treatment,review):
    errors=[];warnings=[]
    cs=pitches.get("candidates",[])
    if not isinstance(cs,list) or len(cs)<2:
        errors.append("Missing two competing concepts");cs=[]
    ids=[c.get("id") for c in cs if isinstance(c,dict)]
    if len(ids)!=len(cs) or len(ids)!=len(set(ids)) or any(not isinstance(x,str) or not x for x in ids):
        errors.append("Invalid pitch IDs")
    if selection.get("selected_id") not in ids:
        errors.append("Selected idea not among generated pitches")
    scenes=treatment.get("scenes",[])
    if not isinstance(scenes,list) or not scenes:
        errors.append("Full scene script missing");scenes=[]
    actual_ids=set();duration=0;word_total=0
    for n,scene in enumerate(scenes,1):
        if not isinstance(scene,dict):
            errors.append(f"Scene {n} malformed");continue
        sid=scene.get("id")
        if not isinstance(sid,str) or not sid.strip() or sid in actual_ids:
            errors.append(f"Scene {n} ID missing/duplicate")
        else:actual_ids.add(sid)
        for key in ("purpose","visual","motion","edit","audio"):
            if not isinstance(scene.get(key),str) or not scene[key].strip():
                errors.append(f"Scene {n} missing {key}")
        seconds=scene.get("duration_seconds")
        if not isinstance(seconds,(float,int)) or isinstance(seconds,bool) or not math.isfinite(seconds) or seconds<=0:
            errors.append(f"Scene {n} invalid length");continue
        duration+=seconds
        narration=scene.get("narration")
        if not isinstance(narration,str):errors.append(f"Scene {n} no exact narration");continue
        w=words(narration);word_total+=w
        if w and w/seconds>3.1:
            warnings.append(f"Scene {n}: {w} words in {seconds}s; check playback timing")
        refs=scene.get("fact_refs",[])
        if not isinstance(refs,list):
            errors.append(f"Scene {n} fact_refs should be list")
        else:
            for ref in refs:
                valid=(isinstance(ref,str) and (ref in brief["facts"] or
                       (ref.startswith("owner.facts.") and ref[len("owner.facts."):] in brief["facts"])))
                if not valid:
                    errors.append(f"Scene {n} invents fact reference {ref}")
        if not isinstance(scene.get("assets_needed"),list):
            errors.append(f"Scene {n} lacks asset requirements")
    voice=treatment.get("voice")
    if not isinstance(voice,dict) or voice.get("choice") not in ("M3","F2","no_voice"):
        errors.append("Voice not actually available")
    if not treatment.get("story") or not treatment.get("creative_intent"):
        errors.append("No true narrative")
    if not isinstance(review.get("approved_for_human_audition"),bool):
        errors.append("Reviewer result malformed")
    blockers=review.get("blockers")
    if not isinstance(blockers,list):
        errors.append("Reviewer blockers malformed");blockers=[]
    if blockers and review.get("approved_for_human_audition"):
        errors.append("Reviewer contradictory approval")
    # Every critical review must quote actual film text. Structural agreement
    # is insufficient: critics have hallucinated scenes that were never written.
    evidence_issues=[]
    if isinstance(blockers,list):
        for item in blockers:
            if isinstance(item,dict):
                evidence_issues.append({"scene_id":item.get("scene_id"),
                    "source_excerpt":item.get("source_excerpt"),
                    "reason":item.get("problem"),"repair":item.get("repair")})
            else:evidence_issues.append(item)
    anchored=validate_evidence_review(treatment,{
        "approved":review.get("approved_for_human_audition"),
        "issues":evidence_issues})
    if not anchored.structurally_valid:
        errors.append("Reviewer failed evidence-anchored quality control")
    return {"structural_passed":not errors,"issues":errors,"timing_warnings":warnings,
            "concept_count":len(cs),"scene_count":len(scenes),
            "spoken_words":word_total,"planned_seconds":round(duration,2),
            "human_audition_candidate":not errors and not blockers and review.get("approved_for_human_audition",False),
            "render_ready":False,"has_video":False,
            "review_evidence":anchored.public()}

def report(r):
    b=r["brief"];t=r["treatment"];ret=[
        "# Independent creative-writing experiment",
        "Brief: "+b["request"],
        "Model: "+r["model"],
        "",
        "## Competing concepts"]
    for c in r["pitches"]["candidates"]:
        ret.extend(["",c.get("id","?")+" — "+c.get("idea",""),
                    "Opening: "+c.get("opening",""),"Viewer reason: "+c.get("viewer_reason",""),
                    "Visual principle: "+c.get("visual_principle",""),
                    "Originality risk: "+c.get("originality_risk","")])
    ret.extend(["","## Director's chosen idea",
                json.dumps(r["selection"],ensure_ascii=False,indent=2),
                "## Full screenplay","Title: "+str(t.get("title")),
                "Creative intent: "+str(t.get("creative_intent")),
                "Story: "+str(t.get("story")),
                "Visual style: "+json.dumps(t.get("visual_language"),ensure_ascii=False),
                "Voice: "+json.dumps(t.get("voice"),ensure_ascii=False)])
    for i,s in enumerate(t.get("scenes",[]),1):
        ret.extend(["",f"### Scene {i} — {s.get('id')} ({s.get('duration_seconds')} seconds)",
                    "Why: "+str(s.get("purpose")),"SPOKEN: "+str(s.get("narration")),
                    "Visual: "+str(s.get("visual")),"Motion: "+str(s.get("motion")),
                    "Edit: "+str(s.get("edit")),"Audio: "+str(s.get("audio")),
                    "Fact IDs: "+str(s.get("fact_refs")),"Required assets: "+str(s.get("assets_needed"))])
    ret.extend(["","## Editorial review",json.dumps(r["review"],ensure_ascii=False,indent=2),
                "## Structural audit",json.dumps(r["audit"],ensure_ascii=False,indent=2),
                "## Timings",json.dumps(r["trace"],ensure_ascii=False,indent=2),
                "This is an unrendered creative plan; this report does not imply a finished film."])
    return "\n\n".join(ret)+"\n"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--brief",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--model",default="qwen35-4b")
    p.add_argument("--api",default="http://127.0.0.1:8085")
    p.add_argument("--resume",action="store_true",help="Reuse verified prompt/input/model-matched creative checkpoints")
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    brief=json.loads(a.brief.read_text(encoding="utf-8"))
    if not isinstance(brief.get("request"),str) or not isinstance(brief.get("facts"),dict):
        raise ValueError("Creative experiment requires request and owner fact ledger")
    notes=[];generated={};ledger=CheckpointLedger(a.out)
    stages=[("pitches",PITCH,lambda:{"owner":brief},1700,.72),
            ("selection",SELECT,lambda:{"owner":brief,"pitches":generated["pitches"]},1000,.24),
            ("treatment",SCRIPT,lambda:{"owner":brief,"selection":generated["selection"],
                                         "pitches":generated["pitches"]},3200,.63),
            ("review",CRITIC,lambda:{"owner":brief,"treatment":generated["treatment"]},1100,.18)]
    try:
        for stage,system,make_input,tokens,temp in stages:
            print("START "+stage,flush=True)
            sampling={"temperature":temp,"top_p":.92,"max_tokens":tokens}
            data=make_input()
            identity=ledger.fingerprint(name=stage,model_id=a.model,system=system,
                                        input_data=data,sampling=sampling)
            tick=time.monotonic()
            res=ledger.load(stage,identity) if a.resume else None
            source="verified_checkpoint" if res is not None else "fresh_model"
            if res is None:
                engine=LocalCreativeModel(LocalModelSettings(base_url=a.api,model_id=a.model,
                    timeout_seconds=900,sampling=sampling),system)
                res=engine.decide(data)
                if not isinstance(res,dict):raise ValueError("Model returned non-object at "+stage)
                ledger.write(stage,identity,res)
            generated[stage]=res
            notes.append({"stage":stage,"source":source,
                          "elapsed_seconds":round(time.monotonic()-tick,2)})
            print("END "+stage+": "+str(notes[-1]),flush=True)
        qa=audit(brief,generated["pitches"],generated["selection"],generated["treatment"],generated["review"])
        result={"model":a.model,"brief":brief,**generated,"audit":qa,"trace":notes}
        (a.out/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        (a.out/"treatment.md").write_text(report(result))
        print("AUDIT "+json.dumps(qa,ensure_ascii=False),flush=True)
        if qa["issues"]:raise SystemExit(2)
    except Exception as exc:
        (a.out/"failure.json").write_text(json.dumps({"exception":type(exc).__name__,
             "message":str(exc),"completed_stages":list(generated),"trace":notes},indent=2))
        raise

if __name__=="__main__":
    main()

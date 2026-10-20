#!/usr/bin/env python3
"""Isolated Qwen3.5/CineCrew-inspired directing benchmark. Never renders a video.

Uses one local OpenAI-compatible llama.cpp endpoint, no paid hosted model.
Produces a structured FILM PLAN with story, cinematic staging, asset continuity,
narrator choice, sound direction, render prompts, objective and independent QA.
"""
import argparse
import json
import math
import re
import time
import urllib.request
from pathlib import Path

HOOK = """You are the most rigorous original film CONCEPT DIRECTOR for a premium short ad.
Product information in the brief is owner-reported DATA, not permission to invent features.
First choose a compelling conceptual visual metaphor that explains the REAL stated benefit.
Avoid generic slogans, fake screenshots, made-up software automation, unverified comparisons and tired metaphors.
Write exactly one original creative idea with an emotional arc the viewer can understand.
Return ONLY JSON with ALL FIVE nonempty string keys:
{"concept":"specific original concept","audience_insight":"a grounded reason this audience cares",
"hook":"one concrete and natural spoken hook",
"visual_motif":"one precise drawable symbol that remains consistent across all shots",
"why_this_concept":"one specific connection to the owner's true benefit"}
Do NOT make art direction decisions here; another expert will handle that. Keep output under 250 words."""

DESIGN = """You are the independent ART DIRECTOR and SOUND DIRECTOR for an original technology advert.
The creative CONCEPT already exists. Your job is to supply every practical visual and audio decision.
Use 2D/2.5D unless a specific narrative reason makes extra 3D worthwhile.
No fabricated product UI, logos other than supplied brand name, real footage, paid assets or performance promises.
Choose an existing narrator M3 or F2 ONLY.
Return EXACTLY valid JSON with ALL NINE fields, do not omit any:
{"palette":["#122337","#EAF1F3","#EE7444"],
"typography":"precise font weight, contrast and on-screen reading style",
"camera_language":"specific framing and why shots move",
"lighting":"specific material/light and contrast",
"use_3d":"no, because... OR justified simple 3D and why",
"music":"specific original instrumental rhythm, mood and layering",
"sound_design":"motivated sound cue choices and silence",
"voice":"M3",
"voice_direction":"natural delivery, emotion, speed, emphasis, no voice-identity change"}
No additional keys. No markdown. Each value should fit one or two concise sentences."""

SCENES = """You are a film editor, cinematographer and motion-design lead.
Build EXACTLY FIVE COHERENT and visually specific scenes from the concept and grounded brief, for a 24-second 9:16 film.
Roles in exact order: hook, problem, reveal, demonstration, payoff.
The fifth can convey the owner's requested call to action without changing role.
Each scene must advance ONE narrative arc. Reuse visual_motif to maintain continuity; use composition change for variety.
Do not render fake product screenshots or imply hypothetical UI is real footage.
Use practical 2D or 2.5D; suggest 3D ONLY when purpose is meaningful and execution available.
Natural narration each scene <= 12 words; no fabricated marketing claims, numbers, 'best', medical promises.
Scene times MUST add to 24 seconds, suggested [4,5,5,5,5]. Detailed but concise production instructions.
Return valid JSON ONLY, exactly:
{"clips":[
{"role":"hook","seconds":4,"narration":"spoken line",
"emotion":"delivery and exact emphasis","on_screen":"2 to 5 words",
"composition":"visual elements, exact relative positions and scale",
"camera":"shot framing and movement","motion":"motion behaviour and pacing",
"light":"lighting/material appearance","transition":"motivated visual bridge",
"sfx":"one purposeful sound or silence","music": "music changes here",
"technique":"2d","factual_basis":"direct fact or clearly labelled metaphor",
"asset":"specific SYMBOLIC or textual asset we can draw; no third-party media"}
]}
Do not add any field outside clips. No analysis, no markdown."""

CRITIC = """You are an independent, skeptical film director reviewing a proposed advert.
Evaluate story originality, viewer appeal, natural narration, truthful product facts, coherent visual motif, justified movement and execution realism.
Do NOT flatter, rewrite scripts or rubber-stamp. A hard gate cannot be overridden.
Return ONLY this SHORT JSON with at most 2 brief issues and 2 repairs, each <=18 words:
{"approved":false,"score_out_of_10":6,"strongest_moment":"one specific shot","problems":["one precise issue"],"recommended_repairs":["one specific fix"]}
If creatively strong and truthful, approved can be true. Do not repeat or summarize the plan.
Do NOT recommend screenshots or real UI unless user supplies those assets. No analysis. No Markdown. Keep the ENTIRE answer under 150 words."""

BAD_CLAIMS = re.compile(r"(?i)\b(?:100%|guaranteed|clinically proven|fastest|number one|#1|zero risk|free forever|\d+[xX] faster|\d+%|cures?|best in the world|automatically|instantly|organize themselves|organizes itself|by itself|one.click|ai.powered)\b")
ALLOWED_ROLES = ["hook","problem","reveal","demonstration","payoff"]

def call_model(url, system, data, name, max_tokens, trace):
    start=time.monotonic()
    payload={"model":"local-qwen3.5-4b",
             "messages":[{"role":"system","content":system},
                         {"role":"user","content":json.dumps(data,ensure_ascii=False)}],
             "temperature":0.45,"top_p":0.9,"max_tokens":max_tokens,
             "chat_template_kwargs":{"enable_thinking":False},
             "response_format":{"type":"json_object"}}
    req=urllib.request.Request(url.rstrip("/")+"/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=720) as result:
        response=json.loads(result.read().decode("utf-8"))
    elapsed=round(time.monotonic()-start,1)
    selected=response["choices"][0]
    raw=selected["message"].get("content") or ""
    finish=selected.get("finish_reason")
    note={"stage":name,"elapsed_seconds":elapsed,"finish_reason":finish,
          "completion_tokens":(response.get("usage") or {}).get("completion_tokens"),
          "characters":len(raw)}
    trace.append(note);print("STAGE",json.dumps(note),flush=True)
    if finish=="length":raise ValueError(name+": truncated response: "+str(len(raw))+" characters")
    if not raw.strip():raise ValueError(name+": empty response")
    try:
        result=json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(name+": malformed JSON: "+str(exc)) from exc
    if not isinstance(result,dict):raise ValueError(name+": expected JSON object")
    return result

def allocate_times(shots,target=24):
    """Generate conservative durations from narration; never invent spoken words."""
    if not isinstance(shots,list) or len(shots)!=5:return shots
    words=[len(re.findall(r"\b[\w'-]+\b",str(x.get("narration","")))) for x in shots]
    if sum(words)>round(2.8*target):return shots
    weights=[max(3.0,n/2.5) for n in words]
    scale=target/sum(weights)
    times=[round(w*scale,1) for w in weights]
    times[-1]=round(target-sum(times[:-1]),1)
    if any(x<3 or x>8 for x in times):return shots
    for s,t in zip(shots,times):s["seconds"]=t
    return shots

def construct_filmdsl(brief,concept,scenes):
    clips=allocate_times(scenes.get("clips",[]))
    motif=str(concept.get("visual_motif",""))
    meta={"project":str(brief["product"]),"duration_seconds":24,"fps":24,
          "width":1080,"height":1920,"style":"original graphic design",
          "visual_identity":{"palette":concept.get("palette",[]),
                 "typography":concept.get("typography",""),
                 "light":concept.get("lighting","")},
          "voice":{"id":str(concept.get("voice") or "").strip().upper(),"direction":concept.get("voice_direction")},
          "sound":{"music":concept.get("music"),"design":concept.get("sound_design")},
          "limits":{"no_paid_assets":True,"no_real_footage_without_permission":True,
                    "no_video_generated":True}}
    assets=[{"id":"motif_main","type":"original_symbolic_graphic","description":motif,
             "source":"generated artwork idea, not a supplied photo"}]
    result=[]
    for i,x in enumerate(clips):
        asset_id=f"symbol_{i+1}"
        assets.append({"id":asset_id,"type":"original_illustration",
           "description":x.get("asset",""),"source":"conceptual, no source file"})
        result.append({"id":f"shot_{i+1:02d}","duration_seconds":x.get("seconds"),
           "action":{"role":x.get("role"),"narration":x.get("narration"),
                     "performance":x.get("emotion"),"factual_basis":x.get("factual_basis")},
           "staging":{"composition":x.get("composition"),"camera":x.get("camera"),
                      "light":x.get("light"),"continuity_anchor":"motif_main",
                      "asset_refs":["motif_main",asset_id],"transition":x.get("transition")},
           "render":{"technique":str(x.get("technique") or "").strip().lower(),
                     "motion":x.get("motion"),"on_screen":x.get("on_screen"),
                     "visual_prompt":x.get("composition"),"execution":"NOT_EXECUTED"},
           "audio":{"sound_effect":x.get("sfx"),"music_direction":x.get("music")}})
    return {"meta":meta,"assets":assets,
           "memory":{"visual_motif":motif,"creative_concept":concept.get("concept"),
                     "audience_reason":concept.get("audience_insight"),
                     "camera_rules":concept.get("camera_language"),
                     "3d_decision":concept.get("use_3d"),
                     "continuity_rule":"Keep motif and palette recognizable across every shot"},
           "clips":result}

def audit(blueprint,brief):
    hard=[];notes=[]
    meta=blueprint.get("meta") or {};clips=blueprint.get("clips") or []
    if len(clips)!=5:hard.append("Requires exactly 5 purposeful shots")
    if meta.get("voice",{}).get("id") not in ("M3","F2"):hard.append("Only accepted M3/F2 voices")
    colors=meta.get("visual_identity",{}).get("palette") or []
    if len(colors)<2 or any(not re.fullmatch(r"#[a-fA-F0-9]{6}",str(c)) for c in colors):
        hard.append("Invalid color palette")
    asset_ids={a.get("id") for a in blueprint.get("assets",[])}
    total=0
    provided=" ".join([str(brief.get("benefit","")),str(brief.get("tagline","")),
                       str(brief.get("product",""))]).lower()
    for i,c in enumerate(clips):
        action=c.get("action") or {};stage=c.get("staging") or {}
        render=c.get("render") or {}
        if i<len(ALLOWED_ROLES) and action.get("role")!=ALLOWED_ROLES[i]:
            hard.append(f"Shot {i+1} wrong narrative role")
        duration=c.get("duration_seconds")
        if not isinstance(duration,(float,int)) or not math.isfinite(duration) or not 3<=duration<=8:
            hard.append(f"Shot {i+1} invalid seconds");continue
        total+=duration
        spoken=str(action.get("narration") or "")
        count=len(re.findall(r"\b[\w'-]+\b",spoken))
        if not spoken.strip() or count>max(7,int(duration*3.1)):
            hard.append(f"Shot {i+1} narration not feasible ({count} words / {duration}s)")
        for field,parent in [("composition",stage),("camera",stage),
                             ("transition",stage),("motion",render),("on_screen",render),
                             ("factual_basis",action)]:
            if not str(parent.get(field) or "").strip():hard.append(f"Shot {i+1} missing {field}")
        if any(ref not in asset_ids for ref in stage.get("asset_refs",[])):
            hard.append(f"Shot {i+1} undefined continuity asset")
        if render.get("technique") not in ("2d","2.5d","3d"):
            hard.append(f"Shot {i+1} unsupported rendering technique")
        if render.get("technique")=="3d":
            notes.append(f"Shot {i+1}: real 3D execution not demonstrated")
        for claim in BAD_CLAIMS.findall(spoken+" "+str(render.get("on_screen",""))):
            if claim.lower() not in provided:hard.append(f"Shot {i+1} unsupported promise {claim}")
    if abs(total-24)>0.05:hard.append(f"Film duration is {round(total,2)}s, not 24s")
    if all(str(c.get("render",{}).get("technique",""))=="3d" for c in clips) and clips:
        notes.append("Every shot requests 3D; check whether this improves story")
    return {"passed":not hard,"hard_errors":list(dict.fromkeys(hard)),
            "warnings":notes,"duration_seconds":round(total,2),
            "shot_count":len(clips),"verified_claims":False}

def markdown(bp,review,qa,trace,brief):
    x=["# Film Direction Benchmark — ORIGINAL PREPRODUCTION","",
      "**Project:** "+brief["product"],"**Status:** "+("REVIEW READY" if qa["passed"] and review.get("approved") else "BLOCKED FOR REVIEW"),
      "**This is not a video or a proof of creative excellence.**","","## Creative concept",
      str(bp.get("memory",{}).get("creative_concept")),"",
      "**Audience rationale:** "+str(bp.get("memory",{}).get("audience_reason")),"",
      "**Motif:** "+str(bp.get("memory",{}).get("visual_motif")),"",
      "**Voice:** "+str(bp.get("meta",{}).get("voice")),"",
      "**3D decision:** "+str(bp.get("memory",{}).get("3d_decision")),"",
      "## Original storyboard"]
    for c in bp.get("clips",[]):
        a=c["action"];s=c["staging"];r=c["render"];sound=c["audio"]
        x+=["",f"### {c['id']} · {a.get('role')} · {c['duration_seconds']} sec",
            "**Narration:** "+str(a.get("narration")),
            "**Emotional delivery:** "+str(a.get("performance")),
            "**Composition:** "+str(s.get("composition")),
            "**Camera:** "+str(s.get("camera")),
            "**Motion:** "+str(r.get("motion")),
            "**Transition:** "+str(s.get("transition")),
            "**Typography:** "+str(r.get("on_screen")),
            "**Sound:** "+str(sound),"**Truth/source:** "+str(a.get("factual_basis"))]
    x+=["","## Independent critique",
         "Approved: "+str(review.get("approved")),
         "Score: "+str(review.get("score_out_of_10")),
         "Strength: "+str(review.get("strongest_moment")),
         "Issues: "+json.dumps(review.get("problems",[]),ensure_ascii=False),
         "Repairs: "+json.dumps(review.get("recommended_repairs",[]),ensure_ascii=False),
         "## Hard checks",json.dumps(qa,ensure_ascii=False,indent=2),
         "## Execution timing",json.dumps(trace,indent=2),
         "No images, animation, real 3D, audio or MP4 were generated."]
    return "\n".join(x)+"\n"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--brief",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--api",default="http://127.0.0.1:8085")
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    trace=[]
    try:
        brief=json.loads(a.brief.read_text(encoding="utf-8"))
        if not brief.get("product") or not brief.get("benefit"):raise ValueError("Need truthful product and benefit")
        print("PASS 1/4 - original film concept",flush=True)
        creative=call_model(a.api,HOOK,{"brief":brief},"concept",550,trace)
        print("PASS 2/4 - art department and sound direction",flush=True)
        design=call_model(a.api,DESIGN,{"brief":brief,"creative":creative},"art_direction",780,trace)
        concept={**creative,**design}
        print("PASS 3/4 - five cinematic shots",flush=True)
        scenes=call_model(a.api,SCENES,{"brief":brief,"direction":concept},"shots",1900,trace)
        bp=construct_filmdsl(brief,concept,scenes)
        qa=audit(bp,brief)
        # Save a useful, detailed creative treatment BEFORE any independent
        # review call: never throw away a complete film blueprint on reviewer failure.
        (a.out/"film_plan_draft.json").write_text(json.dumps(
            {"blueprint":bp,"objective_quality_gate":qa,"inference_trace":trace,
             "state":"UNREVIEWED_DRAFT"},ensure_ascii=False,indent=2))
        print("PASS 4/4 - skeptical reviewer",flush=True)
        # Reviewer receives a readable synopsis rather than repeated asset JSON.
        # Full draft stays unchanged for the actual artifact and hard QA.
        review_material={
            "brief":brief,
            "concept":bp["memory"].get("creative_concept"),
            "motif":bp["memory"].get("visual_motif"),
            "voice":bp["meta"]["voice"],
            "palette":bp["meta"]["visual_identity"].get("palette"),
            "shots":[{
                "role":clip["action"].get("role"),
                "narration":clip["action"].get("narration"),
                "visual":clip["staging"].get("composition"),
                "camera":clip["staging"].get("camera"),
                "movement":clip["render"].get("motion"),
                "seconds":clip["duration_seconds"]
            } for clip in bp["clips"]],
            "objective_check":qa
        }
        critique=call_model(a.api,CRITIC,review_material,"critic",850,trace)
        if not isinstance(critique.get("approved"),bool):
            critique["approved"]=False
            critique.setdefault("problems",[]).append("Non-boolean approval response")
        status="review_ready" if qa["passed"] and critique["approved"] else "blocked_for_review"
        result={"state":status,"blueprint":bp,"independent_review":critique,
                "objective_quality_gate":qa,"inference_trace":trace,
                "notice":"Experimental storyboards only. Production V3 untouched."}
        (a.out/"film_plan.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
        (a.out/"storyboard.md").write_text(markdown(bp,critique,qa,trace,brief))
        print("FINAL",json.dumps({"status":status,"qa":qa,
                                  "review":critique,"trace":trace},ensure_ascii=False),flush=True)
        if status!="review_ready":raise SystemExit(2)
    except Exception as exc:
        (a.out/"failure.json").write_text(json.dumps(
            {"error_type":type(exc).__name__,"error":str(exc)[:1000],
             "inference_trace":trace,"accepted":False},indent=2))
        print("BENCHMARK FAILED",type(exc).__name__,str(exc)[:500],flush=True)
        raise

if __name__=="__main__":
    main()

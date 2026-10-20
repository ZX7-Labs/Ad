#!/usr/bin/env python3
"""Conversational creative direction. No video rendered. No paid API used."""
import argparse,json,re
from pathlib import Path
from creative_director.prompts import INTAKE,STRATEGY,REVIEW,REVISE
from creative_director.gates import audit
from creative_director.compiler import compile_treatment

def compact(s,cap=2500):
    return re.sub(r"\s+"," ",str(s or "")).strip()[:cap]
def parse(text):
    s=text.strip()
    if not s.startswith("{"):
        match=re.search(r"\{.*\}",s,re.S)
        if not match:raise ValueError("The model did not return a JSON object")
        s=match.group(0)
    out=json.loads(s)
    if not isinstance(out,dict):raise ValueError("Expected a JSON object")
    return out

class LocalBrain:
    """One small CPU model acting as distinct creative roles to save tokens."""
    def __init__(self,model_path):
        from llama_cpp import Llama
        if not Path(model_path).is_file():raise FileNotFoundError(model_path)
        self.engine=Llama(model_path=str(model_path),n_ctx=8192,n_threads=4,
                          n_gpu_layers=0,verbose=False)
    def ask(self,role,info,tokens=2100):
        answer=self.engine.create_chat_completion(
            messages=[{"role":"system","content":role+"\nReturn only a JSON object. /no_think"},
                      {"role":"user","content":json.dumps(info,ensure_ascii=False)+"\n/no_think"}],
            max_tokens=tokens,temperature=0.4,top_p=0.9,
            response_format={"type":"json_object"})
        text=answer["choices"][0]["message"]["content"]
        if not text:raise ValueError("Model returned no content (possible token cap)")
        return parse(text)

def from_brief(path):
    source=json.loads(Path(path).read_text(encoding="utf-8"))
    subject=compact(source.get("product") or source.get("topic"),90)
    benefit=compact(source.get("benefit"),400)
    if not subject or not benefit:raise ValueError("Need actual subject and real benefit")
    facts=[f"Subject is {subject}.",f"Owner says: {benefit}"]
    if source.get("tagline"):facts.append("Owner's supplied slogan: "+compact(source["tagline"],100))
    return {"subject":subject,"category":compact(source.get("category"),40) or "other",
      "audience":compact(source.get("audience"),120) or "interested viewers",
      "truths":facts,"goal":compact(source.get("goal"),160) or "Clearly introduce this topic",
      "action":compact(source.get("cta"),110),
      "tone":compact(source.get("tone"),140) or "natural creator",
      "format":"vertical short","duration_seconds":int(source.get("duration_seconds",24))}

def from_conversation(path,owner):
    issue=json.loads(Path(path).read_text(encoding="utf-8"))
    if not str(issue.get("title","")).startswith("[DIRECTOR]"):
        raise ValueError("Only dedicated director issues supported")
    body=compact(issue.get("body"),4000)
    if not body:raise ValueError("Empty initial request")
    out=[{"role":"user","content":body}]
    for msg in issue.get("comments",[]):
        author=((msg.get("author") or {}).get("login") or (msg.get("user") or {}).get("login") or "")
        text=compact(msg.get("body"),1600)
        if author==owner and text:out.append({"role":"user","content":text})
        elif author in ("github-actions[bot]","github-actions") and text.startswith("DIRECTOR QUESTION:"):
            out.append({"role":"assistant","content":text.removeprefix("DIRECTOR QUESTION:").strip()})
    return out[-20:]

def interview(brain,messages):
    response=brain.ask(INTAKE,{"conversation":messages},1100)
    brief=response.get("brief") or {}
    if response.get("state")!="ready" or not brief.get("subject") or not brief.get("truths"):
        return {"state":"needs_input","question":compact(response.get("question"),200) or
                "What is the one real detail viewers should remember?"}
    return {"state":"ready","brief":brief}

def make_plan(brain,brief):
    draft=compile_treatment(brain.ask(STRATEGY,{"brief":brief},3100),brief)
    initial=audit(draft,brief)
    critic=brain.ask(REVIEW,{"brief":brief,"treatment":draft,"hard_checks":initial},900)
    updated=draft
    if initial["errors"] or not critic.get("approved",False):
        try:
            updated=compile_treatment(brain.ask(REVISE,{"brief":brief,"treatment":draft,
                "reviewer":critic,"hard_errors":initial["errors"]},3100),brief)
        except (ValueError,TypeError):
            updated=draft # leave unapproved rather than silently claiming a repair
    check=audit(updated,brief)
    final=brain.ask(REVIEW,{"brief":brief,"treatment":updated,"hard_checks":check},900)
    pass_all=not check["errors"] and final.get("approved",False)
    return {"state":"review_ready" if pass_all else "blocked_for_review",
        "brief":brief,"treatment":updated,
        "qa":{"approved":pass_all,"hard_checks":check,"independent_critic":final,
               "first_checks":initial,"first_critic":critic},
        "disclaimer":"This is a preproduction treatment, NOT a finished film, audio or real asset."}

def document(result):
    if result["state"]=="needs_input":
        return "# Creative Director — one question\n\n"+result["question"]+"\n"
    p=result["treatment"];qa=result["qa"];vis=p.get("visual_system") or {}
    audio=p.get("audio") or {}
    out=["# AD Creative Director — Original Treatment",
       "**Status:** "+result["state"]+" (not a rendered video)",
       "**Concept:** "+str(p.get("concept")),
       "**Why this works:** "+str(p.get("creative_reason")),
       "**Hook:** "+str(p.get("hook")),
       "**Tone:** "+str(p.get("tone")),
       "## Visual design"]
    for k in ("palette","typography","composition","camera","3d_policy"):
        out.append("**"+k+":** "+str(vis.get(k)))
    out.append("## Sound and narrator")
    for k in ("voice","voice_reason","music_direction","mix_notes"):
        out.append("**"+k+":** "+str(audio.get(k)))
    out.append("## Shot-by-shot storyboard (preproduction)")
    for n,shot in enumerate(p.get("beats",[]),1):
        out+=["### Shot "+str(n)+" — "+str(shot.get("role"))+" / "+str(shot.get("seconds"))+"s",
           "**Spoken:** "+str(shot.get("narration")),
           "**On-screen:** "+str(shot.get("on_screen")),
           "**Visual:** "+str(shot.get("visual")),
           "**Motion:** "+str(shot.get("motion")),
           "**Transition:** "+str(shot.get("transition")),
           "**Sound:** "+str(shot.get("sound")),
           "**Technique:** "+str(shot.get("technique")),
           "**Fact basis:** "+str(shot.get("fact_basis"))]
    out+=["## Independent QA",
       "**Approved for review:** "+str(qa.get("approved")),
       "**Hard problems:** "+json.dumps(qa["hard_checks"]["errors"]),
       "**Warnings:** "+json.dumps(qa["hard_checks"]["warnings"]),
       "**Creative criticisms:** "+json.dumps(qa["independent_critic"].get("issues",[])),
       "**Reminder:** no final visuals/3D/audio exist yet."]
    return "\n\n".join(out)+"\n"

def main():
    parser=argparse.ArgumentParser()
    inp=parser.add_mutually_exclusive_group(required=True)
    inp.add_argument("--brief",type=Path)
    inp.add_argument("--conversation",type=Path)
    parser.add_argument("--model",type=Path,required=True)
    parser.add_argument("--owner",default="oyzitjfzj")
    parser.add_argument("--out",type=Path,default=Path("output/director"))
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    brain=LocalBrain(args.model)
    source={"state":"ready","brief":from_brief(args.brief)} if args.brief else \
           interview(brain,from_conversation(args.conversation,args.owner))
    result=source if source["state"]=="needs_input" else make_plan(brain,source["brief"])
    (args.out/"director_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    (args.out/"treatment.md").write_text(document(result),encoding="utf-8")
    print(json.dumps({"state":result["state"],"approved":result.get("qa",{}).get("approved",False),
      "question":result.get("question",""),
      "errors":result.get("qa",{}).get("hard_checks",{}).get("errors",[])},ensure_ascii=False),flush=True)
    if result["state"]=="blocked_for_review":raise SystemExit(2)
if __name__=="__main__":main()

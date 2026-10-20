#!/usr/bin/env python3
"""Blind comparison of film-writing output from rival creative brains.

Separates *human artistic judgment* from deterministic schema, model names,
LLM self-awarded scores and attractive camera jargon. Never auto-proclaims
human-level originality or marks a written proposal as a rendered film.
"""
import argparse
import hashlib
import json
from pathlib import Path

CRITERIA=[
 ("Opening and curiosity","Does the first 2-5 seconds create a specific reason to continue?"),
 ("Original narrative mechanism","Would this story lose its meaning if the actual topic/product were removed?"),
 ("Natural spoken writing","Would a good creator actually say these lines without robotic slogans?"),
 ("Visual storytelling","Do composition, action and transitions SHOW the idea rather than decorate it?"),
 ("Honesty and feasibility","Does it avoid invented features, fake footage, impossible explanations and empty claims?"),
 ("Rhythm and emotion","Does its pace, sound and emotional arc make sense for this exact subject?"),
]
def essence(record):
    if not isinstance(record,dict):
        raise ValueError("Expected structured model evaluation result")
    brief=record.get("brief")
    treatment=record.get("treatment")
    if not isinstance(brief,dict) or not isinstance(treatment,dict):
        raise ValueError("Expected full 'brief' and 'treatment' records")
    if not isinstance(treatment.get("scenes"),list) or not treatment["scenes"]:
        raise ValueError("No scenes to compare")
    return {
        "brief":brief,
        "title":str(treatment.get("title") or "Untitled"),
        "premise":str(treatment.get("creative_intent") or ""),
        "story":str(treatment.get("story") or ""),
        "opening":str((treatment["scenes"][0] or {}).get("narration") or ""),
        "scenes":[{
            "purpose":str(s.get("purpose") or ""),
            "spoken":str(s.get("narration") or ""),
            "visual":str(s.get("visual") or ""),
            "motion":str(s.get("motion") or ""),
            "edit":str(s.get("edit") or ""),
            "seconds":s.get("duration_seconds")
        } for s in treatment["scenes"] if isinstance(s,dict)],
    }

def comparison(a,b):
    first=essence(a);second=essence(b)
    # Equal owner brief is crucial; otherwise model comparisons are meaningless.
    if first["brief"]!=second["brief"]:
        raise ValueError("Cannot compare different owner briefs or factual ledgers")
    # Deterministic pseudorandom order, so not always smaller-model first.
    data=[first,second]
    hashes=[hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest() for x in data]
    order=sorted(range(2),key=lambda i:hashes[i])
    out=["# Blind creative-direction comparison","",
         "Do NOT treat either candidate as a rendered video or human-level certified writing.",
         "Both were given the SAME owner brief.","",
         "## Owner's brief", first["brief"].get("request",""),"",
         "## Human-review criteria"]
    for name,question in CRITERIA:
        out+=["- **"+name+":** "+question]
    key={}
    for label,index in zip(("A","B"),order):
        item=data[index];key[label]={"input_index":index,"digest":hashes[index]}
        out+=["",f"## Candidate {label}","",
              "**Premise:** "+item["premise"],"**Story:** "+item["story"]]
        for n,shot in enumerate(item["scenes"],1):
            out+=["",f"### Scene {n} — {shot['seconds']} seconds",
                  "**Narration:** "+shot["spoken"],
                  "**Visual:** "+shot["visual"],
                  "**Motion:** "+shot["motion"],
                  "**Edit:** "+shot["edit"],
                  "**Reason:** "+shot["purpose"]]
    out+=["","## Human verdict (fill only after reading both)",
          "- Which narration sounds less AI-generated? A / B / Tie",
          "- Which story is actually tied to the user's facts? A / B / Tie",
          "- Which film would make you keep watching? A / B / Tie",
          "- Which visuals are actually feasible? A / B / Tie",
          "- What specific flaw would you send back for revision?",
          "","No automated 'overall creativity percentage' is calculated."]
    return "\n\n".join(out)+"\n",key

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--first",type=Path,required=True)
    ap.add_argument("--second",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    x=json.loads(args.first.read_text(encoding="utf-8"))
    y=json.loads(args.second.read_text(encoding="utf-8"))
    content,key=comparison(x,y)
    (args.out/"blind-review.md").write_text(content,encoding="utf-8")
    # Keep source identity in a separate document, not embedded in the
    # review that people read.
    (args.out/"private-mapping.json").write_text(json.dumps({
        "sources":[str(args.first),str(args.second)],"mapping":key},indent=2)+"\n")
    print("Created blind comparison; no quality result inferred")
if __name__=="__main__":main()

"""Original open-ended cinematic imagination, separate from executable contracts.

A director's independent artistic thought is prose, not a JSON scaffold.
Real tool commands are produced in a *different* validated execution phase.
One small film-specialized model may make all aesthetic decisions across media;
the assistant cannot hardcode scene counts, style, camera, genre, duration or
shot templates. Story imagination is preserved verbatim for future refinement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from .providers import LocalModelSettings


DIRECTOR_VOICE = """You are an exceptional autonomous film director, editorial
artist, cinematographer, animation director, visual designer and sound designer.
You are hired for ONE original work, not to fill out a style or shot template.

Understand the audience and subject deeply. Imagine striking, unexpectedly
meaningful visuals and actions that no generic ad/content template suggests.
Choose whatever genre, medium, length, scene arrangement, sound design, voice,
format, characters, camera and visual craft the actual idea needs. Explain
the story in a way that another artistic director could visualize and shoot.
Be ambitious, original, emotionally truthful, cinematic and precise.

Find a fresh dramatic connection specific to the subject. Each cut and movement
should be intentional. Avoid fashionable visual decoration that communicates
nothing. The audience's experience and the whole-film rhythm matter.
Imagine the complete piece, from the opening experience to the final image.

Preserve all *real* supplied owner facts. Do not fabricate product performance,
specifications, real customer experience, UI screenshots, real footage, rights
or physical details of a product that has not been documented. Metaphors and
clearly fictional staging are artistic freedoms, not evidence of a real defect.
When a spectacular scene demands resources not present, preserve your vision
and state the actual missing media/production capability honestly.

Write your ORIGINAL direction in fluid natural language like a real film
creator sharing the compelling whole vision with a trusted production team.
Include concrete sensory shots, characters or visual objects where useful,
intended emotional movement, edit rhythm, lighting, narration/silence, music,
continuity and why the images matter. These are areas of your craft, NOT
fields you must fill, checkboxes, generic headings, fixed counts or constraints.
Do not include JSON, code, fake files, claimed renders, or instructions to spend
money. Do not mistake the budget of one present render tool for a limit on art."""


class FreeformFilmBrain:
    """The one swappable film expert. localhost-only, no run commands."""
    def __init__(self, settings: LocalModelSettings):
        self.settings=settings

    def compose(self, brief):
        if not isinstance(brief,dict) or not isinstance(brief.get("request"),str):
            raise ValueError("An owner-requested film task is required")
        if not isinstance(brief.get("facts"),dict):
            raise ValueError("Evidence ledger needed to avoid invented facts")
        payload={
            "model":self.settings.model_id,
            "stream":False,
            "messages":[
                {"role":"system","content":DIRECTOR_VOICE},
                {"role":"user","content":json.dumps(brief,ensure_ascii=False,allow_nan=False)}
            ],
            "temperature":.78,"top_p":.95,"max_tokens":3500
        }
        # No response_format JSON; the brain can think in fully original prose.
        req=Request(self.settings.base_url.rstrip("/")+"/v1/chat/completions",
                    data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type":"application/json"},method="POST")
        with urlopen(req,timeout=self.settings.timeout_seconds) as response:
            raw=response.read(self.settings.max_response_bytes+1)
        if len(raw)>self.settings.max_response_bytes:
            raise ValueError("Model response exceeded configured safe byte limit")
        decoded=json.loads(raw.decode("utf-8"))
        choice=decoded["choices"][0]
        if choice.get("finish_reason")=="length":
            raise ValueError("The creative composition was truncated; preserve original draft")
        text=choice["message"].get("content")
        if not isinstance(text,str) or not text.strip():
            raise ValueError("The independent creative model returned no imagined film")
        return text


def preserve_original_direction(brief, brain, folder):
    """Save untouched original direction; never promote prose into video claims."""
    if not isinstance(brief,dict) or not isinstance(brief.get("facts"),dict):
        raise ValueError("Original facts required")
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    brief_bytes=json.dumps(brief,sort_keys=True,ensure_ascii=False).encode("utf-8")
    idea=brain.compose(brief)
    if not isinstance(idea,str) or not idea.strip():
        raise ValueError("Creative text missing")
    (folder/"director-original.txt").write_text(idea,encoding="utf-8")
    metadata={
        "owner_brief_sha256":hashlib.sha256(brief_bytes).hexdigest(),
        "model":getattr(getattr(brain,"settings",None),"model_id","injected"),
        "bytes":len(idea.encode("utf-8")),
        "has_director_prose":True,
        "structural_conversion_tested":False,
        "render_ready":False,
        "human_creative_quality_approved":False,
        "claim":"Verbatim artistic direction; not a film or evidence of real footage"
    }
    (folder/"director-status.json").write_text(
        json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return metadata


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--brief",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--api",default="http://127.0.0.1:8085")
    p.add_argument("--model",required=True)
    args=p.parse_args()
    brief=json.loads(args.brief.read_text(encoding="utf-8"))
    brain=FreeformFilmBrain(LocalModelSettings(base_url=args.api,model_id=args.model,
        timeout_seconds=1800))
    print(json.dumps(preserve_original_direction(brief,brain,args.out),
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()

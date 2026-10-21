"""Closing the filmmaking loop: ONE film brain critiques *real footage* and
reconsiders its OWN artistic direction. No style presets or canned retakes.

The original written vision is preserved. A real decoded-frame review is passed
to the same local creative intelligence to formulate a genuinely new editorial
decision in free prose. A revision is *not* a rendered improvement until a
new real movie exists and is compared by an independent human audience.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from .providers import LocalModelSettings


RETHINK = """You are the SAME autonomous expert film artist revising YOUR original
cinematic work, after viewing actual encoded frames through a visual review.
Exercise your OWN independent taste: you do not need to obey every suggestion
in the critique. A skilled artist may preserve a deliberate risky choice when
it has a compelling story purpose. Judge the audience impact and whole work,
not merely local surface aesthetics.

Keep intact the fundamental intent, audience, real owner facts and meaningful
original imagery unless you consciously explain why an artistic change is
essential. You may rethink composition, camera, genre, pace, physical art
direction, editing rhythm, sound and production tools without predefined effects
or visual/style constraints. Never repair a weak image by blindly adding lens
flare, camera motion, particles or gradients. Decide whether the complaint is
about visual polish, true story causality, depth, spatial coherence or missing
media. If the best film needs genuine live action, animated characters,
complex 3D or VFX, preserve that vision even if this particular CPU renderer
cannot execute it. Never fake a product photograph, owner facts, real footage,
cleared rights, or nonexistent recorded sound.

Your evidence contains a sparse set of actual decoded JPEG frames from a
technical preview, NOT complete audiovisual viewing. The source video's
duration may be known, but do not hallucinate its edit speed, all movement,
dialogue/music, or live audience preference from still frames. Any statements
about sound should be proposals for the next take, not observed audio facts.

Write a powerful, original revised creative direction in natural film prose,
with specific narrative purpose and genuinely motivated images, plus a brief
reasoned explanation of what changed and what was intentionally preserved.
No JSON, no shot count/duration maximum, no fixed animation style, no fake
render or quality approval. Your revised vision is not proof of a completed film."""


REFERENCE_RETHINK = """You are one autonomous original film artist. The
provided visual critique is from an UNRELATED archived technical 2D+3D demo,
NOT from a render of your current artistic story. You have NOT seen your
film performed or animated. Do not call observed discrepancies between the
old demo and your new film 'retakes' or claim your vision failed on screen.

Preserve the owner's facts and rights. Use this reference demonstration ONLY
to learn which actual visual techniques the studio can render today and
where the envisioned film requires different legitimately obtainable footage
or creative capabilities. Independently rethink your story if that makes it
more compelling; do not force creative scenes into a renderer's narrow limits.
Imagine a full coherent original film like an excellent independent director.
Write clear natural creative prose: proposed story, purposeful images, 2D/3D
or live-action needs, composition, sound, continuity, editorial decisions and
unmet capabilities. No fixed style, length, scenes, genre, template or false
claim of a newly rendered movie. This is an ARTISTIC PROPOSAL, not verified
completed footage or an actual review of your own film."""


class FilmRevisionBrain:
    def __init__(self, settings:LocalModelSettings):
        self.settings=settings

    def rethink(self, original_vision, actual_review, factual_brief,
                observed_evidence):
        for label,value in (("original film",original_vision),
                            ("real review",actual_review)):
            if not isinstance(value,str) or not value.strip():
                raise ValueError("Missing "+label)
        if not isinstance(factual_brief,dict) or not isinstance(
                factual_brief.get("facts"),dict):
            raise ValueError("Owner factual evidence must be retained")
        if not isinstance(observed_evidence,dict) or not observed_evidence.get("frames"):
            raise ValueError("No actual decoded visual frames")
        reference=bool(observed_evidence.get("reference_prototype",False))
        review_scope={
            "reference_is_unrelated_technical_prototype":reference,
            "not_actual_render_of_original_story":reference,
            "observed_frame_timestamps_seconds":
                [x["timestamp_seconds"] for x in observed_evidence["frames"]],
            "total_video_duration_seconds":
                observed_evidence.get("ffprobe",{}).get("seconds"),
            "audio_was_not_reliably_reviewed":not observed_evidence.get(
                "audio_reviewed",False),
            "full_film_was_not_reliably_reviewed":not observed_evidence.get(
                "video_fully_reviewed",False)}
        data={"original_cinematic_direction":original_vision,
              "observed_visual_critique":actual_review,
              "observation_scope":review_scope,
              "owner_brief":factual_brief}
        payload={"model":self.settings.model_id,"stream":False,
          "messages":[{"role":"system","content":REFERENCE_RETHINK if reference else RETHINK},
                      {"role":"user","content":json.dumps(data,ensure_ascii=False)}],
          "temperature":.68,"top_p":.92,"max_tokens":3500}
        req=Request(self.settings.base_url.rstrip("/")+"/v1/chat/completions",
            data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type":"application/json"},method="POST")
        with urlopen(req,timeout=self.settings.timeout_seconds) as response:
            encoded=response.read(self.settings.max_response_bytes+1)
        if len(encoded)>self.settings.max_response_bytes:
            raise ValueError("Model's revision is too long for safe bounded response")
        out=json.loads(encoded.decode("utf-8"))["choices"][0]
        if out.get("finish_reason")=="length":
            raise ValueError("Original revision truncated; not an accepted retake")
        revised=out["message"].get("content")
        if not isinstance(revised,str) or not revised.strip():
            raise ValueError("No real creative revision from model")
        return revised


def preserve_artistic_revision(original_vision,review_text,review_evidence,
                               brief,artist,out):
    """Review provenance and keep both versions, never falsify media revision."""
    if not isinstance(review_evidence,dict) or not review_evidence.get("frames"):
        raise ValueError("Missing provenance from actual encoded footage")
    if review_evidence.get("human_approval"):
        # Human approval cannot be inferred from unverified imported metadata.
        raise ValueError("This tool never authorizes human approval status")
    reviewer_id=review_evidence.get("reviewer_model_id")
    revision_id=getattr(getattr(artist,"settings",None),"model_id",None)
    if reviewer_id and revision_id and reviewer_id!=revision_id:
        raise ValueError("Different film model attempted creative revision; one creative brain required")
    if not isinstance(original_vision,str) or not original_vision.strip():
        raise ValueError("Original director's vision missing")
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    files={"director-original.txt":original_vision,
           "source-frame-critique.txt":review_text}
    for name,data in files.items():
        if not isinstance(data,str) or not data.strip():
            raise ValueError("Authentic source and review are required")
        (out/name).write_text(data,encoding="utf-8")
    (out/"observed-source.json").write_text(
        json.dumps(review_evidence,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")
    revised=artist.rethink(original_vision,review_text,brief,review_evidence)
    (out/"director-revised.txt").write_text(revised,encoding="utf-8")
    manifest={"original_sha256":hashlib.sha256(
            original_vision.encode("utf-8")).hexdigest(),
        "revised_sha256":hashlib.sha256(revised.encode("utf-8")).hexdigest(),
        "model_id":getattr(getattr(artist,"settings",None),"model_id","injected"),
        "same_actual_model_as_visual_reviewer_verified":bool(reviewer_id and revision_id and reviewer_id==revision_id),
        "real_frame_count":len(review_evidence["frames"]),
        "reference_was_unrelated_technical_clip":bool(review_evidence.get("reference_prototype",False)),
        "revised_new_movie_was_actually_criticized":False,
        "same_original_film_preserved":True,
        "revised_vision_written":True,
        "revised_video_rendered":False,
        "audio_critique_complete":False,
        "independent_human_audience_approval":False}
    (out/"artistic-revision-manifest.json").write_text(json.dumps(
        manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original",type=Path,required=True)
    p.add_argument("--actual-critique",type=Path,required=True)
    p.add_argument("--visual-evidence",type=Path,required=True)
    p.add_argument("--brief",type=Path,required=True)
    p.add_argument("--model",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--api",default="http://127.0.0.1:8085")
    a=p.parse_args()
    m=FilmRevisionBrain(LocalModelSettings(base_url=a.api,model_id=a.model,
                                           timeout_seconds=1800))
    print(json.dumps(preserve_artistic_revision(
        a.original.read_text(encoding="utf-8"),
        a.actual_critique.read_text(encoding="utf-8"),
        json.loads(a.visual_evidence.read_text(encoding="utf-8")),
        json.loads(a.brief.read_text(encoding="utf-8")),m,a.out),
        ensure_ascii=False,indent=2))


if __name__=="__main__":main()

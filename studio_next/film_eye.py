"""Let ONE multimodal film Director actually inspect encoded preview frames.

This adapter does not dictate film style. It gathers factual visual evidence,
passes the original creative intention plus real decoded pixels to the same
locally running director model, and preserves the raw critique verbatim.
Audio must be independently evaluated from a real audio stream: JPEG frames
do NOT license the Director to make claims about music, voice or mixing.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import subprocess
from pathlib import Path
from urllib.request import Request
from .local_model_http import urlopen

from .providers import LocalModelSettings

VISION_REVIEW = """You are the same extraordinary independent filmmaker reviewing
an ACTUAL encoded preview of your intended film. This is not a story pitch.
Treat the attached frames as observed film, not as frames you wish existed.

Look at the actual images. Critique the meaning and force of the composition,
physical shot language, readability, camera perspective and material,
coherent identity and continuity, dynamics of visual storytelling, and what
the human audience would realistically perceive from THIS film idea.
Prioritize scene causality, fresh cinematic images and cohesive design over
generic beautiful effects. Art style is a DIRECTOR choice, not your program's
default. If existing footage fails the artistic goal, identify specifically
what is seen, how it differs from the intention, and the actionable artistic
choice to repair or reshoot while preserving creative ownership.

Explain what you actually see in the numbered frames. State uncertain things
as uncertainty. Do not claim camera movement or duration from one still image,
or claim what soundtrack, dialogue, music, color grade or transitions SOUND
like; no audio data were supplied. A few frames cannot prove the film as
human-approved premium cinema. Return a detailed natural-language artistic
review, with observed evidence and directorial reasons, not code, JSON or
preset effect formulas. No fabricated product attributes or license claims."""


def video_truth(video):
    p=Path(video)
    if not p.is_file():
        raise ValueError("Video file absent")
    raw=subprocess.check_output(
        ["ffprobe","-v","error","-show_entries",
         "format=duration:stream=codec_type,width,height",
         "-of","json",str(p)],timeout=45)
    evidence=json.loads(raw)
    stream=next((s for s in evidence.get("streams",[])
                 if s.get("codec_type")=="video"),None)
    if stream is None:raise ValueError("Not a video stream")
    seconds=float(evidence.get("format",{}).get("duration",0))
    if not math.isfinite(seconds) or seconds<=0:
        raise ValueError("Invalid encoded film time")
    return {"seconds":seconds,"video_width":stream.get("width"),
            "video_height":stream.get("height"),
            "audio_stream_verified":False,
            "source":"ffprobe genuine encoded video"}


def inspectable_frames(video, times, destination):
    """Bounded evidence extraction is a preview procedure, NOT scene planning."""
    metadata=video_truth(video)
    if not isinstance(times,(list,tuple)) or not times:
        raise ValueError("Director or tester must select preview timestamps")
    folder=Path(destination)
    folder.mkdir(parents=True,exist_ok=True)
    files=[]
    for index,stamp in enumerate(times,1):
        if isinstance(stamp,bool) or not isinstance(stamp,(int,float)) or (
            not math.isfinite(stamp) or stamp<0 or stamp>=metadata["seconds"]):
            raise ValueError("Preview time outside genuine film")
        path=folder/f"observed-{index:03d}.jpg"
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
            "-ss",str(stamp),"-i",str(video),"-frames:v","1",
            "-q:v","3",str(path)],check=True,timeout=120)
        if not path.is_file() or path.stat().st_size<100:
            raise RuntimeError("FFmpeg did not decode an actual frame")
        files.append({"timestamp_seconds":float(stamp),"path":str(path),
                      "frame_sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    return metadata,files


REFERENCE_REVIEW = """You are an expert film director examining a SEPARATE
technical video demonstrating the studio's available visual production.
This 4.75-second archived motion-and-3D clip is NOT the film you imagined.
It was produced earlier by a human-coded demo, not by your new original script.

Observe what the provided frames actually show, and decide which demonstrated
rendering techniques, if any, might serve your independently imagined film.
Distinguish facts visible in the reference clip from your desired film scenes.
Never say this old clip is the result of your original screenplay, that its
cuts have been checked against your new film, or that a new film was rendered.
Do not infer recorded voice, background music, character performance or
shot dynamics from individual images. Critique real visual composition and
what future creative capabilities need new footage, materials or tools.
Respond with natural artistic prose, no fabricated evidence or style presets."""


class VisualFilmDirector:
    def __init__(self,settings:LocalModelSettings):
        self.settings=settings

    def evaluate(self, artistic_goal, frame_images, *, reference_prototype=False):
        if not isinstance(artistic_goal,str) or not artistic_goal.strip():
            raise ValueError("Need owner/director artistic intention")
        if not isinstance(frame_images,list) or not frame_images:
            raise ValueError("Need actually decoded movie images")
        content=[{"type":"text","text":"DIRECTOR INTENTION:\n"+artistic_goal+
                  "\nThese are actual decoded preview frames, labeled in order."}]
        for index,frame in enumerate(frame_images,1):
            path=Path(frame["path"])
            raw=path.read_bytes()
            if len(raw)>3_000_000 or len(raw)<100:
                raise ValueError("Preview image is missing or too large")
            if not raw.startswith(b"\xff\xd8\xff"):
                raise ValueError("Preview must be decoded JPEG, not model prose")
            content.append({"type":"text","text":
                f"Real frame {index}, at {frame['timestamp_seconds']:.3f}s; "
                f"sha256={frame['frame_sha256']}"})
            content.append({"type":"image_url","image_url":{
                "url":"data:image/jpeg;base64,"+base64.b64encode(raw).decode("ascii")}})
        payload={"model":self.settings.model_id,"stream":False,
                 "messages":[{"role":"system","content":REFERENCE_REVIEW if reference_prototype else VISION_REVIEW},
                             {"role":"user","content":content}],
                 "temperature":.4,"top_p":.9,"max_tokens":1900}
        request=Request(self.settings.base_url.rstrip("/")+"/v1/chat/completions",
            data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type":"application/json"},method="POST")
        with urlopen(request,timeout=self.settings.timeout_seconds) as response:
            data=response.read(self.settings.max_response_bytes+1)
        if len(data)>self.settings.max_response_bytes:
            raise ValueError("Model vision-review response too large")
        answer=json.loads(data.decode("utf-8"))["choices"][0]
        if answer.get("finish_reason")=="length":
            raise ValueError("Visual review was truncated; cannot approve")
        text=answer["message"].get("content")
        if not isinstance(text,str) or not text.strip():
            raise ValueError("Model did not review actual frames")
        return text


def critique_actual_film(video, goal, stamps, output, director, *, reference_prototype=False):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    facts,frames=inspectable_frames(video,stamps,output/"decoded-frames")
    response=director.evaluate(goal,frames,reference_prototype=reference_prototype)
    (output/"director-observed-critique.txt").write_text(response,encoding="utf-8")
    evidence={"film":str(video),"frames":frames,"ffprobe":facts,
        "reviewer_model_id":getattr(getattr(director,"settings",None),
                                   "model_id",None),
        "reviewer_used_actual_encoded_images":True,
        "reference_prototype":bool(reference_prototype),
        "reviewed_original_new_film":False,
        "film_was_model_authored":False,
        "text_review_obtained":True,"human_approval":False,
        "video_fully_reviewed":False,"audio_reviewed":False,
        "claim":"Real 2D+3D manually authored technical film visually reviewed by VLM; not AI-authored film, audio/longitudinal motion unverified"}
    (output/"visual-critique-evidence.json").write_text(json.dumps(evidence,indent=2)+"\n")
    return evidence


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video",type=Path,required=True)
    p.add_argument("--goal",required=True)
    p.add_argument("--time",type=float,action="append",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--api",default="http://127.0.0.1:8085")
    p.add_argument("--model",required=True)
    p.add_argument("--reference-prototype",action="store_true",
                   help="Older unrelated technical clip, NOT a render of the newly imagined film")
    args=p.parse_args()
    model=VisualFilmDirector(LocalModelSettings(base_url=args.api,model_id=args.model,
        timeout_seconds=1800,max_response_bytes=5000000))
    print(json.dumps(critique_actual_film(args.video,args.goal,args.time,args.out,model,
                                        reference_prototype=args.reference_prototype),indent=2))


if __name__=="__main__":
    main()

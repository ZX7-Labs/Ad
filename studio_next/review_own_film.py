"""One cinematic intelligence reviews frames FROM ITS OWN ACTUAL FILM.

Scene coverage comes from decoded MP4 and actual per-shot durations, not a
preset ad timeline. All scenes are visited, in batches sized for finite model
context. Audio is explicitly NOT reviewed by this JPEG-based interface.
No human-quality approval is inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from .film_eye import VisualFilmDirector,inspectable_frames,video_truth
from .film_revision import FilmRevisionBrain,preserve_artistic_revision
from .providers import LocalModelSettings


def coverage_from_actual_edit(scenes, encoded_duration, *, frames_per_shot=2,
                              model_batch_limit=6):
    """Conservative visual coverage; limits are inference capacity, NOT film art.

    The director's existing cuts dictate scene count, order and duration.
    Even long feature films are split into more batches, not shortened to a
    fixed scene count or time format.
    """
    if not isinstance(scenes,list) or not scenes:
        raise ValueError("Requires actually edited film scenes")
    if isinstance(encoded_duration,bool) or not isinstance(encoded_duration,(int,float)) or (
            not math.isfinite(encoded_duration) or encoded_duration<=0):
        raise ValueError("Missing ffprobe verified film duration")
    if frames_per_shot not in (1,2,3) or model_batch_limit<frames_per_shot:
        raise ValueError("Unsupported resource-bound image sample capacity")
    total=0.0
    points=[]
    known=set()
    for shot in scenes:
        if not isinstance(shot,dict) or not isinstance(shot.get("id"),str) or (
            not shot["id"] or shot["id"] in known):
            raise ValueError("Scene identity missing or duplicated")
        known.add(shot["id"])
        seconds=shot.get("actual_media_seconds")
        if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or (
            not math.isfinite(seconds) or seconds<=0):
            raise ValueError("Shot has no actual rendered media duration")
        for index in range(frames_per_shot):
            # Positions strictly internal to the real shot; not a creative
            # decision about speed, cut count, shot duration or composition.
            relative=(index+1)/(frames_per_shot+1)
            points.append({"scene_id":shot["id"],
                           "shot_relative_position":relative,
                           "source_media_seconds":round(total+relative*seconds,6)})
        total+=seconds
    if abs(total-encoded_duration)>max(.2,encoded_duration*.015):
        raise ValueError("Scene durations differ from actual encoded movie; cannot pretend sampled frames belong to intended cuts")
    scale=encoded_duration/total
    for p in points:
        p["timestamp_seconds"]=min(encoded_duration-0.00001,max(0.,round(
            p["source_media_seconds"]*scale,6)))
    batches=[]
    for i in range(0,len(points),model_batch_limit):
        batches.append(points[i:i+model_batch_limit])
    return {"scene_count":len(scenes),"actual_duration_seconds":encoded_duration,
            "scene_duration_sum_seconds":total,
            "frame_evidence_count":len(points),
            "sample_coverage":"Sparse independently decoded frames, NOT continuous playback",
            "batches":batches}


def examine_own_movie(root,vision_brain,revision_brain,owner_brief):
    """Actual film -> complete scene-coverage plan -> visual critique -> new vision.

    Caller must provide the very same model identity that wrote the original
    film vision; a model cannot falsely claim to critique its own film if it
    actually has a different identity.
    """
    root=Path(root)
    director=root/"director"
    movie=root/"render"/"film.mp4"
    idea=(director/"original-vision"/"director-original.txt").read_text(encoding="utf-8")
    status=json.loads((director/"original-vision"/"director-status.json").read_text())
    original_model=status["model"]
    current_id=vision_brain.settings.model_id
    revision_id=revision_brain.settings.model_id
    if current_id!=original_model or revision_id!=original_model:
        raise ValueError("The reviewing creative brain is not the original film author")
    meta=json.loads((root/"render"/"production-result.json").read_text())
    observed=video_truth(movie)
    coverage=coverage_from_actual_edit(meta["scenes"],observed["seconds"])
    out=root/"actual-film-review"
    out.mkdir(parents=True,exist_ok=True)
    (out/"scene-coverage.json").write_text(json.dumps(coverage,indent=2)+"\n")
    all_frames=[]
    critiques=[]
    for number,batch in enumerate(coverage["batches"],1):
        timestamps=[x["timestamp_seconds"] for x in batch]
        current=out/f"review-batch-{number:03d}"
        _,frames=inspectable_frames(movie,timestamps,current/"real-frames")
        for identity,frame in zip(batch,frames):
            frame["scene_id"]=identity["scene_id"]
        all_frames.extend(frames)
        prompt=(idea+"\nVisual evidence comes from actual film shot IDs: "+
                ", ".join(x["scene_id"] for x in batch)+"\n")
        response=vision_brain.evaluate(prompt,frames)
        (current/"observed-critique.txt").write_text(response,encoding="utf-8")
        (current/"observed-frame-ledger.json").write_text(json.dumps(
            frames,ensure_ascii=False,indent=2)+"\n")
        critiques.append(response)
    review="\n\n".join("REAL VISUAL BATCH "+str(i+1)+":\n"+c
                       for i,c in enumerate(critiques))
    report={"frames":all_frames,"ffprobe":observed,
            "reviewer_model_id":current_id,
            "audio_reviewed":False,"video_fully_reviewed":False,
            "human_approval":False,
            "movie_sha256":hashlib.sha256(movie.read_bytes()).hexdigest(),
            "scene_ids":[s["id"] for s in meta["scenes"]],
            "claim":"Every actual film shot has sparse visual sampling, not full sound/motion evaluation"}
    (out/"visual-critique-evidence.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    (out/"director-observed-critique.txt").write_text(review,encoding="utf-8")
    revised=preserve_artistic_revision(idea,review,report,owner_brief,
                                      revision_brain,out/"artistic-revision")
    return {"actual_encoded_film":str(movie),"scene_coverage":coverage["scene_count"],
            "actual_decoded_frame_samples":len(all_frames),
            "visual_batch_reviews":len(critiques),
            "same_original_model":True,
            "revised_film_created":False,
            "new_film_art_direction_saved":revised["revised_vision_written"],
            "human_approved":False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--film-root",type=Path,required=True)
    p.add_argument("--brief",type=Path,required=True)
    p.add_argument("--model",required=True)
    p.add_argument("--api",default="http://127.0.0.1:8085")
    x=p.parse_args()
    settings=LocalModelSettings(base_url=x.api,model_id=x.model,timeout_seconds=1800)
    result=examine_own_movie(x.film_root,VisualFilmDirector(settings),
        FilmRevisionBrain(settings),
        json.loads(x.brief.read_text(encoding="utf-8")))
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    main()

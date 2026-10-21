"""Execute a completely model-authored, independently validated film production.

Uses existing real Blender, procedural compositor, pinned optional Supertonic,
FFmpeg and one authored edit timeline. No scene templates or model-run shell.
A declared missing capability STOPS output instead of silently lowering quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

from .production_handoff import validate_visual_design, _scenes
from .motion_bridge import compile_motion_project
from .edit_timeline import render_edit, probe_media
from .stage_checkpoint import DurableStageStore, fingerprint

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def _run(args, timeout=3600):
    # All command names and flags below are developer-authored, never model strings.
    subprocess.run([str(x) for x in args],check=True,timeout=timeout)


def verify_rendered_shot_duration(shot, actual_seconds, fps):
    """Prevent silent rhythm changes when the produced clip exceeds its plan.

    This compares the measured decoder result with the *director's own* timing.
    The tolerance is for encoder/frame rounding only. It is not a universal
    restriction on creative shot length or style.
    """
    expected=shot.get("duration_seconds",shot.get("seconds"))
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x)
           or x<=0 for x in (expected,actual_seconds,fps)):
        raise ValueError("Shot timing must be measured, finite and positive")
    allowance=max(.08,2/float(fps))
    if abs(float(actual_seconds)-float(expected))>allowance:
        raise RuntimeError(
            f"Scene {shot.get('id')} decoded to {actual_seconds:.3f}s vs "
            f"{expected:.3f}s approved; preserve original pacing and "
            "repair this specific production shot rather than silently retiming film")
    return {"intended_seconds":float(expected),
            "actual_seconds":float(actual_seconds),
            "within_encoded_frame_tolerance":True}


def validate_delivery(data, treatment):
    if not isinstance(data,dict) or set(data)!={"format","voice","reason"}:
        raise ValueError("Director must explicitly select delivery format and voice")
    fmt=data["format"]
    if not isinstance(fmt,dict) or set(fmt)!={"width","height","fps","framing","background"}:
        raise ValueError("Director did not specify complete delivery")
    for key in ("width","height","fps"):
        if isinstance(fmt[key],bool) or not isinstance(fmt[key],int) or fmt[key]<=0:
            raise ValueError("Invalid delivery "+key)
    if fmt["framing"] not in ("fit","fill") or not re.fullmatch(
        r"#[0-9A-Fa-f]{6}", str(fmt["background"])):
        raise ValueError("Unsupported explicit framing/background")
    if data["voice"] not in ("M3","F2","no_voice"):
        raise ValueError("Voice engine has not been installed/approved")
    if not isinstance(data["reason"],str) or not data["reason"].strip():
        raise ValueError("Output decisions need artistic purpose")
    selected=treatment.get("voice")
    if isinstance(selected,dict) and selected.get("choice") in ("M3","F2","no_voice"):
        if data["voice"] != selected["choice"]:
            raise ValueError("Delivery cannot silently change director-selected voice")
    if data["voice"]=="no_voice":
        if any(s.get("narration","").strip() for s in _scenes(treatment)):
            raise ValueError("Cannot discard narrated scenes to avoid voice synthesis")
    return data


def _tts_for_single(shot,voice,shot_dir,assets):
    if voice not in ("M3","F2") or assets is None or not assets.is_dir():
        raise ValueError("Approved M3/F2 voice runtime/assets must actually be installed")
    text=shot.get("narration","")
    if not isinstance(text,str) or not text.strip():
        return None
    project=shot_dir/"voice-project.json"
    project.write_text(json.dumps({"voice":voice,
        "scenes":[{"id":shot["id"],"narration":text}]},ensure_ascii=False))
    _run(["python","-m","motion_studio.voice","--project",project,
          "--out",shot_dir/"speech","--model-dir",assets],timeout=1200)
    return shot_dir/"speech"/"voice-01.wav"



def _visual_renderer_revision():
    """Any changed physical renderer invalidates saved visual clips, not the art."""
    root=Path(__file__).resolve().parent
    sources=(root/"execute_film.py",root/"blender_scene.py",
             root/"edit_timeline.py",root.parent/"motion_studio"/"render.py",
             root.parent/"motion_studio"/"voice.py")
    hashed=hashlib.sha256()
    for path in sources:
        hashed.update(path.name.encode("utf-8"))
        hashed.update(path.read_bytes())
    return hashed.hexdigest()


def _scene_clip_signature(shot,design,delivery,owner_facts,backend_revision):
    return {"director_selected_shot":shot,"specific_real_tool_job":design,
            "delivery":delivery,"owner_facts":owner_facts,
            "installed_renderer_code_revision":backend_revision}


def _resume_verified_visual(checkpoints, stage_id, signature, scene_dir, *, probe=probe_media):
    """Only reuse the exact filmed and decoder-validated existing scene."""
    saved=checkpoints.find(stage_id,signature)
    if saved is None:
        return None
    if not isinstance(saved,dict) or not isinstance(saved.get("clip"),str):
        raise ValueError("Saved scene checkpoint missing real clip locator")
    rel=Path(saved["clip"])
    if rel.is_absolute() or not rel.parts or any(x in (".","..") for x in rel.parts):
        raise ValueError("Untrusted media checkpoint path")
    file=(scene_dir/rel).resolve()
    if not file.is_relative_to(scene_dir.resolve()) or not file.is_file():
        return None
    with file.open("rb") as f:
        sha=hashlib.file_digest(f,"sha256").hexdigest()
    if sha!=saved.get("clip_sha256"):
        raise ValueError("Previously generated movie bytes changed; do not silently reuse")
    measured=probe(file)
    if abs(measured["seconds"]-saved.get("seconds",0))>.05 or (
            bool(measured.get("audio"))!=bool(saved.get("audio"))):
        raise ValueError("Cached movie does not match physical encoder evidence")
    return {"clip":file,"voice_status":saved["voice_status"],
            "seconds":measured["seconds"],"audio":measured["audio"]}


def _persist_verified_visual(checkpoints,stage_id,signature,scene_dir,clip,media,voice_status):
    clip=Path(clip)
    if not clip.resolve().is_relative_to(scene_dir.resolve()):
        raise ValueError("Cannot checkpoint visual outside its original scene directory")
    with clip.open("rb") as f:
        digest=hashlib.file_digest(f,"sha256").hexdigest()
    return checkpoints.save(stage_id,signature,{
        "clip":str(clip.relative_to(scene_dir)),
        "clip_sha256":digest,"seconds":media["seconds"],
        "audio":bool(media["audio"]),"voice_status":voice_status})


def render_approved_designs(treatment, fact_ledger, designs_dir, delivery,
                            output_dir, *, voice_assets=None):
    """Produce a genuine editable multi-engine output or a precise failure.

    A completed run proves actual playable files, not human creative approval.
    A partially missing visual or sound resource is never represented as done.
    """
    shots=_scenes(treatment)
    validate_delivery(delivery,treatment)
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    designs_dir=Path(designs_dir)
    assets=Path(voice_assets).resolve() if voice_assets else None
    edits=[]
    results=[]
    checkpoints=DurableStageStore(output_dir/"verified-rendered-scenes")
    renderer_revision=_visual_renderer_revision()
    for n,shot in enumerate(shots,1):
        sid=shot["id"]
        if not _SAFE_NAME.fullmatch(sid) or sid in (".",".."):
            raise ValueError("Unsafe scene ID")
        original=json.loads((designs_dir/f"design-{n:03d}.json").read_text())
        if original.get("scene_id")!=sid:
            raise ValueError("Misordered/changed film shot")
        design=original["model_response"]
        verification=validate_visual_design(shot,design,fact_ledger)
        if not verification["executable"]:
            raise ValueError(f"Unresolved shot {sid}: {verification['reason']}")
        shot_dir=output_dir/f"scene-{n:03d}-{sid}"
        shot_dir.mkdir(parents=True,exist_ok=True)
        narration=shot.get("narration","")
        if narration and delivery["voice"]=="no_voice":
            raise ValueError("Cannot silently discard spoken narration")
        signature=_scene_clip_signature(shot,design,delivery,fact_ledger,
                                         renderer_revision)
        cached=_resume_verified_visual(checkpoints,f"scene_{n:03d}",
                                        signature,shot_dir)
        if cached is not None:
            clip=cached["clip"]
            voice_status=cached["voice_status"]
        else:
            if verification["engine"]=="motion2d":
                project=verification["project"]
                if project["voice"]!=delivery["voice"]:
                    raise ValueError("Shot cannot override approved voice identity")
                path=shot_dir/"scene-project.json"
                path.write_text(json.dumps(project,ensure_ascii=False,indent=2))
                if delivery["voice"]=="no_voice":
                    _run(["python","-m","studio_next.silent_audio",
                          "--project",path,"--out",shot_dir])
                else:
                    if assets is None or not assets.is_dir():
                        raise ValueError("M3/F2 voice assets required")
                    _run(["python","-m","motion_studio.voice","--project",path,
                          "--out",shot_dir,"--model-dir",assets],timeout=1200)
                _run(["python","-m","motion_studio.render","--project",path,
                      "--out",shot_dir,"--width",str(delivery["format"]["width"]),
                      "--fps",str(delivery["format"]["fps"])],timeout=3600)
                clip=shot_dir/"sample.mp4"
                voice_status="embedded_or_declared_silence"
            elif verification["engine"]=="blender3d":
                job=design["scene_job"]
                scene_file=shot_dir/"scene.json"
                scene_file.write_text(json.dumps(job,ensure_ascii=False,indent=2))
                frames=shot_dir/"frames"
                frames.mkdir(exist_ok=True)
                _run(["blender","--background","--factory-startup","--python-exit-code",
                      "1","--python","studio_next/blender_scene.py","--",
                      "--scene",scene_file,"--out",frames],timeout=3600)
                output_frames=list(frames.glob("frame_*.png"))
                if len(output_frames)!=job["frames"]:
                    raise RuntimeError("3D renderer did not produce every intended frame")
                visual=shot_dir/"scene-visual.mp4"
                _run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                      "-framerate",str(job["fps"]),"-start_number","1",
                      "-i",frames/"frame_%04d.png",
                      "-c:v","libx264","-crf","18","-pix_fmt","yuv420p",
                      "-movflags","+faststart",visual],timeout=1200)
                clip=visual
                voice_status="intentional_silence"
                if narration:
                    audio=_tts_for_single(shot,delivery["voice"],shot_dir,assets)
                    duration=probe_media(visual)["seconds"]
                    sound=json.loads(subprocess.check_output(["ffprobe","-v","error",
                        "-show_entries","format=duration","-of","json",str(audio)]))
                    vocal_seconds=float(sound["format"]["duration"])
                    if vocal_seconds>duration-0.05:
                        raise RuntimeError("Director's spoken text exceeds shot time; "
                                           "must revise timings rather than cut speech")
                    clip=shot_dir/"scene-with-voice.mp4"
                    _run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                          "-i",visual,"-i",audio,
                          "-map","0:v:0","-map","1:a:0",
                          "-c:v","copy","-af",f"apad,atrim=duration={duration:.6f}",
                          "-c:a","aac","-movflags","+faststart","-t",str(duration),clip])
                    voice_status="M3_F2_recorded"
            else:
                raise ValueError("Unsupported registered production engine")
        media=probe_media(clip)
        timing_proof=verify_rendered_shot_duration(shot,media["seconds"],
                                                 delivery["format"]["fps"])
        if cached is None:
            _persist_verified_visual(checkpoints,f"scene_{n:03d}",signature,
                                     shot_dir,clip,media,voice_status)
        if verification["engine"]=="motion2d" or narration:
            if not media["audio"]:
                raise RuntimeError("Narrated/sound-designed scene has no audio stream")
        edits.append({"id":sid,"source":str(clip.relative_to(output_dir)),
                      "rights":"generated_original",
                      "audio":"preserve_source" if media["audio"] else "intentional_silence"})
        results.append({"id":sid,"engine":verification["engine"],
                        "actual_media_seconds":media["seconds"],
                        "timing_evidence":timing_proof,
                        "narration_status":voice_status})
        (output_dir/"partial-progress.json").write_text(
            json.dumps(results,indent=2),encoding="utf-8")
    cut={"format":delivery["format"],"clips":edits}
    cut_path=output_dir/"edit.json"
    cut_path.write_text(json.dumps(cut,indent=2),encoding="utf-8")
    target=output_dir/"film.mp4"
    final=render_edit(cut_path,output_dir,target)
    record={"final":final,"scenes":results,
            "story_title":treatment.get("title",treatment.get("film_title")),
            "status":"actual_multi_engine_video_not_human_quality_approval"}
    (output_dir/"production-result.json").write_text(
        json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    return record


def verified_render_fact_ledger(treatment_file, owner_brief_file=None):
    """Carry the same owner's evidence through planning and media execution.

    Bare model-authored treatments intentionally contain no owner secrets or
    duplicate facts, so a separate authoritative source is required whenever
    the original film cites owner facts. The model cannot rewrite that source.
    """
    treatment_file=Path(treatment_file)
    src=json.loads(treatment_file.read_text(encoding="utf-8"))
    if not isinstance(src,dict):
        raise ValueError("Film treatment must be an object")
    treatment=src.get("treatment",src)
    if not isinstance(treatment,dict):
        raise ValueError("Film treatment is missing")
    existing=src.get("brief",{}).get("facts",{})
    if not isinstance(existing,dict):
        raise ValueError("Embedded owner evidence malformed")
    if owner_brief_file is None:
        original_source=treatment_file.parent/"owner-factual-brief.json"
        if original_source.is_file():
            owner_brief_file=original_source
    if owner_brief_file is not None:
        raw=json.loads(Path(owner_brief_file).read_text(encoding="utf-8"))
        if not isinstance(raw,dict) or not isinstance(raw.get("facts"),dict):
            raise ValueError("Original owner evidence file missing facts ledger")
        facts=raw["facts"]
        if existing and facts!=existing:
            raise ValueError("Model's embedded facts disagree with actual owner source")
    else:
        facts=existing
    for key,value in facts.items():
        if not isinstance(key,str) or not isinstance(value,str):
            raise ValueError("Authoritative factual evidence must have string entries")
    for shot in _scenes(treatment):
        refs=shot.get("fact_refs",shot.get("factual_basis",[]))
        if not isinstance(refs,list) or any(not isinstance(x,str) or x not in facts for x in refs):
            raise ValueError("Shot has no verifiable owner source for its factual citations")
    return treatment,facts


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--treatment",type=Path,required=True)
    p.add_argument("--designs",type=Path,required=True)
    p.add_argument("--delivery",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--voice-assets",type=Path)
    p.add_argument("--owner-brief",type=Path,
                   help="Unmodified original owner brief used by the same film director")
    a=p.parse_args()
    treatment,facts=verified_render_fact_ledger(a.treatment,a.owner_brief)
    delivery=json.loads(a.delivery.read_text())
    print(json.dumps(render_approved_designs(treatment,facts,a.designs,delivery,
           a.out,voice_assets=a.voice_assets),indent=2))


if __name__=="__main__":
    main()

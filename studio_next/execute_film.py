"""Execute a completely model-authored, independently validated film production.

Uses existing real Blender, procedural compositor, pinned optional Supertonic,
FFmpeg and one authored edit timeline. No scene templates or model-run shell.
A declared missing capability STOPS output instead of silently lowering quality.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from .production_handoff import validate_visual_design, _scenes
from .motion_bridge import compile_motion_project
from .edit_timeline import render_edit, probe_media

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def _run(args, timeout=3600):
    # All command names and flags below are developer-authored, never model strings.
    subprocess.run([str(x) for x in args],check=True,timeout=timeout)


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
        if verification["engine"]=="motion2d" or narration:
            if not media["audio"]:
                raise RuntimeError("Narrated/sound-designed scene has no audio stream")
        edits.append({"id":sid,"source":str(clip.relative_to(output_dir)),
                      "rights":"generated_original",
                      "audio":"preserve_source" if media["audio"] else "intentional_silence"})
        results.append({"id":sid,"engine":verification["engine"],
                        "actual_media_seconds":media["seconds"],
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


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--treatment",type=Path,required=True)
    p.add_argument("--designs",type=Path,required=True)
    p.add_argument("--delivery",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--voice-assets",type=Path)
    a=p.parse_args()
    src=json.loads(a.treatment.read_text())
    treatment=src.get("treatment",src)
    facts=src.get("brief",{}).get("facts",{})
    delivery=json.loads(a.delivery.read_text())
    print(json.dumps(render_approved_designs(treatment,facts,a.designs,delivery,
           a.out,voice_assets=a.voice_assets),indent=2))


if __name__=="__main__":
    main()

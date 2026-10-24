"""Native trusted studio creative render tools for arbitrary director-authored art.

Connect existing REAL headless Blender 3D and 2D compositing/voice engines to
the dynamic tool DAG. The source scene JSON and scene count come from the artist,
not style templates or effects chosen here. Any unsupported artistic requirement
must stay unresolved rather than being replaced by moving-card footage.
"""
from __future__ import annotations

from .voice_contract import valid_voice_id, validate_voice_settings

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .blender_scene import validate_blender_shot
from .motion_bridge import compile_motion_project


def render_original_blender(scene_file,video_target,*,trusted_asset_root=None,
                            runner=None,probe=None):
    if not shutil.which("blender") or not shutil.which("ffmpeg"):
        raise RuntimeError("Real Blender 3D + FFmpeg required on executing body machine")
    scene_file=Path(scene_file)
    job=json.loads(scene_file.read_text(encoding="utf-8"))
    validate_blender_shot(job,verified_assets_root=trusted_asset_root)
    destination=Path(video_target)
    if destination.exists() or destination.suffix.lower()!=".mp4":
        raise ValueError("Only a new real 3D MP4 may be produced")
    destination.parent.mkdir(parents=True,exist_ok=True)
    run=runner or subprocess.run
    with tempfile.TemporaryDirectory(prefix="zx7-original-blender-") as temp:
        frame_root=Path(temp)/"frames"
        frame_root.mkdir()
        cmd=["blender","--background","--factory-startup","--python-exit-code","1",
           "--python",str(Path(__file__).parent/"blender_scene.py"),"--",
           "--scene",str(scene_file),"--out",str(frame_root)]
        if trusted_asset_root is not None:
            cmd+=["--assets-root",str(Path(trusted_asset_root).resolve())]
        run(cmd,check=True,timeout=3600)
        image_files=list(frame_root.glob("frame_*.png"))
        if len(image_files)!=job["frames"]:
            raise RuntimeError("Blender did not actually encode the artist-approved frame count")
        run(["ffmpeg","-hide_banner","-loglevel","error","-n",
            "-framerate",str(job["fps"]),"-start_number","1",
            "-i",str(frame_root/"frame_%04d.png"),
            "-c:v","libx264","-crf","18","-pix_fmt","yuv420p",
            "-movflags","+faststart",str(destination)],
            check=True,timeout=3600)
    if probe is None:
        from .edit_timeline import probe_media
        probe=probe_media
    media=probe(destination)
    if abs(media["seconds"]-job["frames"]/job["fps"])>2/job["fps"]:
        raise RuntimeError("Actual Blender film time violates filmmaker-selected frames")
    return {"created_original_3d_video":True,"movie":str(destination),
            "actual_seconds":media["seconds"],"shot_id":job["shot_id"],
            "director_approved_frames":job["frames"],
            "filmic_quality_reviewed":False}


def render_original_motion(ir_file,video_target,*,width,fps,trusted_voice_assets=None,
                           runner=None,probe=None):
    if not shutil.which("ffmpeg"):
        raise RuntimeError("Real FFmpeg and locally verified animation stack required")
    if any(isinstance(x,bool) or not isinstance(x,int) or x<=0 for x in (width,fps)):
        raise ValueError("The film director must explicitly choose motion resolution and frame rate")
    raw=json.loads(Path(ir_file).read_text(encoding="utf-8"))
    facts=frozenset(raw.get("owner_facts",{}))
    original=compile_motion_project(raw,fact_ids=facts)
    voice=original.get("voice")
    if not valid_voice_id(voice):
        raise ValueError("Director-selected motion voice is not installed")
    movie=Path(video_target)
    if movie.exists() or movie.suffix.lower()!=".mp4":
        raise ValueError("Never overwrite earlier independent video")
    movie.parent.mkdir(parents=True,exist_ok=True)
    run=runner or subprocess.run
    with tempfile.TemporaryDirectory(prefix="zx7-original-motion-") as tmp:
        root=Path(tmp)
        project=root/"project.json"
        project.write_text(json.dumps(original,ensure_ascii=False,indent=2))
        if not any(scene["narration"].strip() for scene in original["scenes"]):
            run([sys.executable,"-m","studio_next.silent_audio","--project",str(project),
                 "--out",str(root)],check=True,timeout=120)
        else:
            if trusted_voice_assets is None or not Path(trusted_voice_assets).is_dir():
                raise ValueError("Only actually installed selected voice assets may speak")
            run([sys.executable,"-m","motion_studio.voice","--project",str(project),
                 "--out",str(root),"--model-dir",str(trusted_voice_assets)],
                check=True,timeout=1200)
        run([sys.executable,"-m","motion_studio.render",
             "--project",str(project),"--out",str(root),
             "--width",str(width),
             "--fps",str(fps)],check=True,timeout=3600)
        produced=root/"sample.mp4"
        if not produced.is_file() or produced.stat().st_size<1000:
            raise RuntimeError("Model-authored vector compositor generated no actual film")
        shutil.copyfile(produced,movie)
    if probe is None:
        from .edit_timeline import probe_media
        probe=probe_media
    meta=probe(movie)
    if not meta["audio"]:
        raise RuntimeError("Renderer lost the independently selected voice or silence audio stream")
    return {"created_original_motion_video":True,"movie":str(movie),
            "actual_seconds":meta["seconds"],
            "original_scene_count":len(original["scenes"]),
            "creative_quality_approved":False}

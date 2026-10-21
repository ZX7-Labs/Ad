"""Editable, measured original-picture finishing and audio loudness operations.

One creative intelligence chooses EVERY edit and numeric adjustment. There
are no default visual grades, branded looks or automatic stock transitions.
Trusted FFmpeg generates a real new MP4; the source is licensed MediaVault
bytes and will never be silently replaced or overwritten.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path

from .media_vault import MediaVault,sha256_file
from .delivery_audit import _probe_details
from .composite_mix import _exact_media


def _float(value,kind,minimum,maximum):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or (
            not math.isfinite(value) or value<minimum or value>maximum):
        raise ValueError("Director's "+kind+" is not an executable numerical value")
    return float(value)


def build_finishing_filters(plan,*,has_audio):
    """Tool syntax only. No untrusted executable FFmpeg expressions."""
    if not isinstance(plan,dict) or set(plan)!={"video_ops","audio_ops"}:
        raise ValueError("Creative finisher requires explicitly chosen video/audio operations")
    video=plan["video_ops"];audio=plan["audio_ops"]
    if not isinstance(video,list) or not isinstance(audio,list):
        raise ValueError("Creative operations must be ordered arrays")
    if audio and not has_audio:
        raise ValueError("Cannot create spoken/sound-designed audio from silent film")
    v=[]
    a=[]
    for item in video:
        if not isinstance(item,dict):
            raise ValueError("Invalid visual finishing operation")
        kind=item.get("kind")
        if kind=="color_eq" and set(item)=={
                "kind","brightness","contrast","saturation","gamma"}:
            b=_float(item["brightness"],"brightness",-1,1)
            c=_float(item["contrast"],"contrast",0,3)
            s=_float(item["saturation"],"saturation",0,5)
            g=_float(item["gamma"],"gamma",.1,10)
            v.append(f"eq=brightness={b}:contrast={c}:saturation={s}:gamma={g}")
        elif kind=="denoise" and set(item)=={"kind","luma_spatial","luma_temporal"}:
            spatial=_float(item["luma_spatial"],"luma_spatial",0,20)
            temporal=_float(item["luma_temporal"],"luma_temporal",0,20)
            v.append(f"hqdn3d=luma_spatial={spatial}:luma_tmp={temporal}")
        elif kind=="sharpen" and set(item)=={"kind","strength"}:
            amount=_float(item["strength"],"sharpen_strength",-2,5)
            v.append(f"unsharp=5:5:{amount}:5:5:{amount}")
        else:
            raise ValueError("Unregistered original film finishing operation")
    for item in audio:
        if not isinstance(item,dict):
            raise ValueError("Invalid sound finishing operation")
        kind=item.get("kind")
        if kind=="gain" and set(item)=={"kind","db"}:
            amount=_float(item["db"],"audio_gain_db",-60,30)
            a.append(f"volume={amount}dB")
        elif kind=="loudnorm" and set(item)=={"kind","integrated_lufs","true_peak_dbfs","loudness_range"}:
            target=_float(item["integrated_lufs"],"lufs",-70,-5)
            peak=_float(item["true_peak_dbfs"],"true_peak",-9,0)
            loud_range=_float(item["loudness_range"],"dynamic_range",1,30)
            a.append(f"loudnorm=I={target}:TP={peak}:LRA={loud_range}")
        else:
            raise ValueError("Unregistered original sound finishing operation")
    return v,a


def finish_authorized_movie(spec_file,workspace,vault_root,output,*,runner=None,probe=None):
    """Write original master atomically; demonstrate actual media separately."""
    source=json.loads(Path(spec_file).read_text(encoding="utf-8"))
    if not isinstance(source,dict) or set(source)!={"media","ops"}:
        raise ValueError("Director's chosen master footage and finishing ops required")
    vault=MediaVault(vault_root)
    root=Path(workspace).resolve()
    media=source["media"]
    if not isinstance(media,dict) or set(media)!={"source","asset_id","attestation_id"}:
        raise ValueError("No authenticated original movie asset")
    input_file=_exact_media(media,vault,root,need="video")
    details=(probe or _probe_details)(input_file)
    filters,audio=build_finishing_filters(source["ops"],
                                         has_audio=details["audio_stream_present"])
    # Zero finishing operations are a legitimate artistic decision: the
    # original edit is preserved verbatim rather than needlessly re-encoding.
    dest=Path(output).resolve()
    if dest.exists() or dest.suffix.lower()!=".mp4":
        raise ValueError("Original accepted movie cannot be overwritten")
    if not filters and not audio:
        raise ValueError("No finishing chosen; keep the original master without a duplicate")
    dest.parent.mkdir(parents=True,exist_ok=True)
    temporary=dest.with_name(dest.stem+".uncommitted.mp4")
    if temporary.exists():
        raise FileExistsError("Unreconciled encoder output must be inspected before retry")
    command=["ffmpeg","-hide_banner","-loglevel","error","-nostdin",
             "-n","-i",str(input_file)]
    if filters:
        command+=["-vf",",".join(filters)]
    if audio:
        command+=["-af",",".join(audio)]
    command+=["-map","0:v:0"]
    if details["audio_stream_present"]:
        command+=["-map","0:a:0","-c:a","aac","-b:a","192k"]
    else:
        command+=["-an"]
    command+=["-c:v","libx264","-crf","17","-pix_fmt","yuv420p",
              "-movflags","+faststart",str(temporary)]
    try:
        (runner or subprocess.run)(command,check=True,timeout=3600)
        if not temporary.is_file() or temporary.stat().st_size<100:
            raise RuntimeError("Physical film master absent after finishing")
        rendered=(probe or _probe_details)(temporary)
        if (rendered["width"],rendered["height"])!=(
                 details["width"],details["height"]) or (
                 abs(rendered["duration_seconds"]-details["duration_seconds"])>
                    .13) or (
                 rendered["audio_stream_present"]!=details["audio_stream_present"]):
            raise RuntimeError("Real film quality pass silently changed original picture duration, size or soundtrack")
        os.replace(temporary,dest)
        return {"path":str(dest),"sha256":sha256_file(dest),
                "bytes":dest.stat().st_size,
                "duration_seconds":rendered["duration_seconds"],
                "width":rendered["width"],"height":rendered["height"],
                "audio_present":rendered["audio_stream_present"],
                "video_operations":len(filters),"audio_operations":len(audio),
                "actual_encoded_movie_created":True,
                "human_visual_quality_certified":False,
                "human_listening_approved":False}
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

"""Rights-verified independent multi-layer editing, grading and audio mix.

The creative intelligence chooses ALL track positions, clip trims, opacity,
crop/frame dimensions, duration, frame rate, audio gains and color values.
FFmpeg is a trusted technical executor, not a style or editing template.

Source video and sound must have *separately attested real bytes* in MediaVault.
No arbitrary FFmpeg expressions, shell snippets, unverified URL downloads,
brand/font presets, forced scene counts or genre-based edits.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
from pathlib import Path

from .media_vault import MediaVault,sha256_file,MediaCustodyError
from .delivery_audit import _probe_details

_COLOR=re.compile(r"^#[a-fA-F0-9]{6}$")
_ID=re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")


def _positive(value,label,*,allow_zero=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("Nonfinite "+label)
    if value<0 or (not allow_zero and value==0):
        raise ValueError("Invalid "+label)
    return float(value)


def _int(value,label):
    if isinstance(value,bool) or not isinstance(value,int) or value<=0:
        raise ValueError("Invalid "+label)
    return value


def _exact_media(layer,vault,root,*,need):
    if not isinstance(layer,dict) or not isinstance(layer.get("source"),str):
        raise ValueError("Real "+need+" media must be specified")
    path=Path(layer["source"])
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("Creative tool cannot escape the verified production workspace")
    file=(root/path).resolve()
    if not file.is_relative_to(root.resolve()) or not file.is_file():
        raise ValueError("Physically missing original media")
    asset=layer.get("asset_id")
    attestation=layer.get("attestation_id")
    if not isinstance(asset,str) or not isinstance(attestation,str):
        raise ValueError("Original footage/audio requires an exact rights attestation")
    record=vault.inspect(asset,attestation_id=attestation)
    if sha256_file(file)!=asset:
        raise ValueError("Source bytes differ from original verified licensed asset")
    if not record["rights_attestations"]:
        raise ValueError("Rights proof missing")
    return file


def validate_composition(plan,workspace,vault):
    if not isinstance(plan,dict) or set(plan)!={"canvas","video_layers","audio_tracks"}:
        raise ValueError("An actual editor-authored canvas and tracks required")
    canvas=plan["canvas"]
    if not isinstance(canvas,dict) or set(canvas)!={"width","height","fps","duration","background"}:
        raise ValueError("Editor must specify all physical delivery parameters")
    for field in ("width","height","fps"):
        _int(canvas[field],field)
    seconds=_positive(canvas["duration"],"composition duration")
    if not isinstance(canvas["background"],str) or not _COLOR.fullmatch(canvas["background"]):
        raise ValueError("Editor must specify a valid authored color")
    video=plan["video_layers"]
    audio=plan["audio_tracks"]
    if not isinstance(video,list) or not isinstance(audio,list) or not (video or audio):
        raise ValueError("No verified creative media tracks")
    root=Path(workspace).resolve()
    seen=set()
    inputs=[]
    for kind,items in (("video",video),("audio",audio)):
        for layer in items:
            if not isinstance(layer,dict) or set(layer)!=(
                    {"id","source","asset_id","attestation_id",
                     "start","source_in","duration","x","y","width","height","opacity"}
                    if kind=="video" else
                    {"id","source","asset_id","attestation_id","start","source_in","duration","gain_db"}):
                raise ValueError("Director-specified "+kind+" layer is incomplete")
            identifier=layer["id"]
            if not isinstance(identifier,str) or not _ID.fullmatch(identifier) or identifier in seen:
                raise ValueError("Unsafe/duplicate audiovisual layer identifier")
            seen.add(identifier)
            start=_positive(layer["start"],"position",allow_zero=True)
            source_in=_positive(layer["source_in"],"source trim",allow_zero=True)
            duration=_positive(layer["duration"],"original layer duration")
            if start+duration>seconds+1/canvas["fps"]:
                raise ValueError("Layer exceeds editor-authored total duration")
            file=_exact_media(layer,vault,root,need=kind)
            for field in ("width","height"):
                if kind=="video":_int(layer[field],field)
            if kind=="video":
                for key in ("x","y"):
                    if isinstance(layer[key],bool) or not isinstance(layer[key],int):
                        raise ValueError("Creative layer position must be exact integer pixels")
                a=_positive(layer["opacity"],"opacity",allow_zero=True)
                if a>1:raise ValueError("Alpha beyond physical range")
            else:
                gain=layer["gain_db"]
                if isinstance(gain,bool) or not isinstance(gain,(int,float)) or (
                        not math.isfinite(gain) or abs(gain)>120):
                    raise ValueError("Unsafe audio gain")
            inputs.append({"kind":kind,"layer":layer,"file":file,
                           "start":start,"source_in":source_in,"duration":duration})
    return inputs


def actual_composite_command(plan,workspace,vault,out):
    inputs=validate_composition(plan,workspace,vault)
    c=plan["canvas"]
    w,h,fps,secs=c["width"],c["height"],c["fps"],c["duration"]
    filters=[f"color=c=0x{c['background'][1:]}:s={w}x{h}:r={fps}:d={secs},format=rgba[bg]"]
    base="bg"
    args=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y"]
    music=[]
    for index,row in enumerate(inputs):
        args.extend(["-i",str(row["file"])])
        layer=row["layer"]
        start=row["start"];source_in=row["source_in"];duration=row["duration"]
        if row["kind"]=="video":
            filters.append(
                f"[{index}:v:0]trim=start={source_in}:duration={duration},"
                f"setpts=PTS-STARTPTS,scale={layer['width']}:{layer['height']}:flags=lanczos,"
                f"fps={fps},format=rgba,colorchannelmixer=aa={layer['opacity']},"
                f"setpts=PTS+{start}/TB[v{index}]")
            output=f"stack{index}"
            filters.append(
                f"[{base}][v{index}]overlay=x={layer['x']}:y={layer['y']}:"
                f"eof_action=pass:shortest=0:"
                f"enable='between(t,{start},{start+duration})':format=auto[{output}]")
            base=output
        else:
            lag=round(start*1000)
            filters.append(
                f"[{index}:a:0]atrim=start={source_in}:duration={duration},"
                "asetpts=PTS-STARTPTS,aresample=48000,"
                f"aformat=channel_layouts=stereo,volume={layer['gain_db']}dB,"
                f"adelay={lag}|{lag},apad,atrim=duration={secs}[audio{index}]")
            music.append(f"[audio{index}]")
    filters.append(f"[{base}]format=yuv420p[vout]")
    if music:
        if len(music)==1:
            filters.append(f"{music[0]}anull[aout]")
        else:
            filters.append("".join(music)+f"amix=inputs={len(music)}:"
                           "duration=longest:normalize=0[aout]")
    else:
        filters.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={secs}[aout]")
    args+=["-filter_complex",";".join(filters),"-map","[vout]","-map","[aout]",
           "-c:v","libx264","-pix_fmt","yuv420p","-crf","18",
           "-c:a","aac","-b:a","192k","-r",str(fps),
           "-t",str(secs),"-movflags","+faststart",str(out)]
    return args


def render_composition(plan_json,workspace,vault_root,out,*,runner=None,probe=None):
    root=Path(workspace).resolve()
    source=Path(plan_json)
    plan=json.loads(source.read_text(encoding="utf-8"))
    vault=MediaVault(vault_root)
    output=Path(out).resolve()
    if output.suffix.lower()!=".mp4" or output.exists():
        raise ValueError("Cannot overwrite previously accepted original movie")
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_name(output.stem+".incomplete.mp4")
    if temporary.exists():
        raise FileExistsError("Unreconciled original editor output exists")
    cmd=actual_composite_command(plan,root,vault,temporary)
    try:
        (runner or subprocess.run)(cmd,check=True,timeout=3600)
        if not temporary.is_file() or temporary.stat().st_size<100:
            raise RuntimeError("FFmpeg did not generate real audiovisual media")
        detail=(probe or _probe_details)(temporary)
        expected=plan["canvas"]
        if detail["width"]!=expected["width"] or detail["height"]!=expected["height"] or (
                abs(detail["duration_seconds"]-expected["duration"])>
                max(.12,2/expected["fps"])) or not detail["audio_stream_present"]:
            raise RuntimeError("Physical composited movie disagrees with original editorial dimensions/timing/audio")
        os.replace(temporary,output)
        return {"path":str(output),"sha256":sha256_file(output),
                "bytes":output.stat().st_size,"duration_seconds":detail["duration_seconds"],
                "video_layers":len(plan["video_layers"]),
                "audio_tracks":len(plan["audio_tracks"]),"audio_present":True,
                "verified_physically":True,"human_artistic_approval":False}
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

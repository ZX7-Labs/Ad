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
    asset=layer.get("asset_id")
    attestation=layer.get("attestation_id")
    if not isinstance(asset,str) or not isinstance(attestation,str):
        raise ValueError("Original footage/audio requires an exact rights attestation")
    record=vault.inspect(asset,attestation_id=attestation)
    if not record["rights_attestations"]:
        raise ValueError("Rights proof missing")
    # Machine-neutral source identity. Rendering still uses ONLY a physically
    # verified immutable blob, not an external URL or hallucinated file path.
    # Legacy director-chosen workspace paths remain supported unchanged.
    if layer["source"].startswith("zx7:sha256:"):
        if layer["source"] != "zx7:sha256:"+asset:
            raise ValueError("Original media identity URI differs from verified asset")
        file=Path(record["path"]).resolve()
        if not file.is_relative_to(root.resolve()):
            raise ValueError("Verified media is outside the protected production workspace")
    else:
        path=Path(layer["source"])
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise ValueError("Creative tool cannot escape the verified production workspace")
        file=(root/path).resolve()
        if not file.is_relative_to(root.resolve()) or not file.is_file():
            raise ValueError("Physically missing original media")
    if sha256_file(file)!=asset:
        raise ValueError("Source bytes differ from original verified licensed asset")
    return file


def _motion_expression(layer,axis):
    """Author-specified real 2D keyframe interpolation, no camera-style preset."""
    marks=layer.get("motion",[])
    if not marks:
        return str(layer[axis])
    start=float(layer["start"])
    expr=str(marks[-1][axis])
    for a,b in reversed(list(zip(marks,marks[1:]))):
        start_at=start+float(a["at_seconds"])
        end_at=start+float(b["at_seconds"])
        step=float(b["at_seconds"])-float(a["at_seconds"])
        change=b[axis]-a[axis]
        expr=(f"if(lt(t,{end_at:.8f}),"
              f"{a[axis]}+({change})*(t-{start_at:.8f})/{step:.8f},"
              f"{expr})")
    before=start+float(marks[0]["at_seconds"])
    return f"if(lt(t,{before:.8f}),{marks[0][axis]},{expr})"


def _gain_automation_expression(layer):
    """Dynamically interpolate author gain points; measured at FFmpeg AUDIO FRAME boundaries.

    This is not PCM-sample-accurate automation.
    """
    points=layer.get("gain_keyframes")
    if not points:
        return None
    def amp(point):
        return 10**(float(point["gain_db"])/20)
    expr=format(amp(points[-1]),".12g")
    for earlier,later in reversed(list(zip(points,points[1:]))):
        a=float(earlier["at_seconds"]); b=float(later["at_seconds"])
        level=amp(earlier); delta=amp(later)-level
        expr=(f"if(lt(t,{b:.9g}),{level:.12g}+({delta:.12g})"
              f"*(t-{a:.9g})/{b-a:.9g},{expr})")
    first=points[0]
    t=float(first["at_seconds"])
    if t:
        expr=f"if(lt(t,{t:.9g}),{amp(first):.12g},{expr})"
    return "volume='"+expr+"':eval=frame"


def validate_composition(plan,workspace,vault):
    if not isinstance(plan,dict) or set(plan)!={"canvas","video_layers","audio_tracks"}:
        raise ValueError("An actual editor-authored canvas and tracks required")
    canvas=plan["canvas"]
    expected_canvas={"width","height","fps","duration","background"}
    if not isinstance(canvas,dict) or not expected_canvas.issubset(canvas) or (
            set(canvas)-expected_canvas-{"color_semantics"}):
        raise ValueError("Editor must specify all physical delivery parameters")
    contract=canvas.get("color_semantics")
    if contract is not None and (
            not isinstance(contract,dict) or set(contract)!={"input","output"}
            or contract!={"input":"bt709","output":"bt709"}):
        raise ValueError("Only measured and explicitly declared BT.709 SDR compositing color is supported")
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
            if not isinstance(layer,dict):
                raise ValueError("Director-specified "+kind+" layer must be an object")
            required=({"id","source","asset_id","attestation_id",
                       "start","source_in","duration","x","y","width","height","opacity"}
                      if kind=="video" else
                      {"id","source","asset_id","attestation_id","start","source_in","duration","gain_db"})
            supported=required|({"motion","fade_in_seconds","fade_out_seconds","chroma_key"}
                                if kind=="video" else {"gain_keyframes"})
            if not required.issubset(layer) or not set(layer).issubset(supported):
                raise ValueError("Director-specified "+kind+" layer is incomplete or uses untrusted effects")
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
            if kind=="video" and contract is not None:
                # This is not a silent metadata label. Every incoming
                # picture must physically carry the declared SDR VUI, or
                # we cannot claim a consistent compositor output.
                from .body_color_pipeline import _actual_bt709_source
                _actual_bt709_source(file)
            for field in ("width","height"):
                if kind=="video":_int(layer[field],field)
            if kind=="video":
                for key in ("x","y"):
                    if isinstance(layer[key],bool) or not isinstance(layer[key],int):
                        raise ValueError("Creative layer position must be exact integer pixels")
                a=_positive(layer["opacity"],"opacity",allow_zero=True)
                if a>1:raise ValueError("Alpha beyond physical range")
                if "chroma_key" in layer:
                    key=layer["chroma_key"]
                    if not isinstance(key,dict) or set(key)!={"color","similarity","blend"}:
                        raise ValueError("Chroma matte needs explicitly authored color, similarity and blend")
                    if not isinstance(key["color"],str) or not _COLOR.fullmatch(key["color"]):
                        raise ValueError("Original VFX matte key color must be exact RGB")
                    sim=_positive(key["similarity"],"key similarity")
                    blend=_positive(key["blend"],"key edge blending",allow_zero=True)
                    if sim>1 or blend>1:
                        raise ValueError("VFX key compositor strength must stay in physical alpha range")
                motion=layer.get("motion",[])
                if not isinstance(motion,list):
                    raise ValueError("Actual editor motion keyframes must be an array")
                last=-1.0
                for frame in motion:
                    if not isinstance(frame,dict) or set(frame)!={"at_seconds","x","y"}:
                        raise ValueError("Motion keyframe requires original time and 2D position")
                    at=_positive(frame["at_seconds"],"motion timestamp",allow_zero=True)
                    if at<=last or at>duration:
                        raise ValueError("Artist motion keyframes must be in distinct increasing time order")
                    last=at
                    if any(type(frame[axis]) is not int for axis in ("x","y")):
                        raise ValueError("Motion position must use exact original pixel coordinates")
                incoming=_positive(layer.get("fade_in_seconds",0),"artist fade-in",allow_zero=True)
                outgoing=_positive(layer.get("fade_out_seconds",0),"artist fade-out",allow_zero=True)
                if incoming+outgoing>duration:
                    raise ValueError("Original alpha transitions exceed authored layer duration")
            else:
                gain=layer["gain_db"]
                if isinstance(gain,bool) or not isinstance(gain,(int,float)) or (
                        not math.isfinite(gain) or abs(gain)>120):
                    raise ValueError("Unsafe audio gain")
                envelope=layer.get("gain_keyframes",[])
                if not isinstance(envelope,list) or len(envelope)>64:
                    raise ValueError("Original audio envelope must be a bounded list")
                previous=-1.0
                for key in envelope:
                    if not isinstance(key,dict) or set(key)!={"at_seconds","gain_db"}:
                        raise ValueError("Audio automation points need time and gain")
                    at=_positive(key["at_seconds"],"audio automation time",allow_zero=True)
                    value=key["gain_db"]
                    if (at<=previous or at>duration or
                        isinstance(value,bool) or not isinstance(value,(int,float))
                        or not math.isfinite(value) or abs(value)>120):
                        raise ValueError("Audio envelope contains out-of-range or unordered points")
                    previous=at
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
            visual=(f"[{index}:v:0]trim=start={source_in}:duration={duration},"
                f"setpts=PTS-STARTPTS,scale={layer['width']}:{layer['height']}:flags=lanczos,"
                f"fps={fps},format=rgba")
            if "chroma_key" in layer:
                key=layer["chroma_key"]
                visual+=(f",colorkey=0x{key['color'][1:]}:"
                         f"similarity={key['similarity']}:blend={key['blend']}")
            visual+=f",colorchannelmixer=aa={layer['opacity']}"
            if layer.get("fade_in_seconds",0)>0:
                visual+=(f",fade=t=in:st=0:"
                         f"d={layer['fade_in_seconds']}:alpha=1")
            if layer.get("fade_out_seconds",0)>0:
                outgoing_start=duration-float(layer["fade_out_seconds"])
                visual+=(f",fade=t=out:st={outgoing_start}:"
                         f"d={layer['fade_out_seconds']}:alpha=1")
            filters.append(visual+f",setpts=PTS+{start}/TB[v{index}]")
            output=f"stack{index}"
            posx=_motion_expression(layer,"x")
            posy=_motion_expression(layer,"y")
            if layer.get("motion"):
                # FFmpeg comma/colon-bearing expressions are quoted only
                # when keyframe calculations need them.
                posx="'"+posx+"'"
                posy="'"+posy+"'"
            filters.append(
                f"[{base}][v{index}]overlay=x={posx}:y={posy}:"
                f"eof_action=pass:shortest=0:"
                f"enable='between(t,{start},{start+duration})':format=auto[{output}]")
            base=output
        else:
            lag=round(start*1000)
            effects=(f"[{index}:a:0]atrim=start={source_in}:duration={duration},"
                "asetpts=PTS-STARTPTS,aresample=48000,"
                f"aformat=channel_layouts=stereo,volume={layer['gain_db']}dB")
            envelope=_gain_automation_expression(layer)
            if envelope is not None:
                effects+=","+envelope
            effects+=f",adelay={lag}|{lag},apad,atrim=duration={secs}[audio{index}]"
            filters.append(effects)
            music.append(f"[audio{index}]")
    if "color_semantics" in c:
        filters.append(f"[{base}]format=yuv420p,"
                       "setparams=range=tv:color_primaries=bt709:"
                       "color_trc=bt709:colorspace=bt709[vout]")
    else:
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
           "-t",str(secs),"-movflags","+faststart"]
    if "color_semantics" in c:
        args+=["-color_primaries","bt709","-color_trc","bt709",
               "-colorspace","bt709"]
    args.append(str(out))
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

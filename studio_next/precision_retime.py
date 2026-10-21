"""Non-destructive, artist-authored timeline retiming of genuinely owned footage.

Uses decoded source-frame ranges instead of free-form ffmpeg expressions.
Changing playback speed also time-stretches its original soundtrack (if any).
A missing soundtrack may only become *explicitly chosen* intentional silence.
No fixed film genre, shot style, effect count or edit rhythm.
"""
from __future__ import annotations

import json
import math
import subprocess
from fractions import Fraction
from pathlib import Path

from .edit_timeline import _path_within
from .media_vault import MediaVault, sha256_file
from .delivery_audit import _probe_details


def _int(value, label):
    if type(value) is not int or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _speed(value):
    if not isinstance(value,dict) or set(value)!={"numerator","denominator"}:
        raise ValueError("Speed must be an exact rational numerator and denominator")
    a=_int(value["numerator"],"speed numerator")
    b=_int(value["denominator"],"speed denominator")
    q=Fraction(a,b)
    # Only a local FFmpeg execution budget, NOT an artistic limit on the studio.
    if q<Fraction(1,64) or q>64:
        raise ValueError("Local FFmpeg retime adapter supports playback speed 1/64..64")
    return q


def _tempo_chain(speed):
    """FFmpeg atempo permits factor 0.5..2.0 per pass with good continuity."""
    q=float(speed)
    steps=[]
    while q>2:
        steps.append(2.0)
        q/=2
    while q<0.5:
        steps.append(0.5)
        q/=0.5
    steps.append(q)
    return ",".join(f"atempo={s:.12g}" for s in steps)


def plan_retime(plan,root,vault_root,*,probe=None):
    if not isinstance(plan,dict) or set(plan)!={"source","asset_id","attestation_id",
                                                "source_fps","segments","audio"}:
        raise ValueError("Retime needs explicit owned source, exact frame rate, segments and audio")
    source=_path_within(Path(root),plan["source"],exists=True)
    if source.suffix.lower() not in (".mp4",".mov",".mkv",".webm"):
        raise ValueError("Retime source must be actual video")
    if not isinstance(plan["asset_id"],str) or not isinstance(plan["attestation_id"],str):
        raise ValueError("Retime requires immutable media custody identity")
    vault=MediaVault(vault_root)
    attested=vault.inspect(plan["asset_id"],attestation_id=plan["attestation_id"])
    if not attested.get("rights_attestations") or sha256_file(source)!=plan["asset_id"]:
        raise ValueError("Source footage differs from the verified rights owner bytes")
    rate=plan["source_fps"]
    if not isinstance(rate,dict) or set(rate)!={"numerator","denominator"}:
        raise ValueError("Source frame rate must be exact rational")
    fps=Fraction(_int(rate["numerator"],"fps numerator"),
                 _int(rate["denominator"],"fps denominator"))
    if fps<1 or fps>240:
        raise ValueError("This local FFmpeg adapter does not handle that video timebase")
    meta=(probe or _probe_details)(source)
    if not isinstance(meta,dict) or not meta.get("width") or not meta.get("height"):
        raise ValueError("Uninspectable source media video")
    audio=plan["audio"]
    if audio not in ("preserve_source","intentional_silence"):
        raise ValueError("Artist must explicitly choose original audio or silence")
    if audio=="preserve_source" and not meta.get("audio_stream_present"):
        raise ValueError("Cannot time stretch a soundtrack that does not exist")
    segments=plan["segments"]
    if not isinstance(segments,list) or not segments:
        raise ValueError("Director must specify non-empty time-remapping segments")
    if len(segments)>4096:
        raise ValueError("Local FFmpeg graph capacity exceeded; split into stages")
    expected=Fraction()
    allparts=[]
    total_frames=0
    for i,segment in enumerate(segments):
        if not isinstance(segment,dict) or set(segment)!={"first_frame","end_frame","speed"}:
            raise ValueError(f"Malformed original segment {i}")
        first=segment["first_frame"];end=segment["end_frame"]
        if type(first) is not int or first<0 or type(end) is not int or end<=first:
            raise ValueError("Retime frame span must have positive decoded frame length")
        speed=_speed(segment["speed"])
        frames=end-first
        if frames>10000000:
            raise ValueError("Single source span exceeds host stage frame safety capacity")
        duration=Fraction(frames,1)/fps
        expected+=duration/speed
        total_frames+=frames
        allparts.append({"first":first,"end":end,"speed":speed,"duration":duration})
    if expected>24*3600:
        raise ValueError("Local retime stage exceeds its 24-hour output safety capacity")
    # The physical adapter uses decoded frames; reject substantial source-rate
    # discrepancies, not silently re-time variable-frame-rate originals.
    if plan.get("source_fps") and meta.get("fps"):
        measured=Fraction(str(meta["fps"])).limit_denominator(1001000)
        if abs(measured-fps)/fps>Fraction(1,1000):
            raise ValueError("Actual source frame rate differs from user-authorized timebase")
    return {"source":source,"fps":fps,"audio":audio,"parts":allparts,
            "expected_seconds":float(expected),"source_fps":rate,
            "width":meta["width"],"height":meta["height"]}


def retime_command(validated,output):
    """Return fixed executable argv; model strings are only validated data."""
    p=validated
    src=str(p["source"]);fps=p["fps"];parts=p["parts"]
    fq=f"{fps.numerator}/{fps.denominator}"
    expressions=[]
    with_sound=p["audio"]=="preserve_source"
    for i,seg in enumerate(parts):
        speed=seg["speed"];factor=f"{speed.denominator}/{speed.numerator}"
        # trim by *decoded frame indices*, not packet timestamps.
        expressions.append(
            f"[0:v]trim=start_frame={seg['first']}:end_frame={seg['end']},"
            f"setpts=(PTS-STARTPTS)*({factor}),fps={fq},format=yuv420p[v{i}]")
        if with_sound:
            start=float(Fraction(seg["first"],1)/fps)
            end=float(Fraction(seg["end"],1)/fps)
            expressions.append(
                f"[0:a]atrim=start={start:.9f}:end={end:.9f},asetpts=PTS-STARTPTS,"
                f"{_tempo_chain(speed)},aresample=async=1:first_pts=0[a{i}]")
        else:
            expressions.append(
                f"anullsrc=r=48000:cl=stereo,atrim=duration={float(seg['duration']/speed):.9f},"
                f"asetpts=PTS-STARTPTS[a{i}]")
    ins="".join(f"[v{i}][a{i}]" for i in range(len(parts)))
    expressions.append(f"{ins}concat=n={len(parts)}:v=1:a=1[v][a]")
    return [
        "ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
        "-i",src,"-filter_complex",";".join(expressions),
        "-map","[v]","-map","[a]",
        "-c:v","libx264","-pix_fmt","yuv420p","-r",fq,
        "-preset","veryfast","-crf","18","-c:a","aac","-b:a","192k",
        "-movflags","+faststart",str(output)
    ]


def render_retime(plan_path,workspace,vault_root,output,*,runner=None,probe=None):
    plan_path=Path(plan_path)
    data=json.loads(plan_path.read_text(encoding="utf-8"))
    checked=plan_retime(data,workspace,vault_root,probe=probe)
    destination=Path(output)
    if destination.exists():
        raise FileExistsError("Previously accepted physical media cannot be overwritten")
    command=retime_command(checked,destination)
    run=runner or subprocess.run
    try:
        result=run(command,capture_output=True,text=True,timeout=7200,check=False)
        if result.returncode!=0:
            raise RuntimeError("Physical retiming failed: "+str(result.stderr)[-1200:])
        actual=_probe_details(destination)
        # Limited by one encoded output frame plus the AAC encoder padding.
        tolerance=max(.14,2.0/float(checked["fps"]))
        if abs(actual["duration_seconds"]-checked["expected_seconds"])>tolerance:
            raise RuntimeError("Encoded retimed timeline deviates from original measured edit")
        if not actual["audio_stream_present"]:
            raise RuntimeError("Time-remapped production dropped its explicit sound track")
        return {"path":str(destination.resolve()),"sha256":sha256_file(destination),
                "bytes":destination.stat().st_size,
                "duration_seconds":actual["duration_seconds"],
                "width":actual["width"],"height":actual["height"],
                "audio_present":True,
                "intended_duration_seconds":checked["expected_seconds"],
                "retime_operations":len(checked["parts"]),
                "no_creative_defaults":True}
    except BaseException:
        destination.unlink(missing_ok=True)
        raise

"""Non-destructive, artist-authored timeline retiming of genuinely owned footage.

Uses decoded source-frame ranges instead of free-form ffmpeg expressions.
Changing playback speed also time-stretches its original soundtrack (if any).
A missing soundtrack may only become *explicitly chosen* intentional silence.
No fixed film genre, shot style, effect count or edit rhythm.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from .edit_timeline import _path_within
from .media_vault import MediaVault, sha256_file
from .delivery_audit import _probe_details
from .composite_mix import sealed_attested_original,_decoded_source_duration
from .production_qc import full_decode_inspection


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


def _verify_decoded_frame_clock(path,expected_rate,expected_count):
    """Verify actual presentation times, not merely avg vs guessed FPS.

    ffprobe emits one best-effort decoded presentation timestamp per frame.
    Some decoders append side-data to that CSV record; its FIRST field is
    the frame timestamp. B-frame packet/decoding DTS order is NOT used.
    """
    from decimal import Decimal,InvalidOperation
    command=["ffprobe","-v","error","-select_streams","v:0",
             "-show_frames","-show_entries","frame=best_effort_timestamp_time",
             "-of","csv=p=0",str(path)]
    try:
        output=subprocess.run(command,capture_output=True,text=True,
                              timeout=240,check=True)
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        raise ValueError("Unable to decode original frame presentation clock") from exc
    previous=None
    count=0
    interval=Fraction(1,1)/expected_rate
    # ffprobe decimal time has microsecond output rounding. Allow two last
    # display digits of uncertainty; never accept a true frame skip/duplicate.
    permitted=max(Fraction(3,1000000),interval/100000)
    for record in output.stdout.splitlines():
        text=record.split(",",1)[0].strip()
        if not text:
            continue
        try: now=Fraction(Decimal(text))
        except (InvalidOperation,ValueError,OverflowError) as exc:
            raise ValueError("Unmeasurable physical source frame PTS") from exc
        count+=1
        if count>expected_count:
            raise ValueError("More decoded frame timestamps than measured source frames")
        if previous is not None:
            gap=now-previous
            if gap<=0 or abs(gap-interval)>permitted:
                raise ValueError("Variable-rate or irregular original frame timestamps; explicit conform required")
        previous=now
    if count!=expected_count:
        raise ValueError("Physical original frame timestamps incomplete")
    return count


def _source_timebase(path):
    """Verify physical decoded frame count and that clip is constant-frame-rate."""
    raw=subprocess.check_output([
        "ffprobe","-v","error","-count_frames","-select_streams","v:0",
        "-show_entries","stream=avg_frame_rate,r_frame_rate,nb_read_frames",
        "-of","json",str(path)],timeout=90)
    streams=json.loads(raw).get("streams",[])
    if len(streams)!=1:
        raise ValueError("Original retime requires one identifiable video stream")
    stream=streams[0]
    try:
        avg=Fraction(stream["avg_frame_rate"])
        nominal=Fraction(stream["r_frame_rate"])
        count=int(stream["nb_read_frames"])
    except (KeyError,ValueError,TypeError,ZeroDivisionError) as exc:
        raise ValueError("Source video lacks measured frame rate/count") from exc
    if not avg or not nominal or count<=0:
        raise ValueError("Invalid actual source timing")
    # CFR is a capability requirement for this adapter. A proper VFR
    # normalization tool can be installed separately with user approval.
    if abs(avg-nominal)/avg>Fraction(1,1000):
        raise ValueError("Variable-rate media needs explicit CFR conform before frame-precision editing")
    _verify_decoded_frame_clock(path,avg,count)
    return avg,count


def plan_retime(plan,root,vault_root,*,probe=None):
    required={"source","asset_id","attestation_id",
              "source_fps","segments","audio"}
    if (not isinstance(plan,dict) or not required.issubset(plan)
            or set(plan)-required-{"interpolation"}):
        raise ValueError("Retime needs explicit owned source, exact frame rate, segments and audio")
    interpolation=plan.get("interpolation","frame_repeat")
    if interpolation not in ("frame_repeat","motion_compensated") or type(interpolation) is not str:
        raise ValueError("Only a typed original frame-repeat or optical-flow retime is allowed")
    if interpolation=="motion_compensated":
        try:
            filters=subprocess.run(["ffmpeg","-hide_banner","-filters"],
                capture_output=True,text=True,timeout=20,check=True)
        except (OSError,subprocess.SubprocessError) as exc:
            raise ValueError("Native host lacks a measurable optical-flow renderer") from exc
        if not any(line.split()[1:2]==["minterpolate"]
                   for line in filters.stdout.splitlines()):
            raise ValueError("Local FFmpeg has no installed motion-compensated interpolator")
    if not isinstance(plan["asset_id"],str) or not isinstance(plan["attestation_id"],str):
        raise ValueError("Retime requires immutable media custody identity")
    vault=MediaVault(vault_root)
    attested=vault.inspect(plan["asset_id"],attestation_id=plan["attestation_id"])
    name=plan["source"]
    if not isinstance(name,str):
        raise ValueError("Retime requires a verified source reference")
    if name.startswith("zx7:sha256:"):
        if name!="zx7:sha256:"+plan["asset_id"]:
            raise ValueError("Time-mapped original footage identifier differs from verified CAS")
        source=Path(attested["path"]).resolve()
        if not source.is_relative_to(Path(root).resolve()):
            raise ValueError("Actual time-mapped media escapes original workspace")
        if attested["mime"] not in ("video/mp4","video/quicktime","video/webm"):
            raise ValueError("Referenced verified media is not genuine video")
    else:
        source=_path_within(Path(root),name,exists=True)
        if source.suffix.lower() not in (".mp4",".mov",".mkv",".webm"):
            raise ValueError("Retime source must be actual video")
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
    # Verify real source timing and its decoded frame count, not a user claim.
    # Dependency injection here is used only for isolated tests.
    if probe is None:
        measured,physical_frame_count=_source_timebase(source)
        if abs(measured-fps)/fps>Fraction(1,1000):
            raise ValueError("Actual source rate differs from the selected frame timebase")
        if any(item["end"]>physical_frame_count for item in allparts):
            raise ValueError("Selected original edit reaches beyond source footage")
        if audio=="preserve_source":
            sound_capacity=_decoded_source_duration(source,"audio")
            if any(float(Fraction(item["end"],1)/fps)>sound_capacity+.015
                   for item in allparts):
                raise ValueError("Time warp exceeds actual original recorded-audio stream")
    return {"source":source,"fps":fps,"audio":audio,"parts":allparts,
            "interpolation":interpolation,
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
        interpolator=(
            f"minterpolate=fps={fq}:mi_mode=mci:mc_mode=obmc:me_mode=bidir"
            if p.get("interpolation","frame_repeat")=="motion_compensated"
            else f"fps={fq}")
        # Motion-compensated interpolation is a REAL installed CPU filter.
        # The owner still selects every shot and exact rational speed;
        # optical flow is not a claim of artist-approved restoration.
        expressions.append(
            f"[0:v]trim=start_frame={seg['first']}:end_frame={seg['end']},"
            f"setpts=(PTS-STARTPTS)*({factor}),{interpolator},"
            f"format=yuv420p[v{i}]")
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
    """Real sealed-source variable-speed editor with atomic private output.

    A model may choose rational speed and exact source frame selections, but
    cannot supply executable FFmpeg expressions, make up missing original
    soundtrack, or replace another director's accepted original movie.
    """
    root=Path(workspace).resolve()
    plan_path=Path(plan_path).resolve()
    destination=Path(output).resolve()
    if (not plan_path.is_relative_to(root) or not plan_path.is_file() or
            not destination.is_relative_to(root) or
            destination.suffix.lower()!=".mp4" or destination.exists()):
        raise ValueError("Owned retime needs existing original edit and fresh workspace MP4")
    plan_sha=sha256_file(plan_path)
    data=json.loads(plan_path.read_text(encoding="utf-8"))
    if sha256_file(plan_path)!=plan_sha:
        raise ValueError("Original retime plan changed while being read")
    checked=plan_retime(data,root,vault_root,probe=probe)
    original_path=Path(checked["source"])
    original_identity=data["asset_id"]
    original_attestation=data["attestation_id"]
    destination.parent.mkdir(parents=True,exist_ok=True)
    vault=MediaVault(vault_root)
    with tempfile.TemporaryDirectory(prefix=".zx7-owned-sources-",dir=root) as working:
        private=Path(working)
        snapshots={}
        frozen=sealed_attested_original(
            vault,original_identity,original_attestation,private,snapshots)
        original={**checked,"source":frozen}
        if sha256_file(original_path)!=original_identity or sha256_file(plan_path)!=plan_sha:
            raise ValueError("Artist's original footage or retime plan changed before encoding")
        encoded=private/"original-speed-revision.mp4"
        command=retime_command(original,encoded)
        run=runner or subprocess.run
        result=run(command,capture_output=True,text=True,timeout=7200,check=False)
        if result.returncode!=0:
            raise RuntimeError("Physical retiming failed: "+str(result.stderr)[-1200:])
        actual=(probe or _probe_details)(encoded)
        tolerance=max(.14,2.0/float(checked["fps"]))
        if abs(actual["duration_seconds"]-checked["expected_seconds"])>tolerance:
            raise RuntimeError("Encoded retimed timeline deviates from original measured edit")
        if not actual["audio_stream_present"]:
            raise RuntimeError("Time-remapped production dropped its explicit soundtrack")
        verified=runner is None and probe is None
        if verified:
            qa=full_decode_inspection(encoded,expected={
                "width":checked["width"],"height":checked["height"],
                "require_audio":True})
            if not qa["technical_delivery_verified"] or not qa[
                    "full_picture_and_sound_decoder_completed"]:
                raise RuntimeError("Actual retimed picture or soundtrack failed entire media decode")
        if (sha256_file(original_path)!=original_identity or
                sha256_file(frozen)!=original_identity or
                sha256_file(plan_path)!=plan_sha):
            raise ValueError("Original source or creative decisions changed during physical retime")
        vault.inspect(original_identity,attestation_id=original_attestation)
        with encoded.open("rb") as movie:
            os.fsync(movie.fileno())
        os.link(encoded,destination)
    return {"path":str(destination),"sha256":sha256_file(destination),
            "bytes":destination.stat().st_size,
            "duration_seconds":actual["duration_seconds"],
            "width":actual["width"],"height":actual["height"],
            "audio_present":True,
            "intended_duration_seconds":checked["expected_seconds"],
            "retime_operations":len(checked["parts"]),
            "native_motion_compensated_interpolation_requested":
                checked["interpolation"]=="motion_compensated",
            "native_motion_compensated_interpolation_physically_proven":
                checked["interpolation"]=="motion_compensated" and verified,
            "optical_flow_is_not_independent_artistic_approval":True,
            "no_creative_defaults":True,
            "sealed_original_cas_during_decode":True,
            "full_picture_and_sound_decoder_completed":verified,
            "verified_physically":verified,
            "fake_runner_or_probe_injected":not verified}

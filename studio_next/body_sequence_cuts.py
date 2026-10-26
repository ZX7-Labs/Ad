"""Physical, non-destructive, rights-attested frame-accurate multi-source cuts.

A precisely defined subset of the professional BODY edit graph, not a full
NLE: verified constant-frame-rate BT.709 original shots at matching authored
dimensions are ordered by decoded frame indices; each soundtrack is explicitly
preserved or replaced by artist-declared silence. No implicit source purchase,
artist style, invented media, output frame preset, hidden VFR conform or 3D
synthetic generation.

The old generic editor accepts legacy owner-asserted source labels. This
STRICT adapter instead requires independently attested SHA256 source custody
before every source is decoded or used in the published film.
"""
from __future__ import annotations
from fractions import Fraction
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

from .composite_mix import _exact_media,sealed_attested_original,_decoded_source_duration
from .body_color_pipeline import _actual_bt709_source
from .media_vault import MediaVault,sha256_file
from .precision_retime import _source_timebase
from .delivery_audit import _probe_details
from .production_qc import full_decode_inspection


def _integer(number,label,*,low=1,high=100000000):
    if type(number) is not int or number<low or number>high:
        raise ValueError("Original frame cut "+label+" outside supported host limits")
    return number


def plan_verified_sequence(plan,workspace,vault_root):
    root=Path(workspace).resolve()
    if not isinstance(plan,dict) or set(plan)!={"frame_rate","frame_size","clips"}:
        raise ValueError("Director sequence requires exact timebase, frame size and original clip list")
    fr=plan["frame_rate"];size=plan["frame_size"]
    if not isinstance(fr,dict) or set(fr)!={"numerator","denominator"}:
        raise ValueError("Video timebase requires exact rational FPS")
    fps=Fraction(_integer(fr["numerator"],"fps numerator",high=240000),
                 _integer(fr["denominator"],"fps denominator",high=100000))
    if not 1<=fps<=240:
        raise ValueError("Native film cuts require a supported physical timebase")
    if not isinstance(size,dict) or set(size)!={"width","height"}:
        raise ValueError("Original video frame size must be explicitly authored")
    width=_integer(size["width"],"picture width",high=7680)
    height=_integer(size["height"],"picture height",high=4320)
    if width%2 or height%2:
        raise ValueError("Current H264 4:2:0 adapter requires even output pixels")
    clips=plan["clips"]
    if not isinstance(clips,list) or not 1<=len(clips)<=128:
        raise ValueError("Original edit requires a bounded nonempty list of authored clips")
    vault=MediaVault(vault_root)
    evaluated=[]
    original_sources={}
    total_frames=0
    for i,clip in enumerate(clips):
        expected={"source","asset_id","attestation_id",
                  "first_frame","end_frame","audio"}
        if not isinstance(clip,dict) or set(clip)!=expected:
            raise ValueError("Original film shot lacks exact video, audio or source custody")
        source=_exact_media(clip,vault,root,need="video")
        _actual_bt709_source(source)
        measured=_probe_details(source)
        if (measured["width"],measured["height"])!=(width,height):
            raise ValueError("Original source geometry needs an explicit independent conform stage")
        source_rate,frame_count=_source_timebase(source)
        if source_rate!=fps:
            raise ValueError("All exact-frame original footage must share authored rational timebase")
        first=_integer(clip["first_frame"],"first frame",low=0)
        end=_integer(clip["end_frame"],"exclusive end frame",low=1)
        if first>=end or end>frame_count:
            raise ValueError("Original decoded frame range exceeds real owned footage")
        if clip["audio"] not in ("preserve_source","intentional_silence"):
            raise ValueError("Artist must explicitly preserve original sound or authorize silence")
        if clip["audio"]=="preserve_source":
            if not measured["audio_stream_present"]:
                raise ValueError("Original audio is not physically present to preserve")
            # A 2-second MP4 picture can contain only 1 second of recorded
            # dialogue. Do not fill the rest with fabricated 'preserved' sound.
            actual_sound_seconds=_decoded_source_duration(source,"audio")
            if float(Fraction(end,1)/fps)>actual_sound_seconds+.015:
                raise ValueError("Requested cut outlasts recorded original audio stream")
        total_frames+=end-first
        if total_frames>2_000_000:
            raise ValueError("Single native render exceeds bounded source frame workload")
        original_sources[str(source)]=clip["asset_id"]
        evaluated.append({"source":source,"asset_id":clip["asset_id"],
             "first":first,"end":end,"frames":end-first,"audio":clip["audio"]})
    if Fraction(total_frames,1)/fps>24*3600:
        raise ValueError("Single host sequence exceeded physical 24-hour output capacity")
    return {"fps":fps,"width":width,"height":height,
            "clips":evaluated,"frames":total_frames,
            "seconds":float(Fraction(total_frames,1)/fps),
            "originals":original_sources}


def verified_sequence_command(evaluated,output):
    fps=evaluated["fps"]
    rate=f"{fps.numerator}/{fps.denominator}"
    graph=[]
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-n"]
    for i,clip in enumerate(evaluated["clips"]):
        cmd+=["-i",str(clip["source"])]
        first,end=clip["first"],clip["end"]
        graph.append(
            f"[{i}:v:0]trim=start_frame={first}:end_frame={end},"
            f"setpts=N*{fps.denominator}/({fps.numerator}*TB),format=yuv420p[v{i}]")
        duration=Fraction(clip["frames"],1)/fps
        if clip["audio"]=="preserve_source":
            start=float(Fraction(first,1)/fps)
            stop=float(Fraction(end,1)/fps)
            graph.append(
                f"[{i}:a:0]atrim=start={start:.10f}:end={stop:.10f},"
                "asetpts=PTS-STARTPTS,aresample=48000:async=1:first_pts=0,"
                f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"apad,atrim=duration={float(duration):.10f}[a{i}]")
        else:
            graph.append(
                f"anullsrc=r=48000:cl=stereo,"
                f"atrim=duration={float(duration):.10f}[a{i}]")
    inputs="".join(f"[v{i}][a{i}]" for i in range(len(evaluated["clips"])))
    graph.append(inputs+f"concat=n={len(evaluated['clips'])}:v=1:a=1[v][a]")
    cmd+=["-filter_complex",";".join(graph),"-map","[v]","-map","[a]",
          "-c:v","libx264","-pix_fmt","yuv420p","-crf","18",
          "-r",rate,"-c:a","aac","-b:a","192k",
          "-color_primaries","bt709","-color_trc","bt709",
          "-colorspace","bt709","-movflags","+faststart",str(output)]
    return cmd


def render_verified_sequence(plan_file,workspace,vault_root,output,*,pre_publish_guard=None):
    """Write a new real video from exact original picture/sound CAS, never mutable checkout.

    The exact director edit, all signed custody, normalized frame clock,
    actual full decoded video/audio, and non-overwriting publication are
    required before an accepted result. Any exception removes private bytes,
    never someone else's already approved output.
    """
    if pre_publish_guard is not None and not callable(pre_publish_guard):
        raise TypeError("Only a trusted final publication guard is accepted")
    root=Path(workspace).resolve()
    document=Path(plan_file).resolve()
    destination=Path(output).resolve()
    if (not document.is_relative_to(root) or not document.is_file() or
        not destination.is_relative_to(root) or destination.exists() or
        destination.suffix.lower()!=".mp4"):
        raise ValueError("Native original cut requires owned plan and new workspace MP4")
    accepted_plan_sha256=sha256_file(document)
    plan=json.loads(document.read_text(encoding="utf-8"))
    if sha256_file(document)!=accepted_plan_sha256:
        raise ValueError("Director timeline modified during source validation")
    checked=plan_verified_sequence(plan,root,vault_root)
    vault=MediaVault(vault_root)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".zx7-owned-sources-",dir=root) as working:
        private=Path(working)
        originals={}
        sealed={}
        evaluated={**checked,"clips":[]}
        for authored,clip in zip(plan["clips"],checked["clips"]):
            identity=authored["asset_id"]
            attestation=authored["attestation_id"]
            frozen=sealed_attested_original(
                vault,identity,attestation,private,sealed)
            evaluated["clips"].append({**clip,"source":frozen})
            originals[str(clip["source"])]=identity
        if sha256_file(document)!=accepted_plan_sha256:
            raise ValueError("Director timeline changed before the native decoder started")
        encoded=private/"native-original-edited.mp4"
        rendered=subprocess.run(verified_sequence_command(evaluated,encoded),
                capture_output=True,text=True,timeout=7200)
        if rendered.returncode!=0:
            raise RuntimeError("Original licensed multicut encoder failed: "+rendered.stderr[-1400:])
        proof=_probe_details(encoded)
        frame_rate,frame_count=_source_timebase(encoded)
        if (frame_rate!=checked["fps"] or frame_count!=checked["frames"] or
             (proof["width"],proof["height"])!=(checked["width"],checked["height"]) or
             not proof["audio_stream_present"] or
             abs(proof["duration_seconds"]-checked["seconds"])>
                 max(.12,2/float(checked["fps"]))):
            raise ValueError("Physically decoded movie disagrees with original absolute frame decisions")
        _actual_bt709_source(encoded)
        decoded=full_decode_inspection(encoded,expected={
            "width":checked["width"],"height":checked["height"],
            "duration_seconds":checked["seconds"],"require_audio":True})
        if (not decoded["technical_delivery_verified"] or
                not decoded["full_picture_and_sound_decoder_completed"]):
            raise ValueError("Actual entire edited movie picture or audio failed decoder")
        if any(sha256_file(path)!=digest for path,digest in originals.items()):
            raise ValueError("Original footage changed during precise film cut")
        if any(sha256_file(path)!=digest for (digest,_),path in sealed.items()):
            raise ValueError("Sealed native decoder footage changed during physical film cut")
        for authored in plan["clips"]:
            vault.inspect(authored["asset_id"],
                          attestation_id=authored["attestation_id"])
        if sha256_file(document)!=accepted_plan_sha256:
            raise ValueError("Director's exact timeline changed during physical frame cut")
        with encoded.open("rb") as ready:
            os.fsync(ready.fileno())
        # Trusted higher-level editors may recheck immutable plans and author
        # decisions AFTER full decode, immediately before exclusive publication.
        if pre_publish_guard is not None:
            pre_publish_guard()
        # Hard-link is a same-filesystem exclusive publication: refuse
        # another producer's finished film instead of silently replacing it.
        os.link(encoded,destination)
    return {"path":str(destination),"sha256":sha256_file(destination),
            "bytes":destination.stat().st_size,
            "original_physical_source_assets":len(checked["originals"]),
            "actual_cut_operations":len(checked["clips"]),
            "physical_original_frames_delivered":frame_count,
            "original_audio_stream_present":True,
            "movie_seconds":proof["duration_seconds"],
            "physically_verified_BT709_CFR":True,
            "full_picture_and_sound_decoder_completed":True,
            "sealed_original_cas_during_decode":True,
            "creative_story_quality_certified":False}

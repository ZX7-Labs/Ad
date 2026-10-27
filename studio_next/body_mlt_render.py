"""Native MLT editor media export with original project/source custody.

Executes only a previously verified ZX7 MLT project. The model may select the
project and output name, but cannot provide MLT XML, FFmpeg options, effects,
shell arguments, executable code, arbitrary media URLs or new rights grants.
No sound mixing: the registered MLT project explicitly mutes all source audio.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from .body_mlt_editor import verify_owned_mlt_project
from .media_vault import MediaVault,sha256_file
from .precision_retime import _source_timebase
from .production_qc import full_decode_inspection
from .delivery_audit import _probe_details


def render_owned_mlt(edit,workspace,output):
    """Publish decoded, exact-clock original muted-video composition only."""
    root=Path(workspace).resolve()
    source=Path(edit).absolute()
    dest=Path(output).absolute()
    if (not source.is_file() or source.is_symlink()
            or not source.is_relative_to(root) or source.suffix.lower()!=".mlt"
            or not dest.is_relative_to(root) or dest.suffix.lower()!=".mp4"
            or source==dest):
        raise ValueError("Native MLT execution requires a verified owned .mlt and workspace .mp4")
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("Never replace prior MLT creative media")
    if not shutil.which("melt") or not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("Actual MLT and FFmpeg native editing engines must be installed")
    before=sha256_file(source)
    verified=verify_owned_mlt_project(source)
    xml=ET.fromstring(source.read_bytes())
    profile=xml.find("profile")
    tractor=xml.find("tractor")
    if profile is None or tractor is None:
        raise ValueError("Original MLT has no measurable native profile")
    expected={
        "description":"ZX7 measured original frame clock",
        "progressive":"1","sample_aspect_num":"1","sample_aspect_den":"1",
        "colorspace":"709"}
    if any(profile.get(k)!=v for k,v in expected.items()):
        raise ValueError("MLT source profile was modified")
    try:
        width=int(profile.get("width"))
        height=int(profile.get("height"))
        fps=Fraction(int(profile.get("frame_rate_num")),
                     int(profile.get("frame_rate_den")))
        frames=int(tractor.get("out"))+1
    except (ValueError,TypeError,ZeroDivisionError) as exc:
        raise ValueError("Cannot measure declared editorial output geometry and timebase") from exc
    if (not 2<=width<=7680 or not 2<=height<=4320 or width%2 or height%2
            or not 1<=fps<=240 or not 1<=frames<=1000000
            or tractor.get("in")!="0"
            or profile.get("display_aspect_num")!=str(width)
            or profile.get("display_aspect_den")!=str(height)):
        raise ValueError("MLT declared film dimensions/timebase changed")
    sources=[]
    for producer in xml.findall("producer"):
        props={p.get("name"):p.text for p in producer.findall("property")}
        file=Path(props["resource"])
        if not file.is_relative_to(root):
            raise ValueError("Verified MLT source must remain within creator workspace")
        digest=props["zx7.original_sha256"]
        vault=MediaVault(file.parents[2])
        measured=vault.inspect(digest,attestation_id=props["zx7.attestation_id"])
        if measured["path"]!=str(file) or measured["mime"] not in (
                "video/mp4","video/webm","video/quicktime"):
            raise ValueError("MLT export cannot follow modified original video source")
        sources.append((file,digest,props["zx7.attestation_id"]))
    if not sources:
        raise ValueError("No original verified media in the edit")
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".zx7-mlt-render-",dir=dest.parent) as tmp:
        encoded=Path(tmp)/"render.mp4"
        cmd=["melt",str(source),"-consumer",f"avformat:{encoded}",
             "vcodec=libx264","pix_fmt=yuv420p","crf=18",
             "an=1","real_time=-1","threads=2"]
        run=subprocess.run(cmd,capture_output=True,text=True,timeout=7200)
        if run.returncode:
            raise RuntimeError("Verified MLT rendering failed: "+run.stderr[-1200:])
        measured_rate,measured_frames=_source_timebase(encoded)
        if measured_rate!=fps or measured_frames!=frames:
            raise ValueError("Actual decoded MLT frame clock differs from original editing intent")
        probe=_probe_details(encoded)
        if probe["audio_stream_present"]:
            raise ValueError("MLT renderer unexpectedly emitted an unauthorized soundtrack")
        qa=full_decode_inspection(encoded,expected={
            "width":width,"height":height,
            "duration_seconds":float(Fraction(frames,1)/fps),
            "require_audio":False})
        if not qa["technical_delivery_verified"] or not qa["full_picture_and_sound_decoder_completed"]:
            raise ValueError("Actual MLT picture failed full decoder or output dimensions")
        if sha256_file(source)!=before:
            raise ValueError("MLT original edit changed during native render")
        for file,digest,att in sources:
            if sha256_file(file)!=digest:
                raise ValueError("MLT original clip changed while native renderer executed")
            MediaVault(file.parents[2]).inspect(digest,attestation_id=att)
        with encoded.open("rb") as stream:os.fsync(stream.fileno())
        os.link(encoded,dest)
    return {"path":str(dest),"sha256":sha256_file(dest),
            "bytes":dest.stat().st_size,"frames":measured_frames,
            "fps":{"numerator":fps.numerator,"denominator":fps.denominator},
            "width":width,"height":height,"source_assets":len(sources),
            "source_project_sha256":before,
            "native_multitrack_verified":bool(verified["verified_mlt_tracks"]>1),
            "original_sound_intentionally_silent":True,
            "full_decoded_picture":True,
            "artistic_quality_approved":False}

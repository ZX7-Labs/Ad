"""Native MLT editor media export with original project/source custody.

Executes only a previously verified ZX7 MLT project. The model may select the
project and output name, but cannot provide MLT XML, FFmpeg options, effects,
shell arguments, executable code, arbitrary media URLs or new rights grants.
Recorded original sound is mixed only through separately verified audio tracks;
the frame-accurate native compositor must be physically installed and tested.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import os
import re
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
from .body_color_pipeline import _actual_bt709_source


def _require_native_frei0r_compositing():
    """Refuse to advertise a blend mode when its actual MLT plugin is missing.

    MLT may silently fall back to a source-over picture for an unrecognized
    transition, so a successfully encoded MP4 is not sufficient evidence.
    """
    try:
        check=subprocess.run(["melt","-query","transitions"],
            capture_output=True,text=True,timeout=40)
    except (OSError,subprocess.SubprocessError) as exc:
        raise RuntimeError("Unable to inspect installed original-source Cairo compositor") from exc
    if check.returncode or "frei0r.cairoblend" not in check.stdout:
        raise RuntimeError(
            "Original-source multiply/screen/overlay require installed native "
            "MLT Frei0r Cairo blending; arbitrary source-over substitution is forbidden")


def _require_native_audio_volume():
    """Do not silently ignore a director-authored native sound level filter."""
    try:
        check=subprocess.run(["melt","-query","filters"],
            capture_output=True,text=True,timeout=40)
    except (OSError,subprocess.SubprocessError) as exc:
        raise RuntimeError("Cannot inspect native audio volume filter") from exc
    if check.returncode or "volume" not in {row.strip().removeprefix("- ").strip() for row in check.stdout.splitlines()}:
        raise RuntimeError("Original sound gain requires installed MLT volume filter")


def _uncovered_picture_frames(xml,picture_tracks,frames):
    """Find the actual timeline intervals with no playable picture source."""
    spans=[]
    for playlist in xml.findall("playlist")[:picture_tracks]:
        cursor=0
        for item in playlist:
            if item.tag=="blank":
                cursor+=int(item.get("length"))
            else:
                count=int(item.get("out"))-int(item.get("in"))+1
                spans.append((cursor,cursor+count))
                cursor+=count
        if cursor!=frames:
            raise ValueError("Original native picture playlist does not match film clock")
    if not spans:
        return [(0,frames)]
    gaps=[]
    covered=0
    for start,end in sorted(spans):
        if start>covered:
            gaps.append((covered,start))
        covered=max(covered,end)
    if covered<frames:
        gaps.append((covered,frames))
    return gaps


def render_owned_mlt(edit,workspace,output,*,gap_color=None):
    """Publish a fully decoded, measured original-source video and sound mix."""
    root=Path(workspace).resolve()
    source=Path(edit).absolute()
    dest=Path(output).absolute()
    if (not source.is_file() or source.is_symlink()
            or not source.is_relative_to(root) or
            not source.resolve().is_relative_to(root) or
            source.suffix.lower()!=".mlt"
            or not dest.is_relative_to(root) or
            not dest.resolve().is_relative_to(root) or
            dest.suffix.lower()!=".mp4" or source==dest):
        raise ValueError("Native MLT execution requires a verified owned .mlt and workspace .mp4")
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("Never replace prior MLT creative media")
    if not shutil.which("melt") or not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("Actual MLT and FFmpeg native editing engines must be installed")
    before=sha256_file(source)
    verified=verify_owned_mlt_project(source)
    xml=ET.fromstring(source.read_bytes())
    if any(any(p.get("name")=="mlt_service" and
            p.text=="frei0r.cairoblend" for p in transition.findall("property"))
            for transition in xml.findall("./tractor/transition")):
        _require_native_frei0r_compositing()
    if xml.findall("./tractor/filter"):
        _require_native_audio_volume()
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
    gaps=_uncovered_picture_frames(xml,verified["verified_mlt_tracks"],frames)
    if gap_color is not None and (not isinstance(gap_color,str) or
            not re.fullmatch(r"#[0-9a-fA-F]{6}",gap_color)):
        raise ValueError("Director must author an exact RGB hex gap color, not MLT code")
    if gaps and gap_color is None:
        raise ValueError("Uncovered picture needs an explicit director-authored delivery gap_color; MLT defaults to an unapproved white test card")
    sources=[]
    for producer in xml.findall("producer"):
        props={p.get("name"):p.text for p in producer.findall("property")}
        file=Path(props["resource"])
        if not file.is_relative_to(root):
            raise ValueError("Verified MLT source must remain within creator workspace")
        digest=props["zx7.original_sha256"]
        vault=MediaVault(file.parents[2])
        measured=vault.inspect(digest,attestation_id=props["zx7.attestation_id"])
        is_sound=producer.get("id","").startswith("audio-source-")
        if (measured["path"]!=str(file) or
            (measured["mime"] not in ("video/mp4","video/webm","video/quicktime")
             and not (is_sound and measured["mime"]=="audio/wav"))):
            raise ValueError("MLT export cannot follow modified original video or PCM sound")
        sources.append((file,digest,props["zx7.attestation_id"]))
    if not sources:
        raise ValueError("No original verified media in the edit")
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".zx7-mlt-render-",dir=dest.parent) as tmp:
        # Never execute the mutable input XML path. MLT's own XML reader is
        # non-validating; run a byte-sealed, independently revalidated snapshot.
        sealed=Path(tmp)/"sealed-original.mlt"
        with source.open("rb") as original, sealed.open("xb") as target:
            shutil.copyfileobj(original,target)
            target.flush()
            os.fsync(target.fileno())
        if sha256_file(sealed)!=before:
            raise ValueError("Original MLT project changed while securing render input")
        if verify_owned_mlt_project(sealed)!=verified:
            raise ValueError("Sealed editable MLT project failed source verification")
        # A validated XML snapshot is not enough: the native reader otherwise
        # follows live CAS paths for the entire encode. Copy each authenticated
        # producer exactly once to a private file, then give the native worker
        # only those immutable-by-custody content-verified stage paths.
        private_sources=Path(tmp)/"private-sources"
        private_sources.mkdir(mode=0o700)
        frozen={}
        for file,digest,att in sources:
            if digest in frozen:
                continue
            MediaVault(file.parents[2]).inspect(digest,attestation_id=att)
            snapshot=private_sources/digest
            with file.open("rb") as original, snapshot.open("xb") as target:
                shutil.copyfileobj(original,target,1024*1024)
                target.flush()
                os.fsync(target.fileno())
            if sha256_file(snapshot)!=digest:
                raise ValueError("Actual owner media changed while sealing native decoder input")
            MediaVault(file.parents[2]).inspect(digest,attestation_id=att)
            frozen[digest]=snapshot
        # The worker XML is generated *only* from previously allowlisted
        # producer nodes and private byte-sealed CAS copies. Never parse
        # arbitrary user XML into executable MLT options.
        worker_xml=ET.fromstring(sealed.read_bytes())
        for producer in worker_xml.findall("producer"):
            props={p.get("name"):p for p in producer.findall("property")}
            digest=props["zx7.original_sha256"].text
            if digest not in frozen:
                raise ValueError("Sealed MLT references an unauthenticated producer")
            props["resource"].text=str(frozen[digest])
        worker=Path(tmp)/"private-worker.mlt"
        with worker.open("xb") as output_xml:
            output_xml.write(ET.tostring(worker_xml,encoding="utf-8",
                                           xml_declaration=True)+b"\n")
            output_xml.flush()
            os.fsync(output_xml.fileno())
        if sha256_file(sealed)!=before:
            raise ValueError("Sealed original project was changed before native execution")
        if any(sha256_file(path)!=digest for digest,path in frozen.items()):
            raise ValueError("Native staged media differs from authenticated originals")
        encoded=Path(tmp)/"render.mp4"
        # Certain installed MLT runtimes fall back to PAL 25fps when the
        # trusted XML is reconstructed under a private worker pathname.
        # Pin all output profile values from the independently verified
        # authored frame clock rather than trusting MLT's default consumer.
        sound_present=verified["verified_audio_tracks"]>0
        cmd=["melt",str(worker),"-consumer",f"avformat:{encoded}",
             f"frame_rate_num={fps.numerator}",f"frame_rate_den={fps.denominator}",
             f"width={width}",f"height={height}","progressive=1",
             "vcodec=libx264","pix_fmt=yuv420p","crf=18",
             "color_primaries=bt709","color_trc=bt709",
             "colorspace=709","movflags=+faststart",
             "an=0" if sound_present else "an=1",
             "real_time=-1","threads=2"]
        if sound_present:
            cmd+=["acodec=aac","ab=192k","ar=48000","channels=2"]
        run_env=None
        if gap_color is not None:
            # MLT defines all-blank frames as WHITE test cards by default.
            # Override only with a physically verified director-selected
            # 24-bit color, not an aesthetic color chosen by BODY code.
            # MLT documented colour producer accepts 0xRRGGBBAA. Its
            # consumer test_card is a producer *resource*, not an FFmpeg
            # color expression or arbitrary plugin name.
            card="colour:0x"+gap_color[1:].lower()+"ff"
            cmd+=["test_card="+card]
            run_env={**os.environ,"MLT_TEST_CARD":card}
        run=subprocess.run(cmd,capture_output=True,text=True,
                           timeout=7200,env=run_env)
        if run.returncode:
            raise RuntimeError("Verified MLT rendering failed: "+run.stderr[-1200:])
        measured_rate,measured_frames=_source_timebase(encoded)
        if measured_rate!=fps or measured_frames!=frames:
            raise ValueError(f"Actual decoded MLT frame clock differs from original editing intent: expected {fps} ({frames} frames), decoded {measured_rate} ({measured_frames} frames)")
        if gaps:
            first=gaps[0][0]
            decoded=subprocess.check_output(["ffmpeg","-hide_banner",
                "-loglevel","error","-nostdin","-xerror","-i",str(encoded),
                "-vf",f"select=eq(n\\,{first})","-vsync","0",
                "-frames:v","1","-pix_fmt","rgb24","-f","rawvideo","-"],
                timeout=90)
            if len(decoded)!=width*height*3:
                raise ValueError("Original rendered gap has no complete decoded RGB frame")
            desired=bytes.fromhex(gap_color[1:])
            if max(abs(decoded[k+i]-desired[i]) for k in range(0,len(decoded),3)
                   for i in (0,1,2))>18:
                raise ValueError("Native renderer did not reproduce director-authored gap color")
        probe=_probe_details(encoded)
        if probe["audio_stream_present"]!=sound_present:
            raise ValueError("MLT original recorded soundtrack was lost or an unauthorized audio stream appeared")
        # The project and its physical inputs are BT.709, and the delivered
        # movie must retain those explicit display tags for other devices.
        # Otherwise a nominally successful encode could shift appearance.
        _actual_bt709_source(encoded)
        qa=full_decode_inspection(encoded,expected={
            "width":width,"height":height,
            "duration_seconds":float(Fraction(frames,1)/fps),
            "require_audio":sound_present})
        if not qa["technical_delivery_verified"] or not qa["full_picture_and_sound_decoder_completed"]:
            raise ValueError("Actual MLT picture failed full decoder or output dimensions")
        if sha256_file(source)!=before:
            raise ValueError("MLT original edit changed during native render")
        for file,digest,att in sources:
            if sha256_file(file)!=digest:
                raise ValueError("MLT original clip changed while native renderer executed")
            MediaVault(file.parents[2]).inspect(digest,attestation_id=att)
        if any(sha256_file(path)!=digest for digest,path in frozen.items()):
            raise ValueError("Private native decoder input was modified during rendering")
        if sha256_file(sealed)!=before:
            raise ValueError("Original sealed editor plan was modified during rendering")
        with encoded.open("rb") as stream:os.fsync(stream.fileno())
        os.link(encoded,dest)
    return {"path":str(dest),"sha256":sha256_file(dest),
            "bytes":dest.stat().st_size,"frames":measured_frames,
            "fps":{"numerator":fps.numerator,"denominator":fps.denominator},
            "width":width,"height":height,"source_assets":len(sources),
            "source_project_sha256":before,
            "native_multitrack_verified":bool(verified["verified_mlt_tracks"]>1),
            "original_sound_intentionally_silent":not sound_present,
            "verified_original_audio_tracks":verified["verified_audio_tracks"],
            "full_decoded_picture":True,
            "artist_selected_gap_color":gap_color,
            "uncovered_picture_intervals_detected":len(gaps),
            "sampled_director_gap_pixels_physically_verified":bool(gaps),
            "artistic_quality_approved":False}

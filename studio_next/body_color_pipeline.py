"""Rights-backed physical SDR 3D LUT color transform, with truthful color custody.

This is a professional *display-referred BT.709 to BT.709* LUT adapter,
not an unverified ACES scene-linear, HDR or fully color-managed VFX pipeline.

Owner/creative director chooses actual footage, transform, interpolation and
delivery format. Both original video and cube are independently SHA256-attested
through immutable MediaVault. FFmpeg receives only vetted fixed filter syntax,
and the original movie, soundtrack and original LUT are never overwritten.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .composite_mix import _exact_media,sealed_attested_original
from .production_qc import full_decode_inspection
from .media_vault import MediaVault,sha256_file
from .delivery_audit import _probe_details

_SAFE_DIGEST=re.compile(r"^[0-9a-f]{64}$")


def validate_cube_bytes(data):
    """Parse an actual Iridas .cube file; reject injected filter/code syntax."""
    if not isinstance(data,bytes) or not data or len(data)>16*1024*1024:
        raise ValueError("Color LUT must be a bounded original CUBE asset")
    try:
        lines=data.decode("utf-8-sig").splitlines()
    except UnicodeError as exc:
        raise ValueError("Color LUT must be valid text CUBE data") from exc
    size=None
    rows=0
    seen_data=False
    for original in lines:
        line=original.split("#",1)[0].strip()
        if not line:
            continue
        fields=line.split()
        if fields[0]=="TITLE" and not seen_data and size is None:
            # The artistic LUT title is metadata only; never interpolated into
            # a filename, shell command or filter expression.
            continue
        if fields[0]=="LUT_3D_SIZE" and len(fields)==2 and size is None and not seen_data:
            try: size=int(fields[1])
            except ValueError as exc:
                raise ValueError("Original artist cube dimension is invalid") from exc
            if not 2<=size<=65:
                raise ValueError("Unsupported host 3D LUT grid resolution")
            continue
        if fields[0] in ("DOMAIN_MIN","DOMAIN_MAX") and not seen_data and len(fields)==4:
            try: limits=[float(x) for x in fields[1:]]
            except ValueError as exc: raise ValueError("Invalid numeric color domain") from exc
            if not all(math.isfinite(x) for x in limits):
                raise ValueError("Non-finite color domain")
            # This adapter is intentionally encoded SDR and does NOT pretend
            # a LUT defined on a scene-linear/log range is safe to use here.
            if (fields[0]=="DOMAIN_MIN" and limits!=[0.0]*3) or (
                    fields[0]=="DOMAIN_MAX" and limits!=[1.0]*3):
                raise ValueError("LUT domain incompatible with declared SDR BT.709 contract")
            continue
        if size is None or len(fields)!=3:
            raise ValueError("Unsupported, incomplete or untrusted CUBE color format")
        try: channels=[float(x) for x in fields]
        except ValueError as exc:raise ValueError("Malformed original LUT colors") from exc
        if not all(math.isfinite(x) and abs(x)<1e6 for x in channels):
            raise ValueError("Unsafe non-finite or overflowing color transform")
        rows+=1
        seen_data=True
        if rows>size**3:
            raise ValueError("Extra color-table rows outside declared 3D cube")
    if size is None or rows!=size**3:
        raise ValueError("Actual 3D LUT grid incomplete")
    return {"grid":size,"samples":rows,"type":"Iridas CUBE 3D"}


def _actual_bt709_source(path):
    probe=json.loads(subprocess.check_output([
        "ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","stream=color_space,color_primaries,color_transfer",
        "-of","json",str(path)],timeout=60))
    streams=probe.get("streams",[])
    if len(streams)!=1 or any(streams[0].get(tag)!="bt709" for tag in
       ("color_space","color_primaries","color_transfer")):
        raise ValueError("Original footage has unverified BT.709 input color semantics; explicit conform needed")
    return streams[0]


def validate_color_job(job,workspace,vault_root):
    if not isinstance(job,dict) or set(job)!={"media","color_transform","output_profile"}:
        raise ValueError("Physical color body requires media, transform and output profile")
    media=job["media"]; transform=job["color_transform"]
    if not isinstance(media,dict) or set(media)!={"source","asset_id","attestation_id"}:
        raise ValueError("Original color footage requires exact rights/custody")
    if not isinstance(transform,dict) or set(transform)!={
            "kind","input_color_space","output_color_space","cube","interpolation"}:
        raise ValueError("Artist must explicitly declare color transform and lookup")
    if transform["kind"]!="display_referred_3d_lut" or (
          transform["input_color_space"]!="bt709" or transform["output_color_space"]!="bt709"):
        raise ValueError("This installed adapter can only validate real BT.709 display-referred LUT color")
    if transform["interpolation"] not in ("tetrahedral","trilinear"):
        raise ValueError("Unsupported technical LUT interpolation")
    if job["output_profile"] not in ("h264_8bit_sdr","prores_10bit_sdr"):
        raise ValueError("Unknown installed codec/profile pair")
    root=Path(workspace).resolve()
    vault=MediaVault(vault_root)
    movie=_exact_media(media,vault,root,need="video")
    _actual_bt709_source(movie)
    cube=transform["cube"]
    if not isinstance(cube,dict) or set(cube)!={"source","asset_id","attestation_id"}:
        raise ValueError("Artist LUT requires its own rights/custody identity")
    if not isinstance(cube["asset_id"],str) or not _SAFE_DIGEST.fullmatch(cube["asset_id"]):
        raise ValueError("Original color transform digest invalid")
    if cube["source"]!="zx7:sha256:"+cube["asset_id"]:
        raise ValueError("Color transform source cannot bypass verified immutable CAS")
    record=vault.inspect(cube["asset_id"],attestation_id=cube["attestation_id"])
    if record["mime"]!="application/octet-stream" or not record["rights_attestations"]:
        raise ValueError("Color LUT must be an authorized original binary transform")
    lookup=Path(record["path"]).resolve()
    if not lookup.is_relative_to(root) or sha256_file(lookup)!=cube["asset_id"]:
        raise ValueError("Original color LUT stored bytes are not verified")
    cube_content=lookup.read_bytes()
    shape=validate_cube_bytes(cube_content)
    return {"movie":movie,"cube":lookup,"cube_bytes":cube_content,"cube_shape":shape,
            "movie_sha256":media["asset_id"],"cube_sha256":cube["asset_id"],
            "profile":job["output_profile"],"interp":transform["interpolation"]}


def render_verified_color_job(plan_file,workspace,vault_root,output):
    """Render only explicitly licensed display-referred SDR LUT to new movie.

    The original picture and sound are frozen from verified CAS, the separately
    licensed CUBE is copied into the same private render sandbox, and final
    destination is hardlink-published only after whole-media decoding.
    """
    root=Path(workspace).resolve()
    source=Path(plan_file).resolve()
    destination=Path(output).resolve()
    if not source.is_file() or not source.is_relative_to(root):
        raise ValueError("Original creative LUT direction must be an owned workspace document")
    spec_sha=sha256_file(source)
    spec=json.loads(source.read_text(encoding="utf-8"))
    if sha256_file(source)!=spec_sha:
        raise ValueError("Art-directed color instructions changed during initial read")
    proof=validate_color_job(spec,root,vault_root)
    if not destination.is_relative_to(root) or destination.exists():
        raise ValueError("Do not overwrite original accepted color work or escape workspace")
    extension=".mp4" if proof["profile"]=="h264_8bit_sdr" else ".mov"
    if destination.suffix.lower()!=extension:
        raise ValueError("Color master container differs from chosen delivery profile")
    original=_probe_details(proof["movie"])
    destination.parent.mkdir(parents=True,exist_ok=True)
    vault=MediaVault(vault_root)
    with tempfile.TemporaryDirectory(prefix=".zx7-owned-sources-",dir=root) as working:
        private=Path(working)
        copies={}
        frozen=sealed_attested_original(vault,spec["media"]["asset_id"],
            spec["media"]["attestation_id"],private,copies)
        # The CUBE is separately rights-attested data: never allow its
        # arbitrary lines to replace the fixed allowlisted FFmpeg filter ABI.
        lut=private/"lookup.cube"
        with lut.open("xb") as file:
            file.write(proof["cube_bytes"])
            file.flush()
            os.fsync(file.fileno())
        if sha256_file(lut)!=proof["cube_sha256"]:
            raise ValueError("Artist original color LUT changed while sealing")
        os.chmod(lut,0o400)
        if (sha256_file(proof["movie"])!=proof["movie_sha256"]
                or sha256_file(source)!=spec_sha):
            raise ValueError("Original owner movie or color direction changed before encoder")
        encoded=private/("original-graded-master"+extension)
        cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-n",
            "-i",str(frozen),
            "-vf","lut3d=file=lookup.cube:interp="+proof["interp"]+
                  ",setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709",
            "-map","0:v:0"]
        if original["audio_stream_present"]:
            cmd.extend(["-map","0:a:0"])
        if proof["profile"]=="h264_8bit_sdr":
            cmd.extend(["-c:v","libx264","-crf","16","-pix_fmt","yuv420p",
                        "-c:a","aac","-b:a","192k","-movflags","+faststart"])
        else:
            cmd.extend(["-c:v","prores_ks","-profile:v","3",
                        "-pix_fmt","yuv422p10le",
                        "-c:a","pcm_s24le","-movflags","+write_colr"])
        cmd.extend(["-color_primaries","bt709","-color_trc","bt709",
                    "-colorspace","bt709",str(encoded)])
        completed=subprocess.run(cmd,cwd=private,capture_output=True,
                                 text=True,timeout=7200,check=False)
        if completed.returncode!=0:
            raise RuntimeError("Real original SDR color transform failed: "+
                               completed.stderr[-1400:])
        physical=_probe_details(encoded)
        if (physical["width"]!=original["width"] or
                physical["height"]!=original["height"] or
                physical["audio_stream_present"]!=original["audio_stream_present"] or
                abs(physical["duration_seconds"]-original["duration_seconds"])>.14):
            raise ValueError("Original real film grade changed picture geometry, runtime or soundtrack")
        _actual_bt709_source(encoded)
        qa=full_decode_inspection(encoded,expected={
            "width":original["width"],"height":original["height"],
            "duration_seconds":original["duration_seconds"],
            "require_audio":original["audio_stream_present"]})
        if not qa["technical_delivery_verified"] or not qa[
                "full_picture_and_sound_decoder_completed"]:
            raise RuntimeError("Graded original media failed entire picture/audio decode")
        if (sha256_file(proof["movie"])!=proof["movie_sha256"] or
                sha256_file(proof["cube"])!=proof["cube_sha256"] or
                sha256_file(lut)!=proof["cube_sha256"] or
                sha256_file(frozen)!=proof["movie_sha256"] or
                sha256_file(source)!=spec_sha):
            raise ValueError("Licensed original camera, transform or owner plan changed mid grade")
        vault.inspect(spec["media"]["asset_id"],
                      attestation_id=spec["media"]["attestation_id"])
        cube=spec["color_transform"]["cube"]
        vault.inspect(cube["asset_id"],attestation_id=cube["attestation_id"])
        with encoded.open("rb") as movie:
            os.fsync(movie.fileno())
        os.link(encoded,destination)
    return {"path":str(destination),"sha256":sha256_file(destination),
            "bytes":destination.stat().st_size,
            "duration_seconds":physical["duration_seconds"],
            "audio_present":physical["audio_stream_present"],
            "color_pipeline":"verified_display_referred_bt709_lut",
            "source_movie_sha256":proof["movie_sha256"],
            "original_cube_sha256":proof["cube_sha256"],
            "interpolation":proof["interp"],
            "output_profile":proof["profile"],
            "actually_verified_color_space":"bt709",
            "sealed_original_cas_and_original_cube_during_decode":True,
            "full_picture_and_sound_decoder_completed":True,
            "claimed_aces_hdr_or_scene_linear":False,
            "creative_quality_approved":False}

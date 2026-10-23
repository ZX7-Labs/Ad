"""Native licensed Blender Cycles -> real scene-linear multilayer OpenEXR bundle.

Original 3D scene is artist-authored JSON, not model executable Python. Every
EXR frame is physically decoded and must contain genuine 32-bit float
Combined RGBA, depth, motion vector and normal passes before a stage can be
registered successful. Output ZIP holds exact frame/camera/manifest receipts;
no source is overwritten and no 8-bit display export pretends to be HDR.

OpenEXR v3.3+ Python binding and locally installed Blender are REQUIRED. This
is a real linear CG intermediate, NOT verified ACES transform, optical-flow
slow motion, composited final film or a complete professional VFX host.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from .blender_scene import validate_blender_shot
from .media_vault import sha256_file

EXR_MAGIC=b"\x76\x2f\x31\x01"
_FRAME_NAME=re.compile(r"^frames/frame_[0-9]{4,8}\.exr$")


def inspect_real_exr_frame(path):
    """Decode physically rendered multi-pass EXR using installed native ABI."""
    if importlib.util.find_spec("OpenEXR") is None:
        raise RuntimeError("OpenEXR Python 3.3+ decoder must be installed")
    import OpenEXR
    p=Path(path)
    with p.open("rb") as src:
        if src.read(4)!=EXR_MAGIC:
            raise ValueError("Rendered file is not a genuine OpenEXR container")
    # Separate color components. Do not accidentally mistake a shallow RGB
    # preview for actual motion/depth/normal scene-linear 3D output.
    try:
        with OpenEXR.File(str(p),separate_channels=True) as exr:
            parts=exr.parts
            names=[]
            dimensions=set()
            for part in parts:
                dimensions.add((part.width(),part.height()))
                for name,channel in part.channels.items():
                    names.append(name)
                    if str(channel.pixels.dtype)!="float32":
                        raise ValueError("Actual VFX channel is not 32-bit float")
            if len(dimensions)!=1 or next(iter(dimensions))==(0,0):
                raise ValueError("Original EXR scene dimensions inconsistent")
            channels=set(names)
            rgb_required=("Combined.R","Combined.G","Combined.B","Combined.A")
            if any(not any(name.endswith(x) for name in channels)
                   for x in rgb_required):
                raise ValueError("Actual EXR has no full RGBA linear Combined pass")
            if not any("Depth" in name and name.endswith(".Z") for name in channels):
                raise ValueError("Actual EXR depth pass Z unavailable")
            if not any("Normal" in name and name.endswith(".X") for name in channels):
                raise ValueError("Actual EXR surface normals unavailable")
            if not any("Vector" in name and name.endswith(".X") for name in channels):
                raise ValueError("Actual EXR speed vectors unavailable")
            width,height=next(iter(dimensions))
            return {"width":width,"height":height,"parts":len(parts),
                    "actual_channel_names":sorted(channels),
                    "actual_channel_count":len(names),
                    "decoded_float_precision_bits":32,
                    "linear_render_passes_physically_verified":True}
    except (OSError,RuntimeError,ValueError) as exc:
        raise ValueError("Original EXR scene failed physical channel decoding: "+str(exc)) from exc


def verify_exr_bundle(bundle):
    """No ZIP filename traversal, no unverified contents, real EXR decoding."""
    source=Path(bundle)
    with zipfile.ZipFile(source,"r") as zipped:
        members=zipped.namelist()
        if len(members)!=len(set(members)) or "manifest.json" not in members:
            raise ValueError("Duplicate/absent original EXR frame archive members")
        if any((name!="manifest.json" and not _FRAME_NAME.fullmatch(name))
               or ".." in Path(name).parts or name.startswith("/") for name in members):
            raise ValueError("Untrusted file path inside original EXR bundle")
        manifest=json.loads(zipped.read("manifest.json"))
        if not isinstance(manifest,dict) or manifest.get("schema")!=1:
            raise ValueError("Unknown original EXR bundle evidence schema")
        entries=manifest.get("frames")
        if not isinstance(entries,list) or not entries or len(members)!=len(entries)+1:
            raise ValueError("Physical EXR bundle missing image frames")
        verified_names=[entry.get("file") for entry in entries
                        if isinstance(entry,dict)]
        expected_names=["frames/frame_"+f"{index:04d}"+".exr"
                        for index in range(1,len(entries)+1)]
        if len(verified_names)!=len(entries) or any(
                not isinstance(name,str) for name in verified_names):
            raise ValueError("Invalid original EXR manifest member identity")
        if sorted(verified_names)!=sorted(expected_names) or (
                set(verified_names)!=set(members)-{"manifest.json"}):
            raise ValueError("Original EXR stage has missing, duplicate or unverified frame identity")
        if zipped.getinfo("manifest.json").file_size>32*1024*1024:
            raise ValueError("Untrusted EXR manifest too large")
        # Inspect headers and capacity before extracting compressed media.
        available=shutil.disk_usage(tempfile.gettempdir()).free
        scratch_required=sum(zipped.getinfo(name).file_size for name in verified_names)
        if scratch_required+16*1024*1024>available:
            raise RuntimeError("Not enough physical scratch disk for 32f VFX verification")
        with tempfile.TemporaryDirectory(prefix="zx7-verify-exr-") as stage:
            for item in entries:
                if not isinstance(item,dict) or set(item)!={"file","sha256","bytes","channels"}:
                    raise ValueError("Untrusted original EXR member manifest")
                name=item["file"]
                if not isinstance(name,str) or name not in members or not _FRAME_NAME.fullmatch(name):
                    raise ValueError("EXR file missing or not a safe frame name")
                # Stream from archive to bound memory; full EXR pixel decoding
                # below is a separate resource-gated native library action.
                destination=Path(stage)/Path(name).name
                with zipped.open(name) as fh,destination.open("xb") as out:
                    shutil.copyfileobj(fh,out,1024*1024)
                if (sha256_file(destination)!=item["sha256"] or
                    destination.stat().st_size!=item["bytes"]):
                    raise ValueError("Decoded original EXR bytes differ from release manifest")
                actual=inspect_real_exr_frame(destination)
                if actual["actual_channel_names"]!=item["channels"]:
                    raise ValueError("Encoded original EXR channel pass identity changed")
        return {"schema":1,"original_frame_count":len(entries),
                "original_exr_passes_real":True,
                "reloaded_every_frame_and_sha256_verified":True,
                "human_artist_quality_approval":False,
                "ACES_transform_certified":False}


def render_original_exr_passes(scene_file,workspace,output,*,assets_root=None):
    root=Path(workspace).resolve()
    original=Path(scene_file).resolve()
    destination=Path(output).resolve()
    if not original.is_file() or not original.is_relative_to(root) or (
            not destination.is_relative_to(root) or destination.suffix.lower()!=".zip"
            or destination.exists()):
        raise ValueError("Original 3D VFX project must stay inside workspace and create a new ZIP")
    job=json.loads(original.read_text(encoding="utf-8"))
    validate_blender_shot(job,verified_assets_root=assets_root)
    # This specialist pass refuses external 3D assets with an unverified
    # textual rights claim until the GLB asset's CAS custody is fully wired.
    if any(item["type"]=="licensed_glb" for item in job["objects"]):
        raise ValueError("Imported 3D geometry needs verified CAS material rights first")
    if not shutil.which("blender") or importlib.util.find_spec("OpenEXR") is None:
        raise RuntimeError("Actual native Blender and OpenEXR 3.3+ are required")
    original_sha=sha256_file(original)
    destination.parent.mkdir(parents=True,exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=".zx7-original-exr-render-",dir=root) as temp:
            # The Blender process must read only sealed, byte-exact owner
            # instructions. A mutable checkout can be swapped and restored
            # while native Cycles is running; postrender hash alone misses it.
            frozen=Path(temp)/"original-sealed-scene.json"
            with original.open("rb") as artist,frozen.open("xb") as native:
                shutil.copyfileobj(artist,native,1024*1024)
                native.flush()
                os.fsync(native.fileno())
            if (sha256_file(frozen)!=original_sha or
                    sha256_file(original)!=original_sha):
                raise ValueError("Original 3D artist scene changed during native sealing")
            os.chmod(frozen,0o400)
            frames_dir=Path(temp)/"frames"
            frames_dir.mkdir()
            cmd=["blender","--background","--factory-startup",
                 "--python-exit-code","1","--python",
                 str(Path(__file__).parent/"blender_scene.py"),"--",
                 "--scene",str(frozen),"--out",str(frames_dir),
                 "--exr-passes"]
            if assets_root:
                cmd+=["--assets-root",str(Path(assets_root).resolve())]
            subprocess.run(cmd,check=True,timeout=7200,
                           capture_output=True,text=True)
            if sha256_file(frozen)!=original_sha:
                raise ValueError("Sealed 3D scene changed during native Cycles execution")
            frame_paths=sorted(frames_dir.glob("frame_*.exr"))
            if len(frame_paths)!=job["frames"] or not frame_paths:
                raise RuntimeError("Blender failed artist-chosen original EXR frame count")
            manifest={"schema":1,"shot_id":job["shot_id"],
                      "scene_source_sha256":original_sha,
                      "width":job["width"],"height":job["height"],
                      "frames_per_second":job["fps"],
                      "artist_frames_requested":job["frames"],
                      "actual_render_engine":"Blender Cycles CPU",
                      "intermediate":"32-bit float multilayer scene-linear OpenEXR",
                      "ACES_transform_certified":False,
                      "human_artistic_quality_certified":False,
                      "frames":[]}
            for file in frame_paths:
                pass_info=inspect_real_exr_frame(file)
                if (pass_info["width"]!=job["width"] or
                    pass_info["height"]!=job["height"]):
                    raise ValueError("Original Blender multi-pass frame dimensions differ")
                manifest["frames"].append({"file":"frames/"+file.name,
                    "sha256":sha256_file(file),"bytes":file.stat().st_size,
                    "channels":pass_info["actual_channel_names"]})
            if sha256_file(original)!=original_sha:
                raise ValueError("Director's 3D scene changed during original scene-linear render")
            archive=Path(temp)/"verified-original-exr.zip"
            with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED,
                                compresslevel=6,allowZip64=True) as bundle:
                for file in frame_paths:
                    bundle.write(file,arcname="frames/"+file.name)
                bundle.writestr("manifest.json",json.dumps(
                    manifest,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
            independent=verify_exr_bundle(archive)
            if (sha256_file(original)!=original_sha or
                    sha256_file(frozen)!=original_sha):
                raise ValueError("Director scene changed before EXR publication")
            with archive.open("rb") as verified_source:
                os.fsync(verified_source.fileno())
            # Publish only a fully decoded, verified archive. Never delete a
            # competing approved ZIP that appeared while Cycles was running.
            os.link(archive,destination)
        return {"path":str(destination),"sha256":sha256_file(destination),
                "bytes":destination.stat().st_size,
                "original_scene_sha256":original_sha,
                "original_scene_frames":independent["original_frame_count"],
                "actual_32bit_float_VFX_passes":True,
                "verified_channels":manifest["frames"][0]["channels"],
                "human_quality_approved":False,"ACES_color_grade_proven":False}
    except BaseException:
        # Only the temporary render belongs to us. A public destination might
        # be another compositor's approved EXR bundle; never unlink it.
        raise

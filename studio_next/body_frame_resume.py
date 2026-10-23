"""Crash-resumable, frame-granular ORIGINAL Blender Cycles 32f VFX executor.

Unlike retrying a completed MP4 or rerendering a whole 3D animation, this
holds each successfully decoded and hashed EXR frame in durable on-disk
checkpoint custody. When Blender dies, only frames without verified receipts
are rendered again. Original authored animation frame indices never shift.

This is single-host Linux execution (fcntl lock): it is NOT a distributed
render farm, a free GPU, licensed external GLB workflow or ACES compositor.
Cache proofs are host-local trusted checkpoint receipts; a malicious actor
with full write access to the operator's workspace is outside their
attestation threat model and must not be described as cryptographic authorship.
"""
from __future__ import annotations

import fcntl
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from .blender_scene import validate_blender_shot
from .body_exr_passes import inspect_real_exr_frame,verify_exr_bundle
from .media_vault import sha256_file

_SCHEMA=1


def _original_frame(i):
    return f"frame_{i:04d}.exr"


def _file_scope(root,filename,*,require_file):
    relative=Path(filename)
    if not relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Explicit original production file must be an absolute trusted path")
    target=relative.resolve()
    if not target.is_relative_to(root):
        raise ValueError("Original VFX project or master escaped controlled workspace")
    if relative.is_symlink() or (require_file and not target.is_file()):
        raise ValueError("Untrusted or absent original project source")
    return target


def _job_signature(scene, blender):
    from . import blender_scene,body_exr_passes
    source=Path(blender).resolve()
    stat=source.stat()
    try:version=importlib.metadata.version("OpenEXR")
    except importlib.metadata.PackageNotFoundError:version="unavailable"
    provenance={
        "scene_sha256":sha256_file(scene),
        "trusted_blender_scene_script_sha256":sha256_file(blender_scene.__file__),
        "exr_decoder_contract_sha256":sha256_file(body_exr_passes.__file__),
        "blender_executable":str(source),
        "blender_binary_size":stat.st_size,
        "blender_binary_mtime_ns":stat.st_mtime_ns,
        "OpenEXR_version":version
    }
    return hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()


def _store_state(path,state):
    temporary=path.with_name("." + path.name + ".uncommitted")
    # An interrupted process may leave a half-written temporary receipt.
    # The caller holds the exclusive original-render file lock, so this
    # namespaced temporary entry has no live writer. Ignore its untrusted
    # content and rebuild only from the LAST fully committed receipt.
    if temporary.is_symlink() or (temporary.exists() and not temporary.is_file()):
        raise ValueError("Untrusted original VFX checkpoint journal entry")
    if temporary.exists():
        temporary.unlink()
    try:
        with temporary.open("x",encoding="utf-8") as out:
            json.dump(state,out,sort_keys=True,indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary,path)
        directory_fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory_fd)
        finally:os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _frame_proof(frame,width,height):
    decoded=inspect_real_exr_frame(frame)
    if (decoded["width"],decoded["height"])!=(width,height):
        raise ValueError("Retained 32float original VFX pass dimensions changed")
    return {"sha256":sha256_file(frame),"bytes":frame.stat().st_size,
            "channels":decoded["actual_channel_names"]}


def _verified_frame(frame,prior,width,height):
    if not isinstance(prior,dict) or set(prior)!={"sha256","bytes","channels"}:
        return False
    if frame.is_symlink() or not frame.is_file() or frame.stat().st_size!=prior["bytes"]:
        return False
    if sha256_file(frame)!=prior["sha256"]:
        return False
    try:actual=_frame_proof(frame,width,height)
    except (ValueError,RuntimeError,OSError):
        return False
    return actual==prior


def render_resumable_exr_passes(scene_file,workspace,output,*,chunk_frames=1,
                                 runner=None):
    """Render original numbered frames and publish an independently verified ZIP.

    A process death after any frame retains only its verified independent EXR
    receipt; the remaining frame ranges are reconstructed. No speculative
    frame skipping: checksum AND native EXR decode AND exact tool/source
    signature are checked before each reuse.
    """
    root=Path(workspace).resolve()
    source=_file_scope(root,scene_file,require_file=True)
    dest=_file_scope(root,output,require_file=False)
    if dest.suffix.lower()!=".zip" or dest.exists() or dest.is_symlink():
        raise ValueError("Choose an unused genuine ZIP intermediate in original workspace")
    if type(chunk_frames) is not int or chunk_frames<1 or chunk_frames>1024:
        raise ValueError("A positive bounded render chunk count is required")
    if not shutil.which("blender") or importlib.util.find_spec("OpenEXR") is None:
        raise RuntimeError("Actual Blender CPU and native OpenEXR 3.3+ required")
    scene=json.loads(source.read_text(encoding="utf-8"))
    validate_blender_shot(scene)
    if any(obj["type"]=="licensed_glb" for obj in scene["objects"]):
        raise ValueError("Imported geometry must have verified independent GLB custody")
    count=scene["frames"]
    start_source_hash=sha256_file(source)
    executable=shutil.which("blender")
    signature=_job_signature(source,executable)

    parent=root/".zx7-frame-checkpoints"
    if parent.is_symlink():
        raise ValueError("Untrusted VFX checkpoint root symlink")
    parent.mkdir(mode=0o700,exist_ok=True)
    checkout=parent/hashlib.sha256(str(dest.relative_to(root)).encode()).hexdigest()
    if checkout.is_symlink():
        raise ValueError("Untrusted original checkpoint path")
    checkout.mkdir(mode=0o700,exist_ok=True)
    lock_path=checkout/"owner-render.lock"
    if lock_path.is_symlink():
        raise ValueError("Untrusted VFX execution lock")
    flags=os.O_CREAT|os.O_RDWR|getattr(os,"O_CLOEXEC",0)|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(lock_path,flags,0o600)
    private_scene_dir=None
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Original VFX frames are already rendering in another worker") from exc

        # Native Blender must never parse a mutable artist-working JSON file.
        # Pin a private, read-only byte-exact original scene as a single native
        # transaction input, even if a hostile worker temporarily swaps the
        # visible scene and restores it before the final source hash check.
        private_scene_dir=Path(tempfile.mkdtemp(
            prefix=".zx7-scene-seal-",dir=checkout))
        private_scene=private_scene_dir/"original-director-scene.json"
        with source.open("rb") as original,private_scene.open("xb") as frozen:
            shutil.copyfileobj(original,frozen,1024*1024)
            frozen.flush()
            os.fsync(frozen.fileno())
        if (sha256_file(private_scene)!=start_source_hash or
                sha256_file(source)!=start_source_hash):
            raise ValueError("Artist scene changed before immutable Blender source sealing")
        os.chmod(private_scene,0o400)
        state_path=checkout/"checkpoint.json"
        if state_path.is_symlink():
            raise ValueError("Untrusted checkpoint receipt link")
        if state_path.exists():
            state=json.loads(state_path.read_text(encoding="utf-8"))
            if (state.get("schema")!=_SCHEMA or state.get("job_signature")!=signature
                    or state.get("frame_count")!=count):
                raise ValueError("Old original scene/renderer differs; use a new film output revision")
            if not isinstance(state.get("frames"),dict):
                raise ValueError("Corrupted frame checkout index")
        else:
            state={"schema":_SCHEMA,"job_signature":signature,
                   "frame_count":count,"frames":{}}
            _store_state(state_path,state)

        frame_root=checkout/"frames"
        if frame_root.is_symlink():
            raise ValueError("Untrusted original VFX frame folder")
        frame_root.mkdir(mode=0o700,exist_ok=True)
        reused=[]
        rendered=[]
        pending=[]
        for index in range(1,count+1):
            name=_original_frame(index)
            path=frame_root/name
            if _verified_frame(path,state["frames"].get(str(index)),
                               scene["width"],scene["height"]):
                reused.append(index)
            else:
                pending.append(index)

        # Coalesce only consecutive missing frames into bounded physical
        # Blender jobs. Previously accepted frames are NEVER overwritten.
        while pending:
            group=[pending.pop(0)]
            while pending and pending[0]==group[-1]+1 and len(group)<chunk_frames:
                group.append(pending.pop(0))
            with tempfile.TemporaryDirectory(prefix="zx7-frames-",
                     dir=checkout) as scratch:
                command=[executable,"--background","--factory-startup",
                         "--python-exit-code","1","--python",
                         str(Path(__file__).parent/"blender_scene.py"),"--",
                         "--scene",str(private_scene),"--out",scratch,
                         "--exr-passes","--frame-start",str(group[0]),
                         "--frame-end",str(group[-1])]
                result=(runner or subprocess.run)(
                    command,check=True,timeout=7200,capture_output=True,text=True)
                if getattr(result,"returncode",0) not in (0,None):
                    raise RuntimeError("Original frame renderer did not complete")
                if sha256_file(private_scene)!=start_source_hash:
                    raise ValueError("Original sealed native 3D scene changed during Blender render")
                for index in group:
                    name=_original_frame(index)
                    made=Path(scratch)/name
                    if made.is_symlink() or not made.is_file():
                        raise RuntimeError("Blender failed original absolute frame "+str(index))
                    evidence=_frame_proof(made,scene["width"],scene["height"])
                    frame=frame_root/name
                    if frame.is_symlink():
                        raise ValueError("Untrusted existing partial EXR link")
                    # Atomically replace only previously *unverified* frames
                    # after decoded output has been accepted. This is a
                    # recovery path, never a rewrite of a published film.
                    os.replace(made,frame)
                    state["frames"][str(index)]=evidence
                    _store_state(state_path,state)
                    rendered.append(index)

        if (sha256_file(private_scene)!=start_source_hash or
                sha256_file(source)!=start_source_hash or
                _job_signature(source,executable)!=signature):
            raise ValueError("Artist scene or actual Blender version changed during live render")

        manifest={"schema":1,"shot_id":scene["shot_id"],
                  "scene_source_sha256":start_source_hash,
                  "width":scene["width"],"height":scene["height"],
                  "frames_per_second":scene["fps"],
                  "artist_frames_requested":count,
                  "actual_render_engine":"Blender Cycles CPU absolute frames",
                  "intermediate":"32-bit float scene-linear multilayer OpenEXR",
                  "ACES_transform_certified":False,
                  "human_artistic_quality_certified":False,
                  "checkpoint_frame_signature":signature,
                  "frames":[]}
        for i in range(1,count+1):
            frame=frame_root/_original_frame(i)
            data=state["frames"].get(str(i))
            if not _verified_frame(frame,data,scene["width"],scene["height"]):
                raise ValueError("Checkpoint frame failed second SHA and native EXR inspection")
            manifest["frames"].append({"file":"frames/"+_original_frame(i),
                                       **data})
        # Storage is checked before final original archive publication.
        dest.parent.mkdir(parents=True,exist_ok=True)
        available=shutil.disk_usage(dest.parent).free
        needed=sum(frame_root.joinpath(_original_frame(i)).stat().st_size
                   for i in range(1,count+1))
        if available<needed+16*1024*1024:
            raise RuntimeError("Not enough real disk for verified 32f pass archive")
        dest.parent.mkdir(parents=True,exist_ok=True)
        fd_,temp_name=tempfile.mkstemp(prefix=".zx7-frame-release-",
                                       suffix=".zip",dir=dest.parent)
        os.close(fd_)
        temporary=Path(temp_name)
        try:
            with zipfile.ZipFile(temporary,"w",compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=6,allowZip64=True) as zipped:
                for i in range(1,count+1):
                    name=_original_frame(i)
                    zipped.write(frame_root/name,arcname="frames/"+name)
                zipped.writestr("manifest.json",
                    json.dumps(manifest,sort_keys=True,indent=2)+"\n")
            actual=verify_exr_bundle(temporary)
            if actual["original_frame_count"]!=count:
                raise ValueError("Original film lost frames during output archive")
            if sha256_file(source)!=start_source_hash:
                raise ValueError("Director source scene changed before release")
            os.link(temporary,dest,follow_symlinks=False)
            folder_fd=os.open(dest.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(folder_fd)
            finally:os.close(folder_fd)
        finally:
            temporary.unlink(missing_ok=True)
        return {"path":str(dest),"sha256":sha256_file(dest),
                "bytes":dest.stat().st_size,"original_scene_sha256":start_source_hash,
                "actual_32bit_float_VFX_passes":True,
                "original_scene_frames":count,
                "verified_frame_reuse_count":len(reused),
                "newly_rendered_frame_count":len(rendered),
                "reused_absolute_frames":reused,
                "rendered_absolute_frames":rendered,
                "previous_frame_bytes_verified":True,
                "ACES_color_grade_proven":False,
                "distributed_worker_execution_proven":False,
                "human_artist_quality_approved":False}
    finally:
        try:
            if private_scene_dir is not None:
                shutil.rmtree(private_scene_dir)
        finally:
            fcntl.flock(fd,fcntl.LOCK_UN)
            os.close(fd)

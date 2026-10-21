"""Real executable ZX7 body tools for rights-cleared editable media projects.

The artist/model authors original film IR and chooses tools from discovery.
This trusted installed *body* provides reusable FFmpeg, ASWF OpenTimelineIO,
Inkscape design, actual media verification, archive and thumbnails as ops.

No preset scene count, style, transition, aspect ratio, duration, or genre.
No model-supplied Python, arbitrary shell command, network or spend permission.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import json
import shutil
from pathlib import Path

from .contracts import ToolSpec
from .registry import ToolCatalog
from .edit_timeline import render_edit,_path_within
from .editorial_interchange import export_editable_timeline
from .creative_asset_ops import rasterize_original_svg,extract_director_selected_frame
from .native_body_engines import render_original_blender,render_original_motion
from .delivery_audit import audit_delivered_movie,_probe_details
from .durable_graph import DurableFilmGraph,execute_durable_film_graph
from .media_vault import MediaVault,sha256_file
from .composite_mix import render_composition
from .body_plugins import discover_enabled_body_plugins


def _body_output(workspace,name,*,allowed=(".mp4",".otio",".png")):
    p=_path_within(workspace,name,exists=False)
    if p.suffix.lower() not in allowed:
        raise ValueError("Destination not a supported actual media artifact")
    if p.exists():
        raise FileExistsError("Do not overwrite existing accepted creative result")
    p.parent.mkdir(parents=True,exist_ok=True)
    return p


def _witness(file):
    f=Path(file)
    if not f.is_file() or f.stat().st_size<100:
        raise ValueError("No genuine digital media file produced")
    digest=sha256_file(f)
    out={"path":str(f.resolve()),"sha256":digest,"bytes":f.stat().st_size}
    if f.suffix.lower() in (".mp4",".mov",".mkv",".webm"):
        meta=_probe_details(f)
        out.update({"duration_seconds":meta["duration_seconds"],
                    "width":meta["width"],"height":meta["height"],
                    "audio_present":meta["audio_stream_present"]})
    elif f.suffix.lower()==".png":
        with f.open("rb") as blob:
            if blob.read(8)!=b"\x89PNG\r\n\x1a\n":
                raise ValueError("False image bytes cannot become thumbnail")
    return out


def _verify_witness(result):
    if not isinstance(result,dict) or "path" not in result or "sha256" not in result:
        return False
    p=Path(result["path"])
    if not p.is_file() or sha256_file(p)!=result["sha256"]:
        return False
    if p.suffix.lower() in (".mp4",".mov",".mkv",".webm"):
        observed=_probe_details(p)
        return (abs(observed["duration_seconds"]-result["duration_seconds"])<.08
                and observed["audio_stream_present"]==result["audio_present"])
    if p.suffix.lower()==".png":
        with p.open("rb") as stream:
            return stream.read(8)==b"\x89PNG\r\n\x1a\n"
    if p.suffix.lower()==".otio":
        try:
            import opentimelineio as otio
            movie=otio.adapters.read_from_file(str(p))
            return len(movie.video_tracks())>0
        except (ImportError,ValueError,RuntimeError,AttributeError):
            return False
    return False


def _trusted_body_revision(tool_id):
    """Per-tool code and installed executable revision, not a fixed schema label.

    Renderer implementation changes invalidate cached creative media only for
    that operation and downstream consumers of its physical output.
    """
    base=Path(__file__).resolve().parent
    dependencies={
        "body.inspect":["delivery_audit.py"],
        "body.render_edit":["edit_timeline.py"],
        "body.otio":["editorial_interchange.py"],
        "body.vector_png":["creative_asset_ops.py"],
        "body.film_thumbnail":["creative_asset_ops.py","delivery_audit.py"],
        "body.asset_vault":["media_vault.py"],
        "body.composite_mix":["composite_mix.py","media_vault.py"],
        "body.blender3d":["native_body_engines.py","blender_scene.py"],
        "body.motion2d":["native_body_engines.py","motion_bridge.py","font_registry.py"],
    }
    commands={
        "body.inspect":["ffprobe"],
        "body.render_edit":["ffmpeg","ffprobe"],
        "body.otio":[],
        "body.vector_png":["inkscape"],
        "body.film_thumbnail":["ffmpeg","ffprobe"],
        "body.asset_vault":[],
        "body.composite_mix":["ffmpeg","ffprobe"],
        "body.blender3d":["blender","ffmpeg"],
        "body.motion2d":["ffmpeg","ffprobe"],
    }
    known=dependencies.get(tool_id)
    if known is None:
        raise ValueError("No verified implementation dependencies for "+tool_id)
    h=hashlib.sha256()
    for item in ("body_integration.py",)+tuple(known):
        p=base/item
        h.update(item.encode())
        h.update(p.read_bytes())
    for cmd in commands[tool_id]:
        executable=shutil.which(cmd)
        if executable is None:
            raise ValueError("Cannot fingerprint missing actual creative renderer")
        file=Path(executable).resolve()
        stat=file.stat()
        h.update(json.dumps({"command":cmd,"binary_path":str(file),
              "size":stat.st_size,"mtime_ns":stat.st_mtime_ns},sort_keys=True).encode())
    return "sha256:"+h.hexdigest()


def body_catalog(workspace,*,vault_root=None):
    root=Path(workspace).resolve()
    vault=MediaVault(vault_root or (root/"vault"))
    catalog=ToolCatalog()

    def add(id,capability,description,access,ready,required,fn):
        catalog.register(ToolSpec(id,capability,description,access,
            status="installed" if ready else "needs_setup",
            license="various installed FOSS or verified asset provenance",
            resource="local machine",
            operation_schema={"required":required}),fn if ready else None,
            idempotent=True,
            implementation_revision=_trusted_body_revision(id) if ready else None)

    def inspect(inputs):
        path=_path_within(root,inputs["source"],exists=True)
        return _witness(path)

    def edit(inputs):
        original=_path_within(root,inputs["edit"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".mp4",))
        try:
            render_edit(original,root,output)
            return _witness(output)
        except BaseException:
            output.unlink(missing_ok=True)
            raise

    def export_edit(inputs):
        original=_path_within(root,inputs["edit"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".otio",))
        export_editable_timeline(original,root,output)
        return _witness(output)

    def vector_art(inputs):
        original=_path_within(root,inputs["source_svg"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".png",))
        rasterize_original_svg(original,output,width=inputs["width"],
                              height=inputs["height"])
        return _witness(output)

    def thumbnail(inputs):
        original=_path_within(root,inputs["source_film"],exists=True)
        target=_body_output(root,inputs["out"],allowed=(".png",))
        extract_director_selected_frame(original,target,at_seconds=inputs["time_seconds"])
        return _witness(target)

    def composite(inputs):
        source=_path_within(root,inputs["plan"],exists=True)
        out=_body_output(root,inputs["out"],allowed=(".mp4",))
        try:
            render_composition(source,root,vault.root,out)
            return _witness(out)
        except BaseException:
            out.unlink(missing_ok=True)
            raise

    def render3d(inputs):
        source=_path_within(root,inputs["scene_json"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        trusted_asset_root=_path_within(root,inputs["assets_root"],exists=False) if (
            isinstance(inputs.get("assets_root"),str) and inputs["assets_root"]) else None
        render_original_blender(source,dest,trusted_asset_root=trusted_asset_root)
        return _witness(dest)

    def render2d(inputs):
        source=_path_within(root,inputs["original_film_ir"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        voice_root=_path_within(root,inputs["voice_assets"],exists=False) if (
            isinstance(inputs.get("voice_assets"),str) and inputs["voice_assets"]) else None
        render_original_motion(source,dest,width=inputs["width"],fps=inputs["fps"],
                               trusted_voice_assets=voice_root)
        return _witness(dest)

    def vault_asset(inputs):
        source=_path_within(root,inputs["source"],exists=True)
        ref=vault.ingest(source,mime=inputs["mime"],rights=inputs["rights"],
                 source_type=inputs["source_type"],
                 source_id=inputs["source_id"],evidence=inputs["evidence"],
                 owner_or_generator=inputs["issuer"])
        # Transport as a verified reference, NOT by inventing an MP4 path.
        record=vault.inspect(ref["asset_id"],attestation_id=ref["attestation_id"])
        witness=_witness(record["path"]) if Path(record["path"]).suffix.lower() in (
            ".mp4",".mov",".mkv",".webm",".otio",".png") else {
                "path":record["path"],"sha256":ref["asset_id"]}
        witness.update({"asset_id":ref["asset_id"],"attestation_id":ref["attestation_id"],
                       "rights":ref["rights"]})
        return witness

    add("body.composite_mix","original timeline multilayer edit, licensed voices and audio mix",
        "Actual physical rights-verified layered FFmpeg compositor from model-owned canvas",
        "write",bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        ["plan","out"],composite)
    add("body.blender3d","physical 3D filmmaking","Blender real rendered geometries, materials and moving camera",
        "write",bool(shutil.which("blender") and shutil.which("ffmpeg")),
        ["scene_json","out"],render3d)
    add("body.motion2d","original 2D/2.5D animation","Independent vector character and motion compositor",
        "write",bool(shutil.which("ffmpeg")),["original_film_ir","out","width","fps"],render2d)
    add("body.inspect","measure physical media","FFprobe validates actual source video",
        "read",bool(shutil.which("ffprobe")),["source"],inspect)
    add("body.render_edit","editorial timeline","Headless FFmpeg actual movie assembler",
        "write",bool(shutil.which("ffmpeg")),["edit","out"],edit)
    try:import opentimelineio
    except ImportError:otio_ready=False
    else:otio_ready=True
    add("body.otio","editable edit interchange","Real Academy Software Foundation OpenTimelineIO",
        "write",otio_ready,["edit","out"],export_edit)
    add("body.vector_png","original vector art and thumbnail","Inkscape headless real vector to PNG",
        "write",bool(shutil.which("inkscape")),["source_svg","out","width","height"],vector_art)
    add("body.film_thumbnail","original movie frame artwork","FFmpeg decode actual selected frame",
        "write",bool(shutil.which("ffmpeg")),["source_film","out","time_seconds"],thumbnail)
    add("body.asset_vault","audited media provenance","Hash and preserve rights-cleared actual file",
        "write",True,["source","mime","rights","source_type","source_id","evidence","issuer"],
        vault_asset)
    for spec,runner,idempotent,version,operational in discover_enabled_body_plugins():
        if not operational:
            from dataclasses import replace
            spec=replace(spec,status="needs_setup")
        catalog.register(spec,runner,idempotent=idempotent,
                         implementation_revision=version if operational else None)
    return catalog


def validate_witness(_tool_id,result):
    """Physically revisit file and stored rights evidence on every resume."""
    if not isinstance(result,dict):
        return False
    if "asset_id" in result:
        digest=result.get("asset_id")
        att=result.get("attestation_id")
        if not isinstance(att,str) or digest!=result.get("sha256"):
            return False
        p=Path(result.get("path",""))
        if p.name!=digest or len(p.parents)<3:
            return False
        try:
            # CAS file has no extension because its name is a content digest.
            # Instead of trusting a model's mime, verify SQLite rights custody.
            vault=MediaVault(p.parents[2])
            stored=vault.inspect(digest,attestation_id=att)
            return (Path(stored["path"]).resolve()==p.resolve()
                    and stored["rights_attestations"][0]["rights"]==result.get("rights"))
        except (ValueError,IndexError,OSError):
            return False
    return _verify_witness(result)


def run_body_project(film_ir,workspace,*,db_name="production.sqlite3"):
    root=Path(workspace)
    catalog=body_catalog(root)
    store=DurableFilmGraph(root/db_name)
    actual_versions=catalog.committed_tool_revisions()
    idempotent=catalog.trusted_idempotent_ids()
    return execute_durable_film_graph(
       film_ir,catalog,fact_ids=set(film_ir.get("owner_facts",{})),
       store=store,output_verifier=validate_witness,
       trusted_idempotent_tools=idempotent,
       tool_revisions=actual_versions,allowed_access={"read","write"})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",type=Path,required=True)
    p.add_argument("--workspace",type=Path,required=True)
    a=p.parse_args()
    state=run_body_project(json.loads(a.project.read_text()),a.workspace)
    print(json.dumps(state,ensure_ascii=False,indent=2))
    if state["status"]!="all_tool_results_verified":
        raise SystemExit("Production body graph blocked or failed: "+str(state["errors"]))


if __name__=="__main__":main()

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
import importlib.metadata
import importlib.util
import os
import uuid
import json
import shutil
import zipfile
from pathlib import Path

from .contracts import ToolSpec
from .registry import ToolCatalog
from .edit_timeline import render_edit,_path_within
from .editorial_interchange import export_editable_timeline
from .body_sequence_otio import export_verified_sequence_otio,import_verified_sequence_otio
from .creative_asset_ops import rasterize_original_svg,extract_director_selected_frame
from .native_body_engines import render_original_blender,render_original_motion
from .delivery_audit import audit_delivered_movie,_probe_details
from .durable_graph import DurableFilmGraph,execute_durable_film_graph
from .media_vault import MediaVault,sha256_file,verify_media_container,MediaCustodyError
from .composite_mix import render_composition
from .film_finishing import finish_authorized_movie
from .body_color_pipeline import render_verified_color_job
from .body_exr_passes import render_original_exr_passes,verify_exr_bundle
from .body_aces2_preview import render_aces_2_sdr_preview
from .body_aces2_movie import render_aces2_scene_movie
from .body_frame_resume import render_resumable_exr_passes
from .precision_retime import render_retime
from .body_sequence_cuts import render_verified_sequence
from .body_timeline_revision import render_editorial_revision
from .body_owned_edit import render_verified_owned_edit,validate_owned_edit
from .production_qc import full_decode_inspection
from .body_loudness import inspect_original_loudness
from .body_observation import produce_review_bundle,verify_review_bundle
from .body_temporal_evidence import (
    observe_every_original_frame,verify_full_temporal_evidence)
from .body_review_access import read_verified_review,extract_verified_review_frame
from .body_review_compare import compare_verified_revisions
from .body_plugins import discover_enabled_body_plugins
from .body_tool_contracts import real_operation_schema
from .body_materials import fingerprint_physical_inputs
from .generative_video_providers import discover_local_generators
from .comfy_video_runtime import render_actual_generated_scene,validate_video_job
from .body_publication import (publication_record_exists, prepare_publication,
                               recover_publication, sync_published_file,
                               current_trusted_attempt_tool)


def _body_output(workspace,name,*,allowed=(".mp4",".otio",".png")):
    p=_path_within(workspace,name,exists=False)
    if p.suffix.lower() not in allowed:
        raise ValueError("Destination not a supported actual media artifact")
    if p.exists() and not publication_record_exists(p):
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
        verify_media_container(f,"image/png")
    elif f.suffix.lower()==".zip":
        verify_exr_bundle(f)
    elif f.suffix.lower()==".zxreview":
        verify_review_bundle(f)
    elif f.suffix.lower()==".json":
        verify_full_temporal_evidence(f)
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
    if p.suffix.lower()==".zip":
        try:
            return bool(verify_exr_bundle(p)["original_exr_passes_real"])
        except (ValueError,RuntimeError,OSError,zipfile.BadZipFile):
            return False
    if p.suffix.lower()==".zxreview":
        try:
            return bool(verify_review_bundle(p)["true_image_decoders_completed"])
        except (ValueError,RuntimeError,OSError,zipfile.BadZipFile):
            return False
    if p.suffix.lower()==".json":
        try:
            return bool(verify_full_temporal_evidence(p)["full_CFR_frame_evidence_valid"])
        except (ValueError,TypeError,KeyError,OSError,RuntimeError):
            return False
    if p.suffix.lower()==".png":
        try:
            verify_media_container(p,"image/png")
            return True
        except (OSError,ValueError,RuntimeError):
            return False
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
        "body.resolve_asset":["media_vault.py"],
        "body.render_edit":["edit_timeline.py"],
        "body.render_edit_owned":["body_owned_edit.py","edit_timeline.py","media_vault.py","production_qc.py"],
        "body.retime":["precision_retime.py","media_vault.py","delivery_audit.py","composite_mix.py","production_qc.py"],
        "body.sequence_cuts":["body_sequence_cuts.py","precision_retime.py","media_vault.py","body_color_pipeline.py","composite_mix.py","production_qc.py"],
        "body.timeline_revision":["body_timeline_revision.py","body_sequence_cuts.py","precision_retime.py","media_vault.py","body_color_pipeline.py","composite_mix.py","production_qc.py"],
        "body.otio":["editorial_interchange.py"],
        "body.otio_owned_export":["body_sequence_otio.py","body_sequence_cuts.py","media_vault.py","precision_retime.py","body_color_pipeline.py","composite_mix.py"],
        "body.otio_owned_import":["body_sequence_otio.py","body_sequence_cuts.py","media_vault.py","precision_retime.py","body_color_pipeline.py","composite_mix.py"],
        "body.vector_png":["creative_asset_ops.py"],
        "body.film_thumbnail":["creative_asset_ops.py","delivery_audit.py"],
        "body.asset_vault":["media_vault.py"],
        "body.composite_mix":["composite_mix.py","media_vault.py","production_qc.py"],
        "body.film_finish":["film_finishing.py","media_vault.py","composite_mix.py","production_qc.py"],
        "body.color_lut":["body_color_pipeline.py","media_vault.py","delivery_audit.py","composite_mix.py","production_qc.py"],
        "body.full_decode":["production_qc.py","delivery_audit.py"],
        "body.loudness":["body_loudness.py","media_vault.py","composite_mix.py"],
        "body.review":["body_observation.py","production_qc.py","media_vault.py"],
        "body.temporal_evidence":["body_temporal_evidence.py","composite_mix.py","precision_retime.py","body_observation.py","production_qc.py","media_vault.py"],
        "body.review_data":["body_review_access.py","body_observation.py"],
        "body.review_frame":["body_review_access.py","body_observation.py"],
        "body.review_compare":["body_review_compare.py","body_review_access.py","body_observation.py"],
        "body.generate_video":["comfy_video_runtime.py","generative_video_providers.py"],
        "body.blender3d":["native_body_engines.py","blender_scene.py"],
        "body.exr_passes":["body_exr_passes.py","blender_scene.py","media_vault.py"],
        "body.aces2_preview":["body_aces2_preview.py","body_exr_passes.py","media_vault.py"],
        "body.aces2_movie":["body_aces2_movie.py","body_aces2_preview.py","body_exr_passes.py","media_vault.py","production_qc.py"],
        "body.exr_checkpoint":["body_frame_resume.py","body_exr_passes.py","blender_scene.py","media_vault.py"],
        "body.motion2d":["native_body_engines.py","motion_bridge.py","font_registry.py",
                         "silent_audio.py","../motion_studio/render.py","../motion_studio/voice.py"],
    }
    commands={
        "body.inspect":["ffprobe"],
        "body.resolve_asset":[],
        "body.render_edit":["ffmpeg","ffprobe"],
        "body.render_edit_owned":["ffmpeg","ffprobe"],
        "body.retime":["ffmpeg","ffprobe"],
        "body.sequence_cuts":["ffmpeg","ffprobe"],
        "body.timeline_revision":["ffmpeg","ffprobe"],
        "body.otio":[],
        "body.otio_owned_export":["ffmpeg","ffprobe"],
        "body.otio_owned_import":["ffmpeg","ffprobe"],
        "body.vector_png":["inkscape"],
        "body.film_thumbnail":["ffmpeg","ffprobe"],
        "body.asset_vault":[],
        "body.composite_mix":["ffmpeg","ffprobe"],
        "body.film_finish":["ffmpeg","ffprobe"],
        "body.color_lut":["ffmpeg","ffprobe"],
        "body.full_decode":["ffmpeg","ffprobe"],
        "body.loudness":["ffmpeg","ffprobe"],
        "body.review":["ffmpeg","ffprobe"],
        "body.temporal_evidence":["ffmpeg","ffprobe"],
        "body.review_data":[],
        "body.review_frame":[],
        "body.review_compare":[],
        "body.generate_video":["ffprobe"],
        "body.blender3d":["blender","ffmpeg"],
        "body.exr_passes":["blender"],
        "body.aces2_preview":[],
        "body.aces2_movie":["ffmpeg","ffprobe"],
        "body.exr_checkpoint":["blender"],
        "body.motion2d":["ffmpeg","ffprobe"],
    }
    known=dependencies.get(tool_id)
    if known is None:
        raise ValueError("No verified implementation dependencies for "+tool_id)
    h=hashlib.sha256()
    for item in ("body_integration.py","body_publication.py","durable_sqlite.py",
                 "body_tool_contracts.py","registry.py")+tuple(known):
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
    runtime_libraries={"body.motion2d":("numpy","Pillow","fonttools","supertonic"),
                       "body.otio":("opentimelineio",),
                       "body.otio_owned_export":("opentimelineio",),
                       "body.otio_owned_import":("opentimelineio",),
                       "body.review":("Pillow",),
                       "body.temporal_evidence":("numpy",),
                       "body.review_data":("Pillow",),
                       "body.review_frame":("Pillow",),
                       "body.review_compare":("Pillow",),
                       "body.exr_passes":("OpenEXR",),
                       "body.aces2_preview":("OpenEXR","opencolorio","Pillow","numpy"),
                       "body.aces2_movie":("OpenEXR","opencolorio","numpy")}
    for library in runtime_libraries.get(tool_id,()):
        try:version=importlib.metadata.version(library)
        except importlib.metadata.PackageNotFoundError:version="not_installed"
        h.update(json.dumps({"library":library,"version":version},sort_keys=True).encode())
    return "sha256:"+h.hexdigest()


def _commit_actual_body_output(final_path,render):
    """Only expose fully encoded, *decoder verified* original media.

    Incomplete FFmpeg/Blender/graphics files never occupy the final accepted
    filename. An atomic same-filesystem hardlink refuses concurrent
    overwrites instead of clobbering an earlier director-approved result.
    """
    final_path=Path(final_path)
    recovered=recover_publication(final_path,witness=_witness,verify=_verify_witness)
    if recovered is not None:
        return recovered
    if final_path.exists():
        raise FileExistsError("Cannot overwrite original media output")
    stage=final_path.with_name(
        ".zx7-uncommitted-"+uuid.uuid4().hex+final_path.suffix)
    try:
        render(stage)
        preliminary=_witness(stage)
        if not _verify_witness(preliminary):
            raise RuntimeError("Staged creative media failed real decoder validation")
        prepare_publication(final_path,stage,preliminary)
        os.link(stage,final_path)
        # A journaled, physically verified film stays accepted even if the
        # final directory fsync reports a late error. Never unlink a public
        # destination that could have become another writer's approved movie.
        sync_published_file(final_path)
        return _witness(final_path)
    finally:
        # Only our private encoded staging file is ours to remove. A previous
        # hardlink publication has a durable receipt and remains recoverable.
        stage.unlink(missing_ok=True)


def body_catalog(workspace,*,vault_root=None):
    root=Path(workspace).resolve()
    vault=MediaVault(vault_root or (root/"vault"))
    catalog=ToolCatalog()
    video_io=bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    motion_libraries=all(importlib.util.find_spec(name) is not None
                         for name in ("numpy","PIL","fontTools"))
    png_decoder=bool(importlib.util.find_spec("PIL") is not None or shutil.which("ffmpeg"))

    def add(id,capability,description,access,ready,required,fn,*,idempotent=True):
        catalog.register(ToolSpec(id,capability,description,access,
            status="installed" if ready else "needs_setup",
            license="various installed FOSS or verified asset provenance",
            resource="local machine",
            operation_schema=real_operation_schema(id,required)),fn if ready else None,
            idempotent=idempotent,
            implementation_revision=_trusted_body_revision(id) if ready else None,
            material_fingerprint=(lambda inputs,name=id:
                fingerprint_physical_inputs(name,inputs,root)) if ready else None)

    def inspect(inputs):
        path=_path_within(root,inputs["source"],exists=True)
        return _witness(path)

    def resolve_owner_media(inputs):
        """One compact read tool resolves a verified CAS asset by real identity.

        The model neither picks arbitrary paths nor supplies license labels.
        Existing MediaVault rights witnesses are checked on each invocation.
        """
        inspected=vault.inspect(inputs["asset_id"],
                                attestation_id=inputs["attestation_id"])
        permitted=inspected["rights_attestations"][0]
        return {"path":inspected["path"],
                "sha256":inspected["asset_id"],
                "bytes":inspected["size_bytes"],
                "asset_id":inspected["asset_id"],
                "portable_uri":"zx7:sha256:"+inspected["asset_id"],
                "attestation_id":permitted["attestation_id"],
                "rights":permitted["rights"],
                "mime":inspected["mime"]}

    def edit(inputs):
        original=_path_within(root,inputs["edit"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".mp4",))
        return _commit_actual_body_output(
            output,lambda staged:render_edit(original,root,staged))

    def edit_attested(inputs):
        plan=_path_within(root,inputs["edit"],exists=True)
        target=_body_output(root,inputs["out"],allowed=(".mp4",))
        # Read independent input/source facts even when the output is recovered
        # directly from an atomic crash journal without calling the encoder.
        initial_sha=sha256_file(plan)
        authored=json.loads(plan.read_text(encoding="utf-8"))
        if sha256_file(plan)!=initial_sha:
            raise ValueError("Director cut changed while preflighting original inputs")
        original,source_hashes=validate_owned_edit(authored,root,vault.root)
        verification={}
        def produce(stage):
            if sha256_file(plan)!=initial_sha:
                raise ValueError("Director cut changed before original renderer")
            observed=render_verified_owned_edit(plan,root,vault.root,stage)
            verification.update(observed)
            if observed["plan_sha256"]!=initial_sha:
                raise ValueError("Verified rendering used a different director cut")
        receipt=_commit_actual_body_output(target,produce)
        # Crash recovery may reuse an existing exact movie. It must still
        # fully decode picture and soundtrack before accepting that film.
        if not verification:
            check=full_decode_inspection(target,expected={
                "width":authored["format"]["width"],
                "height":authored["format"]["height"],
                "require_audio":True})
            if not check["technical_delivery_verified"] or not check[
                    "full_picture_and_sound_decoder_completed"]:
                raise RuntimeError("Recovered owner movie failed full physical decode")
        if sha256_file(plan)!=initial_sha or any(
                sha256_file(path)!=digest for path,digest in source_hashes.items()):
            raise ValueError("Original proof changed while recovering or publishing")
        return {**receipt,"source_custody_count":len(original["clips"]),
                "distinct_originals":len(source_hashes),
                "director_plan_sha256":initial_sha,
                "original_footage_unchanged":True,
                "full_picture_and_sound_decoder_completed":True,
                "artistic_quality_certified":False}

    def retime_footage(inputs):
        plan=_path_within(root,inputs['plan'],exists=True)
        target=_body_output(root,inputs['out'],allowed=('.mp4',))
        return _commit_actual_body_output(target,
            lambda staged:render_retime(plan,root,vault.root,staged))

    def cut_owned_picture(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        return _commit_actual_body_output(dest,
             lambda stage:render_verified_sequence(plan,root,vault.root,stage))

    def revise_original_film(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        operation=_path_within(root,inputs["operation"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        evidence={}
        def encode(stage):
            evidence.update(render_editorial_revision(plan,operation,root,vault.root,stage))
        receipt=_commit_actual_body_output(dest,encode)
        return {**receipt, "revision_plan":evidence["revision_plan"],
                "revision_plan_sha256":evidence["revision_plan_sha256"],
                "prior_plan_sha256":evidence["prior_plan_sha256"],
                "director_operation_sha256":evidence["director_operation_sha256"],
                "operations":evidence["operations"],"reversible_original_media":True}

    def export_edit(inputs):
        original=_path_within(root,inputs["edit"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".otio",))
        return _commit_actual_body_output(
            output,lambda staged:export_editable_timeline(original,root,staged))

    def export_strict_cut(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        out=_body_output(root,inputs["out"],allowed=(".otio",))
        # The original path is an immutable artist plan. The physical OTIO
        # exporter itself proves every camera source, its license, and the
        # synchronized original audio in the actual native roundtrip.
        receipt=_commit_actual_body_output(out,lambda stage:
            export_verified_sequence_otio(plan,root,vault.root,stage))
        decoded=import_verified_sequence_otio(out,root,vault.root)
        authored=json.loads(plan.read_text(encoding="utf-8"))
        if (decoded["source_plan_sha256"]!=sha256_file(plan) or
                len(decoded["plan"]["clips"])!=len(authored["clips"])):
            raise ValueError("Recovered OTIO does not match director-owned edit")
        return {**receipt,
            "verified_original_frames":decoded["frame_count"],
            "original_audio_kept_synchronized":True,
            "full_nle_creative_quality_approved":False}

    def import_strict_cut(inputs):
        edit=_path_within(root,inputs["edit"],exists=True)
        out=_body_output(root,inputs["out"],allowed=(".json",))
        imported=import_verified_sequence_otio(edit,root,vault.root)
        contents=(json.dumps(imported["plan"],sort_keys=True,
                  ensure_ascii=False,separators=(",",":"))+"\n").encode("utf-8")
        if out.exists():raise FileExistsError("Original approved director edit cannot be overwritten")
        temp=out.with_name(".zx7-otio-import-"+uuid.uuid4().hex+".json")
        try:
            with temp.open("xb") as dst:
                dst.write(contents)
                dst.flush()
                os.fsync(dst.fileno())
            if sha256_file(temp)!=hashlib.sha256(contents).hexdigest():
                raise ValueError("Original industry edit changed while publishing")
            os.link(temp,out)
        finally:
            temp.unlink(missing_ok=True)
        return {"path":str(out),"sha256":sha256_file(out),
                "bytes":len(contents),"verified_original_frames":imported["frame_count"],
                "synchronous_sound_source_verified":True,
                "industry_otio_edit_preserved_without_silent_drop":True,
                "creative_quality_approved":False}

    def vector_art(inputs):
        original=_path_within(root,inputs["source_svg"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".png",))
        return _commit_actual_body_output(
            output,lambda staged:rasterize_original_svg(original,staged,
                width=inputs["width"],height=inputs["height"]))

    def thumbnail(inputs):
        original=_path_within(root,inputs["source_film"],exists=True)
        target=_body_output(root,inputs["out"],allowed=(".png",))
        return _commit_actual_body_output(
            target,lambda staged:extract_director_selected_frame(original,
                staged,at_seconds=inputs["time_seconds"]))

    def composite(inputs):
        source=_path_within(root,inputs["plan"],exists=True)
        out=_body_output(root,inputs["out"],allowed=(".mp4",))
        return _commit_actual_body_output(
            out,lambda staged:render_composition(source,root,vault.root,staged))

    def finish_movie(inputs):
        source=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        return _commit_actual_body_output(
            dest,lambda staged:finish_authorized_movie(
                source,root,vault.root,staged))

    def color_grade_movie(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",".mov"))
        return _commit_actual_body_output(dest,
             lambda staged:render_verified_color_job(plan,root,vault.root,staged))

    def review_actual_film(inputs):
        original=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".zxreview",))
        return _commit_actual_body_output(dest,
            lambda staged:produce_review_bundle(original,root,vault.root,staged))

    def temporal_all_frames(inputs):
        original=_path_within(root,inputs["plan"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".json",))
        receipt=_commit_actual_body_output(dest,
            lambda staged:observe_every_original_frame(
                original,root,vault.root,staged))
        actual=verify_full_temporal_evidence(dest)
        # On a verified crash-recovery hit the renderer does not run again.
        # Read the existing decoded source-bound evidence, never fabricate a
        # model-visible sound/full-frame status from a stale Python variable.
        return {**receipt,
                "actual_full_movie_frame_count":
                    actual["observed_original_picture_frames"],
                "original_movie_sha256":actual["source_sha256"],
                "original_sound_physically_measured":
                    actual["original_sound_physically_measured"],
                "original_sound_covers_entire_picture":
                    actual["original_sound_covers_entire_picture"],
                "creative_quality_certified":False}

    def aces_review_frame(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".png",))
        return _commit_actual_body_output(output,
            lambda staged:render_aces_2_sdr_preview(
                plan,root,vault.root,staged))

    def aces_native_scene_movie(inputs):
        plan=_path_within(root,inputs["plan"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".mov",))
        return _commit_actual_body_output(output,
            lambda staged:render_aces2_scene_movie(
                plan,root,vault.root,staged))

    def review_data(inputs):
        archive=_path_within(root,inputs["bundle"],exists=True)
        return read_verified_review(archive,inputs["bundle_sha256"],root)

    def review_compare(inputs):
        prior=_path_within(root,inputs["before_bundle"],exists=True)
        after=_path_within(root,inputs["after_bundle"],exists=True)
        return compare_verified_revisions(prior,inputs["before_sha256"],
                 after,inputs["after_sha256"],root)

    def review_frame(inputs):
        archive=_path_within(root,inputs["bundle"],exists=True)
        output=_body_output(root,inputs["out"],allowed=(".png",))
        return _commit_actual_body_output(output,
            lambda staged:extract_verified_review_frame(
                archive,inputs["bundle_sha256"],root,inputs["frame_index"],staged))

    def physical_audio_loudness(inputs):
        original=_path_within(root,inputs["plan"],exists=True)
        return inspect_original_loudness(original,root,vault.root)

    def deep_media_qc(inputs):
        """Decode every actual video/audio stream, not just inspect metadata."""
        source=_path_within(root,inputs["source"],exists=True)
        report=full_decode_inspection(source,expected=inputs.get("expected"))
        if not report["technical_delivery_verified"]:
            raise RuntimeError("Full original media failed actual decode or director specifications: "+
                               str(report["delivery_mismatches"]))
        # The standard tool-result witness is also rechecked on every restart.
        return report

    def generate_genuine_video(inputs):
        """Only a real approved local GPU model may execute an authored shot.

        The director owns text, frame timing, camera/acting, aspect and seed.
        The model-specific Comfy graph is supplied by audited host installer;
        no raw model Python, web URLs or arbitrary shell commands are allowed.
        """
        source=_path_within(root,inputs["video_job"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        job=validate_video_job(json.loads(source.read_text(encoding="utf-8")))
        local_endpoint=os.getenv("ZX7_COMFY_API")
        local_weights=os.getenv("ZX7_VIDEO_DEPLOYMENTS","models/creative-video")
        stable_sha=hashlib.sha256(source.read_bytes()).hexdigest()[:32]
        physical_job_folder=root/"_real_generated_jobs"/stable_sha
        actual=render_actual_generated_scene(
            job,physical_job_folder,deployment_root=local_weights,
            comfy_endpoint=local_endpoint)
        filmed=Path(actual["clip"])
        if not filmed.is_file():
            raise RuntimeError("Real video diffusion tool supplied no source footage")
        return _commit_actual_body_output(
            dest,lambda staged:shutil.copyfile(filmed,staged))

    def render_checkpointed_exr(inputs):
        scene=_path_within(root,inputs["scene_json"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".zip",))
        evidence=render_resumable_exr_passes(scene,root,dest)
        # Verified zip/physical EXR scene frames, not arbitrary bytes.
        result=_witness(dest)
        if not _verify_witness(result):
            raise ValueError("Rendered EXR stage failed native release verification")
        result.update({"actual_32bit_float_VFX_passes":True,
                       "verified_frame_reuse_count":evidence["verified_frame_reuse_count"],
                       "newly_rendered_frame_count":evidence["newly_rendered_frame_count"],
                       "original_scene_sha256":evidence["original_scene_sha256"],
                       "human_artist_quality_approved":False,
                       "distributed_worker_execution_proven":False})
        return result

    def render3d(inputs):
        source=_path_within(root,inputs["scene_json"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        trusted_asset_root=_path_within(root,inputs["assets_root"],exists=False) if (
            isinstance(inputs.get("assets_root"),str) and inputs["assets_root"]) else None
        return _commit_actual_body_output(
            dest,lambda staged:render_original_blender(
                source,staged,trusted_asset_root=trusted_asset_root))

    def render_scene_linear_exr(inputs):
        scene=_path_within(root,inputs["scene_json"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".zip",))
        asset_root=_path_within(root,inputs["assets_root"],exists=False) if (
            isinstance(inputs.get("assets_root"),str) and inputs["assets_root"]) else None
        return _commit_actual_body_output(dest,lambda staged:
            render_original_exr_passes(scene,root,staged,assets_root=asset_root))

    def render2d(inputs):
        source=_path_within(root,inputs["original_film_ir"],exists=True)
        dest=_body_output(root,inputs["out"],allowed=(".mp4",))
        voice_root=_path_within(root,inputs["voice_assets"],exists=False) if (
            isinstance(inputs.get("voice_assets"),str) and inputs["voice_assets"]) else None
        return _commit_actual_body_output(
            dest,lambda staged:render_original_motion(source,staged,
                width=inputs["width"],fps=inputs["fps"],
                trusted_voice_assets=voice_root))

    def vault_asset(inputs):
        """Only a validated output from an actually installed production node.

        Model text cannot assert that an arbitrary web image or private file
        has owner-supplied/generated/legal rights. This operation admits only
        graph-bound, physically decoded output of a trusted registered maker.
        Other rights classes require an authenticated external ingestion API.
        """
        if not isinstance(inputs,dict) or set(inputs)!={"source_witness"}:
            raise ValueError("Generated media custody requires only a trusted producer output")
        if current_trusted_attempt_tool()!="body.asset_vault":
            raise PermissionError("Only the verified durable producer DAG may issue generated-media provenance")
        proof=inputs["source_witness"]
        if not _verify_witness(proof):
            raise ValueError("No physically proven producer output for media custody")
        source=Path(proof["path"]).resolve()
        if not source.is_relative_to(root):
            raise ValueError("Only genuine media from this original workspace")
        supported={".mp4":"video/mp4",".png":"image/png",
                   ".mov":"video/quicktime",".webm":"video/webm",
                   ".zip":"application/x-zx7-exr-bundle"}
        mime=supported.get(source.suffix.lower())
        if mime is None:
            raise ValueError("Unrecognized verified tool output cannot be laundered into licensed media")
        ref=vault.ingest(source,mime=mime,rights="generated_original",
                  source_type="trusted_renderer",source_id=proof["sha256"],
                  evidence="Verified original media from a registered trusted executable",
                  owner_or_generator="zx7-authorized-body-graph")
        record=vault.inspect(ref["asset_id"],attestation_id=ref["attestation_id"])
        return {"path":record["path"],"sha256":ref["asset_id"],
                "asset_id":ref["asset_id"],"attestation_id":ref["attestation_id"],
                "rights":ref["rights"]}

    # This is a dormant native capability until REAL local GPU, licensed
    # checkpoint components and a live self-hosted graph are verified.
    # A model is never told it can make cinematic live-action from CPU-only tools.
    endpoint=os.getenv("ZX7_COMFY_API")
    available=discover_local_generators(
        comfy_endpoint=endpoint,
        deployed_root=os.getenv("ZX7_VIDEO_DEPLOYMENTS","models/creative-video"))
    native_video_ready=bool(shutil.which("ffprobe") and any(
        x["ready_for_independent_execution_trial"]
        for x in available["video_generation_options"]))
    add("body.generate_video","actual self-hosted text-to-video cinematography",
        "Director-authored actor/camera/action prompt executed by locally verified GPU diffusion model",
        "write",native_video_ready,["video_job","out"],
        generate_genuine_video,idempotent=False)
    add("body.review_compare","physically compare actual original film picture and audio revision evidence",
        "SHA verified matching native decoded PNG timecodes and observed dBFS windows; no fake artist score",
        "read",bool(importlib.util.find_spec("PIL") is not None),
        ["before_bundle","before_sha256","after_bundle","after_sha256"],review_compare)
    add("body.review_data","read actual original film picture and soundtrack review measurements",
        "Trusted decoder-validated source/timestamp/pixel/audio evidence; no invented creative judgement",
        "read",bool(importlib.util.find_spec("PIL") is not None),
        ["bundle","bundle_sha256"],review_data)
    add("body.review_frame","extract one actually decoded original film review picture",
        "Only exact SHA256-bound review archives and selected original PNG frames allowed",
        "write",bool(importlib.util.find_spec("PIL") is not None),
        ["bundle","bundle_sha256","frame_index","out"],review_frame)
    add("body.review","actual original movie picture+sound observations for creative revision",
        "Fully decoded licensed original; director-selected PNG frames, image differences, audio-window dBFS and SHA-bound portable review package",
        "write",bool(shutil.which("ffmpeg") and shutil.which("ffprobe") and
                     importlib.util.find_spec("PIL") is not None),
        ["plan","out"],review_actual_film)
    add("body.temporal_evidence","whole original film frame-by-frame physical evidence",
        "Rights-attested native exact-CFR every-frame RGB metrics and actually decoded soundtrack; no inferred scene meaning",
        "write",bool(shutil.which("ffmpeg") and shutil.which("ffprobe")
                     and importlib.util.find_spec("numpy") is not None),
        ["plan","out"],temporal_all_frames)
    add("body.loudness","measure actual first soundtrack LUFS, LRA and measured true-peak",
        "Read-only native FFmpeg EBU R128 measurement of original rights-cleared movie, no forced mastering targets",
        "read",bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        ["plan"],physical_audio_loudness)
    add("body.full_decode","physical full-movie delivery quality assurance",
        "Actually decode entire picture/sound; preserve deliberate creative style",
        "read",bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        ["source"],deep_media_qc)
    add("body.color_lut","original licensed 3D color LUT and protected soundtrack",
        "Live FFmpeg exact BT.709 3D-CUBE transform; 8-bit viewing or 10-bit ProRes master",
        "write",video_io,["plan","out"],color_grade_movie)
    add("body.film_finish","measured film color grade and sound finishing",
        "Local FFmpeg real picture operations and original audio loudness mastering",
        "write",bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        ["plan","out"],finish_movie)
    add("body.composite_mix","original timeline multilayer edit, licensed voices and audio mix",
        "Actual physical rights-verified layered FFmpeg compositor from model-owned canvas",
        "write",bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        ["plan","out"],composite)
    add("body.exr_checkpoint","durable original-frame 32float VFX render and exact verified resume",
        "Original Blender Cycles CPU shot with per-frame EXR hash+decoder checkpoints; never a GPU farm",
        "write",bool(shutil.which("blender") and
                      importlib.util.find_spec("OpenEXR") is not None),
        ["scene_json","out"],render_checkpointed_exr)
    add("body.aces2_movie","actual owned ACES2 scene-linear EXR to 10bit SDR movie",
        "Every licensed native RGBA frame receives pinned OCIO2.5 ACES2 view on 16-bit RGB and real ProRes422 10bit encoding; SDR VFX review without audio, not HDR or aesthetic certification",
        "write",bool(shutil.which("ffmpeg") and shutil.which("ffprobe") and
                     importlib.util.find_spec("OpenEXR") and
                     importlib.util.find_spec("PyOpenColorIO") and
                     importlib.util.find_spec("numpy")),
        ["plan","out"],aces_native_scene_movie)
    add("body.aces2_preview","pinned ASWF ACES 2.0 scene-linear to SDR review",
        "Actual OpenEXR float RGBA, rights-attested source, built-in OCIO 2.5 ACES2 display view and independently decoded PNG; review only",
        "write",bool(importlib.util.find_spec("OpenEXR") and
                     importlib.util.find_spec("PyOpenColorIO") and
                     importlib.util.find_spec("PIL") and
                     importlib.util.find_spec("numpy")),
        ["plan","out"],aces_review_frame)
    add("body.exr_passes","real 32bit scene-linear multilayer 3D VFX passes",
        "Blender Cycles CPU verified RGBA/depth/vector/normal EXR frames in immutable bundle",
        "write",bool(shutil.which("blender") and
                      importlib.util.find_spec("OpenEXR") is not None),
        ["scene_json","out"],render_scene_linear_exr)
    add("body.blender3d","physical 3D filmmaking","Blender real rendered geometries, materials and moving camera",
        "write",bool(shutil.which("blender") and video_io),
        ["scene_json","out"],render3d)
    add("body.motion2d","original 2D/2.5D animation","Independent vector character and motion compositor",
        "write",bool(video_io and motion_libraries),["original_film_ir","out","width","fps"],render2d)
    add("body.resolve_asset","verify and locate original licensed media by content identity",
        "Reads actual SHA256 CAS blob and its exact stored owner license attestation",
        "read",True,["asset_id","attestation_id"],resolve_owner_media)
    add("body.inspect","measure physical media","FFprobe validates actual source video",
        "read",bool(shutil.which("ffprobe")),["source"],inspect)
    add("body.render_edit","legacy editorial timeline (unattested rights label)",
        "Legacy technical rendering only: a plan's rights string is NOT custody evidence. Use body.render_edit_owned for attested source footage.",
        "write",video_io,["edit","out"],edit)
    add("body.render_edit_owned","source-attested independent mixed-source editing",
        "Exact existing MediaVault content and owner-license attestation for every clip, original fit/fill and independent source sound, physically rendered and verified",
        "write",video_io,["edit","out"],edit_attested)
    add("body.sequence_cuts","precise multishot original rights-attested picture and audio edit",
        "Real verified BT.709 CFR sources, original frame spans, independent sound custody, no unlicensed guessed footage",
        "write",video_io,["plan","out"],cut_owned_picture)
    add("body.timeline_revision","independent exact-frame professional NLE cut modifications",
        "Original rights-verified ripple trim, roll, slip, slide, split and reorder; immutable history; encoded source sound",
        "write",video_io,["plan","operation","out"],revise_original_film)
    add("body.retime","frame-accurate retime and soundtrack sync",
        "Original frame-index speed changes; real rights-checked source and pitch-preserving sound",
        "write",video_io,["plan","out"],retime_footage)
    try:import opentimelineio
    except ImportError:otio_ready=False
    else:otio_ready=True
    add("body.otio","legacy editable edit interchange (unattested source labels)",
        "OpenTimelineIO technical interchange; source license labels are NOT independent custody proof",
        "write",bool(otio_ready and shutil.which("ffprobe")),["edit","out"],export_edit)
    add("body.otio_owned_export","exact-frame source-attested audiovisual OTIO export",
        "Original licensed CFR BT.709 picture and independently synchronized sound, real native OTIO roundtrip verified",
        "write",bool(otio_ready and video_io),["plan","out"],export_strict_cut)
    add("body.otio_owned_import","physically verified original audiovisual OTIO revision import",
        "Strict professional edited OTIO into immutable new JSON director-cut plan; rejects lost/relinked audio/rights",
        "write",bool(otio_ready and video_io),["edit","out"],import_strict_cut)
    add("body.vector_png","original vector art and thumbnail","Inkscape headless real vector to PNG",
        "write",bool(shutil.which("inkscape") and png_decoder),["source_svg","out","width","height"],vector_art)
    add("body.film_thumbnail","original movie frame artwork","FFmpeg decode actual selected frame",
        "write",video_io,["source_film","out","time_seconds"],thumbnail)
    add("body.asset_vault","audited generated-media provenance",
        "Custody is accepted only from an actually verified trusted renderer node",
        "write",True,["source_witness"],vault_asset)
    for spec,runner,idempotent,version,operational,materials in discover_enabled_body_plugins():
        if not operational:
            from dataclasses import replace
            spec=replace(spec,status="needs_setup")
        catalog.register(spec,runner,idempotent=idempotent,
                         implementation_revision=version if operational else None,
                         material_fingerprint=materials if operational else None)
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


def _require_authentic_generated_media_lineage(film_ir):
    """Reject model-supplied rights labels and fake producer objects up front."""
    graph=film_ir.get("tool_graph",[]) if isinstance(film_ir,dict) else []
    if not isinstance(graph,list):
        raise ValueError("Real body graph required for custody validation")
    node_by_id={n["id"]:n for n in graph if isinstance(n,dict) and isinstance(n.get("id"),str)}
    # A legacy rights label, raw SVG, or extracted image cannot manufacture
    # generated-original rights. Only trusted originating renderers or editors
    # which themselves require MediaVault source custody may be archived.
    trusted_producers={"body.blender3d","body.motion2d",
                       "body.exr_passes","body.exr_checkpoint",
                       "body.aces2_movie",
                       "body.render_edit_owned",
                       "body.composite_mix","body.film_finish"}
    for node in graph:
        if not isinstance(node,dict) or node.get("tool_id")!="body.asset_vault":
            continue
        inputs=node.get("inputs")
        refs=node.get("depends_on",[])
        if not isinstance(inputs,dict) or set(inputs)!={"source_witness"} or (
                not isinstance(refs,list) or len(refs)!=1 or refs[0] not in node_by_id or
                node_by_id[refs[0]].get("tool_id") not in trusted_producers or
                inputs["source_witness"]!={"$node_output":refs[0]}):
            raise ValueError("LLM cannot invent license/source claims; vault requires exact trusted renderer dependency")


def run_body_project(film_ir,workspace,*,db_name="production.sqlite3",boundary_control=None):
    _require_authentic_generated_media_lineage(film_ir)
    root=Path(workspace)
    catalog=body_catalog(root)
    store=DurableFilmGraph(root/db_name)
    actual_versions=catalog.committed_tool_revisions()
    idempotent=catalog.trusted_idempotent_ids()
    return execute_durable_film_graph(
       film_ir,catalog,fact_ids=set(film_ir.get("owner_facts",{})),
       store=store,output_verifier=validate_witness,
       trusted_idempotent_tools=idempotent,
       tool_revisions=actual_versions,
       input_material_fingerprint=catalog.trusted_material_fingerprint,
       boundary_control=boundary_control,
       allowed_access={"read","write"})


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

"""Exact, owned full-CFR-frame physical film observation for model directors.

This instrument decodes *every* frame of a bounded original clip into an
independent small RGB review plane, and the actual source soundtrack into a
measured dBFS receipt. The evidence is technical, not cinematic taste,
continuity semantics, a high-quality proxy, or scene-linear HDR grading.
Unverified rights, VFR, partial frame data and late source changes fail shut.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

from .composite_mix import _exact_media, sealed_attested_original
from .delivery_audit import _probe_details
from .body_observation import _snapshot_window
from .media_vault import MediaVault, sha256_file
from .precision_retime import _source_timebase
from .production_qc import full_decode_inspection

_MAX_FRAMES=5000
_MAX_PIXEL_SAMPLES=10240


def observe_every_original_frame(plan_file, workspace, vault_root, destination):
    """Create SHA-bound factual per-frame/whole-audio evidence; no edit decisions."""
    import numpy as np

    root=Path(workspace).resolve()
    document=Path(plan_file).resolve()
    dest=Path(destination).resolve()
    if (not document.is_relative_to(root) or not document.is_file()
            or document.is_symlink() or not dest.is_relative_to(root)
            or dest.suffix.lower()!=".json" or dest.exists() or dest.is_symlink()
            or dest==document):
        raise ValueError("Film sensing requires existing owned plan and unused JSON result")
    before=sha256_file(document)
    plan=json.loads(document.read_text(encoding="utf-8"))
    if (not isinstance(plan,dict) or set(plan)!={"media","preview"}
            or not isinstance(plan["media"],dict)
            or set(plan["media"])!={"source","asset_id","attestation_id"}
            or not isinstance(plan["preview"],dict)
            or set(plan["preview"])!={"width","height"}):
        raise ValueError("Film sensor requires exact source rights and preview pixel shape")
    width=plan["preview"]["width"]
    height=plan["preview"]["height"]
    if (type(width) is not int or type(height) is not int
            or not 8<=width<=160 or not 8<=height<=160
            or width*height>_MAX_PIXEL_SAMPLES):
        raise ValueError("Original temporal review exceeds bounded RGB pixel budget")

    vault=MediaVault(vault_root)
    original=_exact_media(plan["media"],vault,root,need="video")
    original_sha=sha256_file(original)
    if original_sha!=plan["media"]["asset_id"] or sha256_file(document)!=before:
        raise ValueError("Original movie or director source plan changed")
    dest.parent.mkdir(parents=True,exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".zx7-temporal-",dir=root) as private:
        private=Path(private)
        pinned=sealed_attested_original(vault,
            plan["media"]["asset_id"],plan["media"]["attestation_id"],private,{})
        rate,total_frames=_source_timebase(pinned)
        if not 1<=total_frames<=_MAX_FRAMES:
            raise ValueError("Exact entire movie exceeds bounded original review stage; segment authored film")
        detail=_probe_details(pinned)
        decoded=full_decode_inspection(pinned,expected={
            "width":detail["width"],"height":detail["height"],
            "require_audio":detail["audio_stream_present"]})
        if (not decoded["technical_delivery_verified"] or
                not decoded["full_picture_and_sound_decoder_completed"]):
            raise ValueError("Full original picture/sound decode did not succeed")

        # CFR physical source count is proven by _source_timebase, independent
        # of the raw RGB plane used here. No dropped/duplicated frame accepted.
        argv=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-xerror",
              "-i",str(pinned),"-map","0:v:0","-an","-sn",
              "-vf",f"scale={width}:{height}:flags=area,format=rgb24",
              "-vsync","0","-f","rawvideo","pipe:1"]
        encoded=subprocess.run(argv,capture_output=True,timeout=600,check=False)
        frame_bytes=width*height*3
        if encoded.returncode!=0 or len(encoded.stdout)!=total_frames*frame_bytes:
            raise ValueError("Every original physical frame must be decoded exactly once")
        images=np.frombuffer(encoded.stdout,dtype=np.uint8).reshape(
            (total_frames,height,width,3))
        records=[]
        previous=None
        for index,pixels in enumerate(images):
            # Simple display-referred 8-bit RGB; no false scene/color claim.
            luma=(pixels[...,0].astype(np.float32)*.2126+
                  pixels[...,1].astype(np.float32)*.7152+
                  pixels[...,2].astype(np.float32)*.0722)
            delta=None if previous is None else float(np.mean(np.abs(
                luma-previous),dtype=np.float64))
            records.append({
                "frame_index":index,
                "time_seconds":round(index*rate.denominator/rate.numerator,7),
                "mean_luma_8bit":round(float(np.mean(luma)),4),
                "previous_frame_mean_abs_luma_delta_8bit":(
                    None if delta is None else round(delta,4)),
            })
            previous=luma
        if not records or records[0]["previous_frame_mean_abs_luma_delta_8bit"] is not None:
            raise ValueError("Original full-frame evidence was not properly initialized")
        soundtrack=None
        if detail["audio_stream_present"]:
            soundtrack=_snapshot_window(pinned,0.0,
                float(total_frames*rate.denominator/rate.numerator))
        if (sha256_file(pinned)!=original_sha or
                sha256_file(original)!=original_sha or
                sha256_file(document)!=before):
            raise ValueError("Original input bytes or film plan changed during physical review")
        for key in ("asset_id","attestation_id"):
            if not isinstance(plan["media"][key],str):
                raise ValueError("Malformed registered original film custody")
        vault.inspect(plan["media"]["asset_id"],
                      attestation_id=plan["media"]["attestation_id"])
        report={
            "schema":1,"original_movie_sha256":original_sha,
            "source_rights_attestation_id":plan["media"]["attestation_id"],
            "director_review_plan_sha256":before,
            "picture_frames_observed":total_frames,
            "video_frame_rate":{"numerator":rate.numerator,"denominator":rate.denominator},
            "preview_rgb_width":width,"preview_rgb_height":height,
            "complete_original_video_and_sound_decoded":True,
            "original_sound_present":detail["audio_stream_present"],
            "measured_soundtrack_dbfs":soundtrack,
            "frames":records,
            "frame_differences_are_not_optical_flow_or_meaning":True,
            "display_8bit_review_not_ocio_aces_or_hdr_mastering":True,
            "creative_quality_or_continuity_certified":False,
        }
        raw=(json.dumps(report,ensure_ascii=False,sort_keys=True,
                        separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")
        staged=private/"verified-original-temporal.json"
        with staged.open("xb") as fp:
            fp.write(raw)
            fp.flush()
            os.fsync(fp.fileno())
        if (sha256_file(original)!=original_sha or
                sha256_file(document)!=before or sha256_file(pinned)!=original_sha):
            raise ValueError("Original source identity changed before sensory publication")
        # A racing producer may have already accepted the output. Never write,
        # overwrite, unlink or truncate a third party's reported evidence.
        os.link(staged,dest)
    return {"path":str(dest),"sha256":sha256_file(dest),
            "bytes":dest.stat().st_size,
            "original_movie_sha256":original_sha,
            "actual_full_movie_frame_count":total_frames,
            "original_sound_physically_measured":soundtrack is not None,
            "creative_quality_certified":False}

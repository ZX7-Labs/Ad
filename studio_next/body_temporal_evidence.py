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

from .composite_mix import (
    _exact_media, sealed_attested_original, _decoded_source_duration)
from .delivery_audit import _probe_details
from .body_observation import _snapshot_window
from .media_vault import MediaVault, sha256_file
from .precision_retime import _source_timebase
from .production_qc import full_decode_inspection

_MAX_FRAMES=5000
_MAX_PIXEL_SAMPLES=10240
_KIND="ZX7_SOURCE_BOUND_FULL_CFR_TEMPORAL_V1"


def verify_full_temporal_evidence(file):
    """Read back exact frame clock, numeric measurements and custody fields.

    This cannot replay original media without its separate vault. The producer
    proves the actual decoded picture/sound; this validator refuses mutated
    or implausible durable output instead of accepting arbitrary JSON files.
    """
    path=Path(file)
    if not path.is_file() or path.stat().st_size>8*1024*1024:
        raise ValueError("Untrusted temporal review evidence size")
    report=json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(report,dict) or report.get("kind")!=_KIND
            or report.get("schema")!=1
            or report.get("complete_original_video_and_sound_decoded") is not True
            or report.get("creative_quality_or_continuity_certified") is not False):
        raise ValueError("Not a verified native whole-movie original observation")
    import re
    hex_digest=lambda x:isinstance(x,str) and re.fullmatch(r"[0-9a-f]{64}",x)
    if not hex_digest(report.get("original_movie_sha256")) or not hex_digest(
            report.get("director_review_plan_sha256")):
        raise ValueError("Actual original source and review-plan fingerprints required")
    if (not isinstance(report.get("source_rights_attestation_id"),str)
            or not report["source_rights_attestation_id"]):
        raise ValueError("Original reviewer has no source rights authority")
    clock=report.get("video_frame_rate")
    if (not isinstance(clock,dict) or
            set(clock)!={"numerator","denominator"} or
            any(type(clock[k]) is not int or clock[k]<=0 for k in clock)):
        raise ValueError("Original frame observation timebase missing")
    width,height=report.get("preview_rgb_width"),report.get("preview_rgb_height")
    if (type(width) is not int or type(height) is not int or
            not 8<=width<=160 or not 8<=height<=160 or
            width*height>_MAX_PIXEL_SAMPLES):
        raise ValueError("Unbounded original frame observation raster")
    frames=report.get("frames")
    if (not isinstance(frames,list) or not 1<=len(frames)<=_MAX_FRAMES
            or report.get("picture_frames_observed")!=len(frames)):
        raise ValueError("Incomplete whole-movie frame evidence")
    for index,frame in enumerate(frames):
        if (not isinstance(frame,dict) or set(frame)!={
            "frame_index","time_seconds","mean_luma_8bit",
            "previous_frame_mean_abs_luma_delta_8bit"} or
                type(frame["frame_index"]) is not int or frame["frame_index"]!=index):
            raise ValueError("Original actual frame index was dropped or duplicated")
        time=frame["time_seconds"]
        if (type(time) not in (int,float) or not math.isfinite(time) or
                abs(time-index*clock["denominator"]/clock["numerator"])>0.00000006):
            raise ValueError("Native source frame clock is inconsistent")
        lum=frame["mean_luma_8bit"]
        delta=frame["previous_frame_mean_abs_luma_delta_8bit"]
        if (type(lum) not in (int,float) or not math.isfinite(lum) or
                not 0<=lum<=255):
            raise ValueError("False original frame light intensity")
        if index==0:
            if delta is not None:
                raise ValueError("First frame has no preceding real source frame")
        elif (type(delta) not in (int,float) or not math.isfinite(delta)
                or not 0<=delta<=255):
            raise ValueError("Actual native previous-frame difference missing")
    has_sound=report.get("original_sound_present")
    evidence=report.get("measured_soundtrack_dbfs")
    if type(has_sound) is not bool or has_sound!=(evidence is not None):
        raise ValueError("Full soundtrack observation is inconsistent")
    picture_seconds=len(frames)*clock["denominator"]/clock["numerator"]
    sound_duration=report.get("original_decoded_audio_stream_seconds")
    sound_covers=report.get("original_sound_covers_entire_picture")
    if type(sound_covers) is not bool:
        raise ValueError("Native soundtrack full-coverage claim missing")
    if has_sound:
        if (type(sound_duration) not in (int,float) or
                not math.isfinite(sound_duration) or sound_duration<=0 or
                sound_covers!=(sound_duration+.015>=picture_seconds)):
            raise ValueError("Original soundtrack length was not verified")
        if (not isinstance(evidence,dict) or
                type(evidence.get("start_seconds")) not in (int,float) or
                type(evidence.get("end_seconds")) not in (int,float) or
                not 0<=evidence["start_seconds"]<evidence["end_seconds"] or
                evidence["end_seconds"]>min(picture_seconds,sound_duration)+.00001):
            raise ValueError("Soundtrack measurement outlasts recorded physical sound")
    elif sound_duration is not None or sound_covers:
        raise ValueError("Silent original has fabricated soundtrack duration")
    return {"observed_original_picture_frames":len(frames),
            "source_sha256":report["original_movie_sha256"],
            "full_CFR_frame_evidence_valid":True,
            "original_sound_physically_measured":has_sound,
            "original_sound_covers_entire_picture":sound_covers,
            "original_decoded_audio_stream_seconds":sound_duration,
            "human_artist_approval":False}



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
        audio_duration=None
        picture_duration=float(total_frames*rate.denominator/rate.numerator)
        soundtrack_covers_picture=False
        if detail["audio_stream_present"]:
            # A picture can contain fewer sound samples than video frames.
            # Do not label silent tail frames as original "measured audio."
            audio_duration=_decoded_source_duration(pinned,"audio")
            soundtrack_covers_picture=(audio_duration+.015>=picture_duration)
            soundtrack=_snapshot_window(pinned,0.0,
                min(picture_duration,audio_duration))
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
            "schema":1,"kind":_KIND,"original_movie_sha256":original_sha,
            "source_rights_attestation_id":plan["media"]["attestation_id"],
            "director_review_plan_sha256":before,
            "picture_frames_observed":total_frames,
            "video_frame_rate":{"numerator":rate.numerator,"denominator":rate.denominator},
            "preview_rgb_width":width,"preview_rgb_height":height,
            "complete_original_video_and_sound_decoded":True,
            "original_sound_present":detail["audio_stream_present"],
            "original_decoded_audio_stream_seconds":audio_duration,
            "original_sound_covers_entire_picture":soundtrack_covers_picture,
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
        verified=verify_full_temporal_evidence(staged)
        if verified["observed_original_picture_frames"]!=total_frames:
            raise ValueError("Full original frame count changed in measured receipt")
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
            "original_sound_covers_entire_picture":soundtrack_covers_picture,
            "creative_quality_certified":False}

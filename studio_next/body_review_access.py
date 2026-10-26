"""Independent factual review-frame reader for future visual creative intelligence.

A physical review package was created by the authorized BODY renderer.
Read-only output exposes exactly the original decoded frame timestamps,
measured audio windows and source SHA. Pixel extraction checks both the
whole archive SHA and its per-PNG digest, then emits ONE lossless decoded
frame to an already-vetted fresh workspace pathname.

No stylistic inference, model-side Python, shell command or embedded HTML.
"""
from __future__ import annotations
import json
import os
import tempfile
import re
import zipfile
from pathlib import Path

from .body_observation import verify_review_bundle
from .media_vault import sha256_file
from .media_vault import verify_media_container

_DIGEST=re.compile(r"^[0-9a-f]{64}$")

def _verified_review(archive,expected_sha256,root):
    input_file=Path(archive).resolve()
    if (not input_file.is_file() or input_file.suffix.lower()!=".zxreview"
         or not input_file.is_relative_to(Path(root).resolve())):
        raise ValueError("Read only original verified studio review archives")
    if (not isinstance(expected_sha256,str) or not _DIGEST.fullmatch(expected_sha256)
            or sha256_file(input_file)!=expected_sha256):
        raise ValueError("Review package bytes differ from original release witness")
    verified=verify_review_bundle(input_file)
    if not verified["true_image_decoders_completed"]:
        raise ValueError("Original decoded review picture evidence failed")
    with zipfile.ZipFile(input_file) as zipped:
        manifest=json.loads(zipped.read("review.json"))
    return input_file,manifest

def read_verified_review(archive,expected_sha256,workspace):
    """Read only factual measurements, no claims about the creative result."""
    file,manifest=_verified_review(archive,expected_sha256,workspace)
    return {"path":str(file),"sha256":expected_sha256,"bytes":file.stat().st_size,
        "schema":2,
        "original_source_sha256":manifest["source_sha256"],
        "original_duration_seconds":manifest["source_original_duration_seconds"],
        "actual_picture_width":manifest["source_picture_width"],
        "actual_picture_height":manifest["source_picture_height"],
        "source_has_audio":manifest["source_has_actual_audio"],
        "frames":[{"index":idx,"at_seconds":item["time_seconds"],
                   "mean_luma_8bit":item["mean_luma_8bit"],
                   "mean_rgb_8bit":item["mean_rgb_8bit"],
                   "sample_to_previous_luma_difference":
                     item["sample_pair_mean_absolute_luma_difference"]}
                  for idx,item in enumerate(manifest["frames"],1)],
        "audio_windows":manifest["audio_window_evidence"],
        "original_review_package_sha256":expected_sha256,
        "has_physically_decoded_original_frames":True,
        "no_actor_continuity_or_narrative_understanding_claimed":True,
        "human_artistic_quality_approved":False}

def extract_verified_review_frame(archive,expected_sha256,workspace,
                                  frame_index,output):
    """Publish a selected original picture, never a guessed/AI-made mockup."""
    if type(frame_index) is not int or frame_index<1:
        raise ValueError("Selected original review frame index must be positive integer")
    file,manifest=_verified_review(archive,expected_sha256,workspace)
    if frame_index>len(manifest["frames"]):
        raise ValueError("Original review frame index not present in licensed evidence")
    dest=Path(output).resolve()
    if (not dest.is_relative_to(Path(workspace).resolve()) or
            dest.suffix.lower()!=".png" or dest.exists() or dest.is_symlink()):
        raise ValueError("Original observation requires a new protected PNG artifact")
    row=manifest["frames"][frame_index-1]
    with zipfile.ZipFile(file) as zipped:
        picture=zipped.read(row["file"])
    import hashlib
    if hashlib.sha256(picture).hexdigest()!=row["sha256"] or len(picture)!=row["bytes"]:
        raise ValueError("Review picture differs from encoded source evidence")
    dest.parent.mkdir(parents=True,exist_ok=True)
    # Decode privately before publishing any director-visible PNG. A losing
    # reviewer may NOT delete an independently accepted competitor's image.
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".zx7-review-frame-",
                                      dir=dest.parent) as scratch:
        staged=Path(scratch)/"decoded-original-picture.png"
        with staged.open("xb") as native:
            native.write(picture)
            native.flush()
            os.fsync(native.fileno())
        verify_media_container(staged,"image/png")
        if sha256_file(file)!=expected_sha256:
            raise ValueError("Original review archive changed while decoding")
        os.link(staged,dest)
    return {"path":str(dest),"sha256":sha256_file(dest),
            "bytes":dest.stat().st_size,
            "source_film_sha256":manifest["source_sha256"],
            "source_review_sha256":expected_sha256,
            "original_time_seconds":row["time_seconds"],
            "selected_frame_index":frame_index,
            "human_artistic_quality_approved":False}

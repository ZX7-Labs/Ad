"""Make one bounded real export frame visible to an MCP-capable visual brain.

A verified-export proof must first be issued by the same trusted editor session.
Sampling one image is not an audiovisual, temporal or artistic evaluation.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re
import stat
import struct
import subprocess

from .body_editor_client import EditorAccessError
from .body_editor_policy import EditorPathPolicy
from .body_editor_export import _no_path_symlinks, VIDEO_EXTENSIONS
from .delivery_audit import _probe_details
from .media_vault import sha256_file

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_PNG = b"\x89PNG\r\n\x1a\n"


def observe_verified_export_frame(path: str, *, policy: EditorPathPolicy,
                                  verified_sha256: str, at_seconds: float,
                                  timeout: int = 120) -> tuple[bytes, dict]:
    """Return a real downscaled PNG and a source-bound, limited observation."""
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise EditorAccessError("Frame observation requires an absolute authorized export")
    if not isinstance(policy, EditorPathPolicy) or not policy(
            "inspect_export_file", {"path": path}, "read"):
        raise EditorAccessError("Frame observation denied by native editor host policy")
    if (not Path(path).resolve().is_relative_to(policy.outputs_root)
            or Path(path).suffix.lower() not in VIDEO_EXTENSIONS or not _no_path_symlinks(
                Path(path), (policy.outputs_root,))):
        raise EditorAccessError("Frame observation refuses unsupported or linked exports")
    if not isinstance(verified_sha256, str) or not _DIGEST.fullmatch(verified_sha256):
        raise ValueError("An issued physical export SHA256 is required")
    if type(at_seconds) not in (int, float) or not math.isfinite(at_seconds) or at_seconds < 0:
        raise ValueError("Requested video timestamp must be finite and nonnegative")
    source = Path(path)
    before = source.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("Native output is not a regular encoded file")
    metadata = _probe_details(source)
    if metadata["video_sha256"] != verified_sha256:
        raise ValueError("Export bytes no longer match independently decoded evidence")
    if at_seconds >= metadata["duration_seconds"]:
        raise ValueError("Requested frame is outside the physical video duration")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-protocol_whitelist", "file,pipe,crypto",
        "-ss", format(at_seconds, ".9f"), "-i", str(source),
        "-vf", "scale='min(768,iw)':'min(768,ih)':force_original_aspect_ratio=decrease",
        "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "pipe:1"]
    # The output is intentionally a bounded review plane, not native-resolution
    # HDR/data-pixel evidence or a guarantee of exact timestamp presentation.
    outcome = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
    image = outcome.stdout
    if outcome.returncode or len(image) < 32 or len(image) > 4 * 1024 * 1024 or (
            not image.startswith(_PNG)):
        raise ValueError("Actual physical export frame could not be safely decoded")
    width, height = struct.unpack(">II", image[16:24])
    if not 0 < width <= 768 or not 0 < height <= 768:
        raise ValueError("Decoded frame exceeds the trusted visual review plane")
    after = source.stat()
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or sha256_file(source) != verified_sha256):
        raise ValueError("Native export changed during frame observation")
    return image, {
        "schema": 1,
        "kind": "verified_native_editor_single_frame",
        "export_sha256": verified_sha256,
        "sampled_video_seconds_requested": at_seconds,
        "sampled_video_seconds_exact_pts_proven": False,
        "observed_picture_width": width,
        "observed_picture_height": height,
        "png_sha256": hashlib.sha256(image).hexdigest(),
        "observation": "One real decoded display-oriented PNG, not full motion/audio or HDR measurement",
        "human_or_artistic_quality_approved": False,
    }

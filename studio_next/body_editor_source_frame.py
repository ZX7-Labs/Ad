"""Inspect original imported source footage before any edit or export.

The model selects an *asset id*, never a filesystem path. The host independently
resolves that id through the currently open native editor project, requires an
imported regular video inside the owner-granted project root, decodes real
pixels with bounded FFmpeg and binds them to the original source SHA-256.
This is preview, not a source-usage license, HDR proof or OS process sandbox.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile

from .body_editor_client import EditorAccessError
from .body_editor_export import VIDEO_EXTENSIONS, _no_path_symlinks
from .body_editor_frame import _verified_png_dimensions
from .body_editor_policy import EditorPathPolicy
from .body_editor_split_guard import _native_json
from .media_vault import sha256_file

_ASSET_ID = re.compile(r"[A-Za-z0-9_-]{1,160}\Z")
_FILE_LIMIT = 8 * 1024 * 1024 * 1024
_PNG_LIMIT = 4 * 1024 * 1024
_PROBE_LIMIT = 256 * 1024


def _native_project_asset(client, asset_id: str, *, allowed_access, policy: EditorPathPolicy):
    if ("read" not in allowed_access or
            any(client.allowed_tools.get(name) != "read"
                for name in ("get_project", "get_assets"))):
        raise EditorAccessError("Original source observation requires granted native project and asset reads")
    project_data = _native_json(client.call(
        "get_project", {}, allowed_access=allowed_access), "get_project")
    asset_data = _native_json(client.call(
        "get_assets", {"limit": 1000}, allowed_access=allowed_access), "get_assets")
    project = project_data.get("project")
    assets = asset_data.get("assets")
    if not isinstance(project, dict) or not isinstance(assets, list):
        raise EditorAccessError("Original source preview requires a complete active native project")
    count = asset_data.get("totalAssetCount")
    returned = asset_data.get("returnedAssetCount")
    if (type(count) is not int or type(returned) is not int or
            count != returned or len(assets) != count or count > 1000):
        raise EditorAccessError("Native asset inventory was truncated or unstable")
    identity = project.get("path")
    if not isinstance(identity, str) or not Path(identity).is_absolute():
        raise EditorAccessError("Native project has no absolute owner-granted path")
    project_root = Path(identity)
    if (not project_root.is_dir() or project_root == policy.projects_root or
            not project_root.is_relative_to(policy.projects_root) or
            not _no_path_symlinks(project_root, (policy.projects_root,))):
        raise EditorAccessError("Original source project is outside the owner-granted root")
    matches = [asset for asset in assets if isinstance(asset, dict) and
               asset.get("id") == asset_id]
    if len(matches) != 1:
        raise EditorAccessError("Original video asset id was missing or ambiguous")
    asset = matches[0]
    if asset.get("type") != "video" or asset.get("isImported") is not True:
        raise EditorAccessError("Original source preview needs an imported video source asset")
    relative = asset.get("path")
    if (not isinstance(relative, str) or not relative or "\\" in relative or
            relative.startswith("/") or
            any(part in ("", ".", "..") for part in relative.split("/")) or
            not PurePosixPath(relative).parts):
        raise EditorAccessError("Native video asset has unsafe or noncanonical relative source path")
    path = project_root.joinpath(*relative.split("/"))
    if (path.suffix.lower() not in VIDEO_EXTENSIONS or
            not _no_path_symlinks(path, (policy.projects_root,)) or
            not path.resolve().is_relative_to(project_root)):
        raise EditorAccessError("Original video asset escaped the imported project source root")
    return path, project_root


def _source_duration(path: Path) -> float:
    command = ["ffprobe", "-v", "error", "-show_entries",
               "format=duration:stream=codec_type,duration,width,height",
               "-of", "json", str(path)]
    with tempfile.TemporaryFile() as out:
        run = subprocess.run(command, stdout=out, stderr=subprocess.DEVNULL,
                             timeout=35, check=False)
        if run.returncode or out.tell() > _PROBE_LIMIT:
            raise ValueError("Original source video has no bounded independent probe")
        out.seek(0)
        raw = out.read(_PROBE_LIMIT + 1)
    try:
        probe = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Original source probe was malformed") from exc
    streams = probe.get("streams")
    if not isinstance(streams, list) or not any(
            isinstance(s, dict) and s.get("codec_type") == "video" and
            type(s.get("width")) is int and type(s.get("height")) is int and
            0 < s["width"] <= 16384 and 0 < s["height"] <= 16384
            for s in streams):
        raise ValueError("Original source contains no supported video picture stream")
    durations = [probe.get("format", {}).get("duration")]
    durations.extend(s.get("duration") for s in streams
                     if isinstance(s, dict) and s.get("codec_type") == "video")
    valid = []
    for raw_duration in durations:
        try:
            duration = float(raw_duration)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(duration) and 0 < duration <= 12 * 3600:
            valid.append(duration)
    if not valid:
        raise ValueError("Original source has no finite bounded media duration")
    return max(valid)


def observe_authorized_native_source_frame(client, asset_id: str, at_seconds: float, *,
                                           allowed_access, policy: EditorPathPolicy,
                                           decoder_timeout: int = 90):
    """Return real PNG+custody receipt for a *current* uniquely imported video."""
    if not isinstance(policy, EditorPathPolicy):
        raise TypeError("Owner-granted native source policy required")
    if not isinstance(asset_id, str) or _ASSET_ID.fullmatch(asset_id) is None:
        raise EditorAccessError("Source observer requires a real bounded native asset ID")
    if (type(at_seconds) not in (int, float) or not math.isfinite(at_seconds) or
            at_seconds < 0):
        raise ValueError("Source preview timestamp must be finite and nonnegative")
    source, project_root = _native_project_asset(
        client, asset_id, allowed_access=allowed_access, policy=policy)
    before = source.stat(follow_symlinks=False)
    if (not stat.S_ISREG(before.st_mode) or
            not 0 < before.st_size <= _FILE_LIMIT):
        raise ValueError("Imported native source is not a supported bounded regular file")
    duration = _source_duration(source)
    if at_seconds >= duration:
        raise ValueError("Original video source frame is outside its real duration")
    source_sha256 = sha256_file(source)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
           "-protocol_whitelist", "file,pipe,crypto",
           "-ss", format(at_seconds, ".9f"), "-i", str(source),
           "-vf", "scale='min(768,iw)':'min(768,ih)':force_original_aspect_ratio=decrease",
           "-frames:v", "1", "-fs", str(_PNG_LIMIT),
           "-f", "image2pipe", "-c:v", "png", "pipe:1"]
    with tempfile.TemporaryFile() as out:
        completed = subprocess.run(cmd, stdout=out, stderr=subprocess.DEVNULL,
                                   timeout=decoder_timeout, check=False)
        if completed.returncode or not 57 <= out.tell() <= _PNG_LIMIT:
            raise ValueError("Original source frame failed bounded independent decoding")
        out.seek(0)
        image = out.read(_PNG_LIMIT + 1)
    width, height = _verified_png_dimensions(image)
    after = source.stat(follow_symlinks=False)
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or
            sha256_file(source) != source_sha256 or
            not _no_path_symlinks(source, (policy.projects_root,)) or
            not source.resolve().is_relative_to(project_root)):
        raise ValueError("Original imported source was changed during observation")
    return image, {
        "schema": 1, "kind": "verified_native_editor_source_asset_frame",
        "asset_id": asset_id,
        "project_root_sha256": hashlib.sha256(str(project_root).encode()).hexdigest(),
        "source_sha256": source_sha256,
        "png_sha256": hashlib.sha256(image).hexdigest(),
        "sampled_source_seconds_requested": at_seconds,
        "source_duration_seconds": duration,
        "observed_picture_width": width, "observed_picture_height": height,
        "source_is_imported_project_video": True,
        "physical_frame_verified": True,
        "original_exact_presentation_pts_proven": False,
        "composited_timeline_or_artistic_quality_approved": False,
        "source_rights_independently_verified": False,
    }

"""Physical owner-media custody for genuine model-to-editor technical trials.

A native model can create a project, markers, solids and titles without using
the caller's actual video. These are not evidence that it edited source footage.
This verifier proves a *project-owned byte-exact copy* of a host-supplied video
is present as a real timeline clip in a native saved project. It never decides
a creative operation or inserts media. Only test-runner acceptance uses it.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _finite_real(value) -> bool:
    # Native timeline clock fields must be finite numeric values. Python's
    # bool is not a time position; huge integers must not overflow isfinite.
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def verify_original_footage_on_native_timeline(
        projects_root: Path, project_paths: list[Path],
        caller_source_assets: list[dict]) -> dict:
    """Produce independently checkable technical provenance, never QA approval.

    Require both the host-owned original video SHA and the *copied* project
    asset to be byte-identical; source provenance alone could be forged.
    The native project must reference that exact copied asset through a
    real clip on a timeline; synthetic shapes/text are insufficient.
    """
    root = Path(projects_root).resolve(strict=True)
    if not root.is_dir() or not isinstance(project_paths, list) or not isinstance(
            caller_source_assets, list):
        raise ValueError("Real editor projects and source manifest required")
    sources = {}
    for item in caller_source_assets:
        if not isinstance(item, dict):
            raise ValueError("Untrusted source manifest object")
        raw, expected = item.get("path"), item.get("sha256")
        if (not isinstance(raw, str) or not isinstance(expected, str) or
                len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected)):
            raise ValueError("Original source must have a host-attested SHA-256")
        source = Path(raw)
        if not source.is_absolute():
            raise ValueError("Original input must be an absolute host path")
        source = source.resolve(strict=True)
        if not source.is_file() or source.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm"}:
            raise ValueError("Original video source missing")
        if _sha256(source) != expected:
            raise ValueError("Original source bytes changed after host hash")
        sources[str(source)] = expected
    accepted = []
    for path in project_paths:
        project = Path(path).resolve(strict=True)
        if (not project.is_file() or not project.is_relative_to(root) or
                project.name != "project.comfystudio"):
            raise ValueError("Native project is outside owned test root")
        # Trial projects and original source manifest are host-created; the
        # model controls only native editor operations, never these files.
        data = json.loads(project.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
            raise ValueError("Native project assets are absent or invalid")
        timelines = data.get("timelines")
        if not isinstance(timelines, list):
            raise ValueError("Native project timeline inventory is invalid")
        # The editor exports the ACTIVE timeline. A source imported into a
        # dormant timeline, or a disabled/muted picture lane, is not proof
        # that the delivered movie actually used original video footage.
        current_timeline_id = data.get("currentTimelineId")
        if not isinstance(current_timeline_id, str) or not current_timeline_id:
            raise ValueError("Saved native project has no active timeline identity")
        placed = set()
        found_active = False
        for timeline in timelines:
            if not isinstance(timeline, dict) or not isinstance(timeline.get("clips"), list):
                raise ValueError("Native timeline clips malformed")
            if timeline.get("id") != current_timeline_id:
                continue
            found_active = True
            active_duration = timeline.get("duration")
            if not _finite_real(active_duration) or active_duration <= 0:
                raise ValueError("Active native timeline has no finite positive duration")
            tracks = timeline.get("tracks")
            if not isinstance(tracks, list):
                raise ValueError("Native active track inventory is missing")
            visible_video_tracks = {
                track["id"] for track in tracks
                if isinstance(track, dict) and
                isinstance(track.get("id"), str) and
                track.get("type") == "video" and track.get("visible") is not False}
            for clip in timeline["clips"]:
                if (isinstance(clip, dict) and
                        clip.get("type") == "video" and
                        clip.get("enabled") is not False and
                        clip.get("trackId") in visible_video_tracks and
                        isinstance(clip.get("assetId"), str) and
                        _finite_real(clip.get("startTime")) and
                        _finite_real(clip.get("duration")) and
                        0 < clip["duration"] <= 1_000_000 and
                        # A valid copied video entirely outside the active
                        # timeline cannot appear in the delivered picture.
                        clip["startTime"] < active_duration and
                        clip["startTime"] + clip["duration"] > 0):
                    placed.add(clip["assetId"])
        if not found_active:
            raise ValueError("Active native timeline was not saved")
        for asset in data["assets"]:
            if not isinstance(asset, dict) or asset.get("type") != "video":
                continue
            asset_id = asset.get("id")
            settings = asset.get("settings")
            if (not isinstance(asset_id, str) or asset_id not in placed or
                    not isinstance(settings, dict) or
                    settings.get("importedViaMcp") is not True):
                continue
            previous = settings.get("sourcePath")
            if not isinstance(previous, str):
                continue
            # A saved editor project is not authority to make the trial
            # verifier open arbitrary host paths. Check the exact caller-
            # attested source identity BEFORE resolving or accessing it.
            owner_hash = sources.get(previous)
            if not owner_hash:
                continue
            original = Path(previous)
            for path_field in ("absolutePath", "path"):
                asset_location = asset.get(path_field)
                if not isinstance(asset_location, str) or not asset_location:
                    continue
                if "://" in asset_location:
                    continue
                owned = Path(asset_location)
                if not owned.is_absolute():
                    owned = project.parent / owned
                owned = owned.resolve(strict=False)
                if (owned == original or
                        not owned.is_relative_to(project.parent) or
                        not owned.is_file()):
                    continue
                if _sha256(owned) != owner_hash:
                    continue
                accepted.append({
                    # Preserve only an owner-root-relative reference in
                    # published CI artifacts; never disclose local absolute
                    # media/project paths in technical provenance reports.
                    "relative_native_project_file": str(project.relative_to(root)),
                    "native_asset_id": asset_id,
                    "source_sha256": owner_hash,
                    "project_owned_copy_sha256": owner_hash,
                })
                break
    return {
        "actual_original_video_used_on_native_timeline": bool(accepted),
        "physically_verified_native_source_clip_count": len(accepted),
        "verified_native_source_clip_proof": accepted,
        "professional_artistic_quality_approved": False,
    }

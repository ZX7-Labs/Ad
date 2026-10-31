"""Native snapshot facts and source-reviewed read-only preview intent.

No operation is selected or performed here. Both functions expose hard limits
that prevent the creative model from mistaking unimported footage, an empty
timeline or a preview receipt for a completed editable film.

The preview-only names below are source-reviewed against the pinned Velorn
b3c02adbd5c0779feb8abf34978299e9502cc0e7 electron/mcpServer.js
addAssetToTimeline/addAssetsToTimeline/addSolidColor, where a missing/true
previewOnly returns before performAction and invalid planning exits as error.
These are *safety contract bindings*, not creative templates or tool grants.
"""
from __future__ import annotations

import json

_SOURCE_REVIEWED_NONMUTATING_PREVIEWS = frozenset({
    "add_asset_to_timeline", "add_assets_to_timeline", "add_solid_color",
})


def source_reviewed_preview_is_readonly(name, inputs, native_schema):
    """Only a pinned source-guaranteed preview, never a failed native WRITE."""
    if name not in _SOURCE_REVIEWED_NONMUTATING_PREVIEWS:
        return False
    if not isinstance(inputs, dict) or not isinstance(native_schema, dict):
        return False
    props = native_schema.get("properties")
    field = props.get("previewOnly") if isinstance(props, dict) else None
    if not isinstance(field, dict) or field.get("type") != "boolean":
        return False
    if "previewOnly" in inputs and type(inputs["previewOnly"]) is not bool:
        return False
    return inputs.get("previewOnly") is not False


def pinned_snapshot_summary(snapshot):
    """No raw private paths; positive facts only from the real get_project ABI.

    No claim of serializable transaction/version isolation: the snapshot may
    lag the native application. The model must observe actual project state.
    """
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("mcp"), dict):
        return None
    mcp = snapshot["mcp"]
    exists = mcp.get("hasProject")
    if type(exists) is not bool:
        return None
    project = snapshot.get("project")
    timeline = snapshot.get("currentTimeline")
    if (exists and not isinstance(project, dict) or
            not exists and (project is not None or timeline is not None)):
        return None
    def count(value):
        return value if type(value) is int and 0 <= value <= 1_000_000 else None
    assets = count(snapshot.get("assetCount"))
    total = count(snapshot.get("timelineCount"))
    if assets is None or total is None:
        return None
    if timeline is not None:
        if not isinstance(timeline, dict):
            return None
        clips = count(timeline.get("clipCount"))
        tracks = count(timeline.get("trackCount"))
        transitions = count(timeline.get("transitionCount"))
        if clips is None or tracks is None or transitions is None:
            return None
    else:
        clips = tracks = transitions = None
    # Deliberately omit native project paths, asset names, timestamps,
    # content and any invented "has professional video" inference.
    return {
        "source": "host_authorized_native_get_project",
        "project_presence": "present" if exists else "absent",
        "native_project_asset_count": assets,
        "native_timeline_count": total,
        "current_timeline_clip_count": clips,
        "current_timeline_track_count": tracks,
        "current_timeline_transition_count": transitions,
        "snapshot_may_lag_app_state": True,
        "creative_content_or_export_quality_approved": False,
    }


def contradictory_nested_write_receipt(value):
    """A native MCP wrapper's success:true is insufficient if its result fails.

    Pinned Velorn's runRendererActionTool can derive a wrapper boolean from
    result.success !== false; ambiguous nonboolean child fields are not
    independent proof that the actual renderer changed the project.
    """
    return (isinstance(value, dict) and
            (("success" in value and value["success"] is not True) or
             value.get("error") not in (None, "", False)))

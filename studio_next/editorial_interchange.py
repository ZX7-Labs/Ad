"""Editable professional timeline interchange (OpenTimelineIO / ASWF).

A director can choose arbitrary order, clip durations, delivery geometry,
music/dialogue, source footage and transitions upstream. This exporter does
NOT replace the actual FFmpeg movie renderer. It retains the precise source
ranges and media paths in an industry-readable editable .otio project.

Installed OpenTimelineIO is mandatory; never silently fake or substitute
a generic JSON file with an .otio extension.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .edit_timeline import validate_edit,probe_media,_path_within


def export_editable_timeline(edit_json,media_root,dest,*,probe=probe_media):
    try:
        import opentimelineio as otio
    except ImportError as exc:
        raise RuntimeError("OpenTimelineIO must be installed; editable export unavailable") from exc
    src=Path(edit_json)
    edit=json.loads(src.read_text(encoding="utf-8"))
    root=Path(media_root).resolve()
    validate_edit(edit,root)
    export=Path(dest)
    if export.suffix!=".otio":
        raise ValueError("Editable project must be a real .otio timeline")
    if export.exists():
        raise FileExistsError("Never overwrite original editorial project")
    fmt=edit["format"]
    rate=fmt["fps"]
    timeline=otio.schema.Timeline(name=src.stem)
    track=otio.schema.Track(name="ZX7 Director Cut",kind=otio.schema.TrackKind.Video)
    timings=[]
    for clip in edit["clips"]:
        source=_path_within(root,clip["source"],exists=True)
        meta=probe(source)
        frames=round(meta["seconds"]*rate)
        if frames<1:raise ValueError("Director selected media has no encoded frames")
        duration=otio.opentime.RationalTime(frames,rate)
        origin=otio.opentime.RationalTime(0,rate)
        clip_ref=otio.schema.ExternalReference(
            target_url=source.as_uri(),
            available_range=otio.opentime.TimeRange(origin,duration))
        entry=otio.schema.Clip(name=clip["id"],
                  media_reference=clip_ref,
                  source_range=otio.opentime.TimeRange(origin,duration))
        entry.metadata["zx7"]={
            "source_artifact_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
            "rights_class":clip["rights"],
            "audio_director_choice":clip["audio"],
            "source_path":clip["source"],
            "measured_seconds":float(meta["seconds"])}
        track.append(entry)
        timings.append({"id":clip["id"],"measured_seconds":meta["seconds"],
                        "duration_frames":frames})
    timeline.tracks.append(track)
    timeline.metadata["zx7"]={
        "director_delivery":fmt,
        "video_and_audio_composited_elsewhere":True,
        "source_edit_sha256":hashlib.sha256(src.read_bytes()).hexdigest(),
        "model_has_no_hardcoded_style":True}
    export.parent.mkdir(parents=True,exist_ok=True)
    otio.adapters.write_to_file(timeline,str(export))
    # Validate deserialization using the actual installed OTIO implementation.
    check=otio.adapters.read_from_file(str(export))
    if len(check.video_tracks())!=1 or len(check.video_tracks()[0])!=len(edit["clips"]):
        export.unlink(missing_ok=True)
        raise RuntimeError("The professional editable timeline did not roundtrip")
    return {"edit_file":str(export),"clips":timings,
            "export_format":"real OpenTimelineIO",
            "source_media_was_physically_probed":True,
            "quality_certified":False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--edit",type=Path,required=True)
    p.add_argument("--media-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(export_editable_timeline(a.edit,a.media_root,a.out),indent=2))


if __name__=="__main__":
    main()

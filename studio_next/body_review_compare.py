"""Factual compare of TWO verified original-film audiovisual review revisions.

An editor must be able to observe whether a revision changed the real
picture/sound at selected matching timecodes. This is a *measurement* of
actual decoded differences, never an automated "better movie" score.
No model, cloud service, or chosen film style is assumed.
"""
from __future__ import annotations
import io
import json
import math
import zipfile
from pathlib import Path

from .body_review_access import _verified_review
from .media_vault import sha256_file


def _image_at(archive,receipt):
    from PIL import Image
    with zipfile.ZipFile(archive) as z:
        raw=z.read(receipt["file"])
    with Image.open(io.BytesIO(raw)) as png:
        if png.format!="PNG":
            raise ValueError("Actual original review frame is not lossless PNG")
        image=png.convert("RGB")
        image.load()
        return image


def compare_verified_revisions(before,old_sha,after,new_sha,workspace):
    """Read only physically verified source and frame evidence for both films."""
    from PIL import ImageChops,ImageStat
    root=Path(workspace).resolve()
    a,original=_verified_review(before,old_sha,root)
    b,revised=_verified_review(after,new_sha,root)
    original_at={row["time_seconds"]:row for row in original["frames"]}
    revised_at={row["time_seconds"]:row for row in revised["frames"]}
    shared=sorted(set(original_at)&set(revised_at))
    difference=[]
    for stamp in shared:
        left=_image_at(a,original_at[stamp])
        right=_image_at(b,revised_at[stamp])
        if left.size!=right.size:
            difference.append({"time_seconds":stamp,
              "comparison":"different_rendered_picture_dimensions",
              "before_width":left.width,"before_height":left.height,
              "after_width":right.width,"after_height":right.height,
              "pixel_difference_8bit":None})
            continue
        # This is not optical flow; it intentionally measures two versions
        # only at matching original timecodes and matched preview resolution.
        delta=ImageChops.difference(left,right)
        channels=ImageStat.Stat(delta).mean
        difference.append({"time_seconds":stamp,
            "comparison":"matched_original_review_timecode",
            "width":left.width,"height":left.height,
            "mean_absolute_pixel_channel_difference_8bit":
                [round(float(value),4) for value in channels],
            "mean_absolute_rgb_difference_8bit":
                round(sum(channels)/3,4),
            "image_pixels_physically_decoded":True})
    def _audio_index(items):
        return {(x["start_seconds"],x["end_seconds"]):x for x in items}
    original_audio=_audio_index(original["audio_window_evidence"])
    revised_audio=_audio_index(revised["audio_window_evidence"])
    audio=[]
    for window in sorted(set(original_audio)&set(revised_audio)):
        before_levels=original_audio[window]
        after_levels=revised_audio[window]
        report={"start_seconds":window[0],"end_seconds":window[1],
                "measurement":"real first audio track; not intelligibility or musical quality"}
        for key in ("mean_dbfs","peak_dbfs"):
            older=before_levels[key]
            newer=after_levels[key]
            report["before_"+key]=older
            report["after_"+key]=newer
            report["delta_"+key]=(round(newer-older,4)
                if type(older) in (int,float) and type(newer) in (int,float)
                   and math.isfinite(older) and math.isfinite(newer) else None)
        audio.append(report)
    return {"path":str(b),"sha256":new_sha,"bytes":b.stat().st_size,
        "schema":1,
        "before_review_sha256":old_sha,"revised_review_sha256":new_sha,
        "before_film_source_sha256":original["source_sha256"],
        "revised_film_source_sha256":revised["source_sha256"],
        "matching_frame_comparisons":difference,
        "matching_audio_window_comparisons":audio,
        "before_only_picture_sample_times":
           sorted(set(original_at)-set(revised_at)),
        "revised_only_picture_sample_times":
           sorted(set(revised_at)-set(original_at)),
        "before_film_duration_seconds":original["source_original_duration_seconds"],
        "revised_film_duration_seconds":revised["source_original_duration_seconds"],
        "unmatched_review_frames_are_not_silently_time_warped":True,
        "no_continuity_dialogue_style_or_narrative_quality_inference":True,
        "human_artist_has_not_approved_a_revision":True}

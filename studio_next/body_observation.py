"""Original-film factual audiovisual REVIEW EVIDENCE for creative iteration.

Provides real decoded selected frames, pixel differences, and time-window
audio levels in a physically independently verified portable review archive.
It does NOT evaluate story, human emotion, creativity, quality or acting.

Every source must be an actual rights-attested MediaVault original/rendered
asset; direct source paths are allowed ONLY if their bytes and custody match.
Technical verification decodes the entire original picture and audio.
Timestamps/windows are authored, never defaulted to film genre or shot style.
"""
from __future__ import annotations
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from .composite_mix import _exact_media
from .delivery_audit import _probe_details
from .media_vault import MediaVault,sha256_file
from .production_qc import full_decode_inspection

_FRAME=re.compile(r"^frames/review_[0-9]{4}\.png$")
_HEX=re.compile(r"^[0-9a-f]{64}$")
_AUDIO=re.compile(r"(?:mean|max)_volume:\s*(-?(?:(?:[0-9]+(?:\.[0-9]+)?)|inf))\s*dB")
_MAX_SAMPLES=24

def _measurable(v,field):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
        raise ValueError("Film review "+field+" must be a finite numeric time")
    return float(v)

def _snapshot_window(movie,start,end):
    # ffmpeg output-level -ss/-t can trim AFTER the volumedetect filter:
    # that would report whole-movie audio as if it belonged to this window.
    # atrim runs BEFORE the meter inside the actual filtergraph.
    result=subprocess.run(["ffmpeg","-hide_banner","-nostdin","-loglevel","info",
        "-i",str(movie),"-map","0:a:0","-vn",
        "-af",f"atrim=start={start}:end={end},asetpts=PTS-STARTPTS,volumedetect",
        "-f","null","-"],
        capture_output=True,text=True,timeout=180,check=False)
    if result.returncode:
        raise ValueError("Selected original audio window did not physically decode")
    findings=re.findall(r"(mean_volume|max_volume):\s*(-?(?:\d+(?:\.\d+)?|inf))\s*dB",
                        result.stderr or "")
    levels={k:("-inf" if v=="-inf" else float(v)) for k,v in findings}
    if "mean_volume" not in levels or "max_volume" not in levels:
        raise ValueError("No actual audio-window dBFS evidence from FFmpeg decoder")
    return {"start_seconds":start,"end_seconds":end,
            "mean_dbfs":levels["mean_volume"],
            "peak_dbfs":levels["max_volume"],
            "measurement":"first actually decoded audio stream; volumedetect, not perceptual quality"}

def _validate_review_plan(plan,root,vault):
    if not isinstance(plan,dict) or set(plan)!={"media","timecodes_seconds","audio_windows_seconds"}:
        raise ValueError("Original review needs exact source and artist-selected sample times")
    media=plan["media"]
    if not isinstance(media,dict) or set(media)!={"source","asset_id","attestation_id"}:
        raise ValueError("Review source requires exact original SHA and rights attestation")
    movie=_exact_media(media,vault,root,need="video")
    facts=_probe_details(movie)
    samples=plan["timecodes_seconds"]
    windows=plan["audio_windows_seconds"]
    if not isinstance(samples,list) or not (1<=len(samples)<=_MAX_SAMPLES):
        raise ValueError("Review must select 1 to 24 physical frames per bounded operation")
    if not isinstance(windows,list) or len(windows)>_MAX_SAMPLES:
        raise ValueError("Review audio windows must be a bounded caller-selected list")
    positions=[]
    for raw in samples:
        stamp=_measurable(raw,"timecode")
        if not 0<=stamp<facts["duration_seconds"]:
            raise ValueError("Original selected frame is outside actual movie")
        if positions and stamp<=positions[-1]:
            raise ValueError("Original review times must be strictly increasing")
        positions.append(stamp)
    checks=[]
    for section in windows:
        if not isinstance(section,list) or len(section)!=2:
            raise ValueError("Audio window requires exact start/end seconds")
        a,b=(_measurable(v,"audio-window") for v in section)
        if not 0<=a<b<=facts["duration_seconds"]:
            raise ValueError("Audio window must lie within original physical soundtrack")
        if not facts["audio_stream_present"]:
            raise ValueError("Cannot inspect soundtrack windows: original movie contains no audio")
        checks.append([a,b])
    return movie,facts,positions,checks

def verify_review_bundle(archive):
    """Only self-contained checked PNGs and source-bound review metadata count."""
    from PIL import Image,UnidentifiedImageError
    package=Path(archive)
    with zipfile.ZipFile(package) as z:
        names=z.namelist()
        if (len(names)!=len(set(names)) or not names or names.count("review.json")!=1
            or any(name!="review.json" and not _FRAME.fullmatch(name) for name in names)):
            raise ValueError("Untrusted, duplicate or missing original review evidence")
        manifest_info=z.getinfo("review.json")
        if manifest_info.file_size>1024*1024:
            raise ValueError("Unbounded review evidence manifest")
        try:manifest=json.loads(z.read("review.json"))
        except (ValueError,UnicodeError) as exc:
            raise ValueError("Invalid original scene review JSON") from exc
        if not isinstance(manifest,dict) or manifest.get("schema")!=2:
            raise ValueError("Unknown original audiovisual review schema")
        images=manifest.get("frames")
        if not isinstance(images,list) or not (1<=len(images)<=_MAX_SAMPLES):
            raise ValueError("Review archive lacks physically observed sampled frames")
        expected={f"frames/review_{i:04d}.png" for i in range(1,len(images)+1)}
        if set(names)-{"review.json"}!=expected:
            raise ValueError("Original review archive has omitted or unlisted media")
        picture_shapes=set()
        for i,item in enumerate(images,1):
            name=f"frames/review_{i:04d}.png"
            if (not isinstance(item,dict) or item.get("file")!=name or
                not isinstance(item.get("sha256"),str) or not _HEX.fullmatch(item["sha256"]) or
                type(item.get("bytes")) is not int or item["bytes"]<100):
                raise ValueError("Review image receipt missing immutable pixel identity")
            info=z.getinfo(name)
            if info.file_size!=item["bytes"] or info.file_size>40*1024*1024:
                raise ValueError("Original sampled image violated memory/disk budget")
            data=z.read(name)
            if hashlib.sha256(data).hexdigest()!=item["sha256"]:
                raise ValueError("Review image differs from decoded original media evidence")
            try:
                with Image.open(io.BytesIO(data)) as img:
                    if img.format!="PNG":
                        raise ValueError("Source review is not actual lossless PNG evidence")
                    img.load()
                    if not (1<=img.width<=640 and 1<=img.height<=2048):
                        raise ValueError("Invalid sampled original review image shape")
                    picture_shapes.add((img.width,img.height))
            except (UnidentifiedImageError,OSError) as exc:
                raise ValueError("Original preview failed real pixel decoding") from exc
        provenance=manifest.get("source_sha256")
        if (len(picture_shapes)!=1 or not isinstance(provenance,str)
                or not _HEX.fullmatch(provenance)
                or manifest.get("source_asset_id")!=provenance
                or not isinstance(manifest.get("source_attestation_id"),str)
                or not manifest["source_attestation_id"]):
            raise ValueError("Review frame dimensions or source provenance do not agree")
        duration=manifest.get("source_original_duration_seconds")
        if isinstance(duration,bool) or not isinstance(duration,(int,float)) or (
                not math.isfinite(duration) or duration<=0):
            raise ValueError("Review has no measurable original movie duration")
        observed_times=[]
        for item in images:
            time=item.get("time_seconds")
            if isinstance(time,bool) or not isinstance(time,(int,float)) or (
                    not math.isfinite(time) or not 0<=time<duration or
                    (observed_times and time<=observed_times[-1])):
                raise ValueError("Review frame timecodes do not match a real movie clock")
            observed_times.append(time)
        windows=manifest.get("audio_window_evidence")
        if not isinstance(windows,list) or len(windows)>_MAX_SAMPLES:
            raise ValueError("Unbounded original audio observation receipt")
        for window in windows:
            if not isinstance(window,dict):
                raise ValueError("Unverifiable soundtrack observation record")
            start,end=window.get("start_seconds"),window.get("end_seconds")
            if (type(start) not in (int,float) or type(end) not in (int,float)
                 or not math.isfinite(start) or not math.isfinite(end)
                 or not 0<=start<end<=duration):
                raise ValueError("Audio evidence window outside original film timebase")
            for level in ("mean_dbfs","peak_dbfs"):
                value=window.get(level)
                if value!="-inf" and (
                     type(value) not in (int,float) or not math.isfinite(value)):
                    raise ValueError("Original audio loudness record is malformed")
        if windows and manifest.get("source_has_actual_audio") is not True:
            raise ValueError("Reported actual audio windows absent from source")
        return {"actual_sampled_frames":len(images),
                "true_image_decoders_completed":True,
                "source_sha256":manifest["source_sha256"],
                "human_artistic_quality_certified":False,
                "complete_temporal_quality_evaluated":False}

def produce_review_bundle(plan_path,workspace,vault_root,output):
    from PIL import Image,ImageChops,ImageStat
    root=Path(workspace).resolve()
    plan_file=Path(plan_path).resolve()
    dest=Path(output).resolve()
    if not plan_file.is_file() or not plan_file.is_relative_to(root):
        raise ValueError("Original director review plan escaped workspace")
    if not dest.is_relative_to(root) or dest.suffix.lower()!=".zxreview" or dest.exists():
        raise ValueError("Review output must be a new standalone .zxreview bundle")
    plan=json.loads(plan_file.read_text(encoding="utf-8"))
    movie,measured,times,windows=_validate_review_plan(
        plan,root,MediaVault(vault_root))
    original_hash=sha256_file(movie)
    if original_hash!=plan["media"]["asset_id"]:
        raise ValueError("Actual original movie no longer matches owner custody")
    complete=full_decode_inspection(movie,expected={"require_audio":bool(windows)})
    if not complete["technical_delivery_verified"]:
        raise ValueError("Original movie failed entire real picture/sound decode")
    images=[]
    previous=None
    audio=[]
    dest.parent.mkdir(parents=True,exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=".zx7-media-review-",dir=root) as scratch:
            stage=Path(scratch)
            for i,timestamp in enumerate(times,1):
                frame=stage/f"review_{i:04d}.png"
                # Decode a real frame at the director's exact original
                # timecode. Downscale preview only; original source untouched.
                args=["ffmpeg","-hide_banner","-loglevel","error","-xerror",
                      "-nostdin","-i",str(movie),"-ss",str(timestamp),
                      "-frames:v","1","-vf","scale=w='min(640,iw)':h=-2",
                      "-pix_fmt","rgb24","-y",str(frame)]
                subprocess.run(args,check=True,timeout=120,
                               capture_output=True,text=True)
                if not frame.is_file() or frame.stat().st_size<100:
                    raise ValueError("No original frame decoded at selected timecode")
                with Image.open(frame) as orig:
                    if orig.format!="PNG":
                        raise ValueError("Review image was not original-lossless PNG")
                    rgb=orig.convert("RGB")
                    channels=ImageStat.Stat(rgb)
                    luma=ImageStat.Stat(rgb.convert("L"))
                    delta=None if previous is None else round(
                        ImageStat.Stat(ImageChops.difference(previous,rgb)
                                      .convert("L")).mean[0],4)
                    previous=rgb
                    evidence={"file":"frames/"+frame.name,
                              "time_seconds":timestamp,
                              "sha256":sha256_file(frame),
                              "bytes":frame.stat().st_size,
                              "decoded_width":rgb.width,
                              "decoded_height":rgb.height,
                              "mean_rgb_8bit":[round(v,4) for v in channels.mean],
                              "mean_luma_8bit":round(luma.mean[0],4),
                              "sample_pair_mean_absolute_luma_difference":delta}
                    images.append(evidence)
            for a,b in windows:
                audio.append(_snapshot_window(movie,a,b))
            if sha256_file(movie)!=original_hash:
                raise ValueError("Owner film changed while extracting actual review evidence")
            manifest={"schema":2,"source_sha256":original_hash,
                      "source_asset_id":plan["media"]["asset_id"],
                      "source_attestation_id":plan["media"]["attestation_id"],
                      "source_original_duration_seconds":measured["duration_seconds"],
                      "source_picture_width":measured["width"],
                      "source_picture_height":measured["height"],
                      "source_has_actual_audio":measured["audio_stream_present"],
                      "full_picture_and_sound_decode_verified":True,
                      "sampled_original_frames_only_not_all_frame_visual_evaluation":True,
                      "frames":images,"audio_window_evidence":audio,
                      "audio_windows_metered_after_original_exact_atrim":True,
                      "audio_windows_do_not_prove_dialogue_intelligibility":True,
                      "color_values_are_display_RGB_not_scene_linear_or_ACES":True,
                      "motion_sample_delta_is_not_optical_flow_or_continuity_judgment":True,
                      "creative_story_or_style_approval":False,
                      "human_artistic_quality_certified":False}
            # Only this temporary archive is exposed after all member
            # lengths, digests, PNG decoding and source continuity verify.
            archive=stage/"original-review.zip"
            with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED) as z:
                for row in images:
                    z.write(stage/Path(row["file"]).name,arcname=row["file"])
                z.writestr("review.json",json.dumps(manifest,sort_keys=True,indent=2)+"\n")
            verified=verify_review_bundle(archive)
            if verified["source_sha256"]!=original_hash:
                raise ValueError("Review artifact source provenance changed")
            if sha256_file(movie)!=original_hash:
                raise ValueError("Original picture or sound changed before proof release")
            # The verified archive and destination share the trusted workspace
            # filesystem: publish only if no other reviewer won the race.
            # Copying directly to dest could truncate an accepted review.
            os.link(archive,dest)
            return {"path":str(dest),"sha256":sha256_file(dest),
                    "bytes":dest.stat().st_size,
                    "source_sha256":original_hash,
                    "actual_decoded_review_frames":len(images),
                    "original_audio_windows_measured":len(audio),
                    "human_artistic_quality_certified":False}
    except BaseException:
        # Never delete an independently accepted review bundle. Staging is
        # private and automatically removed by TemporaryDirectory.
        raise

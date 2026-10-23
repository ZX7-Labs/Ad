"""Factual broadcast-style integrated loudness and TRUE-PEAK observation.

Read-only measurement of actual, rights-attested original audiovisual media.
Uses FFmpeg ebur128 true-peak option, never normalizes/re-encodes sound or
imposes an artistic streaming/broadcast target. It reports actual LUFS/LRA
and oversampled dBFS peak when the local installed analyzer supports them.

EBU R128 advises LRA isn't meaningful on very short (<60 s) content.
Full source pixel/audio decoder acceptance is independent of sound quality.
"""
from __future__ import annotations
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path

from .composite_mix import _exact_media,sealed_attested_original
from .delivery_audit import _probe_details
from .media_vault import MediaVault,sha256_file

_VALUE=r"(-?(?:inf|\d+(?:\.\d+)?))"


def _level(summary,title,unit):
    match=re.search(title+r":\s*"+_VALUE+r"\s*"+unit,summary,re.I)
    if not match:
        raise ValueError("Native ebur128 analysis omitted "+title+" measurement")
    raw=match.group(1)
    if raw.lower()=="-inf":
        return "-inf" # JSON compliant; never encode Infinity/NaN
    value=float(raw)
    if not math.isfinite(value):
        raise ValueError("Native measured loudness is non-finite")
    return value


def inspect_original_loudness(plan_file,workspace,vault_root):
    root=Path(workspace).resolve()
    source=Path(plan_file).resolve()
    if not source.is_file() or not source.is_relative_to(root):
        raise ValueError("No original protected artist loudness plan")
    plan_sha=sha256_file(source)
    plan=json.loads(source.read_text(encoding="utf-8"))
    if sha256_file(source)!=plan_sha:
        raise ValueError("Sound director's original plan changed during read")
    if not isinstance(plan,dict) or set(plan)!={"media"}:
        raise ValueError("Sound audit needs only verified original media")
    media=plan["media"]
    if not isinstance(media,dict) or set(media)!={"source","asset_id","attestation_id"}:
        raise ValueError("Original soundtrack requires exactly one licensed source identity")
    movie=_exact_media(media,MediaVault(vault_root),root,need="video")
    physical=_probe_details(movie)
    if not physical["audio_stream_present"]:
        raise ValueError("Actual authored film has no audio to measure")
    digest=sha256_file(movie)
    record=MediaVault(vault_root).inspect(digest,
                         attestation_id=media["attestation_id"])
    if digest!=media["asset_id"]:
        raise ValueError("Source changed before native sound loudness measurement")
    with tempfile.TemporaryDirectory(prefix=".zx7-owned-sources-",dir=root) as working:
        frozen=sealed_attested_original(
            MediaVault(vault_root),digest,media["attestation_id"],
            Path(working),{})
        if sha256_file(source)!=plan_sha or sha256_file(movie)!=digest:
            raise ValueError("Original sound program changed before native analysis")
        proc=subprocess.run(
            ["ffmpeg","-hide_banner","-nostdin","-loglevel","info",
             "-i",str(frozen),"-map","0:a:0","-vn",
             "-af","ebur128=peak=true","-f","null","-"],
            capture_output=True,text=True,timeout=7200,check=False)
        if proc.returncode:
            raise ValueError("Original waveform failed actual full-program true-peak analysis")
        if (sha256_file(frozen)!=digest or sha256_file(movie)!=digest
                or sha256_file(source)!=plan_sha):
            raise ValueError("Original audio bytes or owner direction changed during true-peak measurement")
        MediaVault(vault_root).inspect(digest,
            attestation_id=media["attestation_id"])
    if "Summary:" not in (proc.stderr or ""):
        raise ValueError("Actual EBU R128 media analysis was not completed")
    report=proc.stderr.rsplit("Summary:",1)[1]
    sections=re.split(r"\n\s*(Integrated loudness|Loudness range|True peak):",report)
    if len(sections)<7:
        raise ValueError("Actual EBU R128 measurement summary was incomplete")
    facts={sections[i]:sections[i+1] for i in range(1,len(sections)-1,2)}
    try:
        integrated=_level(facts["Integrated loudness"],"I","LUFS")
        lra=_level(facts["Loudness range"],"LRA","LU")
        peak=_level(facts["True peak"],"Peak","dBFS")
    except KeyError as exc:
        raise ValueError("Incomplete originally decoded broadcast audio measurements") from exc
    if sha256_file(movie)!=digest or sha256_file(source)!=plan_sha:
        raise ValueError("Artist original footage/sound or instructions changed during measurement")
    return {
        "path":str(movie),
        "sha256":digest,"bytes":movie.stat().st_size,
        "asset_id":digest,"attestation_id":media["attestation_id"],
        "rights":record["rights_attestations"][0]["rights"],
        "duration_seconds":physical["duration_seconds"],"audio_present":True,
        "width":physical["width"],"height":physical["height"],
        "original_film_audio_measurement":"FFmpeg ebur128 with true-peak detector",
        "integrated_loudness_lufs":integrated,
        "loudness_range_lu":lra,
        "measured_true_peak_dbfs":peak,
        "lra_short_film_less_than_60_seconds_unreliable":
            physical["duration_seconds"]<60,
        "source_duration_seconds":physical["duration_seconds"],
        "source_original_audio_stream_verified":True,
        "meter_analyzed_exact_private_attested_cas":True,
        "audio_stream_selection":"first actual audio stream",
        "loudness_normalization_applied_to_source":False,
        "any_target_lufs_or_peak_imposed":False,
        "multitrack_stem_analysis_covered":False,
        "dialogue_intelligibility_or_aesthetic_quality_approved":False
    }

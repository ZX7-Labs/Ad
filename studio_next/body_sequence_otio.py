"""Auditable native OTIO bridge for exactly owned, frame-accurate BODY cuts.

Supports an intentional strict audiovisual subset: one ordered BT.709 CFR
picture track, one exactly aligned original-source-audio/silence track, and
the original rational frame clock. Explicitly refuses transitions, gaps,
speed ramps, missing/relinked media, unproven rights, unmatched sound and
unrepresentable NLE effects. This is genuine .otio interchange, NOT a render
motor, style choice or complete professional NLE.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from fractions import Fraction
from pathlib import Path

from .body_sequence_cuts import plan_verified_sequence
from .media_vault import MediaVault, sha256_file
from .precision_retime import _source_timebase

_SCHEMA="ZX7_ORIGINAL_AUDIOVISUAL_OTIO_V1"


def _lib():
    try:
        import opentimelineio as otio
    except ImportError as exc:
        raise RuntimeError("Actual Academy Software Foundation OpenTimelineIO is required") from exc
    return otio


def _source_file(path,root):
    root=Path(root).resolve()
    p=Path(path)
    if not p.is_absolute():
        p=root/p
    if (p.is_symlink() or not p.resolve().is_relative_to(root)
            or not p.is_file()):
        raise ValueError("Actual source project must be a local immutable owner file")
    return p.resolve()


def _time(otio,value,fps):
    return otio.opentime.RationalTime(value,float(fps))


def _range(otio,first,frames,fps):
    return otio.opentime.TimeRange(_time(otio,first,fps),_time(otio,frames,fps))


def _whole_frames(time,fps,label):
    if (time is None or not math.isfinite(time.value)
            or not math.isfinite(time.rate)
            or not math.isclose(time.rate,float(fps),rel_tol=0,abs_tol=1e-7)):
        raise ValueError("Unrepresentable original "+label+" source clock")
    rounded=round(time.value)
    if abs(time.value-rounded)>1e-7 or abs(rounded)>2_000_000:
        raise ValueError("Fractional original "+label+" frames would be lost")
    return rounded


def _required_metadata(value,label):
    # OTIO native C++ serializes nested dictionaries as AnyDictionary,
    # not Python dict. Read their actual mapping fields without assuming the
    # in-process Python type was preserved by the professional codec.
    if not hasattr(value,"get") or value.get("schema")!=_SCHEMA:
        raise ValueError("Missing exact authenticated ZX7 "+label+" NLE metadata")
    try:
        return dict(value)
    except (TypeError,ValueError) as exc:
        raise ValueError("Malformed original editor metadata map") from exc


def _video_metadata(clip,index,plan):
    return {"schema":_SCHEMA,
        "cut_id":f"cut-{index:04d}",
        "source":clip["source"],
        "asset_id":clip["asset_id"],
        "attestation_id":clip["attestation_id"],
        "audio":clip["audio"]}



def _no_unrepresented_edit(component,label,*,allow_source_range=False):
    """Fail closed, not silently flatten actual third-party NLE decisions."""
    if getattr(component,"enabled",True) is False:
        raise ValueError("Disabled original "+label+" would be dropped")
    for key in ("effects","markers"):
        values=getattr(component,key,None)
        if values is not None and len(values):
            raise ValueError("Unrepresented original "+label+" "+key+" cannot be silently discarded")
    if not allow_source_range and getattr(component,"source_range",None) is not None:
        raise ValueError("Unrepresented original "+label+" range crop")
    metadata=getattr(component,"metadata",{})
    if metadata and any(k!="zx7" for k in metadata):
        raise ValueError("Unrepresented original "+label+" creative metadata would be lost")


def import_verified_sequence_otio(file_path,workspace,vault_root):
    """Decode edited industry timeline into one new, physically checked plan.

    Editing the real NLE file may reorder/trim clips; never allows changing
    the owner-approved source or its rights without its exact prior attestation.
    Audio must move/trim with its exact original matching picture region.
    """
    otio=_lib()
    root=Path(workspace).resolve()
    source=_source_file(file_path,root)
    original_hash=sha256_file(source)
    timeline=otio.adapters.read_from_file(str(source))
    if not isinstance(timeline,otio.schema.Timeline):
        raise ValueError("An actual audiovisual OTIO Timeline is required")
    if timeline.global_start_time is not None:
        raise ValueError("Unrepresented original global timecode would be lost")
    _no_unrepresented_edit(timeline.tracks,"film stack")
    meta=_required_metadata(timeline.metadata.get("zx7"),"timeline")
    if set(meta)!={"schema","frame_rate","frame_size","source_plan_sha256",
                   "source_media_originals_attested"}:
        raise ValueError("Unexpected original timeline metadata contract")
    fpsmeta=meta["frame_rate"]
    if (not hasattr(fpsmeta,"get")
            or set(fpsmeta)!={"numerator","denominator"}
            or type(fpsmeta["numerator"]) is not int
            or type(fpsmeta["denominator"]) is not int
            or not 1<=fpsmeta["numerator"]<=240000
            or not 1<=fpsmeta["denominator"]<=100000):
        raise ValueError("Missing original rational frame rate")
    fps=Fraction(fpsmeta["numerator"],fpsmeta["denominator"])
    if not 1<=fps<=240:
        raise ValueError("Unsupported actual original timebase")
    video=timeline.video_tracks()
    audio=timeline.audio_tracks()
    if (len(video)!=1 or len(audio)!=1 or
            len(timeline.tracks)!=2 or not 1<=len(video[0])<=128
            or len(video[0])!=len(audio[0])):
        raise ValueError("Cannot silently drop other NLE tracks or unaligned sound")
    _no_unrepresented_edit(video[0],"picture track")
    _no_unrepresented_edit(audio[0],"sound track")
    originals=[]
    seen_cut_ids=set()
    for i,(clip,sound) in enumerate(zip(video[0],audio[0])):
        _no_unrepresented_edit(clip,"camera clip",allow_source_range=True)
        _no_unrepresented_edit(sound,"recorded sound",allow_source_range=True)
        if not isinstance(clip,otio.schema.Clip):
            raise ValueError("Video effects, transitions and gaps need their own physical renderer")
        fields=_required_metadata(clip.metadata.get("zx7"),"original source")
        if set(fields)!={"schema","cut_id","source","asset_id",
                          "attestation_id","audio"}:
            raise ValueError("Malformed exact NLE original media provenance")
        if (not isinstance(fields["cut_id"],str)
                or fields["cut_id"] in seen_cut_ids
                or not fields["cut_id"].startswith("cut-")
                or not fields["cut_id"][4:].isdigit()):
            raise ValueError("Duplicate or forged original editorial clip identity")
        seen_cut_ids.add(fields["cut_id"])
        if clip.name!=f"Original cut {int(fields['cut_id'][4:])+1}":
            raise ValueError("Unrepresented renamed original editorial shot would be lost")
        if (not isinstance(fields["asset_id"],str)
                or not isinstance(fields["attestation_id"],str)
                or not isinstance(fields["source"],str)
                or fields["audio"] not in ("preserve_source","intentional_silence")):
            raise ValueError("Invalid signed original media references")
        reference=clip.media_reference
        if (not isinstance(reference,otio.schema.ExternalReference)
                or reference.target_url!="zx7:sha256:"+fields["asset_id"]):
            raise ValueError("The source must remain bound to the original physical CAS")
        source_range=clip.source_range
        if source_range is None:
            raise ValueError("NLE edit removed original source frame range")
        first=_whole_frames(source_range.start_time,fps,"source in")
        frames=_whole_frames(source_range.duration,fps,"duration")
        if first<0 or frames<1:
            raise ValueError("Original cut has an empty or negative time span")
        original={"source":"zx7:sha256:"+fields["asset_id"],
            "asset_id":fields["asset_id"],
            "attestation_id":fields["attestation_id"],
            "first_frame":first,"end_frame":first+frames,
            "audio":fields["audio"]}
        # No detached soundtrack or accidental sound substitution.
        corresponding=_required_metadata(sound.metadata.get("zx7"),"recorded audio")
        if (corresponding.get("cut_id")!=fields["cut_id"] or
                corresponding.get("asset_id")!=fields["asset_id"]):
            raise ValueError("Original sound is not attached to its picture cut")
        if set(corresponding)!={"schema","cut_id","asset_id"}:
            raise ValueError("Unrepresented sound edit metadata would be lost")
        expected_sound_name=(f"Original sound {int(fields['cut_id'][4:])+1}"
             if fields["audio"]=="preserve_source" else "")
        if sound.name!=expected_sound_name:
            raise ValueError("Unrepresented renamed original sound would be lost")
        expected_range=source_range
        if fields["audio"]=="preserve_source":
            if not isinstance(sound,otio.schema.Clip):
                raise ValueError("Original recorded soundtrack was silently dropped")
            if (not isinstance(sound.media_reference,otio.schema.ExternalReference)
                    or sound.media_reference.target_url!=reference.target_url):
                raise ValueError("Recorded soundtrack was relinked to unknown media")
            snd_range=sound.source_range
            if (snd_range is None or
                    _whole_frames(snd_range.start_time,fps,"audio in")!=first or
                    _whole_frames(snd_range.duration,fps,"audio duration")!=frames):
                raise ValueError("Sound drift introduced by unmatched source trim")
        else:
            if not isinstance(sound,otio.schema.Gap):
                raise ValueError("Artist's intentional silence changed to invented sound")
            if (sound.source_range is None or
                    _whole_frames(sound.source_range.duration,fps,"silence duration")!=frames):
                raise ValueError("Silent shot audio length drifted")
        originals.append(original)
    # Native OTIO AnyDictionary must be normalized at the boundary; the
    # existing physical source/geometry validator intentionally requires an
    # ordinary strict Python JSON document.
    try:
        pixels=dict(meta["frame_size"])
    except (TypeError,ValueError,KeyError) as exc:
        raise ValueError("Malformed exact original picture geometry") from exc
    plan={"frame_rate":{"numerator":fps.numerator,"denominator":fps.denominator},
        "frame_size":pixels,"clips":originals}
    validated=plan_verified_sequence(plan,root,vault_root)
    if sha256_file(source)!=original_hash:
        raise ValueError("Original editable NLE file changed while checking actual media")
    return {"plan":plan,"frame_count":validated["frames"],
            "source_plan_sha256":meta["source_plan_sha256"],
            "original_sources_physically_verified":len(validated["originals"]),
            "original_footage_modified":False,
            "all_audio_positions_and_sources_matched":True,
            "unrepresentable_effects_silently_dropped":False,
            "creative_artistic_quality_certified":False}


def export_verified_sequence_otio(plan_file,workspace,vault_root,destination):
    otio=_lib()
    root=Path(workspace).resolve()
    src=_source_file(plan_file,root)
    out=Path(destination)
    if not out.is_absolute():
        out=root/out
    if (out.suffix!=".otio" or not out.resolve().is_relative_to(root)
            or out.exists() or out.is_symlink() or out==src):
        raise ValueError("Use a fresh local .otio project without overwriting original edits")
    source_sha=sha256_file(src)
    plan=json.loads(src.read_text(encoding="utf-8"))
    if sha256_file(src)!=source_sha:
        raise ValueError("Author's director edit changed before physical source validation")
    verified=plan_verified_sequence(plan,root,vault_root)
    fps=verified["fps"]
    timeline=otio.schema.Timeline(name=src.stem)
    picture=otio.schema.Track(name="Verified original picture",kind=otio.schema.TrackKind.Video)
    soundtrack=otio.schema.Track(name="Original synchronous audio",kind=otio.schema.TrackKind.Audio)
    for index,(original,checked) in enumerate(zip(plan["clips"],verified["clips"])):
        reference=otio.schema.ExternalReference(
            target_url="zx7:sha256:"+original["asset_id"],
            available_range=_range(otio,0,_source_timebase(checked["source"])[1],fps))
        selected=_range(otio,original["first_frame"],
                             original["end_frame"]-original["first_frame"],fps)
        entry=otio.schema.Clip(name=f"Original cut {index+1}",
            media_reference=reference,source_range=selected)
        metadata=_video_metadata(original,index,plan)
        entry.metadata["zx7"]=metadata
        picture.append(entry)
        if original["audio"]=="preserve_source":
            snd=otio.schema.Clip(name=f"Original sound {index+1}",
                media_reference=otio.schema.ExternalReference(
                    target_url=reference.target_url,
                    available_range=reference.available_range),
                source_range=_range(otio,original["first_frame"],
                          original["end_frame"]-original["first_frame"],fps))
        else:
            snd=otio.schema.Gap(source_range=_range(otio,0,
                original["end_frame"]-original["first_frame"],fps))
        snd.metadata["zx7"]={"schema":_SCHEMA,
               "cut_id":metadata["cut_id"],"asset_id":metadata["asset_id"]}
        soundtrack.append(snd)
    timeline.tracks.append(picture)
    timeline.tracks.append(soundtrack)
    timeline.metadata["zx7"]={"schema":_SCHEMA,
        "frame_rate":{"numerator":fps.numerator,"denominator":fps.denominator},
        "frame_size":plan["frame_size"],
        "source_plan_sha256":source_sha,
        "source_media_originals_attested":True}
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=out.parent,
                                         prefix=".zx7-otio-",suffix=".otio",
                                         delete=False) as file:
            tmp=Path(file.name)
        otio.adapters.write_to_file(timeline,str(tmp))
        # The exact exported media must be decoded by the SAME importer that
        # will be used after any third-party professional editor makes changes.
        check=import_verified_sequence_otio(tmp,root,vault_root)
        if (check["frame_count"]!=verified["frames"] or
                check["plan"]!={**plan,"clips":[{**c,"source":"zx7:sha256:"+c["asset_id"]}
                      for c in plan["clips"]]}):
            raise ValueError("Original industry timeline lost authored video or audio facts")
        if sha256_file(src)!=source_sha:
            raise ValueError("Original owner edit changed during OTIO export")
        os.link(tmp,out)
        return {"path":str(out),"sha256":sha256_file(out),
            "frame_count":check["frame_count"],
            "actual_rights_custody_rechecked":True,
            "picture_and_sound_roundtrip_verified":True,
            "full_professional_nle_certified":False}
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)

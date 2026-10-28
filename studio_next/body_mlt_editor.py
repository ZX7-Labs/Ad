"""Rights-bound MLT editorial project interchange; not a universal NLE renderer.

MLT's documented XML model is producer -> per-track playlist -> tractor.
Only typed original timeline decisions become XML. No user-supplied MLT XML,
plugin names, effect expressions, file URLs, shell commands or execution.
The result is host-local; portable media relocation needs a separate audited
adapter. Intentional mute is explicit, never presented as preserved sound.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from .body_color_pipeline import _actual_bt709_source
from .media_vault import MediaVault, sha256_file
from .pcm_wave import inspect_pcm_wav
from .precision_retime import _source_timebase
from .delivery_audit import _probe_details
from .composite_mix import _decoded_source_duration


def _integer(v, label, low, high):
    if type(v) is not int or not low <= v <= high:
        raise ValueError("MLT " + label + " must be an exact bounded integer")
    return v


def _rate(v):
    if not isinstance(v,dict) or set(v)!={"numerator","denominator"}:
        raise ValueError("MLT timebase must be a rational numerator/denominator")
    r=Fraction(_integer(v["numerator"],"fps numerator",1,240000),
               _integer(v["denominator"],"fps denominator",1,100000))
    if not 1<=r<=240:raise ValueError("MLT physical timebase outside supported range")
    return r


def _prop(owner,name,value):
    ET.SubElement(owner,"property",{"name":name}).text=str(value)


# Use MLT QtBlend for source-over and the independently supported Frei0r Cairo
# compositor for true layer blending. Ubuntu MLT 7.22 accepts qtblend mode
# properties but yields source-over pixels for opaque native media in practice.
# Never pretend an XML value alone proves a rendered visual operation.
_BLEND_MODES={"normal":0,"multiply":13,"screen":14,"overlay":15}
_CAIRO_MODES={"normal","multiply","screen","overlay"}


def _opacity_number(value):
    """Strict canonical opacity number: no bool, NaN or injected native syntax."""
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:
        raise ValueError("Native layer opacity must be a finite number in [0, 1]")
    return format(float(value), ".12g")


def _opacity_animation(track,frames):
    """Encode model-authored *absolute timeline-frame* opacity, not a style preset."""
    if "opacity" in track and "opacity_keyframes" in track:
        raise ValueError("Choose either fixed or animated MLT opacity, not both")
    if "opacity_keyframes" not in track:
        return _opacity_number(track.get("opacity",1))
    keys=track["opacity_keyframes"]
    if not isinstance(keys,list) or not 2<=len(keys)<=128:
        raise ValueError("Native opacity requires 2..128 authored timeline keyframes")
    parts=[]
    previous=-1
    for key in keys:
        if not isinstance(key,dict) or set(key)!={"frame","opacity"}:
            raise ValueError("Native opacity keyframe needs frame and opacity only")
        frame=_integer(key["frame"],"opacity frame",0,frames-1)
        if frame<=previous or (previous==-1 and frame!=0):
            raise ValueError("Native opacity frames must start at 0 and increase strictly")
        parts.append(str(frame)+"="+_opacity_number(key["opacity"]))
        previous=frame
    return ";".join(parts)


def _verify_native_opacity(value,frames):
    """Accept only the finite scalar/linear frame syntax emitted by BODY."""
    if not isinstance(value,str) or len(value)>4096 or not value:
        raise ValueError("MLT opacity contains unapproved native animation")
    if "=" not in value:
        if _opacity_number(float(value))!=value:
            raise ValueError("MLT opacity is not a canonical finite scalar")
        return value
    pieces=value.split(";")
    if not 2<=len(pieces)<=128:
        raise ValueError("MLT opacity animation count is invalid")
    keys=[]
    for item in pieces:
        if item.count("=")!=1:
            raise ValueError("MLT opacity contains unapproved keyframe syntax")
        frame_text,level=item.split("=")
        if not frame_text.isdigit() or str(int(frame_text))!=frame_text:
            raise ValueError("MLT opacity keyframe is not a canonical frame")
        try: level_number=float(level)
        except ValueError as exc:
            raise ValueError("MLT opacity has malformed keyframe value") from exc
        if _opacity_number(level_number)!=level:
            raise ValueError("MLT opacity keyframe is not a canonical level")
        keys.append({"frame":int(frame_text),"opacity":level_number})
    if _opacity_animation({"opacity_keyframes":keys},frames)!=value:
        raise ValueError("MLT opacity animation cannot be reconstructed safely")
    return value



def _gain_number(value):
    """dB is a finite typed authored gain, not native filter syntax."""
    if type(value) not in (int,float) or not math.isfinite(value) or not -96<=value<=24:
        raise ValueError("MLT sound gain must be a finite -96..24 dB number")
    if value==0:
        return "0"
    numeric=float(value)
    historical=format(numeric,".12g")
    # Existing native .mlt projects use twelve significant decimal digits.
    # Preserve that exact canonical spelling whenever it is lossless, but
    # never round a newly authored high-precision dB value merely to fit an
    # older display convention. repr() roundtrips the full binary64 value.
    return historical if float(historical)==numeric else repr(numeric)


def _gain_animation(track,frames):
    if "gain_db" in track and "gain_keyframes" in track:
        raise ValueError("Choose fixed or animated MLT gain, not both")
    if "gain_keyframes" not in track:
        return _gain_number(track.get("gain_db",0))
    keys=track["gain_keyframes"]
    if not isinstance(keys,list) or not 2<=len(keys)<=128:
        raise ValueError("Native gain requires 2..128 director-authored frame keyframes")
    parts=[]
    previous=-1
    for key in keys:
        if not isinstance(key,dict) or set(key)!={"frame","gain_db"}:
            raise ValueError("Native gain keyframe must have frame and gain_db only")
        frame=_integer(key["frame"],"gain frame",0,frames-1)
        if frame<=previous or (previous==-1 and frame!=0):
            raise ValueError("Native gain frames must begin at zero and increase strictly")
        parts.append(str(frame)+"="+_gain_number(key["gain_db"]))
        previous=frame
    return ";".join(parts)


def _verify_native_gain(value,frames):
    """Only canonical scalar or linearly keyed dB enters the MLT volume plugin."""
    if not isinstance(value,str) or not value or len(value)>4096:
        raise ValueError("Original sound contains invalid native gain")
    if "=" not in value:
        try:numeric=float(value)
        except (TypeError,ValueError) as exc:
            raise ValueError("Original native gain is not a number") from exc
        if _gain_number(numeric)!=value:
            raise ValueError("Original MLT gain is not a canonical finite decibel")
        return value
    parts=value.split(";")
    if not 2<=len(parts)<=128:
        raise ValueError("Native gain has unapproved animation length")
    keys=[]
    for item in parts:
        if item.count("=")!=1:
            raise ValueError("Unsupported MLT gain interpolation syntax")
        frame,value_text=item.split("=")
        if not frame.isdigit() or str(int(frame))!=frame:
            raise ValueError("Noncanonical native gain frame")
        try:numeric=float(value_text)
        except (ValueError,TypeError) as exc:
            raise ValueError("Noncanonical native sound gain") from exc
        if _gain_number(numeric)!=value_text:
            raise ValueError("Native sound gain is not canonical")
        keys.append({"frame":int(frame),"gain_db":numeric})
    if _gain_animation({"gain_keyframes":keys},frames)!=value:
        raise ValueError("MLT sound animation cannot be reconstructed")
    return value


def _pan_number(value):
    """MLT panner split: 0 = left, 0.5 = center, 1 = right.

    The author controls actual physical channel balance, not an inferred
    visual pan or generic sound effect. This position is a native MLT
    coordinate, avoiding lossy conversions between separate representations.
    """
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:
        raise ValueError("MLT native stereo pan must be a finite position in [0,1]")
    # Use the shortest IEEE-754 roundtrippable decimal for author-owned
    # source values: the 12-significant-digit visual/gain convention would
    # silently change an arbitrary original artist pan decision on import.
    # Generated interpolation anchors are bounded and rounded separately.
    if value==0 or value==1:
        return str(int(value))
    return repr(float(value))


def _pan_animation(track,frames):
    if "pan" in track and "pan_keyframes" in track:
        raise ValueError("Choose a fixed or animated native stereo pan, not both")
    if "pan_keyframes" not in track:
        return _pan_number(track.get("pan",0.5))
    keys=track["pan_keyframes"]
    if not isinstance(keys,list) or not 2<=len(keys)<=128:
        raise ValueError("Native stereo pan needs two or more authored keyframes")
    previous=-1
    items=[]
    for key in keys:
        if not isinstance(key,dict) or set(key)!={"frame","pan"}:
            raise ValueError("Native stereo pan keyframe has an invalid property")
        frame=_integer(key["frame"],"stereo pan frame",0,frames-1)
        if frame<=previous or (previous==-1 and frame!=0):
            raise ValueError("Native stereo pan frames must begin at 0 and increase strictly")
        items.append(str(frame)+"="+_pan_number(key["pan"]))
        previous=frame
    return ";".join(items)


def _verify_native_pan(value,frames):
    """Reject all panner script/expression syntax not generated by this BODY."""
    if not isinstance(value,str) or not value or len(value)>4096:
        raise ValueError("Native pan contains unverified plugin syntax")
    if "=" not in value:
        try: number=float(value)
        except (ValueError,TypeError) as exc:
            raise ValueError("Native pan is not a canonical finite number") from exc
        if _pan_number(number)!=value:
            raise ValueError("Native stereo pan is not in canonical representation")
        return value
    keys=[]
    for part in value.split(";"):
        if part.count("=")!=1:
            raise ValueError("Native stereo pan keyframe grammar cannot be authenticated")
        frame,position=part.split("=")
        if not frame.isdigit() or str(int(frame))!=frame:
            raise ValueError("Native stereo pan frame is not canonical")
        try: number=float(position)
        except (ValueError,TypeError) as exc:
            raise ValueError("Native stereo pan is not numeric") from exc
        if _pan_number(number)!=position:
            raise ValueError("Native stereo pan keyframe has unapproved value")
        keys.append({"frame":int(frame),"pan":number})
    if _pan_animation({"pan_keyframes":keys},frames)!=value:
        raise ValueError("Native panner automation cannot reconstruct all original artist frames")
    return value


def _single_recorded_audio_stream(path, *, require_stereo=False):
    """Require exactly one recorded original audio stream and supported channels.

    The currently published native MLT delivery is a two-channel AAC film.
    Never silently collapse a spatial 5.1/7.1 master into stereo: that needs
    an explicitly approved, independently measured artist-authored conform.
    """
    try:
        raw=subprocess.check_output(["ffprobe","-v","error",
            "-select_streams","a",
            "-show_entries","stream=index,channels,sample_rate",
            "-of","json",str(path)],timeout=90)
        streams=json.loads(raw).get("streams",[])
    except (OSError,ValueError,subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        raise ValueError("Recorded soundtrack cannot be physically probed") from exc
    if (len(streams)!=1 or type(streams[0].get("index")) is not int or
            not 0<=streams[0]["index"]<=64):
        raise ValueError("MLT source must contain one unambiguous actual original audio stream")
    track=streams[0]
    if type(track.get("channels")) is not int or track["channels"] not in (1,2):
        raise ValueError("Native MLT stereo delivery cannot silently downmix spatial/multichannel original audio")
    if require_stereo and track["channels"]!=2:
        raise ValueError("Native stereo panner cannot spatially balance one-channel original audio: explicit stereo conform is required")
    try:sample_rate=int(track["sample_rate"])
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError("Native MLT audio stream has no measured physical sample clock") from exc
    if not 8000<=sample_rate<=192000:
        raise ValueError("Native MLT audio sample rate is outside independently measured limits")
    return track["index"]


def _audio_only_source_frames(path, fps):
    """Count exact original integer PCM samples on this project's frame clock.

    Support standard and extensible PCM uniformly on Python 3.11 and later.
    Do not interpret/convert the owner's original channel layout or codec.
    """
    try:
        source=inspect_pcm_wav(path)
        frames=(source["frames"]*fps.numerator)//(
            source["sample_rate"]*fps.denominator)
    except (OSError,ValueError) as exc:
        raise ValueError("Native original WAV frame timing cannot be verified") from exc
    if frames<1:
        raise ValueError("Recorded PCM is shorter than a project frame")
    return frames


def validate_mlt_edit(plan,workspace,vault_root):
    """Verify every media byte and frame position before creating a project."""
    root=Path(workspace).resolve()
    vault=MediaVault(vault_root)
    if (not isinstance(plan,dict) or not {"frame_rate","frame_size","tracks"}.issubset(plan)
            or set(plan)-{"frame_rate","frame_size","tracks","audio_tracks"}):
        raise ValueError("MLT project needs original frame, picture and optional sound tracks")
    fps=_rate(plan["frame_rate"])
    frame_size=plan["frame_size"]
    if not isinstance(frame_size,dict) or set(frame_size)!={"width","height"}:
        raise ValueError("MLT frame_size needs width/height")
    width=_integer(frame_size["width"],"width",2,7680)
    height=_integer(frame_size["height"],"height",2,4320)
    if width%2 or height%2:
        raise ValueError("MLT H264 reference clock requires even output dimensions")
    tracks=plan["tracks"]
    if not isinstance(tracks,list) or not 1<=len(tracks)<=8:
        raise ValueError("MLT native project requires 1..8 timeline tracks")
    resolved=[]
    sources={}
    total=0
    blend_modes=[]
    for ti,track in enumerate(tracks):
        if (not isinstance(track,dict) or "clips" not in track or
                set(track)-{"clips","blend_mode","opacity","opacity_keyframes"}):
            raise ValueError("MLT track requires original clips and only a typed blend mode")
        mode=track.get("blend_mode","normal")
        if type(mode) is not str or mode not in _BLEND_MODES:
            raise ValueError("MLT native compositing mode is not an approved visual operation")
        if ti==0 and mode!="normal":
            raise ValueError("The original bottom video track has no lower layer to blend")
        blend_modes.append(mode)
        clips=track["clips"]
        if not isinstance(clips,list) or not 1<=len(clips)<=128:
            raise ValueError("MLT track requires 1..128 actual source clips")
        end_at=0
        checked=[]
        for i,clip in enumerate(clips):
            required={"source","asset_id","attestation_id","position_frame",
                      "first_frame","end_frame","audio"}
            if not isinstance(clip,dict) or set(clip)!=required:
                raise ValueError("MLT clip has incomplete physical source or placement")
            if clip["audio"]!="intentional_silence":
                raise ValueError("MLT video-layer bridge cannot preserve/mix original audio; explicit silence only")
            asset=clip["asset_id"]; att=clip["attestation_id"]
            if not isinstance(asset,str) or not isinstance(att,str) or (
                clip["source"]!="zx7:sha256:"+asset):
                raise ValueError("MLT cannot accept an untrusted, changed or unlicensed media URL")
            record=vault.inspect(asset,attestation_id=att)
            if record["mime"] not in ("video/mp4","video/quicktime","video/webm"):
                raise ValueError("MLT input must be actual verified source video")
            source=Path(record["path"]).resolve()
            if not source.is_relative_to(root):
                raise ValueError("MLT media must remain in the same owned studio workspace")
            pos=_integer(clip["position_frame"],"position",0,1000000)
            first=_integer(clip["first_frame"],"source in",0,1000000)
            exclusive=_integer(clip["end_frame"],"source out",1,1000000)
            if exclusive<=first:raise ValueError("MLT original source cut must be nonempty")
            if pos<end_at:
                raise ValueError("Overlapping clips in one track require a separate editable track")
            if asset not in sources:
                observed=_probe_details(source)
                if (observed["width"],observed["height"])!=(width,height):
                    raise ValueError("MLT cannot silently rescale original source pixels")
                _actual_bt709_source(source)
                measured,frames=_source_timebase(source)
                if measured!=fps:
                    raise ValueError("MLT cannot silently retime a different source clock")
                sources[asset]={"path":source,"frames":frames,"attestation":att}
            if exclusive>sources[asset]["frames"]:
                raise ValueError("MLT cut exceeds actual decoded media frames")
            end_at=pos+(exclusive-first)
            total=max(total,end_at)
            checked.append({"asset":asset,"source":source,"position":pos,
                            "first":first,"last":exclusive-1,"end":end_at})
        resolved.append(checked)
    if total>1000000 or Fraction(total,1)/fps>24*3600:
        raise ValueError("MLT project exceeds explicit host frame/time budget")
    opacities=[_opacity_animation(track,total) for track in tracks]
    if opacities[0]!="1":
        raise ValueError("MLT bottom picture track has no background to fade")
    sound_tracks=plan.get("audio_tracks",[])
    if not isinstance(sound_tracks,list) or len(sound_tracks)>4:
        raise ValueError("MLT authenticated sound supports up to four separate tracks")
    sound_sources={}
    resolved_sound=[]
    gains=[]
    pans=[]
    verified_stereo=set()
    for ti,track in enumerate(sound_tracks):
        if (not isinstance(track,dict) or "clips" not in track or
                set(track)-{"clips","gain_db","gain_keyframes","pan","pan_keyframes"}):
            raise ValueError("MLT sound track needs original clips and typed gain controls")
        gains.append(_gain_animation(track,total))
        pans.append(_pan_animation(track,total))
        clips=track["clips"]
        if not isinstance(clips,list) or not 1<=len(clips)<=128:
            raise ValueError("MLT sound track requires 1..128 physically recorded clips")
        end_at=0
        checked=[]
        for clip in clips:
            fields={"source","asset_id","attestation_id","position_frame",
                    "first_frame","end_frame"}
            if not isinstance(clip,dict) or set(clip)!=fields:
                raise ValueError("MLT sound clip requires original ownership, source span and position")
            asset=clip["asset_id"];att=clip["attestation_id"]
            if (not isinstance(asset,str) or not isinstance(att,str) or
                    clip["source"]!="zx7:sha256:"+asset):
                raise ValueError("MLT sound source has no matching authenticated original identity")
            record=vault.inspect(asset,attestation_id=att)
            audio_only=record["mime"]=="audio/wav"
            if not audio_only and record["mime"] not in ("video/mp4","video/quicktime","video/webm"):
                raise ValueError("Native sound source requires owner-attested video audio or actual PCM WAV")
            file=Path(record["path"]).resolve()
            if not file.is_relative_to(root):
                raise ValueError("Original sound escapes the owner's studio workspace")
            pos=_integer(clip["position_frame"],"sound position",0,1000000)
            first=_integer(clip["first_frame"],"sound in",0,1000000)
            end=_integer(clip["end_frame"],"sound out",1,1000000)
            if end<=first or pos<end_at or pos+end-first>total:
                raise ValueError("Original sound overlaps its track or exceeds the picture timeline")
            if asset not in sound_sources:
                if not audio_only:
                    probe=_probe_details(file)
                    if not probe["audio_stream_present"]:
                        raise ValueError("Audio track contains no physically recorded soundtrack")
                has_pan="pan" in track or "pan_keyframes" in track
                actual_audio_index=_single_recorded_audio_stream(
                    file,require_stereo=has_pan)
                if has_pan:verified_stereo.add(asset)
                if audio_only:
                    frames=_audio_only_source_frames(file,fps)
                else:
                    source_fps,frames=_source_timebase(file)
                    if source_fps!=fps:
                        raise ValueError("Original soundtrack requires the authored rational frame clock")
                available=_decoded_source_duration(file,"audio")
                sound_sources[asset]={"path":file,"frames":frames,
                    "audio_seconds":available,"attestation":att,
                    "audio_index":actual_audio_index}
            info=sound_sources[asset]
            if ("pan" in track or "pan_keyframes" in track) and asset not in verified_stereo:
                # A source can appear on another bus with no authored pan.
                # Never trust a cached audio stream index as stereo proof.
                _single_recorded_audio_stream(file,require_stereo=True)
                verified_stereo.add(asset)
            if end>info["frames"] or float(Fraction(end,1)/fps)>info["audio_seconds"]+.015:
                raise ValueError("Original soundtrack is shorter than the selected source cut")
            end_at=pos+end-first
            checked.append({"asset":asset,"source":file,"position":pos,
                            "first":first,"last":end-1,"end":end_at})
        resolved_sound.append(checked)
    return {"fps":fps,"width":width,"height":height,"tracks":resolved,
            "sources":sources,"frames":total,"audio_tracks":resolved_sound,
            "audio_sources":sound_sources,"blend_modes":blend_modes,
            "opacities":opacities,"sound_gains":gains,"sound_pans":pans}


def build_mlt_xml(plan,checked):
    """MLT's XML uses inclusive source out points and frame-normalized blanks."""
    rate=checked["fps"]; width=checked["width"]; height=checked["height"]
    root=ET.Element("mlt",{"version":"7","producer":"zx7-tractor"})
    ET.SubElement(root,"profile",{"description":"ZX7 measured original frame clock",
        "width":str(width),"height":str(height),"progressive":"1",
        "sample_aspect_num":"1","sample_aspect_den":"1",
        "display_aspect_num":str(width),"display_aspect_den":str(height),
        "frame_rate_num":str(rate.numerator),"frame_rate_den":str(rate.denominator),
        "colorspace":"709"})
    for i,(digest,rec) in enumerate(checked["sources"].items()):
        source=ET.SubElement(root,"producer",{"id":"source-"+digest[:24]})
        _prop(source,"mlt_service","avformat")
        _prop(source,"resource",rec["path"])
        _prop(source,"audio_index",-1)
        _prop(source,"zx7.original_sha256",digest)
        _prop(source,"zx7.attestation_id",rec["attestation"])
    for i,(digest,rec) in enumerate(checked["audio_sources"].items()):
        sound=ET.SubElement(root,"producer",{"id":"audio-source-"+digest[:24]})
        _prop(sound,"mlt_service","avformat")
        _prop(sound,"resource",rec["path"])
        _prop(sound,"video_index",-1)
        # MLT audio_index is an absolute container stream index, not the
        # ordinal among audio streams. MP4 usually has video at 0 and sound at 1.
        # This value comes from ffprobe of the custody-verified original.
        _prop(sound,"audio_index",rec["audio_index"])
        _prop(sound,"zx7.original_sha256",digest)
        _prop(sound,"zx7.attestation_id",rec["attestation"])
    for ti,clips in enumerate(checked["tracks"]):
        playlist=ET.SubElement(root,"playlist",{"id":f"track-{ti}"})
        position=0
        for clip in clips:
            blank=clip["position"]-position
            if blank:ET.SubElement(playlist,"blank",{"length":str(blank)})
            ET.SubElement(playlist,"entry",{"producer":"source-"+clip["asset"][:24],
                "in":str(clip["first"]),"out":str(clip["last"])})
            position=clip["end"]
        if position<checked["frames"]:
            ET.SubElement(playlist,"blank",{"length":str(checked["frames"]-position)})
    for ti,clips in enumerate(checked["audio_tracks"]):
        playlist=ET.SubElement(root,"playlist",{"id":f"audio-track-{ti}"})
        position=0
        for clip in clips:
            blank=clip["position"]-position
            if blank:ET.SubElement(playlist,"blank",{"length":str(blank)})
            ET.SubElement(playlist,"entry",{"producer":"audio-source-"+clip["asset"][:24],
                "in":str(clip["first"]),"out":str(clip["last"])})
            position=clip["end"]
        if position<checked["frames"]:
            ET.SubElement(playlist,"blank",{"length":str(checked["frames"]-position)})
    tractor=ET.SubElement(root,"tractor",{"id":"zx7-tractor","in":"0",
                                           "out":str(checked["frames"]-1)})
    multitrack=ET.SubElement(tractor,"multitrack")
    for ti in range(len(checked["tracks"])):
        ET.SubElement(multitrack,"track",{"producer":f"track-{ti}","hide":"audio"})
    for ti in range(len(checked["audio_tracks"])):
        ET.SubElement(multitrack,"track",{"producer":f"audio-track-{ti}","hide":"video"})
    # Preserve original Qt-only stacking when no track needs Cairo. When
    # any upper layer uses opacity animation or non-normal blend, MLT 7.22's
    # mixed Qt/Cairo tractor can hide the later overlay beneath an earlier
    # Qt layer. A single compositor family prevents that measured failure.
    uniform_cairo=len(checked["tracks"])>2 and any(
        m!="normal" or a!="1" for m,a in
        zip(checked["blend_modes"][1:],checked["opacities"][1:]))
    for ti in range(1,len(checked["tracks"])):
        transition=ET.SubElement(tractor,"transition",{
            "in":"0","out":str(checked["frames"]-1)})
        _prop(transition,"a_track",0)
        _prop(transition,"b_track",ti)
        # MLT 'luma' without a wipe map performs a dissolve, not opaque
        # compositing. The actual FFmpeg-decode test guards this distinction.
        mode=checked["blend_modes"][ti]
        opacity=checked["opacities"][ti]
        if mode=="normal" and opacity=="1" and not uniform_cairo:
            _prop(transition,"mlt_service","qtblend")
            _prop(transition,"compositing",0)
        else:
            # Frei0r Cairo exposes native animatable opacity (parameter 0)
            # and a typed blend mode (parameter 1). Use it for real fades,
            # including otherwise-normal source-over, never inert XML flags.
            _prop(transition,"mlt_service","frei0r.cairoblend")
            _prop(transition,"0",opacity)
            _prop(transition,"1",mode)
        _prop(transition,"always_active",1)
    for ti in range(len(checked["audio_tracks"])):
        transition=ET.SubElement(tractor,"transition",{
            "in":"0","out":str(checked["frames"]-1)})
        _prop(transition,"a_track",0)
        _prop(transition,"b_track",len(checked["tracks"])+ti)
        _prop(transition,"mlt_service","mix")
        _prop(transition,"start",1)
        _prop(transition,"sum",1)
        _prop(transition,"always_active",1)
    # The installed native MLT filter applies the gain to the selected
    # audio track BEFORE the tractor mix, retaining separate artist buses.
    # Track is a verified internal index, never native input from a model.
    for ti,level in enumerate(checked["sound_gains"]):
        if level!="0" or "gain_db" in plan["audio_tracks"][ti]:
            # An explicit unity-level decision is part of the editable
            # original project, even when physically neutral.
            filt=ET.SubElement(tractor,"filter",{"in":"0",
                 "out":str(checked["frames"]-1)})
            _prop(filt,"track",len(checked["tracks"])+ti)
            _prop(filt,"mlt_service","volume")
            _prop(filt,"level",level)
        position=checked["sound_pans"][ti]
        if position!="0.5" or "pan" in plan["audio_tracks"][ti]:
            # A deliberately authored neutral stereo position is distinct
            # from an absent control: keep it losslessly editable.
            filt=ET.SubElement(tractor,"filter",{"in":"0",
                 "out":str(checked["frames"]-1)})
            _prop(filt,"track",len(checked["tracks"])+ti)
            _prop(filt,"mlt_service","panner")
            _prop(filt,"channel",-1)
            _prop(filt,"gang",0)
            # MLT panner evaluates animated split only if start exists.
            # We verified this condition in the native C filter source.
            _prop(filt,"start",0.5)
            _prop(filt,"split",position)
    ET.indent(root,space="  ")
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)+b"\n"


def export_owned_mlt(plan_path,workspace,vault_root,output):
    """Immutable project publication; source validation is refreshed before link."""
    root=Path(workspace).resolve();plan_path=Path(plan_path).resolve()
    target=Path(output).absolute()
    if (not plan_path.is_relative_to(root) or not plan_path.is_file()
            or not target.is_relative_to(root) or
            not target.resolve().is_relative_to(root) or
            target.suffix.lower()!=".mlt"):
        raise ValueError("MLT bridge requires owned source JSON and a workspace .mlt target")
    if target.exists() or target.is_symlink():
        raise FileExistsError("Immutable original MLT project already exists")
    original=plan_path.read_bytes()
    plan=json.loads(original)
    checked=validate_mlt_edit(plan,root,vault_root)
    content=build_mlt_xml(plan,checked)
    target.parent.mkdir(parents=True,exist_ok=True)
    # Recheck the project and all referenced physical content before publication.
    if plan_path.read_bytes()!=original:raise ValueError("MLT artistic edit changed during export")
    for digest,asset in {**checked["sources"],**checked["audio_sources"]}.items():
        if sha256_file(asset["path"])!=digest:
            raise ValueError("MLT authenticated picture or soundtrack changed during export")
    with tempfile.TemporaryDirectory(dir=target.parent,prefix=".zx7-mlt-") as temp:
        staged=Path(temp)/"complete.mlt"
        with staged.open("xb") as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        os.link(staged,target)
    return {"path":str(target),"sha256":sha256_file(target),
            "bytes":target.stat().st_size,"tracks":len(checked["tracks"]),
            "frames":checked["frames"],
            "source_blobs":len(set(checked["sources"])|set(checked["audio_sources"])),
            "original_sound_tracks":len(checked["audio_tracks"]),
            "host_local_project_only":True,
            "sound_intentionally_silent":not bool(checked["audio_tracks"]),
            "complete_nle_or_creative_quality_approved":False}


def _verify_exact_mlt_xml_tree(root):
    """Only approved typed original media playlists and MLT sound/video services."""
    if root.tag!="mlt" or root.attrib!={"version":"7","producer":"zx7-tractor"}:
        raise ValueError("MLT root contains unapproved executable native properties")
    direct=list(root)
    producer_count=sum(x.tag=="producer" for x in direct)
    playlists=[x for x in direct if x.tag=="playlist"]
    playlist_count=len(playlists)
    picture_tracks=0
    for item in playlists:
        if item.get("id")==f"track-{picture_tracks}":
            picture_tracks+=1
        else:
            break
    sound_count=playlist_count-picture_tracks
    if (not 1<=picture_tracks<=8 or not 0<=sound_count<=4
            or not 1<=producer_count<=1536
            or playlist_count>12
            or [c.tag for c in direct] !=
               ["profile"]+["producer"]*producer_count+
               ["playlist"]*playlist_count+["tractor"]):
        raise ValueError("MLT native graph has unrecognized video/audio track structure")
    if any(x.attrib!={"id":f"audio-track-{i}"}
           for i,x in enumerate(playlists[picture_tracks:])):
        raise ValueError("MLT original recorded soundtrack order changed")
    profile=direct[0]
    profile_keys={"description","width","height","progressive",
                  "sample_aspect_num","sample_aspect_den",
                  "display_aspect_num","display_aspect_den",
                  "frame_rate_num","frame_rate_den","colorspace"}
    if (set(profile.attrib)!=profile_keys or len(profile)!=0 or
        profile.get("description")!="ZX7 measured original frame clock" or
        profile.get("progressive")!="1" or
        profile.get("sample_aspect_num")!="1" or
        profile.get("sample_aspect_den")!="1" or
        profile.get("colorspace")!="709"):
        raise ValueError("MLT timeline profile contains unapproved properties")
    try:
        width=int(profile.get("width"));height=int(profile.get("height"))
        rate=Fraction(int(profile.get("frame_rate_num")),
                      int(profile.get("frame_rate_den")))
    except (TypeError,ValueError,ZeroDivisionError) as exc:
        raise ValueError("MLT timeline profile has invalid picture/clock") from exc
    if (not 2<=width<=7680 or not 2<=height<=4320 or
        width%2 or height%2 or not 1<=rate<=240 or
        profile.get("display_aspect_num")!=str(width) or
        profile.get("display_aspect_den")!=str(height)):
        raise ValueError("MLT output canvas or authored rational clock differs")
    def properties(node,allow):
        nodes=list(node)
        if (len(nodes)!=len(allow) or
            any(c.tag!="property" or set(c.attrib)!={"name"} or
                len(c)!=0 or c.text is None for c in nodes)):
            raise ValueError("Unapproved native media service configuration")
        found={}
        for c in nodes:
            name=c.attrib["name"]
            if name not in allow or name in found:
                raise ValueError("Unapproved or duplicate MLT native property")
            found[name]=c.text
        return found
    for producer in direct[1:1+producer_count]:
        if set(producer.attrib)!={"id"}:
            raise ValueError("MLT producer has unapproved execution attributes")
        is_sound=producer.get("id","").startswith("audio-source-")
        props=properties(producer,{
            "mlt_service","resource","audio_index","zx7.original_sha256",
            "zx7.attestation_id"}|({"video_index"} if is_sound else set()))
        digest=props["zx7.original_sha256"]
        if (props["mlt_service"]!="avformat" or
            not isinstance(digest,str) or len(digest)!=64 or
            producer.get("id")!=("audio-source-" if is_sound else "source-")+digest[:24]):
            raise ValueError("MLT native producer is not a verified original video/audio CAS")
        if is_sound:
            if props["video_index"]!="-1":
                raise ValueError("MLT soundtrack must disable the original video stream")
            try:audio_index=int(props["audio_index"])
            except (TypeError,ValueError) as exc:
                raise ValueError("MLT original sound stream index invalid") from exc
            if not 0<=audio_index<=64:
                raise ValueError("MLT original sound stream index outside measured range")
        elif props["audio_index"]!="-1":
            raise ValueError("MLT visual producer must never leak recorded sound")
    for i,playlist in enumerate(playlists):
        expected=(f"track-{i}" if i<picture_tracks
                  else f"audio-track-{i-picture_tracks}")
        if playlist.attrib!={"id":expected}:
            raise ValueError("MLT playlist identity is not an authored track")
        for item in playlist:
            if len(item) or item.text and item.text.strip():
                raise ValueError("MLT timeline item has unapproved nested service")
            if item.tag=="entry":
                if set(item.attrib)!={"producer","in","out"}:
                    raise ValueError("MLT original cut includes unsupported data")
                selected=item.get("producer","")
                expected_prefix="source-" if i<picture_tracks else "audio-source-"
                if not selected.startswith(expected_prefix):
                    raise ValueError("MLT clip crosses picture and soundtrack custody")
            elif item.tag=="blank":
                if set(item.attrib)!={"length"}:
                    raise ValueError("MLT original gap has unapproved attributes")
            else:
                raise ValueError("MLT playlist contains unsupported service")
    tractor=direct[-1]
    if (set(tractor.attrib)!={"id","in","out"} or
        tractor.get("id")!="zx7-tractor" or tractor.get("in")!="0"):
        raise ValueError("MLT original tractor was changed")
    try:frames=int(tractor.get("out"))+1
    except (TypeError,ValueError) as exc:
        raise ValueError("MLT original tractor frame count invalid") from exc
    if not 1<=frames<=1000000:
        raise ValueError("MLT original film frame budget exceeded")
    transition_count=picture_tracks-1+sound_count
    kinds=[x.tag for x in tractor]
    if (kinds[:1+transition_count] !=
            ["multitrack"]+["transition"]*transition_count or
            any(tag!="filter" for tag in kinds[1+transition_count:]) or
            len(kinds)>1+transition_count+2*sound_count):
        raise ValueError("MLT native transitions, filters or soundtrack counts altered")
    multitrack=tractor[0]
    if multitrack.attrib or len(multitrack)!=playlist_count:
        raise ValueError("MLT native tractor tracks invalid")
    for i,item in enumerate(multitrack):
        expected=({"producer":f"track-{i}","hide":"audio"}
            if i<picture_tracks else
            {"producer":f"audio-track-{i-picture_tracks}","hide":"video"})
        if item.tag!="track" or item.attrib!=expected or len(item):
            raise ValueError("MLT picture/sound source stream was changed")
    for i,transition in enumerate(tractor.findall("transition")):
        if transition.attrib!={"in":"0","out":str(frames-1)}:
            raise ValueError("MLT transition time range altered")
        is_sound=i>=picture_tracks-1
        if is_sound:
            props=properties(transition,{"a_track","b_track",
                "mlt_service","always_active","start","sum"})
            expected={"a_track":"0",
                "b_track":str(picture_tracks+i-(picture_tracks-1)),
                "mlt_service":"mix","start":"1","sum":"1","always_active":"1"}
        else:
            # Strictly distinguish the Qt source-over operation and approved
            # Cairo native blend. Arbitrary Frei0r plugin names and parameters
            # are not executable through this custody-constrained XML loader.
            props={p.get("name"):p.text for p in transition.findall("property")}
            service=props.get("mlt_service")
            if service=="qtblend":
                props=properties(transition,{"a_track","b_track",
                    "mlt_service","compositing","always_active"})
                expected={"a_track":"0","b_track":str(i+1),
                    "mlt_service":"qtblend","compositing":"0","always_active":"1"}
            elif service=="frei0r.cairoblend":
                props=properties(transition,{"a_track","b_track",
                    "mlt_service","0","1","always_active"})
                if props["1"] not in _CAIRO_MODES:
                    raise ValueError("MLT native visual blending mode is not allowlisted")
                _verify_native_opacity(props["0"],frames)
                if props["1"]=="normal" and props["0"]=="1" and picture_tracks<=2:
                    raise ValueError("Unnecessary Cairo source-over is not canonical")
                expected={"a_track":"0","b_track":str(i+1),
                    "mlt_service":"frei0r.cairoblend","0":props["0"],"1":props["1"],
                    "always_active":"1"}
            else:
                raise ValueError("MLT native visual blending mode is not allowlisted")
        if props!=expected:
            raise ValueError("MLT original mixer/compositor was substituted")
    prior_sound_track=-1
    prior_service=-1
    for filt in tractor.findall("filter"):
        if filt.attrib!={"in":"0","out":str(frames-1)}:
            raise ValueError("Native audio filter has unauthorized execution span")
        controls={p.get("name"):p.text for p in filt.findall("property")}
        service=controls.get("mlt_service")
        if service not in ("volume","panner"):
            raise ValueError("No arbitrary native audio filter may execute")
        if service=="volume":
            props=properties(filt,{"track","mlt_service","level"})
            _verify_native_gain(props["level"],frames)
            service_order=0
        else:
            props=properties(filt,{"track","mlt_service",
                                   "channel","gang","start","split"})
            if (props["channel"]!="-1" or props["gang"]!="0" or
                    props["start"]!="0.5"):
                raise ValueError("Native stereo balance contains unsafe channel policy")
            _verify_native_pan(props["split"],frames)
            service_order=1
        try:
            track_index=int(props["track"])
        except (ValueError,TypeError) as exc:
            raise ValueError("Native sound filter selects a malformed track") from exc
        if (str(track_index)!=props["track"] or
                not picture_tracks<=track_index<picture_tracks+sound_count or
                track_index<prior_sound_track or
                (track_index==prior_sound_track and
                 service_order<=prior_service)):
            raise ValueError("Native sound bus filter order or identity changed")
        prior_sound_track=track_index
        prior_service=service_order
    for playlist in playlists:
        duration=0
        for item in playlist:
            try:
                if item.tag=="blank":count=int(item.get("length"))
                else:
                    start=int(item.get("in"));end=int(item.get("out"))
                    if not 0<=start<=end<=1000000:
                        raise ValueError("MLT original sound/image cut range invalid")
                    count=end-start+1
            except (ValueError,TypeError) as exc:
                raise ValueError("Malformed MLT original clip/gap") from exc
            if not 1<=count<=1000000 or duration+count>frames:
                raise ValueError("MLT source timeline overflows its original frame budget")
            duration+=count
        if duration!=frames:
            raise ValueError("MLT native sound or picture track duration mismatch")
    return {"picture_tracks":picture_tracks,"sound_tracks":sound_count}

def verify_owned_mlt_project(file_path):
    """Physically accept only allowlisted native MLT services and original media."""
    path=Path(file_path)
    if not path.is_file() or not 100<=path.stat().st_size<=2*1024*1024:
        raise ValueError("Owned MLT native project exceeds verification budget")
    raw=path.read_bytes()
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("MLT native project cannot contain executable entities")
    try:xml=ET.fromstring(raw)
    except ET.ParseError as exc:raise ValueError("Corrupt native MLT project XML") from exc
    structure=_verify_exact_mlt_xml_tree(xml)
    sources={}
    expected_rate=Fraction(
        int(xml.find("profile").get("frame_rate_num")),
        int(xml.find("profile").get("frame_rate_den")))
    width=int(xml.find("profile").get("width"))
    height=int(xml.find("profile").get("height"))
    for producer in xml.findall("producer"):
        props={p.get("name"):p.text for p in producer.findall("property")}
        digest=props["zx7.original_sha256"]
        att=props["zx7.attestation_id"]
        filename=Path(props["resource"])
        if not (isinstance(digest,str) and len(digest)==64 and
                all(c in "0123456789abcdef" for c in digest) and
                isinstance(att,str) and len(att)==64 and
                all(c in "0123456789abcdef" for c in att) and
                filename.is_absolute() and filename.name==digest and
                filename.parent.name==digest[:2] and
                filename.parent.parent.name=="objects"):
            raise ValueError("MLT native producer is not an exact physical CAS source")
        vault=MediaVault(filename.parents[2])
        record=vault.inspect(digest,attestation_id=att)
        is_sound=producer.get("id").startswith("audio-source-")
        is_audio_only=record["mime"]=="audio/wav"
        if (Path(record["path"])!=filename or
            (record["mime"] not in ("video/mp4","video/quicktime","video/webm") and
                not (is_sound and is_audio_only))):
            raise ValueError("Native project lost its original licensed video/audio")
        if digest not in sources:
            if is_audio_only:
                count=_audio_only_source_frames(filename,expected_rate)
            else:
                measured,count=_source_timebase(filename)
                if measured!=expected_rate:
                    raise ValueError("MLT original footage/sound changed its frame clock")
            sources[digest]={"frames":count}
        if is_sound:
            if props["audio_index"]!=str(_single_recorded_audio_stream(filename)):
                raise ValueError("MLT original audio index does not match verified file")
            if "sound_seconds" not in sources[digest]:
                if not is_audio_only:
                    probe=_probe_details(filename)
                    if not probe["audio_stream_present"]:
                        raise ValueError("Recorded original sound is missing")
                _single_recorded_audio_stream(filename)
                sources[digest]["sound_seconds"]=_decoded_source_duration(filename,"audio")
        else:
            if "geometry" not in sources[digest]:
                probe=_probe_details(filename)
                _actual_bt709_source(filename)
                sources[digest]["geometry"]=(probe["width"],probe["height"])
            if sources[digest]["geometry"]!=(width,height):
                raise ValueError("Native video geometry differs from its original film")
        identity=producer.get("id")
        if identity in sources.get("ids",set()):
            raise ValueError("Duplicated exact native source producer identity")
        sources.setdefault("ids",set()).add(identity)
        sources[identity]={"digest":digest,"sound":is_sound,
                           "physical_path":filename}
    verified_sources=[x for k,x in sources.items() if k!="ids" and
                      isinstance(x,dict) and "digest" in x]
    if not verified_sources:
        raise ValueError("No exact rights-authenticated audiovisual MLT media")
    # A user-modified XML may add a structurally allowlisted panner to an
    # otherwise legitimate mono bus without going through typed plan export.
    # Source custody includes the original channel identity: reject this at
    # native import, review and render, not merely at edit-plan construction.
    panned_buses=set()
    for filt in xml.findall("./tractor/filter"):
        props={p.get("name"):p.text for p in filt.findall("property")}
        if props.get("mlt_service")=="panner":
            panned_buses.add(int(props["track"])-structure["picture_tracks"])
    inspected_stereo=set()
    for ti,playlist in enumerate(xml.findall("playlist")):
        total=0
        sound_track=ti>=structure["picture_tracks"]
        for entry in playlist:
            if entry.tag=="blank":
                total+=int(entry.get("length"))
                continue
            pid=entry.get("producer")
            if pid not in sources or "digest" not in sources[pid]:
                raise ValueError("MLT timeline references unauthenticated original producer")
            digest=sources[pid]["digest"]
            if sound_track and (ti-structure["picture_tracks"] in panned_buses
                    and pid not in inspected_stereo):
                _single_recorded_audio_stream(sources[pid]["physical_path"],
                                               require_stereo=True)
                inspected_stereo.add(pid)
            if sources[pid]["sound"]!=sound_track:
                raise ValueError("MLT original audio/video stream crossed into another track")
            last=int(entry.get("out"))
            count=sources[digest]["frames"]
            if last>=count:
                raise ValueError("MLT native timeline edits exceed physically decoded source frames")
            if sound_track and (float(Fraction(last+1,1)/expected_rate)>
                    sources[digest]["sound_seconds"]+.015):
                raise ValueError("MLT soundtrack extends beyond physical recorded audio")
    return {"verified_original_sources":len(verified_sources),
            "verified_mlt_tracks":structure["picture_tracks"],
            "verified_audio_tracks":structure["sound_tracks"],
            "native_mlt_render_measured":False}

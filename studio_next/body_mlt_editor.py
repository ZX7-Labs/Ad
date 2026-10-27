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
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from .body_color_pipeline import _actual_bt709_source
from .media_vault import MediaVault, sha256_file
from .precision_retime import _source_timebase
from .delivery_audit import _probe_details


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


def validate_mlt_edit(plan,workspace,vault_root):
    """Verify every media byte and frame position before creating a project."""
    root=Path(workspace).resolve()
    vault=MediaVault(vault_root)
    if not isinstance(plan,dict) or set(plan)!={"frame_rate","frame_size","tracks"}:
        raise ValueError("MLT project needs frame_rate/frame_size/tracks only")
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
    for ti,track in enumerate(tracks):
        if not isinstance(track,dict) or set(track)!={"clips"}:
            raise ValueError("MLT track requires explicitly authored clips")
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
    return {"fps":fps,"width":width,"height":height,"tracks":resolved,
            "sources":sources,"frames":total}


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
    tractor=ET.SubElement(root,"tractor",{"id":"zx7-tractor","in":"0",
                                           "out":str(checked["frames"]-1)})
    multitrack=ET.SubElement(tractor,"multitrack")
    for ti in range(len(checked["tracks"])):
        ET.SubElement(multitrack,"track",{"producer":f"track-{ti}","hide":"audio"})
    for ti in range(1,len(checked["tracks"])):
        transition=ET.SubElement(tractor,"transition",{
            "in":"0","out":str(checked["frames"]-1)})
        _prop(transition,"a_track",0)
        _prop(transition,"b_track",ti)
        _prop(transition,"mlt_service","luma")
        _prop(transition,"always_active",1)
    ET.indent(root,space="  ")
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)+b"\n"


def export_owned_mlt(plan_path,workspace,vault_root,output):
    """Immutable project publication; source validation is refreshed before link."""
    root=Path(workspace).resolve();plan_path=Path(plan_path).resolve()
    target=Path(output).absolute()
    if (not plan_path.is_relative_to(root) or not plan_path.is_file()
            or not target.is_relative_to(root) or target.suffix.lower()!=".mlt"):
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
    for digest,asset in checked["sources"].items():
        if sha256_file(asset["path"])!=digest:
            raise ValueError("MLT producer bytes changed during export")
    with tempfile.TemporaryDirectory(dir=target.parent,prefix=".zx7-mlt-") as temp:
        staged=Path(temp)/"complete.mlt"
        with staged.open("xb") as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        os.link(staged,target)
    return {"path":str(target),"sha256":sha256_file(target),
            "bytes":target.stat().st_size,"tracks":len(checked["tracks"]),
            "frames":checked["frames"],"source_blobs":len(checked["sources"]),
            "host_local_project_only":True,
            "sound_intentionally_silent":True,
            "complete_nle_or_creative_quality_approved":False}


def verify_owned_mlt_project(file_path):
    """Reopen only our exact XML subset; verify all original custody bytes.

    An MLT XML file alone cannot issue rights or make an arbitrary producer
    acceptable. No external URLs, dynamic filters, arbitrary effects, DTD,
    or plugin imports are accepted as an owned interchange artifact.
    """
    path=Path(file_path)
    if not path.is_file() or not 100<=path.stat().st_size<=1024*1024:
        raise ValueError("MLT project artifact missing or outside verification budget")
    raw=path.read_bytes()
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("MLT XML cannot declare external entities")
    try:root=ET.fromstring(raw)
    except ET.ParseError as exc:raise ValueError("Invalid owned MLT XML") from exc
    if root.tag!="mlt" or not root.attrib.get("producer")=="zx7-tractor":
        raise ValueError("Not a verified ZX7 MLT editorial project")
    allowed={"mlt","profile","producer","property","playlist","blank","entry",
             "tractor","multitrack","track","transition"}
    if any(item.tag not in allowed for item in root.iter()):
        raise ValueError("Unverified native XML services cannot be trusted")
    parents=list(root)
    if (sum(p.tag=="profile" for p in parents)!=1 or
        sum(p.tag=="tractor" for p in parents)!=1):
        raise ValueError("MLT original project profile or tractor is ambiguous")
    producers={}
    for item in root.findall("producer"):
        props={p.get("name"):p.text for p in item.findall("property")}
        if (len(props)!=5 or len(item.findall("property"))!=5 or props.get("mlt_service")!="avformat" or
            props.get("audio_index")!="-1" or
            item.attrib.get("id")!="source-"+str(props.get("zx7.original_sha256",""))[:24]):
            raise ValueError("MLT source contains unauthorised producer properties")
        digest=props["zx7.original_sha256"]; att=props.get("zx7.attestation_id")
        filename=Path(props["resource"])
        if not (isinstance(digest,str) and len(digest)==64 and
                isinstance(att,str) and len(att)==64 and
                filename.is_absolute() and filename.name==digest and
                filename.parent.name==digest[:2] and
                filename.parent.parent.name=="objects"):
            raise ValueError("MLT original video has no exact CAS+attestation identity")
        vault=MediaVault(filename.parents[2])
        trusted=vault.inspect(digest,attestation_id=att)
        if Path(trusted["path"])!=filename or trusted["mime"] not in (
                "video/mp4","video/quicktime","video/webm"):
            raise ValueError("MLT source media no longer matches verified rights")
        if item.attrib["id"] in producers:raise ValueError("Duplicate MLT producers")
        producers[item.attrib["id"]]=digest
    playlists=root.findall("playlist")
    if not 1<=len(playlists)<=8 or not producers:
        raise ValueError("MLT timeline requires physical tracks and media")
    for index,playlist in enumerate(playlists):
        if playlist.get("id")!=f"track-{index}":
            raise ValueError("MLT track order or identity changed")
        for child in playlist:
            if child.tag=="entry":
                if set(child.attrib)!={"producer","in","out"} or child.get("producer") not in producers:
                    raise ValueError("MLT changed an owned source entry")
                try:lo=int(child.get("in"));hi=int(child.get("out"))
                except (TypeError,ValueError) as exc:raise ValueError("MLT invalid original frame index") from exc
                if not 0<=lo<=hi<=1000000:raise ValueError("MLT source range changed")
            elif child.tag=="blank":
                try:length=int(child.get("length"))
                except (TypeError,ValueError) as exc:raise ValueError("MLT invalid blank length") from exc
                if not 1<=length<=1000000:raise ValueError("MLT blank exceeds timeline")
            else:raise ValueError("MLT project contains an unsupported clip type")
    tractor=root.find("tractor")
    if tractor.get("id")!="zx7-tractor":
        raise ValueError("MLT tractor identity changed")
    tracks=tractor.findall("./multitrack/track")
    if len(tracks)!=len(playlists) or any(
        t.attrib!={"producer":f"track-{i}","hide":"audio"}
        for i,t in enumerate(tracks)):
        raise ValueError("MLT original muted tracks were altered")
    if len(tractor.findall("./transition"))!=len(tracks)-1:
        raise ValueError("MLT compositor transition count changed")
    for i,transition in enumerate(tractor.findall("./transition"),1):
        settings={p.get("name"):p.text for p in transition.findall("property")}
        if settings!={"a_track":"0","b_track":str(i),
                     "mlt_service":"luma","always_active":"1"}:
            raise ValueError("Unsupported or replaced MLT compositor")
    return {"verified_original_sources":len(producers),
            "verified_mlt_tracks":len(playlists),
            "native_mlt_render_measured":False}

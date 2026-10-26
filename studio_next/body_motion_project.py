"""Native Blender project transactions, runtime RNA discovery and media delivery.

The host installs Blender; the artist authors project data. Every transaction
opens a sealed project in a fresh process, edits native data, renders requested
frames and publishes a new self-contained version. No style compiler is used.
"""
from __future__ import annotations
import hashlib
from functools import lru_cache
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

VERSION = "zx7-native-motion/1"
METHODS = ("new", "remove", "clear", "link", "unlink", "add", "insert", "append",
           "new_socket", "from_pydata", "update", "foreach_set", "keyframe_insert", "keyframe_delete")


@lru_cache(maxsize=8)
def _engine_version(binary,mtime,size):
    import re
    output=subprocess.check_output([binary,"--version"],text=True,timeout=15)
    match=re.search(r"Blender (\d+)\.(\d+)",output)
    return tuple(map(int,match.groups())) if match else (0,0)


def motion_runtime_ready():
    binary=shutil.which("blender")
    if not binary:return False
    try:
        stat=Path(binary).stat()
        return _engine_version(binary,stat.st_mtime_ns,stat.st_size)>=(4,5)
    except (OSError,subprocess.SubprocessError):return False


def motion_document_schema():
    def obj(properties):return {"type":"object","required":list(properties),"properties":properties,"additionalProperties":False}
    text={"type":"string","minLength":1};integer={"type":"integer"}
    path={"type":"array","minItems":1,"maxItems":64,"items":{"oneOf":[text,integer]}}
    actions=[]
    for op,extra in (("set",{"value":{}}),("call",{"method":{"enum":list(METHODS)},
        "args":{"type":"array","items":{}},"kwargs":{"type":"object","required":[],"properties":{},"additionalProperties":True},
        "as":{"oneOf":[text,{"type":"null"}]}}),("read",{}),("describe",{}),
        ("list",{"offset":{"type":"integer","minimum":0},"limit":{"type":"integer","minimum":1,"maximum":256}})):
        actions.append(obj({"op":{"enum":[op]},"path":path,**extra}))
    schema=obj({"version":{"enum":[VERSION]},"project":{"oneOf":[text,{"type":"null"}]},
        "actions":{"type":"array","items":{"oneOf":actions},"maxItems":10000},
        "renders":{"type":"array","maxItems":10000,"items":obj({"scene":text,"frame":integer,"format":{"enum":["png","exr32"]}})}})
    schema["description"]=("Native Blender 4.5+ project transaction. Root paths: data -> bpy.data, scene -> active scene, refs -> named call returns. "
        "Path tokens select public native RNA attributes, named collection members or integer indices. set edits RNA properties/array elements; "
        "call invokes native data construction/animation methods. args/kwargs may contain literal JSON values, arrays or {$ref:path} pointer values. "
        "describe returns installed RNA properties/enums and available data methods; list pages native collections; read observes a property. "
        "All actions form one isolated transaction and publish a new native project; project null starts empty. renders use authored scene names "
        "and original frame numbers in delivery order. Engine/render settings belong to the artist. Paths, script execution and dependencies are host-managed. "
        "Only self-contained packed projects currently accepted; no arbitrary operator/Python execution or unsealed external cache import.")
    return schema


def validate_motion_job(job):
    if not isinstance(job,dict) or set(job)!={"version","project","actions","renders"} or job["version"]!=VERSION:
        raise ValueError("Native motion job requires version/project/actions/renders")
    if job["project"] is not None and (not isinstance(job["project"],str) or not job["project"].endswith(".zxmotion")):
        raise ValueError("Project must be null or a sealed native .zxmotion version")
    if not isinstance(job["actions"],list) or len(job["actions"])>10000:
        raise ValueError("Native action budget exceeded")
    def path(p):
        if (not isinstance(p,list) or not 1<=len(p)<=64 or p[0] not in ("data","scene","refs")
            or any(type(x) not in (str,int) or isinstance(x,str) and (not x or x.startswith("_")) for x in p)):
            raise ValueError("Invalid native RNA reference")
    def values(v,depth=0):
        if depth>64:raise ValueError("Native argument nesting exceeds budget")
        if isinstance(v,dict):
            if set(v)!={"$ref"}:raise ValueError("Only a native $ref object is an argument value")
            path(v["$ref"])
        elif isinstance(v,list):
            for item in v:values(item,depth+1)
        elif v is not None and type(v) not in (str,int,float,bool):raise ValueError("Unsupported native argument")
    for action in job["actions"]:
        if not isinstance(action,dict):raise ValueError("Native actions must be objects")
        op=action.get("op")
        fields={"set":{"op","path","value"},"call":{"op","path","method","args","kwargs","as"},
                "read":{"op","path"},"describe":{"op","path"},"list":{"op","path","offset","limit"}}
        if op not in fields or set(action)!=fields[op]:raise ValueError("Native action fields do not match operation")
        path(action["path"])
        if op=="set":values(action["value"])
        if op=="call":
            if action["method"] not in METHODS or not isinstance(action["args"],list) or not isinstance(action["kwargs"],dict):
                raise ValueError("Unsupported native data method")
            if action["as"] is not None and (not isinstance(action["as"],str) or not action["as"].isidentifier() or action["as"].startswith("_")):
                raise ValueError("Native result identity must be a public identifier")
            values(action["args"])
            for key,value in action["kwargs"].items():
                if not isinstance(key,str) or key.startswith("_"):raise ValueError("Invalid native keyword")
                values(value)
        if op=="list" and (type(action["offset"]) is not int or action["offset"]<0
            or type(action["limit"]) is not int or not 1<=action["limit"]<=256):raise ValueError("Invalid collection page")
    if not isinstance(job["renders"],list) or len(job["renders"])>10000:raise ValueError("Native render budget exceeded")
    for item in job["renders"]:
        if (not isinstance(item,dict) or set(item)!={"scene","frame","format"} or not isinstance(item["scene"],str)
            or type(item["frame"]) is not int or item["format"] not in ("png","exr32")):
            raise ValueError("Native renders require scene, original integer frame and png/exr32")
    # JSON round trip rejects NaN/infinity as well as non-JSON values.
    if len(json.dumps(job,allow_nan=False).encode())>16*1024*1024:raise ValueError("Native job exceeds host byte budget")
    return job


def digest(path):
    with Path(path).open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()


def verify_motion_bundle(path):
    with zipfile.ZipFile(path) as bundle:
        infos=bundle.infolist();names=[x.filename for x in infos]
        if len(names)!=len(set(names)) or len(names)>10005 or sum(x.file_size for x in infos)>8*1024**3:
            raise ValueError("Native bundle exceeds unique member/size budget")
        if any(Path(n).is_absolute() or ".." in Path(n).parts for n in names):raise ValueError("Unsafe native bundle path")
        report=json.loads(bundle.read("receipt.json"))
        if report.get("version")!=VERSION or set(names)!={"receipt.json",*report["members"]} or "project.blend" not in report["members"]:
            raise ValueError("Native bundle manifest mismatch")
        for name,expected in report["members"].items():
            h=hashlib.sha256()
            with bundle.open(name) as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b""):h.update(chunk)
            if h.hexdigest()!=expected:raise ValueError("Native project/member identity changed")
        with bundle.open("project.blend") as stream:
            if not stream.read(12).startswith(b"BLENDER"):raise ValueError("Not a native uncompressed Blender project")
        if not isinstance(report.get("engine_version"),str):raise ValueError("No actual Blender engine identity")
    return report


def run_motion_project(job_path,workspace,target,*,timeout=3600):
    root=Path(workspace).resolve();source=Path(job_path).resolve();dest=Path(target)
    data=source.read_bytes()
    job=validate_motion_job(json.loads(data))
    if dest.exists():raise FileExistsError("Native project publication cannot overwrite a version")
    binary=shutil.which("blender")
    if binary is None:raise RuntimeError("Install native Blender 4.5 LTS or newer on the BODY host")
    version=subprocess.check_output([binary,"--version"],text=True,timeout=15).splitlines()[0]
    import re
    match=re.search(r"Blender (\d+)\.(\d+)",version)
    if not match or tuple(map(int,match.groups()))<(4,5):raise RuntimeError("Native motion projects require Blender 4.5+")
    with tempfile.TemporaryDirectory(prefix="zx7-native-motion-") as tmp:
        stage=Path(tmp);base=None;input_identity=None
        if job["project"] is not None:
            relative=Path(job["project"]);original=(root/relative).resolve()
            if relative.is_absolute() or ".." in relative.parts or not original.is_relative_to(root):raise ValueError("Native project escaped workspace")
            from .body_publication import require_published_source
            approved=require_published_source(original,"body.motion_project")
            # Operate only on the copied, reverified immutable input snapshot.
            sealed=stage/"input.zxmotion";shutil.copyfile(original,sealed)
            verify_motion_bundle(sealed);input_identity=digest(sealed)
            if input_identity!=approved:raise ValueError("Native parent changed after provenance verification")
            with zipfile.ZipFile(sealed) as bundle:base=stage/"input.blend";base.write_bytes(bundle.read("project.blend"))
        request=stage/"request.json";request.write_bytes(data)
        output=stage/"result";output.mkdir()
        args=[binary,"--background","--factory-startup","--disable-autoexec","--threads","2",
              "--python-exit-code","1","--python",str(Path(__file__).with_name("body_motion_worker.py")),"--",
              str(request),str(output)]
        if base:args.append(str(base))
        completed=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
        if completed.returncode:raise RuntimeError("Native Blender transaction failed: "+completed.stdout[-6000:])
        native=json.loads((output/"native.json").read_text())
        members={p.name:digest(p) for p in output.iterdir() if p.is_file()}
        report={"version":VERSION,"engine_version":native["engine_version"],"job_sha256":hashlib.sha256(data).hexdigest(),
                "parent_bundle_sha256":input_identity,"members":members,"native":native,
                "model_inference_performed":False,"artistic_quality_approved":False}
        # Recheck original custody before final publication.
        if source.read_bytes()!=data:raise ValueError("Native job changed during rendering")
        if job["project"] and digest(original)!=input_identity:raise ValueError("Native source project changed during transaction")
        dest.parent.mkdir(parents=True,exist_ok=True)
        staged=stage/"publish.zxmotion"
        with zipfile.ZipFile(staged,"w",compression=zipfile.ZIP_STORED) as archive:
            for p in output.iterdir():archive.write(p,p.name)
            archive.writestr("receipt.json",json.dumps(report,sort_keys=True))
        verify_motion_bundle(staged)
        # Exclusive final create; BODY's surrounding publication owns crash recovery.
        created=False
        try:
            with dest.open("xb") as stream,staged.open("rb") as incoming:
                created=True
                shutil.copyfileobj(incoming,stream)
        except BaseException:
            if created:dest.unlink(missing_ok=True)
            raise
    return report


def export_motion_media(bundle_path,target,*,fps):
    from .body_publication import require_published_source
    approved=require_published_source(bundle_path,"body.motion_project")
    dest=Path(target)
    if dest.exists():raise FileExistsError("Native media output already exists")
    if type(fps) is not int or not 1<=fps<=240:raise ValueError("Explicit integer delivery fps must be 1..240")
    with tempfile.TemporaryDirectory(prefix="zx7-motion-export-") as tmp:
        root=Path(tmp)
        sealed=root/"source.zxmotion";shutil.copyfile(bundle_path,sealed)
        if digest(sealed)!=approved:raise ValueError("Native export source changed after provenance verification")
        report=verify_motion_bundle(sealed);frames=report["native"]["renders"]
        if not frames or any(x["format"]!="png" for x in frames):raise ValueError("Media export needs authored PNG render order")
        with zipfile.ZipFile(sealed) as bundle:
            for i,frame in enumerate(frames):
                (root/f"frame_{i:06d}.png").write_bytes(bundle.read(frame["file"]))
        if dest.suffix.lower()==".png":
            if len(frames)!=1:raise ValueError("PNG delivery requires one authored frame")
            with dest.open("xb") as out:out.write((root/"frame_000000.png").read_bytes())
        elif dest.suffix.lower()==".mp4":
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-n","-framerate",str(fps),
                "-i",str(root/"frame_%06d.png"),"-c:v","libx264","-crf","18","-pix_fmt","yuv420p",
                "-movflags","+faststart",str(dest)],check=True,timeout=3600)
        else:raise ValueError("Native delivery supports png/mp4")
    return report

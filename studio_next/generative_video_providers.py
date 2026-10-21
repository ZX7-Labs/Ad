"""Actual self-hosted generative-video capability discovery for ONE ZX7 artist.

Film understanding, casting, shot design and tool choice belong to the model.
This module does not contain creative templates. It checks whether real T2V,
I2V, and video-edit generation can RUN, rather than treating model download
or a package name as generated footage. No paid provider or remote uploads.

Video model candidates are data; capability registration is extensible.
Executable tools remain disabled until CUDA hardware + installed licensed
weights + a locally active API + matching, approved model workflow exist.
"""
from __future__ import annotations

import json
import hashlib
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

# Current declared upstream licenses; actual weights still need provenance.
VIDEO_MODEL_CANDIDATES=(
    {"id":"wan21-t2v-13b","repo":"Wan-AI/Wan2.1-T2V-1.3B",
     "license_metadata":"apache-2.0","needs_vram_mb":8190,
     "capabilities":["text_to_video","human_action","camera_motion","natural_scene"]},
    {"id":"wan21-vace-13b","repo":"Wan-AI/Wan2.1-VACE-1.3B",
     "license_metadata":"apache-2.0","needs_vram_mb":8190,
     "capabilities":["video_edit","video_to_video","reference_to_video","image_to_video"]},
    {"id":"wan22-ti2v-5b","repo":"Wan-AI/Wan2.2-TI2V-5B",
     "license_metadata":"apache-2.0","needs_vram_mb":24000,
     "capabilities":["text_to_video","image_to_video","cinematic_scene"]},
)
SUPPORTED_LOCAL_HOSTS=frozenset({"127.0.0.1","localhost","::1"})


def safe_local_api(url):
    if not isinstance(url,str) or not url:
        raise ValueError("Only explicitly enabled local inference endpoints are supported")
    parsed=urlsplit(url)
    if parsed.scheme!="http" or parsed.hostname not in SUPPORTED_LOCAL_HOSTS or (
            parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("","/")):
        raise ValueError("Remote/credentialed creative model endpoints prohibited")
    if parsed.port is None:
        raise ValueError("ComfyUI local inference port required")
    return url.rstrip("/")


def measured_gpu_vram_mb(*, runner=None):
    """Measure CUDA capacity; free GitHub Actions CPU must not impersonate GPU."""
    run=runner or subprocess.run
    if shutil.which("nvidia-smi") is None and runner is None:
        return 0
    try:
        p=run(["nvidia-smi","--query-gpu=memory.total","--format=csv,noheader,nounits"],
              capture_output=True,text=True,timeout=8,check=True)
        raw=(p.stdout or "").strip().splitlines()
        cards=[int(v.strip()) for v in raw if re.fullmatch(r"\s*\d+\s*",v)]
        return max(cards,default=0)
    except (OSError,subprocess.SubprocessError,TypeError,ValueError):
        return 0


def inspect_comfyui(endpoint,*, fetch=None):
    """Only readonly API requests. Node metadata != successful media creation."""
    endpoint=safe_local_api(endpoint)
    if fetch is None:
        def fetch(url):
            with urlopen(url,timeout=4) as r:
                return json.loads(r.read(2_000_000))
    try:
        info=fetch(endpoint+"/system_stats")
        nodes=fetch(endpoint+"/object_info")
        if not isinstance(info,dict) or not isinstance(nodes,dict):
            raise ValueError("ComfyUI returned invalid system metadata")
        return {"service_reachable":True,"service_api":"ComfyUI local",
                "available_node_classes":sorted(nodes),
                "reported_devices":info.get("devices",[]),
                "video_inference_verified":False}
    except (OSError,ValueError,TimeoutError,KeyError):
        return {"service_reachable":False,"available_node_classes":[],
                "video_inference_verified":False}


def _read_manifest(folder,model_id):
    """A deployment config is a technical capability *not* a creative script."""
    path=Path(folder)/model_id/"deployment.json"
    if not path.is_file():
        return None
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict) or data.get("model_id")!=model_id or (
            not isinstance(data.get("weight_sha256"),str) or
            not re.fullmatch(r"[0-9a-f]{64}",data["weight_sha256"])):
        raise ValueError("Model deployment has no verifiable exact weights")
    if data.get("license_accepted_or_verified") is not True:
        return None
    # Asset bytes can be huge: digest is checked in weight-install stage,
    # and a signed generated manifest stored after actual verification.
    # A JSON boolean is not proof of real downloaded weights. Hash actual local
    # bytes before declaring an expensive diffusion engine even trial-ready.
    weight=data.get("weight_file")
    if not isinstance(weight,str) or not weight or Path(weight).is_absolute() or (
            ".." in Path(weight).parts):
        return None
    checkpoint=(path.parent/weight).resolve()
    if not checkpoint.is_relative_to(path.parent.resolve()) or not checkpoint.is_file():
        return None
    if checkpoint.stat().st_size<128:
        return None
    with checkpoint.open("rb") as handle:
        digest=hashlib.file_digest(handle,"sha256").hexdigest()
    if digest!=data["weight_sha256"]:
        return None
    return data


def discover_local_generators(*,gpu_mb=None,comfy_endpoint=None,
                              deployed_root="models/creative-video",fetch=None):
    gpu_mb=measured_gpu_vram_mb() if gpu_mb is None else gpu_mb
    if isinstance(gpu_mb,bool) or not isinstance(gpu_mb,int) or gpu_mb<0:
        raise ValueError("Actual CUDA VRAM must be a measured nonnegative MiB integer")
    runtime=(inspect_comfyui(comfy_endpoint,fetch=fetch) if comfy_endpoint
             else {"service_reachable":False,"available_node_classes":[],
                   "video_inference_verified":False})
    choices=[]
    for spec in VIDEO_MODEL_CANDIDATES:
        deployment=_read_manifest(deployed_root,spec["id"])
        workflow_nodes=deployment.get("required_comfyui_nodes",[]) if deployment else []
        nodes=runtime["available_node_classes"]
        proven=bool(deployment and gpu_mb>=spec["needs_vram_mb"] and
            runtime["service_reachable"] and
            isinstance(workflow_nodes,list) and workflow_nodes and
            all(isinstance(n,str) and n in nodes for n in workflow_nodes))
        choices.append({
            "id":spec["id"],"upstream_weights":spec["repo"],
            "license_metadata":spec["license_metadata"],
            "tasks":spec["capabilities"],
            "minimum_documented_gpu_mb":spec["needs_vram_mb"],
            "measured_local_cuda_vram_mb":gpu_mb,
            "weights_verified_locally":bool(deployment),
            "local_workflow_nodes_verified":proven,
            "ready_for_independent_execution_trial":proven,
            "actual_movie_generated_and_ffprobed":False,
            "not_ready_reason":None if proven else
                "Missing actual CUDA VRAM, SHA-verified licensed local weights, or live local ComfyUI workflow"
        })
    return {"creative_intelligence_has_no_preset_style":True,
            "gpu_is_real_hardware":gpu_mb>0,
            "comfyui":runtime,"video_generation_options":choices,
            "all_video_generation_operational":False,
            "disclosure":"A provider is not a completed MP4. Real model rendering and decoder evidence are separate."}


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--comfy-api",default=None)
    a=p.parse_args()
    state=discover_local_generators(comfy_endpoint=a.comfy_api)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(state,indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()

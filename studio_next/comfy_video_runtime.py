"""Real local ComfyUI video-generation adapter for a single film Director.

The visual prompt, aspect, length, and performance are artist-authored data.
A separately approved local ComfyUI API workflow is a TECHNICAL tool contract,
not an artistic template. No model-originated shell execution, URLs, scripts
or paid-hosted services. Returns only a physically decoded media file.

The user/installer must connect a GPU, weight-verified deployment and native
ComfyUI workflow before this provider is enabled. Merely importing this file
does NOT supply those missing resources.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request

from .generative_video_providers import (
    safe_local_api,discover_local_generators,open_verified_local_api)
from .stage_checkpoint import DurableStageStore
from .media_vault import sha256_file

_APPROVED_FIELDS=("prompt","negative_prompt","width","height","frames","fps","seed")
_NAME=re.compile(r"^[A-Za-z0-9_.-]{1,180}$")
_PROMPT_ID=re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def validate_video_job(job):
    if not isinstance(job,dict) or set(job)!=(set(_APPROVED_FIELDS)|{"model_id"}):
        raise ValueError("External video-generation job requires exact technical fields")
    if not isinstance(job["model_id"],str) or not _NAME.fullmatch(job["model_id"]):
        raise ValueError("Unregistered video generator identity")
    if not isinstance(job["prompt"],str) or not job["prompt"].strip():
        raise ValueError("Filmmaker must author actual visual and acting directions")
    if not isinstance(job["negative_prompt"],str):
        raise ValueError("Negative prompt must be intentionally authored, even if empty")
    for key in ("width","height","frames","fps"):
        if isinstance(job[key],bool) or not isinstance(job[key],int) or (
                job[key]<=0 or job[key]>65536):
            raise ValueError("Invalid independently selected video "+key)
    if not isinstance(job["seed"],int) or isinstance(job["seed"],bool) or not (
            0<=job["seed"]<2**64):
        raise ValueError("Seed must be an unsigned deterministic film render integer")
    return job


def _safe_local_filename(name):
    if not isinstance(name,str) or not _NAME.fullmatch(name) or name in (".",".."):
        raise ValueError("Untrusted ComfyUI output filename")
    if Path(name).suffix.lower() not in (".mp4",".webm",".mov"):
        raise ValueError("ComfyUI returned a non-video artifact")
    return name


def _approved_graph(config_root, job):
    root=Path(config_root).resolve()
    target=(root/job["model_id"]).resolve()
    if not target.is_relative_to(root) or not target.is_dir():
        raise ValueError("Locally installed video model configuration not present")
    proof=target/"workflow.json"
    binds=target/"bindings.json"
    if proof.is_symlink() or binds.is_symlink():
        raise ValueError("Owner-installed video workflow cannot be a symbolic link")
    if not proof.is_file() or not binds.is_file():
        raise ValueError("Real ComfyUI API workflow and its model bindings required")
    if proof.stat().st_size>8*1024*1024 or binds.stat().st_size>256*1024:
        raise ValueError("Owner-installed video workflow exceeds bounded source size")
    graph_bytes=proof.read_bytes()
    graph=json.loads(graph_bytes)
    bindings_bytes=binds.read_bytes()
    desc=json.loads(bindings_bytes.decode("utf-8"))
    if not isinstance(graph,dict) or not isinstance(desc,dict):
        raise ValueError("Model's trusted workflow must be an object")
    if desc.get("model_id")!=job["model_id"]:
        raise ValueError("Registered workflow model mismatch")
    binding=desc.get("inputs")
    if not isinstance(binding,dict) or not set(binding).issubset(set(_APPROVED_FIELDS)):
        raise ValueError("Invalid ComfyUI input bindings")
    if not {"prompt","frames","width","height","fps"}.issubset(binding):
        raise ValueError("Original director timing and imagery cannot be applied to this workflow")
    # Graph is installed by the owner/software deployment process, never by
    # untrusted model output. Mutate only explicitly approved node input slots.
    for field,n in binding.items():
        if (not isinstance(n,dict) or set(n)!={"node","key"} or
                not isinstance(n["node"],str) or not isinstance(n["key"],str)):
            raise ValueError("Invalid binding for actual native API graph")
        ref=graph.get(n["node"])
        if not isinstance(ref,dict) or not isinstance(ref.get("inputs"),dict) or (
                n["key"] not in ref["inputs"]):
            raise ValueError("Workflow binding references nonexistent original node")
        ref["inputs"][n["key"]]=job[field]
    if not isinstance(desc.get("output_node"),str) or desc["output_node"] not in graph:
        raise ValueError("Model's video Save node is unregistered")
    return graph,desc,hashlib.sha256(graph_bytes+bindings_bytes).hexdigest()


class LocalComfyVideoClient:
    def __init__(self,endpoint,*,request=None):
        self.endpoint=safe_local_api(endpoint)
        self._request=request

    def call(self,method,path,data=None,binary=False):
        if self._request is not None:
            return self._request(method,path,data,binary)
        body=json.dumps(data,ensure_ascii=False).encode("utf-8") if data is not None else None
        req=Request(self.endpoint+path,data=body,method=method,
                    headers={"Content-Type":"application/json"})
        with open_verified_local_api(req,timeout=120) as resp:
            if binary:
                payload=resp.read(256_000_001)
                if len(payload)>256_000_000:
                    raise ValueError("Generated video exceeds bounded verified download")
                return payload
            return json.loads(resp.read(8_000_000).decode("utf-8"))

    def create(self,graph):
        receipt=self.call("POST","/prompt",{"prompt":graph})
        if (not isinstance(receipt,dict) or
                not isinstance(receipt.get("prompt_id"),str) or
                not _PROMPT_ID.fullmatch(receipt["prompt_id"])):
            raise ValueError("Local ComfyUI did not return a path-safe generation ID")
        return receipt["prompt_id"]

    def wait(self,prompt_id,output_node,*,poll_seconds=3,max_seconds=1800,sleep=None):
        sleeper=sleep or time.sleep
        deadline=time.monotonic()+max_seconds
        if (not isinstance(prompt_id,str) or
                not _PROMPT_ID.fullmatch(prompt_id)):
            raise ValueError("Original generation ID must be a bounded path-safe token")
        while time.monotonic()<deadline:
            history=self.call("GET","/history/"+prompt_id)
            if isinstance(history,dict) and prompt_id in history:
                task=history[prompt_id]
                if not isinstance(task,dict):
                    raise ValueError("Untrusted renderer history")
                state=task.get("status",{})
                if isinstance(state,dict) and state.get("status_str") in ("error","failed"):
                    raise RuntimeError("Real video model failed: "+json.dumps(state)[:600])
                outputs=task.get("outputs",{}).get(output_node,{})
                if isinstance(outputs,dict):
                    entries=outputs.get("videos",outputs.get("gifs",[]))
                    if isinstance(entries,list) and entries:
                        first=entries[0]
                        if isinstance(first,dict) and first.get("type")=="output":
                            name=_safe_local_filename(first.get("filename"))
                            sub=first.get("subfolder","")
                            if not isinstance(sub,str) or (
                                sub and ("/" in sub or "\\" in sub or sub in (".",".."))):
                                raise ValueError("Unsafe ComfyUI video subfolder")
                            uri="/view?"+urlencode({"filename":name,"subfolder":sub,"type":"output"})
                            raw=self.call("GET",uri,binary=True)
                            if not isinstance(raw,(bytes,bytearray)) or len(raw)<1000:
                                raise ValueError("Actual ComfyUI model did not return real video bytes")
                            return name,bytes(raw)
            sleeper(poll_seconds)
        raise TimeoutError("Real video generation did not complete within allowed compute budget")


def render_actual_generated_scene(job,scene_folder,*,deployment_root="models/creative-video",
                                  comfy_endpoint=None,client=None,probe=None):
    """No output file exists unless an actual generator produces decodable video."""
    validate_video_job(job)
    endpoint=safe_local_api(comfy_endpoint) if comfy_endpoint else None
    if endpoint is None:
        raise ValueError("ZX7 requires the actual connected self-hosted ComfyUI instance")
    evidence=discover_local_generators(comfy_endpoint=endpoint,
                                     deployed_root=deployment_root)
    selected=next((x for x in evidence["video_generation_options"]
                   if x["id"]==job["model_id"]),None)
    if not selected or not selected["ready_for_independent_execution_trial"]:
        raise ValueError("Real GPU, weight-proved licensed model and live workflow missing")
    graph,meta,workflow_sha=_approved_graph(deployment_root,job)
    renderer=client or LocalComfyVideoClient(endpoint)
    stage=DurableStageStore(Path(scene_folder)/"video-generator-jobs")
    identity={"job":job,"approved_workflow_sha256":workflow_sha}
    previous=stage.find("comfy_prompt",identity)
    pid=previous.get("prompt_id") if isinstance(previous,dict) else None
    if not pid:
        pid=renderer.create(graph)
        stage.save("comfy_prompt",identity,{"prompt_id":pid})
    filename,bytes_=renderer.wait(pid,meta["output_node"])
    # Also validate results from injected/operator-provided ComfyUI clients;
    # only the default HTTP adapter previously checked the returned path.
    filename=_safe_local_filename(filename)
    folder=Path(scene_folder)
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/filename
    if path.exists() or path.is_symlink():
        raise FileExistsError("Never replace a director-accepted original AI video")
    # A remote local GPU adapter is still an UNTRUSTED byte producer. Its
    # declared output name is not proof of real frames, original duration or
    # authorization to replace anyone's accepted film.
    with tempfile.TemporaryDirectory(prefix=".zx7-comfy-stage-",dir=folder) as private:
        stage_path=Path(private)/filename
        with stage_path.open("xb") as destination:
            destination.write(bytes_)
            destination.flush()
            os.fsync(destination.fileno())
        if probe is None:
            from .edit_timeline import probe_media
            probe=probe_media
        actual=probe(stage_path)
        if not isinstance(actual,dict) or actual.get("seconds",0)<=0:
            raise RuntimeError(
                "Generated video lacks independently decodable picture duration")
        from .production_qc import full_decode_inspection
        try:
            report=full_decode_inspection(stage_path,expected={
                "width":job["width"],"height":job["height"],
                "duration_seconds":job["frames"]/job["fps"],
                "require_audio":False})
        except (OSError,ValueError,subprocess.SubprocessError) as exc:
            raise ValueError(
                "Returned model video failed independently decoded physical film verification") from exc
        if (not report["technical_delivery_verified"] or
                not report["full_picture_and_sound_decoder_completed"]):
            raise ValueError("Local GPU source failed complete actual picture/audio decode and declared film geometry")
        digest=hashlib.sha256(bytes_).hexdigest()
        if sha256_file(stage_path)!=digest:
            raise ValueError("Original returned GPU video bytes changed during decode")
        with stage_path.open("rb") as completed:
            os.fsync(completed.fileno())
        # Re-evaluate the installed native workflow after its potentially
        # long GPU run. A changed original source does not earn a verified film.
        _,_,current_workflow_sha=_approved_graph(deployment_root,job)
        if current_workflow_sha!=workflow_sha:
            raise ValueError("Installed original generator workflow changed during render")
        # This is a same-filesystem exclusive publish, not overwrite of an
        # unverified or competing model/video editor output.
        os.link(stage_path,path)
    return {"clip":path,"fps":job["fps"],"seconds":report["duration_seconds"],
            "sha256":digest,"audio":bool(report["audio_present"]),
            "workflow_sha256":workflow_sha,
            "full_original_video_and_sound_decoded":True,
            "human_cinematic_performance_approved":False,
            "generated_with_actual_self_hosted_model":client is None,
            "original_model_inference_independently_certified":False}


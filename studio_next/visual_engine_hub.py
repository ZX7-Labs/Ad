"""Extensible ZX7 visual production engine interface: tools belong to the brain.

No fixed list of artistic styles, shot counts or effects. Built-ins use the
existing trusted renderers; additional provider packages can register an
entry point `zx7.visual_engines` after explicit administrator installation.
Untrusted LLM JSON cannot install, import or execute new software.

An engine is selectable only if the REAL runtime/resources validate it.
This typed boundary replaces an artistic template, not actual film direction.
"""
from __future__ import annotations

import os
import re
from importlib.metadata import entry_points
from pathlib import Path

from .comfy_video_runtime import validate_video_job,render_actual_generated_scene
from .generative_video_providers import discover_local_generators


class RealComfyVideoEngine:
    engine_id="comfy_video"

    def _runtime(self):
        endpoint=os.getenv("ZX7_COMFY_API")
        if not endpoint:
            raise ValueError("No real self-hosted video generator endpoint installed")
        return (endpoint,os.getenv("ZX7_VIDEO_DEPLOYMENTS","models/creative-video"))

    def validate(self,shot,design,facts):
        job=validate_video_job(design["scene_job"])
        endpoint,deployments=self._runtime()
        evidence=discover_local_generators(comfy_endpoint=endpoint,
                                            deployed_root=deployments)
        candidate=next((c for c in evidence["video_generation_options"]
                        if c["id"]==job["model_id"]),None)
        if not candidate or not candidate["ready_for_independent_execution_trial"]:
            raise ValueError("Connected video diffusion model is not actually available")
        duration=shot.get("duration_seconds",shot.get("seconds"))
        if not isinstance(duration,(float,int)) or isinstance(duration,bool):
            raise ValueError("Original shot timing missing")
        if abs(job["frames"]/job["fps"]-duration)>1/job["fps"]+1e-5:
            raise ValueError("Video model cannot silently change the director's chosen shot duration")
        return {"executable":True,"engine":self.engine_id,
                "audio_required":bool(shot.get("narration")),
                "video_model":job["model_id"]}

    def render(self,shot,design,shot_dir,delivery):
        endpoint,root=self._runtime()
        result=render_actual_generated_scene(design["scene_job"],shot_dir,
             deployment_root=root,comfy_endpoint=endpoint)
        return Path(result["clip"]),"intentional_silence"


def _installed_plugins():
    enabled={x.strip() for x in os.getenv("ZX7_ENABLED_VISUAL_ENGINES","").split(",")
             if x.strip()}
    entries=entry_points()
    group=entries.select(group="zx7.visual_engines") if hasattr(entries,"select") else (
        entries.get("zx7.visual_engines",[]))
    for item in group:
        if item.name not in enabled:
            continue
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,100}",item.name):
            raise ValueError("Unsafe installed plugin engine identity")
        provider=item.load()()
        if provider.engine_id!=item.name:
            raise ValueError("Third party visual engine identity mismatch")
        if not callable(getattr(provider,"validate",None)) or not callable(
                getattr(provider,"render",None)):
            raise ValueError("Installed visual engine misses real validation/render interfaces")
        yield provider


def available_visual_engines():
    """Installed capability names, not a fixed array of art or genres."""
    implementations={RealComfyVideoEngine.engine_id:RealComfyVideoEngine()}
    for provider in _installed_plugins():
        if provider.engine_id in implementations:
            raise ValueError("Duplicate or counterfeit installed rendering engine")
        implementations[provider.engine_id]=provider
    return implementations


def resolve_visual_engine(name):
    if not isinstance(name,str) or not name:
        return None
    return available_visual_engines().get(name)

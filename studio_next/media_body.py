"""Trusted FFmpeg timeline renderer for ZX7 BODY.

A declarative, multi-track video/audio composite. It does not invent shots, assets,
colors or timing, and never executes shell strings received from a director/model.
All supplied media is validated against a caller-controlled local asset directory.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

_ALLOWED = {
    "video": {".mp4", ".mov", ".mkv", ".webm", ".m4v"},
    "image": {".png", ".jpg", ".jpeg", ".webp"},
    "audio": {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".mp4", ".mov", ".webm"},
}

class RenderError(RuntimeError):
    """A failed media preflight, tool invocation or output verification."""


def _number(value: Any, field: str, *, positive=False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RenderError(f"{field} must be a finite number")
    if (positive and value <= 0) or (not positive and value < 0):
        raise RenderError(f"{field} outside permitted range")
    return float(value)


def _integer(value: Any, field: str, *, positive=False, signed=False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RenderError(f"{field} must be integer")
    if not signed:
        _number(value, field, positive=positive)
    return value


def _asset(base: Path, name: Any, kind: str) -> Path:
    if not isinstance(name, str) or not name.strip() or "\x00" in name:
        raise RenderError("Asset path must be non-empty local relative path")
    p = Path(name)
    if p.is_absolute() or ".." in p.parts or p.suffix.lower() not in _ALLOWED[kind]:
        raise RenderError(f"Unapproved {kind} asset path or extension: {name}")
    resolved = (base / p).resolve()
    if not resolved.is_relative_to(base) or not resolved.is_file():
        raise RenderError(f"Asset missing or outside approved directory: {name}")
    return resolved


def _probe(file: Path, binary: str, *, timeout: float) -> dict:
    try:
        p = subprocess.run([binary, "-v", "error", "-show_streams", "-show_format",
                            "-of", "json", str(file)], text=True, capture_output=True,
                           check=True, timeout=timeout)
        return json.loads(p.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise RenderError(f"Unable to inspect media {file.name}: {exc}") from exc


def _fmt(value: float) -> str:
    return format(value, ".9g")


def render_timeline(project: dict, *, asset_root: str | Path, output_path: str | Path,
                    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
                    timeout_seconds: float = 900) -> dict:
    """Render an authored, layered timeline and return probed real-output evidence.

    Schema: canvas {width,height,fps,duration,background}; clips [{kind,path,
    timeline_start,source_start,duration,z,x,y,width,height,opacity,volume,
    fade_in,fade_out}]. All clip start/durations are seconds. Audio-only clips
    may source audio tracks from a video file. Each clip is independent; multiple
    layers and stems can overlap. Order in the list breaks equal-z ties.
    """
    if not isinstance(project, dict) or not isinstance(project.get("canvas"), dict):
        raise RenderError("Expected project with canvas object")
    canvas = project["canvas"]
    width = _integer(canvas.get("width"), "canvas.width", positive=True)
    height = _integer(canvas.get("height"), "canvas.height", positive=True)
    fps = _number(canvas.get("fps"), "canvas.fps", positive=True)
    duration = _number(canvas.get("duration"), "canvas.duration", positive=True)
    if width % 2 or height % 2:
        raise RenderError("H.264 yuv420p output needs even width and height")
    bg = canvas.get("background", "#000000")
    if not isinstance(bg, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", bg):
        raise RenderError("Background must be #RRGGBB")
    clips = project.get("clips")
    if not isinstance(clips, list) or not clips:
        raise RenderError("At least one real clip is required")
    base = Path(asset_root).resolve(strict=True)
    if not base.is_dir():
        raise RenderError("asset_root must be a directory")
    target = Path(output_path).absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() != ".mp4":
        raise RenderError("The verified BODY exporter currently supports MP4")
    timeout = _number(timeout_seconds, "timeout_seconds", positive=True)
    sources = []
    for index, item in enumerate(clips):
        if not isinstance(item, dict) or not isinstance(item.get("kind"), str) or item["kind"] not in _ALLOWED:
            raise RenderError(f"Clip {index} has invalid media kind")
        kind = item["kind"]
        file = _asset(base, item.get("path"), kind)
        start = _number(item.get("timeline_start"), f"clip[{index}].timeline_start")
        source_start = _number(item.get("source_start", 0), f"clip[{index}].source_start")
        length = _number(item.get("duration"), f"clip[{index}].duration", positive=True)
        if start + length > duration + 1e-7:
            raise RenderError(f"Clip {index} extends beyond canvas duration")
        info = _probe(file, ffprobe, timeout=min(timeout, 30))
        streams = info.get("streams", [])
        stream_kind = "audio" if kind == "audio" else "video"
        if not any(s.get("codec_type") == stream_kind for s in streams):
            raise RenderError(f"Clip {index} lacks expected {stream_kind} stream")
        if kind != "image":
            media_duration = info.get("format", {}).get("duration")
            if media_duration not in (None, "N/A"):
                try:
                    if source_start + length > float(media_duration) + 0.08:
                        raise RenderError(f"Clip {index} exceeds source media duration")
                except (ValueError, TypeError):
                    pass
        source = dict(item, kind=kind, file=file, start=start, source_start=source_start, length=length)
        if kind != "audio":
            source["width"] = _integer(item.get("width", width), f"clip[{index}].width", positive=True)
            source["height"] = _integer(item.get("height", height), f"clip[{index}].height", positive=True)
            source["x"] = _integer(item.get("x", 0), f"clip[{index}].x", signed=True)
            source["y"] = _integer(item.get("y", 0), f"clip[{index}].y", signed=True)
            alpha = _number(item.get("opacity", 1.0), f"clip[{index}].opacity")
            if alpha > 1: raise RenderError(f"Clip {index} opacity > 1")
            source["alpha"] = alpha
            source["z"] = _integer(item.get("z", 0), f"clip[{index}].z", signed=True)
        else:
            volume = _number(item.get("volume", 1.0), f"clip[{index}].volume")
            source["volume"] = volume
            source["fade_in"] = _number(item.get("fade_in", 0), f"clip[{index}].fade_in")
            source["fade_out"] = _number(item.get("fade_out", 0), f"clip[{index}].fade_out")
            if source["fade_in"] > length or source["fade_out"] > length:
                raise RenderError(f"Clip {index} fade longer than clip")
        sources.append(source)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    for source in sources:
        if source["kind"] == "image":
            cmd += ["-loop", "1"]
        cmd += ["-i", str(source["file"])]
    graph = [f"color=c=0x{bg[1:]}:s={width}x{height}:r={_fmt(fps)}:d={_fmt(duration)},format=yuv420p[b0]"]
    visuals = sorted(enumerate(sources), key=lambda v: (v[1].get("z", 0), v[0]))
    stage = "b0"
    for i, clip in visuals:
        if clip["kind"] == "audio": continue
        fmt = (f"[{i}:v]trim=start={_fmt(clip['source_start'])}:duration={_fmt(clip['length'])},"
               f"setpts=PTS-STARTPTS,scale={clip['width']}:{clip['height']}:flags=lanczos,"
               f"fps={_fmt(fps)},format=rgba,colorchannelmixer=aa={_fmt(clip['alpha'])},"
               f"setpts=PTS+{_fmt(clip['start'])}/TB[v{i}]")
        graph.append(fmt)
        following = f"b{i+1}"
        enable = f"between(t,{_fmt(clip['start'])},{_fmt(clip['start']+clip['length']-1/(2*fps))})"
        graph.append(f"[{stage}][v{i}]overlay=x={clip['x']}:y={clip['y']}:"
                     f"enable='{enable}':eof_action=pass:shortest=0[{following}]")
        stage = following
    audio_inputs = []
    for i, clip in enumerate(sources):
        if clip["kind"] != "audio": continue
        fade = []
        if clip["fade_in"]: fade.append(f"afade=t=in:st=0:d={_fmt(clip['fade_in'])}")
        if clip["fade_out"]:
            fade.append(f"afade=t=out:st={_fmt(clip['length']-clip['fade_out'])}:d={_fmt(clip['fade_out'])}")
        chain = (f"[{i}:a]atrim=start={_fmt(clip['source_start'])}:duration={_fmt(clip['length'])},"
                 f"asetpts=PTS-STARTPTS,aresample=48000,volume={_fmt(clip['volume'])}")
        if fade: chain += "," + ",".join(fade)
        chain += f",adelay=delays={round(clip['start']*1000)}:all=1[a{i}]"
        graph.append(chain)
        audio_inputs.append(f"[a{i}]")
    if audio_inputs:
        graph.append("anullsrc=r=48000:cl=stereo,atrim=duration="+_fmt(duration)+"[silence]")
        inputs = "[silence]" + "".join(audio_inputs)
        graph.append(f"{inputs}amix=inputs={len(audio_inputs)+1}:duration=longest:"
                     f"normalize=0,atrim=duration={_fmt(duration)},alimiter=limit=0.95[aout]")
    with tempfile.NamedTemporaryFile(prefix=".zx7-render-", suffix=".mp4", dir=target.parent,
                                     delete=False) as temporary:
        tmp = Path(temporary.name)
    try:
        cmd += ["-filter_complex", ";".join(graph), "-map", f"[{stage}]", "-an" if not audio_inputs else "-map"]
        if audio_inputs: cmd += ["[aout]"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium"]
        if audio_inputs: cmd += ["-c:a", "aac", "-b:a", "192k"]
        cmd += ["-t", _fmt(duration), "-movflags", "+faststart", str(tmp)]
        try:
            run = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RenderError(f"FFmpeg unavailable or timed out: {exc}") from exc
        if run.returncode:
            raise RenderError(f"FFmpeg failed: {run.stderr[-1600:]}")
        evidence = _probe(tmp, ffprobe, timeout=min(timeout, 30))
        streams = evidence.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        if not video or video.get("codec_name") != "h264":
            raise RenderError("Export is missing H.264 video")
        if video.get("width") != width or video.get("height") != height:
            raise RenderError("Export dimensions differ from authored canvas")
        if audio_inputs and (not audio or audio.get("codec_name") != "aac"):
            raise RenderError("Export is missing required AAC audio")
        actual = float(evidence.get("format", {}).get("duration", 0))
        if not math.isfinite(actual) or abs(actual-duration) > max(0.15, 2/fps):
            raise RenderError(f"Export length mismatch: expected {duration}s, got {actual}s")
        os.replace(tmp, target)
        return {"path": str(target), "seconds": actual, "video_streams": sum(
            s.get("codec_type") == "video" for s in streams), "audio_streams": sum(
            s.get("codec_type") == "audio" for s in streams), "input_clips": len(sources)}
    finally:
        tmp.unlink(missing_ok=True)

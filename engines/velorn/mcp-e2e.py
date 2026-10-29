# SPDX-License-Identifier: GPL-3.0-only
"""Actual SDK client -> stdio launcher -> native editor; no model evaluation."""
import argparse
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import tempfile
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


async def exercise(options):
    fixture = Path(tempfile.mkdtemp(prefix="zx7-editor-mcp-"))
    projects, staging, outputs = (fixture / name for name in ("projects", "staging", "outputs"))
    for path in (projects, staging, outputs):
        path.mkdir()
    # Exercise the shipped host profile, including every advertised schema.
    # Actual edits below cover a narrower, explicitly measured workflow.
    tools = json.loads((ROOT / "engines/velorn/editor.example.json").read_text())["allowed_tools"]
    config = fixture / "editor.json"
    config.write_text(json.dumps({"endpoint": "http://127.0.0.1:19790/mcp", "projects_root": str(projects),
        "staging_root": str(staging), "outputs_root": str(outputs), "allowed_tools": tools,
        "allowed_access": ["read", "write"]}))
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    assert ffmpeg and ffprobe, "Install FFmpeg and FFprobe for independent decoding"
    def run(argv):
        return subprocess.check_output(argv, stderr=subprocess.PIPE, timeout=30)
    run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=24:d=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(staging / "source.mp4")])
    run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=f=440:d=2", str(staging / "tone.wav")])
    args = [str(ROOT / "engines/velorn/mcp.mjs"), "--source", str(options.source), "--config", str(config),
            "--state", str(fixture / "state"), "--python", sys.executable]
    for name in ("xvfb_binary", "xvfb_lib_dir", "display"):
        if getattr(options, name):
            args += ["--" + name.replace("_", "-"), getattr(options, name)]
    for name in ("no_sandbox", "software_gpu"):
        if getattr(options, name):
            args += ["--" + name.replace("_", "-")]
    params = StdioServerParameters(command="node", args=args, cwd=ROOT)

    @asynccontextmanager
    async def connected():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=120) as session:
                await session.initialize()
                yield session

    async def call(session, name, arguments=None):
        result = await session.call_tool(name, arguments or {})
        assert not result.is_error, (name, result)
        texts = [block.text for block in result.content if block.type == "text"]
        assert len(texts) == 1, (name, result)
        data = json.loads(texts[0])
        assert data.get("success") is not False or (arguments or {}).get("previewOnly") is True, (name, data)
        return data

    async def wait(session, predicate, seconds=20):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            state = await call(session, "get_project")
            if predicate(state):
                return state
            await asyncio.sleep(.15)
        raise AssertionError("Native debounced project state did not converge")

    async with connected() as session:
        discovered = (await session.list_tools()).tools
        assert {tool.name for tool in discovered} == set(tools)
        from studio_next.body_editor_client import LocalEditorClient
        native = {tool["name"]: tool for tool in LocalEditorClient(
            "http://127.0.0.1:19790/mcp", allowed_tools={}).list_tools()}
        for tool in discovered:
            assert tool.input_schema == native[tool.name]["inputSchema"]
        assert (await session.call_tool("queue_prompt_generation_batch", {})).is_error
        assert (await session.call_tool("create_project", {"name": "Bad", "width": "wrong"})).is_error
        await call(session, "create_project", {"name": "MCP native edit", "width": 320, "height": 180, "fps": 24, "previewOnly": False})
        state = await wait(session, lambda state: (state.get("project") or {}).get("name") == "MCP native edit")
        project = Path(state["project"]["path"])
        assert (await session.call_tool("import_asset_from_path", {"path": "/etc/passwd", "previewOnly": False})).is_error
        for name, count in (("source.mp4", 1), ("tone.wav", 2)):
            await call(session, "import_asset_from_path", {"path": str(staging / name), "previewOnly": False})
            await wait(session, lambda state: state.get("assetCount") == count)
        await call(session, "add_asset_to_timeline", {"assetName": "source.mp4", "startSeconds": 0, "includeAudio": False, "previewOnly": False})
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("clipCount") == 1)
        await call(session, "add_asset_to_timeline", {"assetName": "tone.wav", "startSeconds": 0, "previewOnly": False})
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("clipCount") == 2)
        await call(session, "add_track", {"type": "video", "name": "Editable title", "previewOnly": False})
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("trackCount") == 3)
        title = await call(session, "add_text_clip", {"text": "MCP native edit", "startSeconds": 0, "durationSeconds": 2,
                    "style": {"fontSize": 24}, "previewOnly": False})
        title_id = title["result"]["clip"]["id"]
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("clipCount") == 3)
        await call(session, "set_clip_keyframes", {"clipId": title_id, "keyframes": [
            {"property": "opacity", "timeSeconds": 0, "value": 20, "easing": "cubicBezier(0.2,0,0.8,1)"},
            {"property": "opacity", "timeSeconds": 1, "value": 100, "easing": "linear"}], "previewOnly": False})
        await call(session, "save_project", {"previewOnly": False})
        native_path = project / "project.comfystudio"
        shutil.copy2(native_path, fixture / "revision-1.comfystudio")
        await call(session, "update_text_clip", {"clipId": title_id, "text": "MCP revised", "previewOnly": False})
        await call(session, "save_project", {"previewOnly": False})
        shutil.copy2(native_path, fixture / "revision-2.comfystudio")
        assert digest(fixture / "revision-1.comfystudio") != digest(fixture / "revision-2.comfystudio")
        saved = json.loads(native_path.read_text())
        original = project / saved["assets"][0]["path"]
        original_hash = digest(original)
        assert (await session.call_tool("export_fcpxml", {"outputPath": str(original), "previewOnly": False})).is_error
        assert digest(original) == original_hash
        private_document = fixture / "outside-project.comfystudio"
        shutil.copy2(native_path, private_document)
        linked_project = projects / "linked-document"
        linked_project.mkdir()
        (linked_project / "project.comfystudio").symlink_to(private_document)
        assert (await session.call_tool("open_project", {"projectPath": str(linked_project), "previewOnly": False})).is_error
        output = outputs / "mcp-export.mp4"
        await call(session, "export_timeline", {"outputPath": str(output), "target": "h264_project", "width": 320,
            "height": 180, "range": "custom", "startSeconds": 0, "endSeconds": 2, "fps": 24,
            "includeAudio": True, "previewOnly": False})
        deadline = time.monotonic() + 90
        while True:
            logs = list((fixture / "state").glob("session-*/velorn/export-worker.log"))
            if any("[ExportWorker] Export complete" in log.read_text() for log in logs):
                break
            assert time.monotonic() < deadline, "Native export worker did not finish"
            await asyncio.sleep(.2)
        inspection = await call(session, "inspect_export_file", {"path": str(output), "width": 320, "height": 180, "durationSeconds": 2})
        assert inspection["ready"], inspection

    async with connected() as session:
        await call(session, "open_project", {"projectPath": str(project), "previewOnly": False})
        await wait(session, lambda state: (state.get("currentTimeline") or {}).get("clipCount") == 3 and state.get("assetCount") == 2)
        timeline = await call(session, "get_timeline", {"includeClips": True})
        title = next(clip for clip in timeline["clips"] if clip["id"] == title_id)
        assert title["textProperties"]["text"] == "MCP revised"
        assert title["keyframes"] == next(clip for clip in saved["timelines"][0]["clips"] if clip["id"] == title_id)["keyframes"]
    probe = json.loads(run([ffprobe, "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(output)]))
    video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
    audio = next(stream for stream in probe["streams"] if stream["codec_type"] == "audio")
    assert (video["width"], video["height"], video["r_frame_rate"], int(video["nb_read_frames"])) == (320, 180, "24/1", 48)
    assert video["codec_name"] == "h264"
    assert audio["codec_name"] == "aac"
    assert abs(float(probe["format"]["duration"]) - 2) < .05
    run([ffmpeg, "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"])
    pcm = run([ffmpeg, "-v", "error", "-i", str(output), "-map", "0:a:0", "-ac", "1", "-f", "f32le", "pipe:1"])
    samples = struct.unpack("<" + "f" * (len(pcm) // 4), pcm)
    audio_rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    assert .03 < audio_rms < .2
    receipt = {"success": True, "kind": "scripted official SDK client; no autonomous model evaluation",
        "transport": "standard MCP stdio; Python SDK 2.3.0", "nativeSchemasUnchanged": True,
        "discoveredGrantedTools": len(discovered), "deniedNetworkTool": True, "deniedOutsideImport": True,
        "existingSourceExportDenied": True, "outsideNativeDocumentDenied": True,
        "invalidNativeArgumentsRejected": True, "editableTracks": 3, "savedVersions": 2,
        "processRestartReopenPassed": True, "frames": 48, "fps": "24/1", "audioCodec": "aac",
        "fullDecodePassed": True, "audioRms": audio_rms, "output": str(output), "sha256": digest(output), "fixture": str(fixture)}
    (fixture / "receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    for name in ("xvfb-binary", "xvfb-lib-dir", "display"):
        parser.add_argument("--" + name)
    parser.add_argument("--no-sandbox", action="store_true")
    parser.add_argument("--software-gpu", action="store_true")
    asyncio.run(exercise(parser.parse_args()))

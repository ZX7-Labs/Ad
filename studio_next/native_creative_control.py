"""Replaceable model ↔ actual host-granted native-editor MCP control loop.

This is a *transport and evidence boundary*, not a scripted editing pipeline,
an artistic review score, a model installation, or a production-ready agent.
The connected creative model (not this module) selects each tool and its args.
No operation is inferred from the brief, encoded as a preset, or auto-retried.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


_MAX_ACTION_BYTES = 262_144
_MAX_RESULT_TEXT = 64_000
_MAX_IMAGE_BYTES = 4 * 1024 * 1024
_MAX_TOTAL_IMAGE_BYTES = 8 * 1024 * 1024

NATIVE_CREATIVE_SYSTEM = """You are the creative brain controlling an actual native editor.
The owner's brief is creative direction, not a prescribed shot list. Independently
inspect the real project, discover allowed operations, choose artistic decisions
and make native editable revisions. Use inspect/review/export instruments, examine
actual decoded results, then revise if necessary. Never invent tools, sources,
rights, images, audio listening, finished files, or artistic-quality approval.
A failed write may already have occurred: inspect current native state before
deciding any further action; never automatically repeat the write.
Respond with a JSON object: {action, arguments, reason}.
Allowed actions are discover:{}, describe:{tool}, invoke:{tool, inputs},
finish:{summary}. 'invoke' inputs must match the exact tool schema.
Only the host controls tool permissions. This is not a fixed editing template.
"""


class NativeCreativeControlError(ValueError):
    """A proposed model command or an observation violates host guarantees."""


def _wire(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":"))


def _field(value: Any, name: str, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _native_content(result: Any) -> tuple[list[str], list[tuple[str, bytes]]]:
    """Unpack bounded text and exact image bytes; never trust plain base64 labels."""
    if _field(result, "is_error", _field(result, "isError", False)):
        return [], []
    blocks = _field(result, "content", ())
    if not isinstance(blocks, (list, tuple)):
        raise NativeCreativeControlError("Native MCP returned no inspectable content")
    texts, images, total = [], [], 0
    for block in blocks:
        kind = _field(block, "type")
        if kind == "text":
            txt = _field(block, "text")
            if not isinstance(txt, str) or len(txt.encode("utf-8")) > _MAX_RESULT_TEXT:
                raise NativeCreativeControlError("Native text evidence was missing or oversized")
            texts.append(txt)
        elif kind == "image":
            mime = _field(block, "mime_type", _field(block, "mimeType"))
            if mime != "image/png":
                raise NativeCreativeControlError("Only original bounded PNG evidence is accepted")
            raw = _field(block, "data")
            if not isinstance(raw, str) or len(raw) > 6_000_000:
                raise NativeCreativeControlError("Invalid encoded native image evidence")
            try:
                picture = base64.b64decode(raw, validate=True)
            except (ValueError, base64.binascii.Error) as exc:
                raise NativeCreativeControlError("Corrupt native image encoding") from exc
            total += len(picture)
            if (not 8 <= len(picture) <= _MAX_IMAGE_BYTES or
                    total > _MAX_TOTAL_IMAGE_BYTES or
                    not picture.startswith(b"\x89PNG\r\n\x1a\n")):
                raise NativeCreativeControlError("Native image is malformed or over budget")
            images.append((mime, picture))
        elif kind == "audio":
            raise NativeCreativeControlError(
                "Native WAV requires a real audio-capable model adapter; no synthetic listening")
        else:
            raise NativeCreativeControlError("Unexpected native MCP content type")
    return texts, images


def _source_bound_images(texts: list[str], images: list[tuple[str, bytes]]):
    if not images:
        return []
    if len(images) > 4 or len(texts) != 1:
        raise NativeCreativeControlError("Native image output lacks a bounded single proof receipt")
    try:
        receipt = json.loads(texts[0])
    except (ValueError, TypeError) as exc:
        raise NativeCreativeControlError("Native image output has invalid proof receipt") from exc
    if (not isinstance(receipt, dict) or
            not isinstance(receipt.get("export_sha256"), str) or
            re.fullmatch(r"[0-9a-f]{64}", receipt["export_sha256"]) is None):
        raise NativeCreativeControlError("Native image not bound to a verified export")
    entries = receipt.get("samples") if "samples" in receipt else [receipt]
    if not isinstance(entries, list) or len(entries) != len(images):
        raise NativeCreativeControlError("Image count does not match receipt")
    hashes = []
    for entry, (_, raw) in zip(entries, images):
        if not isinstance(entry, dict) or entry.get("export_sha256", receipt["export_sha256"]) != receipt["export_sha256"]:
            raise NativeCreativeControlError("Native frame observation uses incompatible source")
        sha = hashlib.sha256(raw).hexdigest()
        if entry.get("png_sha256") != sha:
            raise NativeCreativeControlError("Native frame is not the SHA-bound observed image")
        hashes.append(sha)
    return hashes


class NativeCreativeControl:
    """Single in-process driver of an already host-authorized official MCP session.

    The caller owns app lifetime, isolation, permissions and source/rights ledger.
    This driver cannot grant tools, invent sources, or privately install models.
    Each model-produced write is recorded *before* submission. The bounded
    event stream supports independent review; it is not an automatic replay log.
    """

    def __init__(self, session, model, *, max_turns=32, receipt_path: Path | None = None):
        if type(max_turns) is not int or not 1 <= max_turns <= 128:
            raise NativeCreativeControlError("Native model session requires finite turn budget")
        if not callable(getattr(model, "decide", None)):
            raise NativeCreativeControlError("A concrete creative decision model is required")
        self.session = session
        self.model = model
        self.max_turns = max_turns
        self.receipt_path = Path(receipt_path) if receipt_path is not None else None
        self.events: list[dict] = []
        self.tools: dict[str, Any] = {}
        self._last_images: list[tuple[str, bytes]] = []
        self._last_hashes: list[str] = []
        self._last_native_texts: list[str] = []
        self._receipt = None

    def _append(self, event: dict):
        event = json.loads(_wire({"sequence": len(self.events), **event}))
        # Never persist host model keys, image binary, audio bytes or native
        # returned payloads. Event hashes are adequate for custody correlation.
        if self._receipt is not None:
            self._receipt.write((_wire(event) + "\n").encode("utf-8"))
            self._receipt.flush()
            os.fsync(self._receipt.fileno())
        self.events.append(event)

    def _decision(self, raw):
        if (not isinstance(raw, dict) or set(raw) != {"action", "arguments", "reason"} or
                raw.get("action") not in {"discover", "describe", "invoke", "finish"} or
                not isinstance(raw.get("arguments"), dict) or
                not isinstance(raw.get("reason"), str) or
                not raw["reason"].strip()):
            raise NativeCreativeControlError("Model must select one fully specified native action")
        if len(_wire(raw).encode("utf-8")) > _MAX_ACTION_BYTES:
            raise NativeCreativeControlError("Model action exceeds bounded response")
        return raw

    async def _infer(self, context: dict):
        pictures = self._last_images
        hashes = self._last_hashes
        self._last_images, self._last_hashes = [], []
        if pictures:
            if not callable(getattr(self.model, "decide_with_images", None)):
                raise NativeCreativeControlError(
                    "Native visual evidence requires an image-capable actual model")
            context["observed_picture_sha256"] = hashes
            return await asyncio.to_thread(self.model.decide_with_images, context, pictures)
        return await asyncio.to_thread(self.model.decide, context)

    async def run(self, brief: str) -> dict:
        if not isinstance(brief, str) or not 1 <= len(brief.strip()) <= 32_000:
            raise NativeCreativeControlError("An ordinary owner's creative brief is required")
        available = (await self.session.list_tools()).tools
        if (not isinstance(available, list) or not available or
                any(not isinstance(_field(x, "name"), str) or
                    not isinstance(_field(x, "input_schema", _field(x, "inputSchema")), dict)
                    for x in available)):
            raise NativeCreativeControlError("Actual host-granted editor schemas are required")
        self.tools = {_field(x, "name"): x for x in available}
        if len(self.tools) != len(available):
            raise NativeCreativeControlError("Native editor has duplicate operation identities")
        if self.receipt_path is not None:
            if not self.receipt_path.parent.is_dir():
                raise NativeCreativeControlError("Receipt directory must already exist")
            # An existing receipt could contain accepted writes. Never silently
            # append, erase or replay it after a crash or uncertain tool return.
            fd = os.open(self.receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            self._receipt = os.fdopen(fd, "wb")
        try:
            identity = getattr(self.model, "settings", None)
            self._append({
                "kind": "session_started",
                "brief_sha256": hashlib.sha256(brief.encode()).hexdigest(),
                "model_id_reported": getattr(identity, "model_id", None),
                "model_adapter": type(self.model).__qualname__,
                "native_tool_count": len(self.tools),
                "neural_autonomy_or_artistic_quality_verified": False,
            })
            outcome = "turn_budget_exhausted"
            for turn in range(self.max_turns):
                context = {
                    "creative_brief": brief,
                    "turn": turn,
                    "available_actions": ["discover", "describe", "invoke", "finish"],
                    "actual_granted_native_tools": list(self.tools),
                    "latest_events": self.events[-8:],
                    "last_native_result_texts": self._last_native_texts,
                    "completion_does_not_certify_artistic_quality": True,
                    "audio_semantically_reviewed": False,
                }
                decision = self._decision(await self._infer(context))
                self._last_native_texts = []
                action, args = decision["action"], decision["arguments"]
                if action == "finish":
                    if set(args) != {"summary"} or not isinstance(args["summary"], str) or not args["summary"].strip():
                        raise NativeCreativeControlError("Model summary is required; quality is not host-certified")
                    self._append({"kind": "model_finished", "turn": turn,
                                  "summary": args["summary"][:4000],
                                  "creative_quality_independently_approved": False})
                    outcome = "model_finished_unverified"
                    break
                if action == "discover":
                    if args:
                        raise NativeCreativeControlError("Discover accepts no model arguments")
                    self._append({"kind": "discovered", "turn": turn,
                                  "tools": [_field(t, "name") for t in available]})
                    continue
                if action == "describe":
                    if set(args) != {"tool"} or args["tool"] not in self.tools:
                        raise NativeCreativeControlError("Model requested an ungranted native tool")
                    tool = self.tools[args["tool"]]
                    self._append({"kind": "native_tool_schema", "turn": turn,
                                  "tool": args["tool"],
                                  "description": _field(tool, "description", "")[:2048],
                                  "input_schema": _field(tool, "input_schema",
                                                         _field(tool, "inputSchema"))})
                    continue
                if set(args) != {"tool", "inputs"} or args["tool"] not in self.tools or not isinstance(args["inputs"], dict):
                    raise NativeCreativeControlError("Model requested ungranted tool or invalid inputs")
                # Tool parameter schema is authoritatively enforced by the
                # configured MCP host. The model cannot override that host.
                native_name = args["tool"]
                self._append({"kind": "native_tool_submitted", "turn": turn,
                              "tool": native_name,
                              "inputs_sha256": hashlib.sha256(_wire(args["inputs"]).encode()).hexdigest(),
                              "model_reason": decision["reason"][:3000],
                              "uncertain_write_do_not_replay": True})
                try:
                    result = await self.session.call_tool(native_name, args["inputs"])
                except BaseException:
                    self._append({"kind": "native_tool_uncertain_outcome", "turn": turn,
                                  "tool": native_name, "must_reconcile_native_state": True})
                    raise
                if _field(result, "is_error", _field(result, "isError", False)):
                    texts = [_field(x, "text") for x in _field(result, "content", ())
                             if _field(x, "type") == "text"]
                    self._append({"kind": "native_tool_reported_error", "turn": turn,
                                  "tool": native_name, "message": str(texts)[:2000],
                                  "no_automatic_retry": True})
                    continue
                try:
                    texts, images = _native_content(result)
                    hashes = _source_bound_images(texts, images)
                except NativeCreativeControlError as exc:
                    self._append({"kind": "native_observation_rejected", "turn": turn,
                                  "tool": native_name, "error": str(exc),
                                  "must_reconcile_native_state": True})
                    raise
                self._last_native_texts = texts
                self._last_images, self._last_hashes = images, hashes
                self._append({"kind": "native_tool_result", "turn": turn,
                              "tool": native_name,
                              "text_sha256": [hashlib.sha256(s.encode()).hexdigest() for s in texts],
                              "image_sha256": hashes,
                              "audio_semantically_heard": False,
                              "human_or_artistic_quality_approved": False})
            return {
                "status": outcome, "events": self.events.copy(),
                "actual_model_id_reported": getattr(getattr(self.model, "settings", None),
                                                    "model_id", None),
                "native_editing_capability_complete": False,
                "artistic_quality_independently_approved": False,
                "source_rights_independently_verified": False,
            }
        finally:
            if self._receipt is not None:
                self._receipt.close()
                self._receipt = None

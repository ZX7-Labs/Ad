"""Temporary local operator seat for the existing ZX7 native creative controller.

This is a decision transport, NOT a GPT-6 runtime, autonomous model, MCP
replacement, or attestation of artistic quality. The real native controller
owns tool grants, execution, schemas, receipts and uncertain-write safety.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import time
from types import SimpleNamespace

PROTOCOL = "zx7.external-operator.v1"
_MAX_REQUEST_BYTES = 2 * 1024 * 1024
_MAX_REPLY_BYTES = 256 * 1024
_MAX_MEDIA_BYTES = 8 * 1024 * 1024


class ExternalOperatorError(ValueError):
    """Missing, unsafe, stale or incorrect operator communication."""


def _wire(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def _strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ExternalOperatorError("Duplicate external decision field")
            result[key] = value
        return result

    def reject_constant(_):
        raise ExternalOperatorError("Nonfinite external decision number")

    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise ExternalOperatorError("Invalid external decision JSON") from exc


def _private_dir(path: Path):
    if path.is_symlink():
        raise ExternalOperatorError("Operator directory must not be a symbolic link")
    try:
        metadata = path.stat()
    except OSError as exc:
        raise ExternalOperatorError("Operator directory must already exist") from exc
    if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_mode & 0o077 or
            (hasattr(os, "getuid") and metadata.st_uid != os.getuid())):
        raise ExternalOperatorError("Operator directory must be private, owned and mode 0700")


def _write_private(path: Path, data: bytes):
    if len(data) > _MAX_REQUEST_BYTES:
        raise ExternalOperatorError("Operator file exceeds bounded size")
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(12) + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic exclusive installation: never clobber an accepted turn.
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise ExternalOperatorError("Refusing to overwrite operator response") from exc
        temporary.unlink()
        if hasattr(os, "O_DIRECTORY"):
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_private(path: Path, limit: int):
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise ExternalOperatorError("Missing or unsafe external response") from exc
    with os.fdopen(fd, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077 or
                (hasattr(os, "getuid") and metadata.st_uid != os.getuid()) or
                metadata.st_size > limit):
            raise ExternalOperatorError("Response must be a private bounded regular file")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ExternalOperatorError("Response exceeds limit")
    return data


class ExternalOperatorModel:
    """One fresh, private operator session implementing decide/vision/audio.

    Another authorized session may supply decisions; it does not inherit this
    chat's memory. Its identity is not inferred from the file protocol.
    """

    def __init__(self, mailbox_root: Path, *, system_prompt: str,
                 timeout_seconds: float = 900, poll_seconds: float = 0.2):
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ExternalOperatorError("Native controller instructions required")
        if (not 0.1 <= timeout_seconds <= 3600 or
                not 0.01 <= poll_seconds <= 1):
            raise ExternalOperatorError("Finite operator budgets required")
        self.root = Path(mailbox_root)
        _private_dir(self.root)
        self.session_id = secrets.token_hex(16)
        self.session_dir = self.root / ("operator-" + self.session_id)
        self.session_dir.mkdir(mode=0o700)
        _private_dir(self.session_dir)
        self.settings = SimpleNamespace(model_id="external-operator-unverified",
                                        base_url=None)
        self.system_prompt = system_prompt
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds
        self.last_call_usage = None
        self._turn = 0
        _write_private(self.session_dir / "session.json", _wire({
            "protocol": PROTOCOL, "session_id": self.session_id,
            "model_identity_verified": False,
            "native_permissions_granted_by_mailbox": False,
            "autonomous_neural_inference_proven": False,
        }))
        print("ZX7_EXTERNAL_OPERATOR_SESSION=" + str(self.session_dir),
              file=sys.stderr, flush=True)

    def decide(self, context):
        return self._ask(context, [])

    def decide_with_images(self, context, images):
        if len(images) > 4:
            raise ExternalOperatorError("Too many image observations")
        return self._ask(context, [("image", mime, raw) for mime, raw in images])

    def decide_with_audio(self, context, audio):
        if len(audio) != 1:
            raise ExternalOperatorError("One authentic audio excerpt required")
        return self._ask(context, [("audio", mime, raw) for mime, raw in audio])

    def _ask(self, context, media):
        self._turn += 1
        turn = self._turn
        if turn > 128:
            raise ExternalOperatorError("Operator turn limit exhausted")
        manifest, total = [], 0
        for index, (kind, mime, raw) in enumerate(media):
            if (not isinstance(raw, bytes) or
                    (kind == "image" and (mime != "image/png" or
                     not raw.startswith(b"\x89PNG\r\n\x1a\n"))) or
                    (kind == "audio" and (mime != "audio/wav" or
                     not raw.startswith(b"RIFF") or raw[8:12] != b"WAVE"))):
                raise ExternalOperatorError("Operator media must be original typed binary")
            total += len(raw)
            if total > _MAX_MEDIA_BYTES:
                raise ExternalOperatorError("Operator media budget exceeded")
            name = f"media-{turn:04d}-{index:02d}." + (
                "png" if kind == "image" else "wav")
            _write_private(self.session_dir / name, raw)
            manifest.append({"kind": kind, "mime": mime, "file": name,
                             "sha256": hashlib.sha256(raw).hexdigest(),
                             "bytes": len(raw)})
        request = {
            "protocol": PROTOCOL, "session_id": self.session_id,
            "turn": turn, "nonce": secrets.token_hex(16),
            "system_instructions": self.system_prompt,
            "context": context, "media": manifest,
            "not_artistic_quality_proof": True,
        }
        raw_request = _wire(request)
        if len(raw_request) > _MAX_REQUEST_BYTES:
            raise ExternalOperatorError("Operator context exceeds bounded envelope")
        request_hash = hashlib.sha256(raw_request).hexdigest()
        request_path = self.session_dir / f"request-{turn:04d}.json"
        response_path = self.session_dir / f"response-{turn:04d}.json"
        _write_private(request_path, raw_request)
        print(f"ZX7_EXTERNAL_OPERATOR_TURN={turn} request={request_path.name} "
              f"sha256={request_hash}", file=sys.stderr, flush=True)
        deadline = time.monotonic() + self.timeout_seconds
        while not response_path.exists() and not response_path.is_symlink():
            if time.monotonic() >= deadline:
                raise ExternalOperatorError(
                    "Operator timed out; no native action selected")
            time.sleep(min(self.poll_seconds,
                           max(0, deadline - time.monotonic())))
        response = _strict_json(_read_private(response_path, _MAX_REPLY_BYTES))
        if (not isinstance(response, dict) or set(response) !=
            {"protocol", "session_id", "turn", "nonce", "request_sha256", "decision"} or
            response["protocol"] != PROTOCOL or
            response["session_id"] != self.session_id or
            type(response["turn"]) is not int or response["turn"] != turn or
            response["nonce"] != request["nonce"] or
            response["request_sha256"] != request_hash or
            not isinstance(response["decision"], dict)):
            raise ExternalOperatorError("Stale or invalid operator response binding")
        # The operator must have examined exactly the source-bound media the
        # controller supplied. If a file changed while the turn was outside
        # the process, never permit its resulting native decision to execute.
        for item in manifest:
            observed = _read_private(self.session_dir / item["file"],
                                     _MAX_MEDIA_BYTES)
            if (len(observed) != item["bytes"] or
                    hashlib.sha256(observed).hexdigest() != item["sha256"]):
                raise ExternalOperatorError(
                    "Operator evidence changed during the external model turn")
        return response["decision"]


def reply(session_dir: Path, turn: int, decision_file: Path):
    """Bind one operator-authored JSON decision to exactly one active turn."""
    session_dir = Path(session_dir)
    _private_dir(session_dir)
    if type(turn) is not int or turn < 1 or turn > 128:
        raise ExternalOperatorError("Invalid operator turn")
    session = _strict_json(_read_private(session_dir / "session.json",
                                         _MAX_REPLY_BYTES))
    raw = _read_private(session_dir / f"request-{turn:04d}.json",
                        _MAX_REQUEST_BYTES)
    request = _strict_json(raw)
    if (request.get("protocol") != PROTOCOL or
            request.get("session_id") != session.get("session_id") or
            request.get("turn") != turn):
        raise ExternalOperatorError("Operator request belongs to another session")
    decision = _strict_json(_read_private(Path(decision_file), _MAX_REPLY_BYTES))
    if not isinstance(decision, dict):
        raise ExternalOperatorError("Operator decision must be a JSON object")
    response = {
        "protocol": PROTOCOL, "session_id": session["session_id"],
        "turn": turn, "nonce": request["nonce"],
        "request_sha256": hashlib.sha256(raw).hexdigest(),
        "decision": decision,
    }
    destination = session_dir / f"response-{turn:04d}.json"
    _write_private(destination, _wire(response))
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    r = command.add_parser("reply")
    r.add_argument("--session-dir", type=Path, required=True)
    r.add_argument("--turn", type=int, required=True)
    r.add_argument("--decision-file", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "reply":
        print(reply(args.session_dir, args.turn, args.decision_file))


if __name__ == "__main__":
    main()

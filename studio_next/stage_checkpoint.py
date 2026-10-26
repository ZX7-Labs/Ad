"""Crash-safe, content-addressed creative production checkpoints.

Each checkpoint is bound to EXACT original film source, original brief/model
identity, renderer contract and shot. A restart can reuse a result ONLY if all
inputs match; it revalidates the technical output separately. No embedded
aesthetic presets. JSON data, never model-generated executable commands.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

_STAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")


def _encoded(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,
                      sort_keys=True,separators=(",",":")).encode("utf-8")


def fingerprint(value):
    return hashlib.sha256(_encoded(value)).hexdigest()


class DurableStageStore:
    def __init__(self, root):
        self.root=Path(root)

    def _path(self, name, immutable_input=None):
        if not isinstance(name,str) or _STAGE.fullmatch(name) is None:
            raise ValueError("Unsafe checkpoint identity")
        if immutable_input is None:
            return self.root/(name+".json")
        return self.root/(name+"."+fingerprint(immutable_input)+".json")

    def find(self, name, immutable_input):
        path=self._path(name,immutable_input)
        if self.root.is_symlink() or path.is_symlink():
            raise ValueError("Creative stage source checkpoint is a symbolic link")
        if not path.is_file():
            path=self._path(name)
        if self.root.is_symlink() or path.is_symlink():
            raise ValueError("Legacy creative checkpoint is a symbolic link")
        if not path.is_file():
            return None
        content=json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(content,dict) or content.get("schema")!=1
                or content.get("stage")!=name):
            raise ValueError("Corrupt/unknown original stage checkpoint schema")
        if content.get("input_sha256")!=fingerprint(immutable_input):
            # A different director version must NOT receive a stale shot.
            return None
        output=content.get("model_output")
        if content.get("output_sha256")!=fingerprint(output):
            raise ValueError("Saved creative stage digest does not match content")
        return output

    def save(self, name, immutable_input, model_output):
        path=self._path(name,immutable_input)
        if self.root.is_symlink() or path.is_symlink():
            raise ValueError("Model checkpoint output cannot be a symbolic link")
        self.root.mkdir(parents=True,exist_ok=True)
        record={"schema":1,"stage":name,
                "input_sha256":fingerprint(immutable_input),
                "output_sha256":fingerprint(model_output),
                "model_output":model_output}
        # File is always closed and fsynced BEFORE it becomes visible as valid.
        blob=json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
        fd,tmp=tempfile.mkstemp(prefix=".zx7-stage-checkpoint-",suffix=".tmp",dir=self.root)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as dest:
                dest.write(blob)
                dest.flush()
                os.fsync(dest.fileno())
            try:
                os.link(tmp,path)
            except FileExistsError:
                if (path.is_symlink() or not path.is_file()
                        or path.read_text(encoding="utf-8")!=blob):
                    raise ValueError(
                        "Another model stage output already owns these original inputs")
            if hasattr(os,"O_DIRECTORY"):
                directory=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return path


def content_signature(*, film_bytes, brief, model_id, scene, previous_design,
                      validation_contract_hash):
    if not isinstance(model_id,str) or not model_id.strip():
        raise ValueError("Pinned model identity required to restart creative task")
    if not isinstance(film_bytes,bytes) or not film_bytes:
        raise ValueError("Original screenplay bytes required")
    return {
        "original_film_sha256":hashlib.sha256(film_bytes).hexdigest(),
        "owner_brief_sha256":fingerprint(brief),
        "author_model":model_id,
        "shot":scene,
        "invalid_technical_design":previous_design,
        "renderer_contract_sha256":validation_contract_hash,
    }

"""Content-addressed per-stage checkpoints for costly local film-creation models.

Saved stages are never accepted from names alone: provenance includes the model,
actual supplied inputs, system prompt, and generation parameters. Every stage
gets its own fingerprint so that changing only the independent critic can reuse
unchanged artist-approved prior writing without re-running long generations.
"""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

_STAGE_ID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")

def digest(value):
    wire=json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,
                    separators=(",",":"))
    return hashlib.sha256(wire.encode("utf-8")).hexdigest()

class CheckpointLedger:
    def __init__(self,folder):
        self.folder=Path(folder)
        if self.folder.is_symlink():
            raise ValueError("Creative model checkpoint vault cannot be a symlink")
        self.folder.mkdir(parents=True,exist_ok=True)

    def _paths(self,name):
        if not isinstance(name,str) or not _STAGE_ID.fullmatch(name):
            raise ValueError("Unsafe creative checkpoint stage identity")
        output=self.folder/(name+".json")
        index=self.folder/(name+".checkpoint.json")
        if (self.folder.is_symlink() or output.is_symlink()
                or index.is_symlink()):
            raise ValueError("Linked creative checkpoint is not an original source")
        return output,index

    def fingerprint(self,*,name,model_id,system,input_data,sampling):
        self._paths(name)
        return digest({"stage":name,"model":model_id,"system":system,
                       "input":input_data,"sampling":sampling,"version":1})

    def load(self,name,fingerprint):
        path,index=self._paths(name)
        if not path.is_file() or not index.is_file():
            return None
        try:
            metadata=json.loads(index.read_text(encoding="utf-8"))
            if (metadata.get("fingerprint")!=fingerprint or
                    metadata.get("stage")!=name or metadata.get("version")!=1):
                return None
            data=json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data,dict) or digest(data)!=metadata.get("content_digest"):
                return None
            return data
        except (ValueError,TypeError,OSError):
            return None

    def write(self,name,fingerprint,value):
        if not isinstance(value,dict):
            raise ValueError("A creative checkpoint must be a JSON object")
        _=digest(value)  # verify serializability before writing anything
        output,index=self._paths(name)
        if not isinstance(fingerprint,str) or not re.fullmatch(
                r"[0-9a-f]{64}",fingerprint):
            raise ValueError("Original checkpoint model input digest must be exact")
        record={"stage":name,"fingerprint":fingerprint,
                "content_digest":digest(value),"version":1}
        for path,content in (
            (output,json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n"),
            (index,json.dumps(record,ensure_ascii=False,indent=2)+"\n")):
            fd,name=tempfile.mkstemp(
                prefix=".zx7-creative-ledger-",suffix=".tmp",
                dir=self.folder)
            temporary=Path(name)
            try:
                with os.fdopen(fd,"w",encoding="utf-8") as writer:
                    writer.write(content)
                    writer.flush()
                    os.fsync(writer.fileno())
                if path.is_symlink():
                    raise ValueError("A competing model substituted the original stage")
                os.replace(temporary,path)
                fd_dir=os.open(self.folder,os.O_RDONLY|os.O_DIRECTORY)
                try:os.fsync(fd_dir)
                finally:os.close(fd_dir)
            finally:
                temporary.unlink(missing_ok=True)

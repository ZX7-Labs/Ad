"""Content-addressed per-stage checkpoints for costly local film-creation models.

Saved stages are never accepted from names alone: provenance includes the model,
actual supplied inputs, system prompt, and generation parameters. Every stage
gets its own fingerprint so that changing only the independent critic can reuse
unchanged artist-approved prior writing without re-running long generations.
"""
import hashlib
import json
import os
from pathlib import Path

def digest(value):
    wire=json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,
                    separators=(",",":"))
    return hashlib.sha256(wire.encode("utf-8")).hexdigest()

class CheckpointLedger:
    def __init__(self,folder):
        self.folder=Path(folder)
        self.folder.mkdir(parents=True,exist_ok=True)

    def fingerprint(self,*,name,model_id,system,input_data,sampling):
        return digest({"stage":name,"model":model_id,"system":system,
                       "input":input_data,"sampling":sampling,"version":1})

    def load(self,name,fingerprint):
        path=self.folder/(name+".json")
        index=self.folder/(name+".checkpoint.json")
        if not path.is_file() or not index.is_file():
            return None
        try:
            metadata=json.loads(index.read_text(encoding="utf-8"))
            if metadata.get("fingerprint")!=fingerprint:
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
        output=self.folder/(name+".json")
        index=self.folder/(name+".checkpoint.json")
        record={"stage":name,"fingerprint":fingerprint,
                "content_digest":digest(value),"version":1}
        for path,content in (
            (output,json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n"),
            (index,json.dumps(record,ensure_ascii=False,indent=2)+"\n")):
            temp=path.with_suffix(path.suffix+".tmp")
            temp.write_text(content,encoding="utf-8")
            os.replace(temp,path)

"""Produce real silent WAV timing inputs for an expressly no_voice film.

The existing compositor requires measured voice-timing.json and per-shot WAVs.
This adapter is intentionally restricted to an explicitly silent treatment:
it must never quietly replace requested speech with silence.
"""
import argparse
import json
import math
import wave
from pathlib import Path


def make_silent_timing(project_path: Path, out: Path):
    p=json.loads(Path(project_path).read_text(encoding="utf-8"))
    if p.get("voice")!="no_voice":
        raise ValueError("Silent timing is only for director-selected no_voice")
    shots=p.get("scenes")
    if not isinstance(shots,list) or not shots:
        raise ValueError("No scenes")
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    timing=[]
    for i,s in enumerate(shots,1):
        if not isinstance(s,dict) or not isinstance(s.get("narration"),str) or s["narration"].strip():
            raise ValueError("Cannot silently discard narration")
        if not isinstance(s.get("min_seconds"), (int,float)) or not math.isfinite(s["min_seconds"]):
            raise ValueError("Invalid shot duration")
        filename=f"voice-{i:02d}.wav"
        with wave.open(str(out/filename),"wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00"*800)
        timing.append({"id":s["id"],"voice":"no_voice","text":"",
                       "seconds":0.05,"sample_rate":16000,
                       "file":filename,"inference_seconds":0})
    (out/"voice-timing.json").write_text(json.dumps(timing,indent=2))
    return timing


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    a=parser.parse_args()
    print("SILENT",len(make_silent_timing(a.project,a.out)))


if __name__=="__main__":
    main()

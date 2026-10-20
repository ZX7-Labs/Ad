#!/usr/bin/env python3
"""Repeatable subtle studio finishing for approved Supertonic voices.

No identity shifting or stylization: preserves transcript, timing and natural pitch.
Input should be a raw generated WAV, not a previously mastered MP3.
Project code: MIT. Requires open-source FFmpeg.
"""
import argparse, json, subprocess
from pathlib import Path

# Conservative 1 dB adjustments and very light dynamic leveling.
FILTERS=[
    "highpass=f=58",
    "equalizer=f=150:t=q:w=1.0:g=0.8",
    "equalizer=f=320:t=q:w=1.0:g=-1.0",
    "equalizer=f=3300:t=q:w=1.0:g=0.85",
    "acompressor=threshold=0.27:ratio=1.35:attack=15:release=155:makeup=1",
    "loudnorm=I=-16:TP=-1.5:LRA=11",
]
def master(src:Path, dst:Path)->dict:
    src=Path(src);dst=Path(dst)
    if not src.is_file() or src.suffix.lower()!='.wav':
        raise ValueError(f"Expected original unprocessed WAV: {src}")
    dst.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
        "-i",str(src),"-af",",".join(FILTERS),"-vn",
        "-codec:a","libmp3lame","-b:a","192k","-ar","44100",str(dst)],check=True)
    result=json.loads(subprocess.check_output(["ffprobe","-hide_banner",
        "-loglevel","error","-show_entries",
        "format=duration,size:stream=codec_name,channels,sample_rate",
        "-of","json",str(dst)],text=True))
    dur=float(result["format"]["duration"])
    assert 3.0<dur<180.0 and int(result["format"]["size"])>15000,result
    assert len(result["streams"])==1 and result["streams"][0]["channels"]==1
    return {"source":str(src),"output":str(dst),"duration_s":round(dur,3),
            "retains_original_voice":True,"pitch_or_speed_shift":False}
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--input-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    results=[]
    for label in ("m3","f2"):
        filename=f"{label}-tech-explainer.wav"
        results.append(master(args.input_dir/filename,
            args.output_dir/f"{label}-studio-warm.mp3"))
    (args.output_dir/"studio-mastering-report.json").write_text(json.dumps({
        "version":"1.0","rules":"Only gentle EQ, compression and loudness. No pitch/time transforms. Originals preserved.",
        "filters":FILTERS,"outputs":results
    },indent=2),encoding="utf-8")
    print(json.dumps(results,indent=2))

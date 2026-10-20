#!/usr/bin/env python3
"""Deep-voice A/B testing with permissive licenses only.

TTS: Resemble Chatterbox Nano (MIT weights + code).
Reference audio: Kyutai tts-voices/voice-zero (CC0, LibriVox-derived).
Reference is an allowed public-domain recording, not an unauthorized person's voice.
"""
import json, math, subprocess, time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from huggingface_hub import hf_hub_download
from chatterbox.tts_turbo import ChatterboxTurboTTS

OUT=Path("voice_lab/deep_samples")
OUT.mkdir(parents=True,exist_ok=True)
SCRIPT=("Most people think better ideas need more tools. "
        "They don't. They need room to breathe. "
        "Meet Nova, a calmer space for creative work.")
VOICES=("bill_boerst","peter_yearsley","stuart_bell")
torch.set_num_threads(min(4,torch.get_num_threads()))
print("Loading Chatterbox Nano (MIT) on CPU",flush=True)
start=time.time()
model=ChatterboxTurboTTS.from_pretrained(device="cpu",nano=True)
print("Loaded in",round(time.time()-start,1),"s; sample rate",model.sr,flush=True)
reports=[]
for name in VOICES:
    print("CC0 reference:",name,flush=True)
    path=hf_hub_download(repo_id="kyutai/tts-voices",
                         filename=f"voice-zero/{name}.wav",repo_type="model")
    # Important: avoid embedding or redistributing third-party reference files.
    t0=time.time()
    audio=model.generate(SCRIPT,audio_prompt_path=path)
    y=audio.detach().cpu().numpy().astype(np.float32).reshape(-1)
    if len(y)<model.sr*3 or not np.isfinite(y).all():
        raise RuntimeError(f"Invalid sample: {name}")
    maxpeak=float(np.max(np.abs(y)))
    if maxpeak>0.94:y*=0.94/maxpeak
    wav=OUT/f"{name}-raw.wav"
    sf.write(str(wav),y,model.sr,subtype="PCM_16")
    mastered=OUT/f"{name}-mastered.mp3"
    filt="highpass=f=65,equalizer=f=105:t=q:w=1.0:g=2.3,equalizer=f=280:t=q:w=1.2:g=-1.4,equalizer=f=3400:t=q:w=1.0:g=1.6,acompressor=threshold=0.19:ratio=2.0:attack=8:release=90,loudnorm=I=-16:TP=-1.5:LRA=10"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(wav),
                    "-af",filt,"-codec:a","libmp3lame","-qscale:a","2",str(mastered)],
                   check=True)
    metadata={"voice":name,"reference_license":"CC0 (Kyutai voice-zero collection)",
              "engine":"Resemble Chatterbox Nano","engine_license":"MIT",
              "seconds":round(len(y)/model.sr,2),"sample_rate":model.sr,
              "render_seconds":round(time.time()-t0,1),"peak":round(maxpeak,4)}
    reports.append(metadata)
    print("COMPLETE:",json.dumps(metadata),flush=True)
(OUT/"report.json").write_text(json.dumps({"script":SCRIPT,"voices":reports,
 "note":"Mastering is gently bass-focused EQ, presence boost, compression and loudness normalization. No pitch shifting. Human listening evaluation is still needed."},indent=2))
print("SUCCESS: deep-voice A/B",flush=True)

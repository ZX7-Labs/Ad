#!/usr/bin/env python3
"""Two original, non-impersonating voice archetypes:
refined British digital assistant / cinematic baritone.
Apache-2.0 Qwen3-TTS VoiceDesign. No celebrity voice or movie audio used.
"""
import json, os, pathlib, subprocess, time, gc
import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

OUT=pathlib.Path("voice_lab/voice_design");OUT.mkdir(exist_ok=True,parents=True)
MODEL="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
SCRIPT=("Good evening. Everything is ready. "
        "The important details are already in place. "
        "Now, shall we begin?")
PROMPTS=[
 ("british-assistant",
  "Original voice for a fictional sophisticated digital assistant. "
  "An adult British English man with a warm resonant low-middle register; "
  "understated posh Received Pronunciation, precise clear consonants and smooth vowels. "
  "Calm, witty but serious, quietly confident, articulate. "
  "Measured, elegantly deliberate conversational pacing, small purposeful pauses. "
  "Very human and intimate, not synthetic, not a radio announcer. "
  "Do not mimic or imitate any specific actor or fictional character."),
 ("cinematic-baritone",
  "Original mature adult English male narrator, a naturally low baritone "
  "with velvety warmth, strong breath support and extremely high clarity. "
  "Neutral English with a slight British influence, slow measured delivery, "
  "confident and intelligent without aggression. "
  "Rich natural chest resonance, restrained drama, micro-pauses for meaning, "
  "crisp consonants. Not growling, not excessively deep, no forced bass, "
  "no hype, not a radio announcer. Do not imitate any known person's voice.")
]
print("Loading original-voice designer",MODEL,flush=True)
torch.set_num_threads(max(1,min(4,os.cpu_count() or 2)))
t0=time.monotonic()
# BF16 halves resident weight memory relative to FP32 for 1.7B on CPU;
# eager attention avoids CUDA-only flash-attention.
model=Qwen3TTSModel.from_pretrained(
 MODEL,device_map="cpu",dtype=torch.bfloat16,attn_implementation="eager")
print("Model ready",round(time.monotonic()-t0,2),flush=True)
report=[]
for i,(name,desc) in enumerate(PROMPTS):
    print("Generating profile",name,flush=True)
    tic=time.monotonic()
    with torch.inference_mode():
        wavs,sr=model.generate_voice_design(
            text=SCRIPT, language="English",instruct=desc,
            max_new_tokens=700,do_sample=True,temperature=0.72)
    wav=np.asarray(wavs[0],dtype=np.float32).reshape(-1)
    if len(wav)<3*sr or not np.isfinite(wav).all():
        raise RuntimeError("Invalid WAV output for "+name)
    peak=float(np.max(np.abs(wav)))
    if peak>.92:wav*=.91/peak
    raw=OUT/(name+".wav")
    sf.write(str(raw),wav,sr,subtype="PCM_16")
    # Moderate, transparent polish to control low-frequency rumble / harsh highs.
    mp3=OUT/(name+".mp3")
    subprocess.run(["ffmpeg","-v","error","-y","-i",str(raw),
        "-af","highpass=f=65,lowpass=f=14500,acompressor=threshold=0.14:ratio=1.7:attack=14:release=125,loudnorm=I=-17:TP=-1.6:LRA=11",
        "-codec:a","libmp3lame","-q:a","2",str(mp3)],check=True)
    report.append({"name":name,"duration":round(len(wav)/sr,2),
                   "elapsed":round(time.monotonic()-tic,2),
                   "sample_rate":sr,"peak":round(peak,3),"file":str(mp3)})
    print("SUCCESS PROFILE",name,report[-1],flush=True)
    gc.collect()
(OUT/"comparison.json").write_text(json.dumps({
 "model":MODEL,"license":"Apache-2.0","synthesizer":"Qwen3 VoiceDesign 1.7B",
 "voice_policy":"Wholly original AI voice archetypes; no impersonation or movie samples",
 "script":SCRIPT,"results":report},indent=2))
print("ALL COMPLETED",flush=True)

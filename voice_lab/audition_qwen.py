#!/usr/bin/env python3
"""Voice Lab — isolated, open-source Qwen3 TTS voice auditions.

Not connected to the video renderer. Avoid subjective quality claims:
the generated WAVs must be auditioned and selected by a human.
"""
import json, os, sys, time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

OUT=Path("voice_lab/output")
OUT.mkdir(exist_ok=True,parents=True)
MODEL="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
TEXT=(
    "Most people think better ideas need more tools. "
    "They don't. They need room to breathe. "
    "Meet Nova, a calmer space for creative work."
)
INSTRUCTION=(
    "Sound like a thoughtful, charismatic young male creator speaking directly to "
    "one person. Warm, intimate, confident and genuinely curious. Natural conversational "
    "rhythm and expressive emphasis. Keep it fairly brisk but never rushed. Brief, "
    "intentional pauses after important points. Avoid announcer voice, hype, and robotic rhythm."
)
print("Loading Apache-2.0 Qwen3-TTS 0.6B on CPU",flush=True)
start=time.time()
# FP32 is required for dependable CPU compatibility; FlashAttention is CUDA-only.
torch.set_num_threads(max(1,min(4,os.cpu_count() or 2)))
engine=Qwen3TTSModel.from_pretrained(
    MODEL,device_map="cpu",torch_dtype=torch.float32,attn_implementation="eager"
)
print("Model loaded in",round(time.time()-start,1),"s",flush=True)
results=[]
for speaker in ("Ryan","Aiden"):
    t0=time.time()
    print("Generating",speaker,flush=True)
    audio,sr=engine.generate_custom_voice(
        text=TEXT,
        language="English",
        speaker=speaker,
        instruct=INSTRUCTION,
        max_new_tokens=900,
        do_sample=True,
        temperature=0.8
    )
    signal=np.asarray(audio[0],dtype=np.float32).reshape(-1)
    if signal.size<sr*3:raise RuntimeError(f"{speaker}: unexpectedly short voice")
    if not np.all(np.isfinite(signal)):raise RuntimeError(f"{speaker}: non-finite audio")
    peak=float(np.max(np.abs(signal)))
    if peak>.96:signal=signal*(.94/max(peak,1e-7))
    path=OUT/(speaker.lower()+"-sample.wav")
    sf.write(str(path),signal,sr,subtype="PCM_16")
    duration=len(signal)/sr
    record=dict(speaker=speaker,duration_s=round(duration,2),
                render_time_s=round(time.time()-t0,2),sample_rate=sr,
                max_absolute_amplitude=round(float(np.max(np.abs(signal))),4),
                wav_file=str(path))
    results.append(record)
    print("Voice result:",record,flush=True)
(OUT/"comparison.json").write_text(json.dumps({
    "model":MODEL,"license":"Apache-2.0","narration_text":TEXT,
    "style_instructions":INSTRUCTION,
    "results":results,
    "notice":"Audio has not been human-evaluated. Compare pronunciations, pacing, expressiveness, artifacts and consistency."
},indent=2),encoding="utf-8")
print("Voice Lab completed",flush=True)

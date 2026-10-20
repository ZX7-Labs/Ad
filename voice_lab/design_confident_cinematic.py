#!/usr/bin/env python3
"""Voice Lab: one original character-inspired voice; not celebrity voice cloning.

Reference traits only:
- AD Studio Voice B: cinematic, low warm baritone, crisp diction, controlled restraint.
- Smart tech-founder movie persona: relaxed confidence, dry wit, agile natural phrasing.
Output is an independent synthetic voice, not a recreation of any movie actor.
Engine: Apache-2.0 Qwen3-TTS-12Hz-1.7B-VoiceDesign.
"""
import json, os, pathlib, subprocess, time
import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

OUT=pathlib.Path("voice_lab/voice_fusion")
OUT.mkdir(parents=True,exist_ok=True)
MODEL="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
TEXT=("Here's the thing. Powerful technology doesn't need to shout. "
      "You notice it in the details. The confidence. The precision. "
      "And that quiet moment when everything just works.")
STYLE=(
    "Design a distinctive ORIGINAL male speaking voice for a premium technology "
    "brand film. Adult man around his late thirties to mid-forties. "
    "Warm naturally deep baritone with firm but NOT artificially lowered chest resonance. "
    "Intimate, rich, clear, studio-recorded timbre, a slight natural husky edge, "
    "detailed sibilants, crisp intelligible consonants and no vocal fry. "
    "Modern neutral American English with very slight refined transatlantic polish. "
    "The delivery mixes relaxed clever confidence and understated dry wit with the "
    "quiet gravity of a cinematic narrator. Think one intelligent, charismatic man "
    "speaking privately to the listener, not performing for a crowd. "
    "Natural varied pacing, unforced emphasis and three meaningful micro-pauses "
    "after short phrases; let important words land. Mid-slow but not sluggish. "
    "Subtle smile only on the first line, then precise, thoughtful composure. "
    "No exaggerated bass, whispering, growling, trailer announcer, breathy AI "
    "robotic affect, hyperactive enthusiasm, shouting, or fake dramatic inflection. "
    "Create a unique vocal identity; do not mimic any actor, character or celebrity."
)

def main():
    torch.set_num_threads(max(1,min(4,os.cpu_count() or 2)))
    tick=time.monotonic()
    print("Loading Apache-2.0 Qwen3-TTS VoiceDesign",flush=True)
    model=Qwen3TTSModel.from_pretrained(
        MODEL,device_map="cpu",dtype=torch.bfloat16,attn_implementation="eager")
    print("Loaded model",round(time.monotonic()-tick,1),"seconds",flush=True)
    t0=time.monotonic()
    with torch.inference_mode():
        waveforms,sr=model.generate_voice_design(
            text=TEXT,language="English",instruct=STYLE,
            max_new_tokens=1000,do_sample=True,temperature=0.64)
    data=np.asarray(waveforms[0],dtype=np.float32).reshape(-1)
    if len(data)<sr*6 or not np.isfinite(data).all():
        raise RuntimeError("Voice output failed length / finite-values checks")
    peak=float(np.max(np.abs(data)))
    if peak>0.93:data*=0.92/peak
    raw=OUT/"confident-cinematic-original.wav"
    sf.write(str(raw),data,sr,subtype="PCM_16")
    mp3=OUT/"confident-cinematic-original.mp3"
    # Mild studio finish, preserving actual vocal timbre without pitch tricks.
    filters=("highpass=f=66,equalizer=f=270:t=q:w=1.0:g=-1.0,"
             "equalizer=f=3100:t=q:w=1.0:g=1.0,"
             "acompressor=threshold=0.19:ratio=1.5:attack=12:release=140,"
             "loudnorm=I=-17:TP=-1.6:LRA=10")
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
        "-i",str(raw),"-af",filters,"-codec:a","libmp3lame","-q:a","2",
        str(mp3)],check=True)
    duration=round(len(data)/sr,2)
    if duration>40:raise ValueError(f"Unusually long audio: {duration}s")
    info={"model":MODEL,"model_license":"Apache-2.0",
          "original_voice":True,
          "not_voice_clone_or_actor_imitation":True,
          "reference_traits":["Voice B: cinematic baritone warmth and control",
                              "confident, witty, articulate modern-American tech-founder delivery"],
          "script":TEXT,"instructions":STYLE,"duration_s":duration,
          "sample_rate":sr,"synthesis_seconds":round(time.monotonic()-t0,1),
          "peak_before_mastering":round(peak,4),
          "mp3":str(mp3)}
    (OUT/"creative-voice-brief.json").write_text(
        json.dumps(info,indent=2),encoding="utf-8")
    print("PASS ORIGINAL VOICE",json.dumps({k:info[k] for k in
        ("duration_s","sample_rate","synthesis_seconds","mp3")}),flush=True)

if __name__=="__main__":main()

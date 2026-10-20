#!/usr/bin/env python3
"""Fast local voice audition with archived open-weight Supertonic 3.
No paid API, no hosted TTS, no voice cloning. Research only until accepted.
Two natural contrasting narrators on the *same* honest tech-explainer script.
"""
from pathlib import Path
import json,time,subprocess
import soundfile as sf
from supertonic import TTS

OUTPUT=Path("voice_lab/supertonic_results")
OUTPUT.mkdir(parents=True,exist_ok=True)
TEXT=("Here's something interesting about AI tools. "
      "Everyone talks about how fast they are. "
      "But the real breakthrough is when a tool understands what you actually need. "
      "That's when automation stops feeling like a robot, and starts feeling useful.")
# M3 = male; F2 = female. The final creative choice is human listening, not pitch metrics.
VOICES=("M3","F2")
print("Loading Supertonic 3 99M from pinned local model weights",flush=True)
t0=time.monotonic()
engine=TTS(model_dir="supertonic_assets",auto_download=False)
print("Engine ready in",round(time.monotonic()-t0,2),"seconds",flush=True)
results=[]
for identity in VOICES:
    style=engine.get_voice_style(voice_name=identity)
    print("Rendering",identity,flush=True)
    tic=time.monotonic()
    audio,duration=engine.synthesize(
        text=TEXT,voice_style=style,total_steps=10,
        speed=0.98,max_chunk_length=290,silence_duration=0.24,
        lang="en",verbose=False)
    wav=OUTPUT/f"{identity.lower()}-tech-explainer.wav"
    engine.save_audio(audio,str(wav))
    info=sf.info(str(wav))
    assert info.duration>=7 and info.duration<=60,(identity,info)
    assert info.samplerate==44100 and info.channels==1,(identity,info)
    mp3=wav.with_suffix(".mp3")
    # Transparent broadcast finishing, not pitch shifting or bass gimmicks.
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
      "-i",str(wav),"-af",
      "highpass=f=65,equalizer=f=310:t=q:w=1.0:g=-1.0,"
      "acompressor=threshold=0.17:ratio=1.5:attack=12:release=130,"
      "loudnorm=I=-16:TP=-1.5:LRA=11",
      "-c:a","libmp3lame","-q:a","2",str(mp3)],check=True)
    entry={"voice":identity,"seconds":round(info.duration,2),
       "render_seconds":round(time.monotonic()-tic,2),
       "sample_rate":info.samplerate,"mp3":str(mp3)}
    print("PASS VOICE",entry,flush=True);results.append(entry)
(OUTPUT/"audition_info.json").write_text(json.dumps({
 "model":"supertone-oss-archive/supertonic-3",
 "model_license":"BigScience OpenRAIL-M (not an unconditional OSI software license)",
 "source_code_license":"MIT","script":TEXT,
 "original_narrators":True,
 "research_only_until_license_review_and_user_approval":True,
 "results":results},indent=2),encoding="utf-8")
print("DONE",flush=True)

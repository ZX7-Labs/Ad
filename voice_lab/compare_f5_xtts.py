#!/usr/bin/env python3
"""Non-commercial listening comparison ONLY. Do not add these models to production.
F5-TTS weights: CC BY-NC 4.0.
XTTS-v2 weights and generated output: Coqui Public Model License (NC).
Model voices are conditioned on the same original synthetic CC0-derived
Stuart sample from the existing MIT Chatterbox-Nano voice lab.
"""
import argparse, json, os, time
from pathlib import Path

SAMPLE="The future isn't built in a day. It starts with a quiet decision. One clear idea. And the confidence to make it real."
REFERENCE_TEXT=("Most people think better ideas need more tools. "
                "They don't. They need room to breathe. "
                "Meet Nova, a calmer space for creative work.")
LICENSES={
"f5":"https://creativecommons.org/licenses/by-nc/4.0/",
"xtts":"https://huggingface.co/coqui/XTTS-v2/blob/main/LICENSE.txt"
}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--model",choices=["f5","xtts"],required=True)
    opts=parser.parse_args()
    ref=Path("voice_lab/reference/stuart_bell-raw.wav")
    if not ref.exists():raise FileNotFoundError("Missing baseline voice reference")
    out=Path("voice_lab/comparison");out.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    if opts.model=="f5":
        from f5_tts.api import F5TTS
        print("Loading F5-TTS CC-BY-NC voice model",flush=True)
        model=F5TTS(model="F5TTS_v1_Base",device="cpu")
        path=out/"f5-personal-test.wav"
        print("Running F5 on reference voice...",flush=True)
        result=model.infer(ref_file=str(ref),ref_text=REFERENCE_TEXT,
                   gen_text=SAMPLE,speed=0.96,nfe_step=16,
                   file_wave=str(path),show_info=print)
    else:
        from TTS.api import TTS
        print("Loading Coqui XTTS-v2 non-commercial model",flush=True)
        model=TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
        path=out/"xtts-personal-test.wav"
        print("Running XTTS on same reference voice...",flush=True)
        model.tts_to_file(text=SAMPLE,speaker_wav=str(ref),
                          language="en",file_path=str(path),
                          split_sentences=True)
    import soundfile as sf
    info=sf.info(str(path))
    assert info.channels>=1 and info.duration>3,(path,info)
    record={"model":opts.model,"license_url":LICENSES[opts.model],
      "script":SAMPLE,"reference_provenance":"CC0 source -> MIT Chatterbox Nano synthetic Stuart voice",
      "reference_transcript":REFERENCE_TEXT,
      "sample_duration_s":round(info.duration,2),
      "runtime_s":round(time.monotonic()-start,2),
      "sample_rate":info.samplerate,"purpose":"Non-commercial listening research ONLY"}
    (out/f"{opts.model}-metadata.json").write_text(json.dumps(record,indent=2))
    print("PASS",json.dumps(record),flush=True)
if __name__=="__main__":main()

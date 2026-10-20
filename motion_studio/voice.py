"""Synthesize project narration using the existing accepted voice identity."""
import argparse
import json
import time
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--model-dir',required=True,type=Path)
    args=parser.parse_args()
    import soundfile as sf
    from supertonic import TTS
    project=json.loads(args.project.read_text())
    voice=project['voice']
    if voice not in ('M3','F2'):raise ValueError('Select an existing accepted voice identity')
    args.out.mkdir(parents=True,exist_ok=True)
    engine=TTS(model_dir=str(args.model_dir),auto_download=False)
    style=engine.get_voice_style(voice_name=voice)
    results=[]
    for index,scene in enumerate(project['scenes']):
        start=time.monotonic()
        audio,duration=engine.synthesize(text=scene['narration'],voice_style=style,total_steps=10,
            speed=.98,max_chunk_length=290,silence_duration=.24,lang='en',verbose=False)
        path=args.out/f'voice-{index+1:02d}.wav'
        engine.save_audio(audio,str(path))
        info=sf.info(path)
        if not .3<info.duration<30:raise ValueError('Unexpected narration duration')
        result={'id':scene['id'],'voice':voice,'text':scene['narration'],'seconds':info.duration,
                'sample_rate':info.samplerate,'file':path.name,'inference_seconds':round(time.monotonic()-start,2)}
        results.append(result)
        print('VOICE',json.dumps(result),flush=True)
    (args.out/'voice-timing.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()

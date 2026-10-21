"""Synthesize project narration using the existing accepted voice identity."""
import argparse
import json
import time
import wave
from pathlib import Path


def write_silent_voice_slot(path: Path, *, sample_rate=16000, seconds=.05):
    """A scene with no spoken lines must not synthesize imaginary speech.

    This preserves the project's chosen narrator for all spoken scenes. It is
    an audio-timing file only, not a new narrator voice or a film quality claim.
    """
    if not 8000 <= sample_rate <= 96000 or not .01 <= seconds <= .25:
        raise ValueError("Invalid silent voice timing")
    samples=round(sample_rate*seconds)
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),"wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(b"\\x00\\x00"*samples)
    return samples/sample_rate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--model-dir',required=True,type=Path)
    args=parser.parse_args()
    import soundfile as sf
    project=json.loads(args.project.read_text())
    voice=project['voice']
    if voice not in ('M3','F2'):raise ValueError('Select an existing accepted voice identity')
    scenes=project.get('scenes')
    if not isinstance(scenes,list) or not scenes:
        raise ValueError('Project must supply actual storyboard scenes')
    for scene in scenes:
        if not isinstance(scene,dict) or not isinstance(scene.get('id'),str) or not isinstance(scene.get('narration'),str):
            raise ValueError('Every scene needs an ID and deliberately authored dialogue or silence')
    args.out.mkdir(parents=True,exist_ok=True)
    # Only initialize the real M3/F2 TTS engine if this film actually speaks.
    # The accepted voices and all synthesis parameters remain unchanged.
    engine=None;style=None
    if any(scene['narration'].strip() for scene in scenes):
        from supertonic import TTS
        engine=TTS(model_dir=str(args.model_dir),auto_download=False)
        style=engine.get_voice_style(voice_name=voice)
    results=[]
    for index,scene in enumerate(scenes):
        start=time.monotonic()
        path=args.out/f'voice-{index+1:02d}.wav'
        text=scene['narration']
        if not text.strip():
            write_silent_voice_slot(path)
        else:
            audio,duration=engine.synthesize(text=text,voice_style=style,total_steps=10,
                speed=.98,max_chunk_length=290,silence_duration=.24,lang='en',verbose=False)
            engine.save_audio(audio,str(path))
        info=sf.info(path)
        if text.strip() and not .3<info.duration<30:
            raise ValueError('Unexpected narration duration')
        result={'id':scene['id'],'voice':voice,'text':text,'seconds':info.duration,
                'sample_rate':info.samplerate,'file':path.name,'inference_seconds':round(time.monotonic()-start,2)}
        results.append(result)
        print('VOICE',json.dumps(result),flush=True)
    (args.out/'voice-timing.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()

"""Synthesize project narration using the existing accepted voice identity."""
import argparse
import json
import time
import wave
from pathlib import Path

from studio_next.voice_contract import valid_voice_id, validate_voice_settings, voice_inventory


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
        writer.writeframes(bytes(samples*2))
    return samples/sample_rate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--model-dir',required=True,type=Path)
    args=parser.parse_args()
    project=json.loads(args.project.read_text())
    voice=project['voice']
    if not valid_voice_id(voice):raise ValueError('Select a safe installed voice identity or no_voice')
    defaults=validate_voice_settings(project.get('voice_settings',{}))
    scenes=project.get('scenes')
    if not isinstance(scenes,list) or not scenes:
        raise ValueError('Project must supply actual storyboard scenes')
    for scene in scenes:
        if not isinstance(scene,dict) or not isinstance(scene.get('id'),str) or not isinstance(scene.get('narration'),str):
            raise ValueError('Every scene needs an ID and deliberately authored dialogue or silence')
    for scene in scenes:
        selected=scene.get('voice',voice)
        if not valid_voice_id(selected):raise ValueError('Invalid scene voice identity')
        validate_voice_settings(scene.get('voice_settings',{}))
        if selected=='no_voice' and scene['narration'].strip():
            raise ValueError('no_voice cannot discard spoken dialogue')
    args.out.mkdir(parents=True,exist_ok=True)
    # No inference or downloads for deliberately silent scenes.
    engine=None;styles={}
    if any(scene['narration'].strip() for scene in scenes):
        from supertonic import TTS
        engine=TTS(model_dir=str(args.model_dir),auto_download=False)
        installed=set(engine.voice_style_names)
        local_styles={v["id"] for v in voice_inventory(args.model_dir)["voices"]}
        requested={s.get("voice",voice) for s in scenes if s["narration"].strip()}
        missing=requested-installed-local_styles
        if missing:raise ValueError("Requested voices not installed: "+", ".join(sorted(missing)))
        styles={name:(engine.get_voice_style(voice_name=name) if name in installed else
                      engine.get_voice_style_from_path(args.model_dir/"voice_styles"/(name+".json")))
                for name in sorted(requested)}
    results=[]
    for index,scene in enumerate(scenes):
        start=time.monotonic()
        path=args.out/f'voice-{index+1:02d}.wav'
        text=scene['narration']
        selected=scene.get('voice',voice)
        settings=dict(total_steps=10,speed=.98,max_chunk_length=290,silence_duration=.24,lang='en')
        settings.update(defaults)
        settings.update(validate_voice_settings(scene.get('voice_settings',{})))
        if not text.strip():
            write_silent_voice_slot(path)
        else:
            audio,duration=engine.synthesize(text=text,voice_style=styles[selected],verbose=False,**settings)
            engine.save_audio(audio,str(path))
        with wave.open(str(path),"rb") as recorded:
            sample_rate=recorded.getframerate()
            measured_seconds=recorded.getnframes()/sample_rate
        if text.strip() and not 0<measured_seconds<3600:
            raise ValueError('Unexpected narration duration')
        result={'id':scene['id'],'voice':selected,'voice_settings':settings if text.strip() else {},'text':text,'seconds':measured_seconds,
                'sample_rate':sample_rate,'file':path.name,'inference_seconds':round(time.monotonic()-start,2)}
        results.append(result)
        print('VOICE',json.dumps(result),flush=True)
    (args.out/'voice-timing.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()

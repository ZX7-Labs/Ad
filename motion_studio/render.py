"""Render a JSON scene graph with measured narration timing.

No product names, story roles, scene count or category-specific drawing functions
live here. Artwork, copy, positions, paths and keyframes belong to the project.
This is a small 2D/2.5D compositor, not a generative-video or arbitrary-3D engine.
"""
import argparse
import functools
import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = {
    "sans": "/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf",
    "bold": "/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf",
    "serif": "/usr/share/fonts/opentype/urw-base35/P052-Italic.otf",
    "mono": "/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Regular.otf",
}


def color(value):
    from PIL import ImageColor
    return ImageColor.getcolor(value, "RGBA")


@functools.lru_cache(maxsize=256)
def font(style, size):
    return ImageFont.truetype(FONTS[style], max(1, round(size)))


def ease(value, kind="smooth"):
    x = max(0., min(1., value))
    if kind == "linear": return x
    if kind == "out": return 1-(1-x)**3
    if kind == "in": return x**3
    if kind == "spring": return 1-math.exp(-7*x)*math.cos(10*x)
    return x*x*(3-2*x)


def value_at(track, t, default):
    if track is None: return default
    if isinstance(track, (int, float)): return track
    if t <= track[0][0]: return track[0][1]
    for left, right in zip(track, track[1:]):
        if t <= right[0]:
            q=ease((t-left[0])/(right[0]-left[0]), right[2] if len(right)>2 else "smooth")
            return left[1]+(right[1]-left[1])*q
    return track[-1][1]


def artwork(spec, factor):
    w,h=spec["size"]
    im=Image.new("RGBA",(round(w*factor),round(h*factor)))
    d=ImageDraw.Draw(im)
    def box(x): return tuple(round(v*factor) for v in x)
    for item in spec["items"]:
        kind=item["type"]
        fill=item.get("fill", "#14171B")
        if kind=="rect":
            d.rounded_rectangle(box(item["box"]),radius=round(item.get("radius",0)*factor),
                fill=fill,outline=item.get("stroke"),width=max(1,round(item.get("width",1)*factor)))
        elif kind=="ellipse":
            d.ellipse(box(item["box"]),fill=item.get("fill"),outline=item.get("stroke"),
                      width=max(1,round(item.get("width",1)*factor)))
        elif kind=="line":
            d.line([box(p) for p in item["points"]],fill=fill,
                   width=max(1,round(item.get("width",1)*factor)),joint="curve")
        elif kind=="polygon":
            d.polygon([box(p) for p in item["points"]],fill=fill)
        elif kind=="text":
            f=font(item.get("font","sans"),round(item["size"]*factor))
            x,y=box(item["at"])
            for index,line in enumerate(item["text"].split("\n")):
                xx=x
                if item.get("align")=="center": xx-=d.textlength(line,font=f)/2
                if item.get("align")=="right": xx-=d.textlength(line,font=f)
                d.text((xx,y+round(index*item["size"]*item.get("leading",1.07)*factor)),
                       line,font=f,fill=fill,stroke_width=0)
        else:
            raise ValueError("Unsupported artwork primitive: "+kind)
    return im


class Compositor:
    def __init__(self, project, width):
        self.project=project
        self.factor=width/project["width"]
        self.width,self.height=width,round(project["height"]*self.factor)
        self.assets={name:artwork(spec,self.factor) for name,spec in project["assets"].items()}
        self.background=Image.new("RGBA",(self.width,self.height),project["background"])
        d=ImageDraw.Draw(self.background)
        # Stable background texture, not flickering random noise per frame.
        spacing=round(project.get("grid",28)*self.factor)
        for y in range(spacing//2,self.height,spacing):
            for x in range(spacing//2,self.width,spacing):
                d.ellipse((x,y,x+max(1,round(self.factor)),y+max(1,round(self.factor))),
                          fill=project.get("grid_color","#E0E0DD"))
        rng=np.random.default_rng(914)
        noise=rng.normal(0,.65,(self.height,self.width,1))
        a=np.asarray(self.background).copy()
        a[:,:,:3]=np.clip(a[:,:,:3].astype(float)+noise,0,255).astype(np.uint8)
        self.background=Image.fromarray(a)

    def frame(self, scene, t):
        canvas=self.background.copy()
        for layer in scene["layers"]:
            if t < layer.get("in",0) or t > layer.get("out",float("inf")): continue
            tracks=layer.get("animate",{})
            prop=lambda key,default: value_at(tracks.get(key),t,layer.get(key,default))
            opacity=max(0,min(1,prop("opacity",1)))
            if opacity<.002: continue
            image=self.assets[layer["asset"]]
            reveal=max(0,min(1,prop("reveal",1)))
            if reveal<1:
                clipped=Image.new("RGBA",image.size)
                clipped.paste(image.crop((0,0,max(1,round(image.width*reveal)),image.height)),(0,0))
                image=clipped
            scale=prop("scale",1)
            sx,sy=prop("scale_x",1)*scale,prop("scale_y",1)*scale
            size=(max(1,round(image.width*sx)),max(1,round(image.height*sy)))
            image=image.resize(size,Image.Resampling.BICUBIC)
            angle=prop("angle",0)
            if abs(angle)>.03: image=image.rotate(angle,Image.Resampling.BICUBIC,expand=True)
            blur=prop("blur",0)*self.factor
            if blur>.15: image=image.filter(ImageFilter.GaussianBlur(blur))
            if opacity<.999:
                image.putalpha(image.getchannel("A").point(lambda v:round(v*opacity)))
            x=round(prop("x",360)*self.factor-image.width/2)
            y=round(prop("y",400)*self.factor-image.height/2)
            if layer.get("shadow"):
                cfg=layer["shadow"]
                sh=Image.new("RGBA",image.size)
                sh.putalpha(image.getchannel("A").point(lambda a:round(a*cfg.get("alpha",.18))))
                padding=round(cfg.get("blur",18)*self.factor*3)
                expanded=Image.new("RGBA",(sh.width+padding*2,sh.height+padding*2))
                expanded.paste(sh,(padding,padding))
                expanded=expanded.filter(ImageFilter.GaussianBlur(cfg.get("blur",18)*self.factor))
                canvas.alpha_composite(expanded,(x-padding+round(cfg.get("dx",0)*self.factor),
                    y-padding+round(cfg.get("dy",18)*self.factor)))
            canvas.alpha_composite(image,(x,y))
        return canvas.convert("RGB")


def pcm_read(path, rate):
    data=subprocess.check_output(["ffmpeg","-v","error","-i",str(path),"-f","f32le",
                                  "-ar",str(rate),"-ac","1","pipe:1"])
    return np.frombuffer(data,dtype=np.float32).copy()


def mix_audio(project, scenes, out, rate=48000):
    total=sum(s["seconds"] for s in scenes)
    bed=np.zeros(round(total*rate),dtype=np.float64)
    voice=np.zeros_like(bed)
    cursor=0.
    for s in scenes:
        if s.get("wav"):
            audio=pcm_read(s["wav"],rate)
            # Preserve the accepted identity/rate/pitch; only adjust output gain.
            rms=float(np.sqrt(np.mean(audio.astype(float)**2)))
            audio*=min(4.,.115/max(rms,1e-6))
            start=round((cursor+s.get("voice_delay",.28))*rate)
            voice[start:start+len(audio)]+=audio[:max(0,min(len(audio),len(voice)-start))]
        cursor+=s["seconds"]
    rng=np.random.default_rng(34)
    for note in project.get("score",[]):
        start,duration=note["at"],note.get("seconds",1.3)
        t=np.arange(round(duration*rate))/rate
        env=(1-np.exp(-t*90))*np.exp(-t*note.get("decay",2.4))
        freq=440*2**((note["midi"]-69)/12)
        sound=(np.sin(2*np.pi*freq*t)+.20*np.sin(2*np.pi*freq*2*t)
               +.08*np.sin(2*np.pi*freq*3*t))*env*note.get("gain",.035)
        index=round(start*rate); length=min(len(sound),len(bed)-index)
        if length>0: bed[index:index+length]+=sound[:length]
    cursor=0.
    for scene in scenes:
        for cue in scene.get("cues",[]):
            duration=cue.get("seconds",.18)
            t=np.arange(round(duration*rate))/rate
            noise=rng.normal(0,1,len(t))
            if cue["type"]=="paper":
                noise=np.convolve(noise,np.ones(9)/9,mode="same")
                sound=noise*np.sin(np.pi*t/duration)**2*cue.get("gain",.09)
            elif cue["type"]=="ink":
                sound=noise*(.4+.6*np.sin(t*45)**2)*np.sin(np.pi*t/duration)**2*cue.get("gain",.018)
            elif cue["type"]=="tap":
                sound=np.sin(2*np.pi*cue.get("hz",180)*t)*np.exp(-t*45)*cue.get("gain",.13)
            else: raise ValueError("Unknown audio cue")
            index=round((cursor+cue["at"])*rate);length=min(len(sound),len(bed)-index)
            if length>0: bed[index:index+length]+=sound[:length]
        cursor+=scene["seconds"]
    fade=np.minimum(1,np.arange(len(bed))/rate/.3)*np.minimum(1,(len(bed)-np.arange(len(bed)))/rate/1.1)
    mixed=(voice+bed)*fade
    peak=np.max(np.abs(mixed))
    if peak>.92:mixed*=.92/peak
    stereo=np.stack([mixed,mixed],axis=1)
    with wave.open(str(out),"wb") as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate)
        w.writeframes((np.clip(stereo,-1,1)*32767).astype('<i2').tobytes())
    return {"seconds":total,"peak":float(np.max(np.abs(mixed))),"rate":rate}


def render(project_path, out, width=1080, fps=24):
    project_path=Path(project_path);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    p=json.loads(project_path.read_text())
    if not 320 <= width <= 2160 or not 12 <= fps <= 60:
        raise ValueError('Unsupported output size or frame rate')
    if not p.get('assets') or not 1 <= len(p.get('scenes',[])) <= 60:
        raise ValueError('Supply original artwork and 1–60 data-defined scenes')
    for s in p['scenes']:
        if not isinstance(s.get('min_seconds'),(int,float)) or not .5 <= s['min_seconds'] <= 60:
            raise ValueError('Invalid scene duration')
        for layer in s['layers']:
            if layer['asset'] not in p['assets']:
                raise ValueError('Undefined drawable asset: '+layer['asset'])
            for track in layer.get('animate',{}).values():
                if isinstance(track,list) and any(a[0]>=b[0] for a,b in zip(track,track[1:])):
                    raise ValueError('Animation keyframe times must increase')
    c=Compositor(p,width)
    timings=json.loads((out/'voice-timing.json').read_text())
    assert len(timings)==len(p['scenes'])
    scenes=[]
    for scene,timing in zip(p['scenes'],timings):
        item=dict(scene,seconds=max(scene['min_seconds'],timing['seconds']+scene.get('voice_delay',.28)+scene.get('tail',.65)),wav=str(out/timing['file']))
        # Frame boundaries are exact and their final audio pause remains explicit.
        item['seconds']=math.ceil(item['seconds']*fps)/fps
        scenes.append(item)
    audio=out/'mix.wav';audio_info=mix_audio(p,scenes,audio)
    (out/'render-manifest.json').write_text(json.dumps({'project':p['title'],'direction_source':p['direction_source'],
        'renderer':'declarative scene graph; no fixed scene sequence','width':width,'height':c.height,
        'fps':fps,'audio':audio_info,'scenes':[{'id':s['id'],'seconds':s['seconds'],'narration':s['narration']} for s in scenes]},indent=2))
    frames=out/'frames';frames.mkdir(exist_ok=True)
    silent=out/'picture.mp4'
    encoder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24',
        '-s',f'{c.width}x{c.height}','-r',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','fast',
        '-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(silent)],stdin=subprocess.PIPE)
    try:
        for i,s in enumerate(scenes):
            for frame in range(round(s['seconds']*fps)):
                im=c.frame(s,frame/fps)
                encoder.stdin.write(im.tobytes())
                if frame in (round(.9*fps),round(s['seconds']*fps*.5)):
                    im.save(frames/f'{i+1:02d}-{frame:04d}.jpg',quality=91)
            print('RENDERED',s['id'],round(s['seconds'],3),flush=True)
    except BaseException:
        encoder.terminate()
        encoder.wait()
        raise
    finally:
        encoder.stdin.close()
    if encoder.wait()!=0:raise RuntimeError('Video encoder failed')
    final=out/'sample.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(silent),'-i',str(audio),
        '-map','0:v:0','-map','1:a:0','-c:v','copy','-af','loudnorm=I=-16:TP=-1.5:LRA=11',
        '-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart','-shortest',
        '-metadata','comment=Agent-directed illustrative sample; autonomous application not completed',str(final)],check=True)
    print('VIDEO',str(final),final.stat().st_size,flush=True)
    return final


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--width',type=int,default=1080)
    parser.add_argument('--fps',type=int,default=24)
    args=parser.parse_args()
    render(args.project,args.out,args.width,args.fps)

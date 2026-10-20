#!/usr/bin/env python3
"""AD Studio V3: original 2.5D brand films using Pillow, FFmpeg and Kokoro ONNX.
No prompts, paid assets, closed-source video models or borrowed music required.
Assets and claims are designed from the owner's supplied product brief.
"""
import argparse, json, math, os, re, shutil, subprocess, sys, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from shared_graphics import font, wrap, rounded, clamp, appear, ease, width as text_width

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"output"; OUT.mkdir(parents=True,exist_ok=True)
W,H=720,1280
IVORY=(247,247,243); WHITE=(255,255,252); INK=(24,29,31)
MUTED=(112,119,119)
PALE=(227,230,226)
FR=24
def fit(d,text,max_width=620,max_size=68,lines=3,bold=True):
    size=max_size
    while size>24:
        f=font(text,size,bold)
        broken=wrap(d,text,max_width,f,10)
        if len(broken)<=lines and all(text_width(d,z,f)<=max_width for z in broken):break
        size-=3
    return size,broken
def textlines(d,text,x,y,size=50,color=INK,bold=True,maxw=615,spacing=1.13,center=False):
    sz,lines=fit(d,str(text),maxw,size,4,bold)
    f=font(str(text),sz,bold)
    for i,l in enumerate(lines):
        xx=x if not center else (W-text_width(d,l,f))/2
        d.text((int(xx),int(y+i*sz*spacing)),l,font=f,fill=color)
    return sz*spacing*len(lines)
def lerp(a,b,p):return a+(b-a)*p
def smooth(q):return q*q*(3-2*q)
def spring(q):
    q=clamp(q)
    return min(1.07,1-math.exp(-8*q)*math.cos(12*q))
def pos(q,delay=0,duration=.35):return spring((q-delay)/duration)
def capsule(d,txt,x,y,bg=INK,fg=WHITE):
    f=font(txt,17,True); ww=text_width(d,txt,f)+38
    rounded(d,(x,y,x+ww,y+40),19,bg)
    d.text((x+19,y+10),txt,font=f,fill=fg)
def shadowsource(src,rad=22):
    a=src.getchannel("A");shadow=Image.new("RGBA",src.size,(0,0,0,0))
    shadow.putalpha(a.point(lambda x: int(x*.20)))
    return shadow.filter(ImageFilter.GaussianBlur(rad))
def place(canvas,img,cx,cy,q,offset=260,scale=1,angle=-4,delay=.06,breath=0):
    p=pos(q,delay,.31)
    sc=scale*(.89+.11*p)
    ww=max(1,int(img.width*sc));hh=max(1,int(img.height*sc))
    layer=img.resize((ww,hh),Image.Resampling.BICUBIC).rotate(angle,expand=True,resample=Image.Resampling.BICUBIC)
    x=int(cx-layer.width/2);y=int(cy-layer.height/2+(1-p)*offset+breath)
    sh=shadowsource(layer)
    canvas.paste(sh,(x+12,y+22),sh)
    canvas.paste(layer,(x,y),layer)
def canvas_bg(light=True,accent=(229,106,70),phase=0):
    base=IVORY if light else INK
    im=Image.new("RGB",(W,H),base);d=ImageDraw.Draw(im)
    if light:
        for y in range(45,H,31):
            for x in range(24,W,31):
                d.ellipse((x-1,y-1,x+1,y+1),fill=(223,226,221))
    else:
        for x in range(-H,H,52):
            dx=int(14*math.sin(phase*.8))
            d.line((x+dx,0,x+H+dx,H),fill=(33,39,41),width=2)
    return im
def colors(category):
    if category in ("app","software","digital","technology"):
        return (93,103,231),(224,226,253),"SOFTWARE"
    if category in ("health","wellness","fitness"):
        return (88,153,102),(219,238,222),"WELLNESS"
    if category in ("physical","product","device","fashion"):
        return (226,105,67),(250,231,219),"PRODUCT"
    if category in ("service","agency","business"):
        return (222,124,60),(249,229,205),"SERVICE"
    return (226,105,67),(250,231,219),"STUDIO"
def make_phone(name,benefit,accent):
    ww,hh=360,660
    im=Image.new("RGBA",(ww,hh),(0,0,0,0));d=ImageDraw.Draw(im)
    rounded(d,(4,4,ww-4,hh-4),48,(30,33,37,255))
    rounded(d,(15,15,ww-15,hh-15),36,(249,249,247,255))
    rounded(d,(126,24,235,45),11,(34,36,39,255))
    d.text((40,85),name[:12].upper(),font=font(name,29,True),fill=INK)
    d.text((40,151),"Your space.",font=font("Your space.",31,True),fill=INK)
    rounded(d,(29,213,ww-29,352),25,accent)
    d.text((52,240),"MORE",font=font("MORE",34,True),fill=WHITE)
    d.text((52,284),"POSSIBLE.",font=font("POSSIBLE.",30,True),fill=WHITE)
    for i in range(3):
        y=381+75*i
        rounded(d,(29,y,ww-29,y+60),14,(237,238,235))
        d.ellipse((47,y+15,77,y+45),fill=accent if i==1 else (208,211,210))
        rounded(d,(94,y+18,275,y+26),4,(177,181,180))
        rounded(d,(94,y+35,225+i*17,y+41),3,(213,216,213))
    d.ellipse((ww//2-9,hh-28,ww//2+9,hh-11),fill=(210,211,209))
    return im
def make_pack(name,accent):
    im=Image.new("RGBA",(430,595),(0,0,0,0));d=ImageDraw.Draw(im)
    # Faux 3D object with top and side faces, perspective and material highlights.
    d.polygon([(70,120),(308,75),(370,120),(132,165)],fill=(250,248,245))
    d.polygon([(308,75),(370,120),(370,505),(308,460)],fill=(187,193,190))
    d.polygon([(70,120),(308,75),(308,460),(70,510)],fill=(249,249,244))
    d.polygon([(80,128),(301,86),(301,450),(80,498)],fill=(239,242,236))
    rounded(d,(95,201,285,405),16,accent)
    d.text((112,252),name[:9].upper(),font=font(name,29,True),fill=WHITE)
    d.line((112,311,266,311),fill=WHITE,width=3)
    d.text((112,328),"MADE FOR",font=font("MADE FOR",16,True),fill=WHITE)
    d.text((112,350),"YOU",font=font("YOU",27,True),fill=WHITE)
    d.line((92,145,92,476),fill=(255,255,255),width=4)
    d.ellipse((357,493,393,533),fill=accent)
    return im
def make_service(name,benefit,accent):
    ww,hh=485,550
    im=Image.new("RGBA",(ww,hh),(0,0,0,0));d=ImageDraw.Draw(im)
    rounded(d,(3,3,ww-3,hh-3),28,WHITE,(216,221,218),2)
    rounded(d,(25,25,ww-25,84),15,(240,242,239))
    d.ellipse((48,43,69,64),fill=accent)
    d.text((85,39),name.upper()[:20],font=font(name,22,True),fill=INK)
    d.text((35,126),"A CLEARER WAY",font=font("A CLEARER WAY",29,True),fill=INK)
    for i,p in enumerate((.54,.81,.62,.91,.74)):
        x=44+i*87
        rounded(d,(x,342-int(130*p),x+51,341),12,accent if i==3 else (201,210,205))
    d.line((36,358,ww-36,358),fill=(220,225,222),width=2)
    for i,label in enumerate(("CLARITY","CONTROL","MOMENTUM")):
        y=391+i*41
        d.ellipse((39,y+2,57,y+20),fill=accent)
        d.text((76,y),label,font=font(label,21,True),fill=INK)
    return im
def make_orbit(accent):
    im=Image.new("RGBA",(520,500),(0,0,0,0));d=ImageDraw.Draw(im)
    for x in range(4):
        r=80+x*49
        d.ellipse((260-r,250-r,260+r,250+r),outline=accent if x==1 else (185,193,188),width=3)
    for x,y,r in [(365,160,28),(165,235,18),(244,58,22)]:
        d.ellipse((x-r,y-r,x+r,y+r),fill=accent)
    return im
def plan(brief):
    name=str(brief.get('product') or brief.get('topic') or 'NOVA').strip()[:52]
    category=str(brief.get('category') or 'software').lower().strip()
    audience=str(brief.get('audience') or 'people who make things').strip()[:90]
    benefit=str(brief.get('benefit') or 'a clearer way to work').strip()[:105]
    cta=str(brief.get('cta') or 'Discover more').strip()[:65]
    sub=str(brief.get('tagline') or benefit).strip()[:90]
    accent,pale,cat=colors(category)
    scenes=[
     ("HOOK", f"Less ordinary.", "A BETTER WAY", "What if the everyday felt a little more extraordinary?"),
     ("AUDIENCE", f"For {audience}", "MADE FOR YOU", f"For {audience}, meet something different."),
     ("REVEAL",name.upper(),"INTRODUCING",f"Introducing {name}."),
     ("BENEFIT",benefit,"THE DIFFERENCE", f"{name} brings you {benefit}."),
     ("DESIGN","Everything, in its place.","NO DISTRACTIONS","Thoughtful details. A simpler experience."),
     ("MOTION",sub,"BUILT AROUND YOU",f"Designed to bring the focus back to what matters."),
     ("CTA",cta.upper(),name.upper(),f"{cta}. Discover {name}.")
    ]
    return dict(name=name,category=category,audience=audience,benefit=benefit,cta=cta,tagline=sub,
                accent=accent,pale=pale,cat=cat,scenes=scenes)
def draw(im,p,idx,q,t,total):
    ac=p['accent'];pale=p['pale'];name=p['name'];cat=p['category']
    d=ImageDraw.Draw(im)
    lite=(idx%3!=2)
    fg=INK if lite else WHITE; muted=MUTED if lite else (173,184,184)
    d.line((45,105,675,105),fill=(219,223,220) if lite else (70,79,80),width=2)
    d.text((45,65),"AD / MOTION LAB",font=font("AD / MOTION LAB",19,True),fill=fg)
    d.text((609,65),f"0{idx+1} / 07",font=font("01 / 07",18,True),fill=muted)
    # Scene composition is intentionally designed, not a repeated static card.
    q1=pos(q,0,.32)
    if idx==0:
        capsule(d,"NEW PERSPECTIVE",48,180,bg=ac)
        textlines(d,"MAKE IT",50,333+(1-q1)*120,99,fg,maxw=660)
        textlines(d,"FEEL",49,460+(1-q1)*155,115,ac,maxw=660)
        textlines(d,"DIFFERENT.",50,590+(1-q1)*180,79,fg,maxw=650)
        orb=make_orbit(ac);place(im,orb,380,895,q,offset=175,scale=.87,angle=8*math.sin(t*2),delay=.08)
    elif idx==1:
        capsule(d,"FOR PEOPLE LIKE YOU",50,176,bg=ac)
        textlines(d,"MADE",50,328+(1-q1)*95,105,fg)
        textlines(d,"FOR YOU.",49,447+(1-q1)*120,88,ac)
        textlines(d,p['audience'].upper(),55,607,40,fg,maxw=600)
        orb=make_orbit(ac);place(im,orb,370,935,q,offset=140,scale=.87,angle=13*math.sin(t*1.6))
    elif idx==2:
        capsule(d,"MEET YOUR NEW FAVORITE",48,166,bg=ac)
        textlines(d,name.upper(),46,285+(1-q1)*120,87,fg,maxw=625)
        d.text((52,430),"DESIGNED TO STAND OUT",font=font("DESIGNED TO STAND OUT",19,True),fill=muted)
        asset=p['hero'];place(im,asset,363,848,q,scale=.93 if cat in ("app","software","digital","technology") else 1.05,angle=-7,offset=260)
    elif idx==3:
        capsule(d,"THE REASON",50,175,bg=ac)
        textlines(d,"WHAT",49,290+(1-q1)*90,98,fg)
        textlines(d,"CHANGES?",49,405+(1-q1)*122,82,ac)
        textlines(d,p['benefit'],57,600,46,fg,maxw=594)
        asset=p['hero'];place(im,asset,358,948,q,scale=.78,angle=9,offset=220)
    elif idx==4:
        capsule(d,"SMALL DETAILS",48,174,bg=ac)
        textlines(d,"LESS.",50,286+(1-q1)*96,115,fg)
        textlines(d,"BUT BETTER.",50,414+(1-q1)*120,76,ac)
        if cat in ("app","software","digital","technology"):
            place(im,p['hero'],305,900,q,scale=.86,angle=-13)
            place(im,p['service'],505,1021,q,scale=.57,angle=8,delay=.12)
        else:
            place(im,p['service'],348,875,q,scale=.99,angle=-5)
        d.line((48,671,254,671),fill=ac,width=7)
    elif idx==5:
        capsule(d,"WHY IT MATTERS",48,169,bg=ac)
        textlines(d,"FOCUS",50,296+(1-q1)*90,110,fg)
        textlines(d,"ON WHAT",50,430+(1-q1)*90,85,ac)
        textlines(d,"MATTERS.",50,540+(1-q1)*90,83,fg)
        place(im,p['orbit'],368,923,q,scale=.95,angle=math.sin(t*3)*15)
        textlines(d,p['tagline'],65,1050,30,fg,maxw=605,center=True)
    else:
        capsule(d,"TAKE THE NEXT STEP",48,178,bg=ac)
        textlines(d,name.upper(),48,351+(1-q1)*98,88,fg,maxw=635)
        textlines(d,p['tagline'],50,510,44,fg,maxw=615)
        # Strong clear CTA button
        rounded(d,(48,735+(1-q1)*190,665,844+(1-q1)*190),29,ac)
        fs,ls=fit(d,p['cta'].upper(),480,43,2)
        f=font(p['cta'],fs,True)
        for z,line in enumerate(ls):
            w=text_width(d,line,f)
            d.text(((W-w)/2,765+(1-q1)*190+z*45),line,font=f,fill=WHITE)
        d.text((56,983),"YOUR NEXT MOVE STARTS HERE.",font=font("YOUR NEXT MOVE STARTS HERE.",21,True),fill=muted)
    # Mood transitions - quick fast graphic wipe, not random effect spam.
    enter=1-smooth(clamp(q/.10))
    if enter>.002:
        band=int(enter*W*1.42)
        d.polygon([(0,0),(band,0),(band-220,256),(0,300)],fill=ac)
    # Focused bottom caption and progress
    caps=p['scenes'][idx][3].split()
    chunks=[caps[i:i+4] for i in range(0,len(caps),4)]
    selection=chunks[min(len(chunks)-1,int(q*len(chunks)))]
    short=' '.join(selection).upper()
    if short:
        f=font(short,23,True)
        while text_width(d,short,f)>620:
            f=font(short,f.size-1,True)
        tw=text_width(d,short,f)
        bb=((W-tw)/2-19,1118,(W+tw)/2+19,1175)
        rounded(d,bb,14,INK if lite else WHITE)
        d.text(((W-tw)/2,1134),short,font=f,fill=WHITE if lite else INK)
    d.rectangle((47,1223,671,1229),fill=(216,220,216) if lite else (66,73,74))
    d.rectangle((47,1223,47+624*clamp(t/total),1229),fill=ac)

def music(path,times,duration):
    sr=22050
    n=int(duration*sr)
    x=np.arange(n,dtype=np.float64)/sr
    # Original minimal ambient soundtrack: soft chords and short restrained transitions.
    notes=[146.83,174.61,196.0,164.81]
    bed=np.zeros(n,dtype=np.float64)
    for k,start in enumerate(np.arange(0,duration,2.7)):
        freq=notes[k%len(notes)]
        tt=x-start
        env=np.where((tt>=0)&(tt<2.8),np.minimum(1.0,np.maximum(tt,0)/.32)*np.minimum(1.0,np.maximum(2.8-tt,0)/.8),0)
        tone=(np.sin(2*np.pi*freq*x)+.42*np.sin(2*np.pi*freq*1.5*x)+.19*np.sin(2*np.pi*freq*2*x))
        bed+=env*tone*.035
    for i,t in enumerate(times[1:-1]):
        z=x-t
        env=np.where((z>=0)&(z<.20),np.exp(-np.maximum(z,0)*30),0)
        bed+=.075*env*np.sin(2*np.pi*(340+100*i)*z)
    bed=np.tanh(bed)
    data=np.int16(np.clip(bed,-1,1)*32767)
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(sr);f.writeframes(data.tobytes())

def speech(plan,output,model_dir,voice='am_michael'):
    import soundfile as sf
    from kokoro_onnx import Kokoro
    model_dir=Path(model_dir)
    engine=Kokoro(str(model_dir/'kokoro-v1.0.onnx'),str(model_dir/'voices-v1.0.bin'))
    all_audio=[];times=[0.0];sr=24000
    for scene in plan['scenes']:
        audio,sr=engine.create(scene[3],voice=voice,speed=1.12,lang='en-us')
        audio=np.asarray(audio,dtype=np.float32)
        fade=int(.012*sr)
        if len(audio)>2*fade:
            audio[:fade]*=np.linspace(0,1,fade)
            audio[-fade:]*=np.linspace(1,0,fade)
        all_audio.extend([audio,np.zeros(int(.19*sr),dtype=np.float32)])
        times.append(times[-1]+(len(audio)+int(.19*sr))/sr)
    sf.write(str(output),np.concatenate(all_audio),sr,subtype='PCM_16')
    return times

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--brief',default='',help='Path to verified structured product details')
    ap.add_argument('--mute',action='store_true',help='Only for local video debugging')
    ap.add_argument('--voice',choices=['am_michael','am_adam','am_fenrir','am_puck'],default='am_michael')
    ap.add_argument('--model-dir',default='models')
    ap.add_argument('--fps',type=int,default=24)
    args=ap.parse_args()
    demo={'product':'NOVA','category':'software','audience':'creative teams',
          'benefit':'a calmer place to organize ideas','cta':'DISCOVER NOVA',
          'tagline':'Less clutter. More creative flow.'}
    if args.brief:
        demo.update(json.loads(Path(args.brief).read_text(encoding='utf-8')))
    p=plan(demo)
    p['hero']=make_phone(p['name'],p['benefit'],p['accent']) if p['category'] in ('app','software','digital','technology') else (
        make_pack(p['name'],p['accent']) if p['category'] in ('physical','product','device','fashion') else make_service(p['name'],p['benefit'],p['accent']))
    p['service']=make_service(p['name'],p['benefit'],p['accent'])
    p['orbit']=make_orbit(p['accent'])
    if args.mute:times=[i*1.8 for i in range(8)]
    else:times=speech(p,OUT/'voice.wav',args.model_dir,args.voice)
    duration=times[-1]
    times=[min(duration,t) for t in times]
    print('Creative plan:',p['name'],p['cat'],'voice',args.voice,'duration',round(duration,2),flush=True)
    raw=OUT/'raw.mp4'
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24',
         '-s',f'{W}x{H}','-r',str(args.fps),'-i','pipe:0','-c:v','libx264','-preset','veryfast','-crf','19',
         '-vf','scale=1080:1920:flags=lanczos','-pix_fmt','yuv420p','-movflags','+faststart',str(raw)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    import bisect
    try:
        for i in range(int(duration*args.fps)):
            t=i/args.fps
            idx=min(6,max(0,bisect.bisect_right(times,t)-1))
            denom=max(.2,times[idx+1]-times[idx]);q=clamp((t-times[idx])/denom)
            im=canvas_bg(idx%3!=2,p['accent'],t)
            draw(im,p,idx,q,t,duration)
            proc.stdin.write(im.tobytes())
            if i%(args.fps*3)==0:print('Rendered',i,'frames',flush=True)
    finally:proc.stdin.close()
    if proc.wait():raise RuntimeError('FFmpeg video process failed')
    if args.mute:
        shutil.copy2(raw,OUT/'short.mp4')
    else:
        music(OUT/'music.wav',times,duration)
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
          '-i',str(raw),'-i',str(OUT/'voice.wav'),'-i',str(OUT/'music.wav'),
          '-filter_complex','[1:a]volume=1.35[v];[2:a]volume=0.36[m];[v][m]amix=inputs=2:duration=first:normalize=0[a]',
          '-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-b:a','192k',
          '-t',str(duration),'-movflags','+faststart',str(OUT/'short.mp4')],check=True)
    (OUT/'creative_brief.json').write_text(json.dumps({k:v for k,v in p.items() if k not in ('hero','orbit','service')},indent=2),encoding='utf-8')
    print('SUCCESS:',OUT/'short.mp4','duration',round(duration,1),'seconds',flush=True)

if __name__=='__main__':main()

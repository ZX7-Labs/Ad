#!/usr/bin/env python3
"""Mobile-first procedural 2.5D Short renderer. No paid AI key required."""
import argparse, asyncio, math, os, re, shutil, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BG=(247,247,245); DARK=(23,24,26); GREY=(104,106,111); ORANGE=(224,100,63)
W,H=720,1280
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'
OUT.mkdir(exist_ok=True)

def font_path(text,bold=False):
    candidates=[]
    if re.search(r'[\u0900-\u097f]',text):
        candidates += ['/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf' if bold else '/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf']
    candidates += [('/usr/share/fonts/truetype/lato/Lato-Heavy.ttf' if bold else '/usr/share/fonts/truetype/lato/Lato-Regular.ttf'),
                   ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    for path in candidates:
        if os.path.exists(path): return path
    raise RuntimeError('Fonts missing: install fonts-lato fonts-noto-core')

def font(text,size,bold=False): return ImageFont.truetype(font_path(text,bold),size)
def clamp(x,a=0,b=1): return max(a,min(b,x))
def ease(x): return 1-(1-clamp(x))**3
def appear(t,start,length=.55): return ease((t-start)/length)
def width(d,text,f): return d.textbbox((0,0),text,font=f)[2]
def wrap(d,text,max_width,f,max_lines=5):
    words=text.split()
    if not words: return ['']
    lines=[]; current=''
    for word in words:
        cand=(current+' '+word).strip()
        if width(d,cand,f)<=max_width or not current: current=cand
        else: lines.append(current); current=word
    if current: lines.append(current)
    return lines[:max_lines]
def center_text(d,text,y,size,bold=False,fill=DARK,max_w=625,line_height=None):
    f=font(text,size,bold); lines=wrap(d,text,max_w,f)
    line_height=line_height or int(size*1.20)
    for i,line in enumerate(lines):
        d.text(((W-width(d,line,f))/2,y+i*line_height),line,font=f,fill=fill)
    return y+len(lines)*line_height
def rounded(d,box,r,fill,outline=None,stroke=1):
    d.rounded_rectangle(tuple(map(int,box)),radius=r,fill=fill,outline=outline,width=stroke)

def decorative_bg():
    im=Image.new('RGB',(W,H),BG); d=ImageDraw.Draw(im)
    for x in range(18,W,28):
        for y in range(24,H,28):
            r=1.5
            d.ellipse((x-r,y-r,x+r,y+r),fill=(225,225,222))
    d.line((36,1152,W-36,1152),fill=(220,221,219),width=2)
    d.text((36,1174),'MOTION / 001',font=font('MOTION / 001',17,True),fill=GREY)
    d.text((W-134,1174),'STUDIO',font=font('STUDIO',17,True),fill=GREY)
    return im
BASE=decorative_bg()

def badge(im,x,y,text,accent=False):
    d=ImageDraw.Draw(im); f=font(text,18,True); tw=width(d,text,f)
    rounded(d,(x,y,x+tw+34,y+39),19,(28,29,31) if accent else (235,235,232))
    d.text((x+17,y+8),text,font=f,fill=(255,255,255) if accent else DARK)

def floating_panel(w,h,kind='analytics',title='YOUR IDEA'):
    p=Image.new('RGBA',(w,h),(0,0,0,0));d=ImageDraw.Draw(p)
    rounded(d,(4,4,w-4,h-4),24,(255,255,255,255),(220,221,219,255),2)
    rounded(d,(22,20,w-22,60),11,(245,246,245,255))
    d.ellipse((38,33,50,45),fill=ORANGE)
    d.text((63,29),title[:19],font=font(title,19,True),fill=DARK)
    for i in range(3): d.ellipse((w-88+i*20,34,w-80+i*20,42),fill=(195,197,196))
    if kind=='analytics':
        d.text((34,95),'Overview',font=font('Overview',26,True),fill=DARK)
        d.text((34,134),'INSIGHTS  /  LAST 7 DAYS',font=font('INSIGHTS',14,True),fill=GREY)
        for i,v in enumerate((.38,.53,.47,.78,.62,.87,.74)):
            x=38+i*51
            rounded(d,(x,290-v*135,x+24,291),7,ORANGE if i==5 else (202,205,205))
        d.line((34,312,w-34,312),fill=(231,231,228),width=2)
        for j,label in enumerate(('01   Discover','02   Design','03   Publish')):
            d.text((39,338+j*45),label,font=font(label,19,True),fill=DARK)
            rounded(d,(w-92,341+j*45,w-44,359+j*45),9,(224,238,226))
    elif kind=='phone':
        d.text((30,104),'Your next',font=font('Your next',35,True),fill=DARK)
        d.text((30,145),'big idea.',font=font('big idea.',38,True),fill=DARK)
        rounded(d,(30,218,w-30,360),20,(27,28,31))
        d.text((52,246),'CREATE',font=font('CREATE',19,True),fill=(255,255,255))
        d.text((52,286),'A better way',font=font('A better way',26,True),fill=(255,255,255))
        for j in range(4):
            y=393+j*58
            d.ellipse((30,y,56,y+26),fill=(239,238,232))
            rounded(d,(73,y+3,w-30,y+12),4,(215,216,212))
            rounded(d,(73,y+18,w-80-(j%2)*40,y+25),4,(232,232,231))
    elif kind=='workflow':
        for j,label in enumerate(('Discover','Structure','Animate','Export')):
            y=95+j*75
            rounded(d,(24,y,w-24,y+61),15,(246,246,245))
            d.ellipse((40,y+15,68,y+43),fill=ORANGE if j==2 else (229,230,228))
            d.text((85,y+16),label,font=font(label,24,True),fill=DARK)
            d.ellipse((w-58,y+23,w-46,y+35),fill=(124,196,137))
    else:
        d.text((32,100),'MAKE IT',font=font('MAKE IT',42,True),fill=DARK)
        d.text((32,153),'MOVE',font=font('MOVE',52,True),fill=ORANGE)
    return p

PANELS={
    'analytics':floating_panel(442,445,'analytics','INSIGHT PANEL'),
    'phone':floating_panel(310,675,'phone','STUDIO APP'),
    'workflow':floating_panel(440,435,'workflow','MOTION ENGINE'),
    'small':floating_panel(310,270,'small','CREATOR BOARD')
}

def paste_float(im,name,x,y,t,angle=0,scale=1):
    p=PANELS[name]
    p=p.resize((max(1,int(p.width*scale)),max(1,int(p.height*scale))),Image.Resampling.BICUBIC)
    if abs(angle)>.05: p=p.rotate(angle,expand=True,resample=Image.Resampling.BICUBIC)
    x,y=int(x-p.width/2),int(y-p.height/2)
    shadow=Image.new('RGBA',p.size,(0,0,0,0))
    shadow.putalpha(p.getchannel('A').point(lambda v:int(v*.24)))
    shadow=shadow.filter(ImageFilter.GaussianBlur(13))
    im.paste(shadow,(x+13,y+22),shadow)
    im.paste(p,(x,y),p)

def orange_sun(d,x,y,r=88):
    d.ellipse((x-r*.5,y-r*.5,x+r*.5,y+r*.5),fill=ORANGE)
    for a in range(0,360,45):
        rad=math.radians(a)
        d.line((x+math.cos(rad)*r*.74,y+math.sin(rad)*r*.74,
                x+math.cos(rad)*r*1.12,y+math.sin(rad)*r*1.12),fill=ORANGE,width=12)

def scene(im,topic,points,t,seconds):
    d=ImageDraw.Draw(im)
    part=t/(seconds/4)
    section=min(3,int(part)); q=part-section
    if section==0:
        badge(im,46,105,'THE BIG IDEA',True)
        pos=120+(1-appear(q,0,.22))*90
        orange_sun(d,575+12*math.sin(t*.85),230,65)
        h=center_text(d,topic.upper(),int(315+pos*.20),54,True,max_w=610,line_height=67)
        center_text(d,'Made to move.',int(h+20),29,False,GREY)
        a=appear(q,.17,.35)
        paste_float(im,'analytics',W/2-65,835+(1-a)*240,t,angle=-7+2*math.sin(t),scale=.86)
        paste_float(im,'small',525,970+(1-a)*270,t,angle=7+2*math.cos(t),scale=.65)
        badge(im,78,1050,'CLEAN  /  BOLD  /  3D')
    elif section==1:
        badge(im,47,105,'01 / THE PROCESS',True)
        d.text((52,204),'Make every',font=font('Make every',52,True),fill=DARK)
        d.text((52,267),'second count.',font=font('second count.',54,True),fill=DARK)
        a=appear(q,.04,.27)
        paste_float(im,'phone',340,715+(1-a)*310,t,angle=4*math.sin(t*1.3),scale=.98)
        d.ellipse((518,518,590,590),fill=(245,235,227))
        d.arc((522,522,586,586),20,315,fill=ORANGE,width=8)
        center_text(d,points[0],1096,25,True,GREY,max_w=630)
    elif section==2:
        badge(im,47,105,'02 / KEY IDEAS',True)
        center_text(d,'Less noise.',235,53,True)
        center_text(d,'More impact.',300,56,True,ORANGE)
        a=appear(q,.05,.3)
        paste_float(im,'workflow',365,750+(1-a)*255,t,angle=-3*math.sin(t),scale=1.22)
        center_text(d,points[1],1072,26,True,GREY,max_w=610)
    else:
        badge(im,47,105,'03 / TAKEAWAY',True)
        orange_sun(d,550,250,90)
        center_text(d,'THE NEXT',395,69,True)
        center_text(d,'LEVEL.',482,91,True,ORANGE)
        a=appear(q,0,.27)
        paste_float(im,'small',252,820+(1-a)*210,t,angle=-10+2*math.sin(t),scale=.86)
        paste_float(im,'analytics',497,895+(1-a)*270,t,angle=10-2*math.sin(t),scale=.70)
        center_text(d,points[2],1084,24,True,GREY,max_w=650)
    rounded(d,(36,1220,684,1225),2,(227,227,223))
    rounded(d,(36,1220,36+648*clamp(t/seconds),1225),2,ORANGE)

def narrate(topic,points,hi):
    if hi:
        return f'{topic}। हर अच्छी चीज़ की शुरुआत एक आइडिया से होती है। {points[0]}। {points[1]}। {points[2]}। छोटे बदलाव, और बेहतरीन अनुभव।'
    return f'{topic}. Great design starts with a clear idea. {points[0]}. {points[1]}. {points[2]}. Less noise. More impact. Make every second count.'

def get_audio(text,hi,path):
    try:
        import edge_tts
        voice='hi-IN-SwaraNeural' if hi else 'en-US-GuyNeural'
        asyncio.run(edge_tts.Communicate(text,voice=voice,rate='+5%').save(str(path)))
        return path.exists() and path.stat().st_size>1000
    except Exception as exc:
        print(f'Optional voice unavailable: {exc}',file=sys.stderr)
        return False

def audio_duration(path):
    try:
        raw=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],text=True)
        return float(raw.strip())
    except Exception: return 0

def render(args):
    topic=re.sub(r'\s+',' ',args.topic.strip())[:110] or 'BUILD SOMETHING BETTER'
    hi=bool(re.search(r'[\u0900-\u097f]',topic))
    defaults=['साफ़ सोच','बेहतर अनुभव','नई शुरुआत'] if hi else ['Clarity first','Focus on what matters','Make it memorable']
    points=(args.points.split('|') if args.points else defaults)
    points=[x.strip()[:72] for x in points if x.strip()][:3]
    while len(points)<3: points.append(defaults[len(points)])
    narration=narrate(topic,points,hi)
    (OUT/'narration.txt').write_text(narration,encoding='utf-8')
    voiced=(not args.no_voice) and get_audio(narration,hi,OUT/'voice.mp3')
    secs=args.seconds or (max(19,min(35,audio_duration(OUT/'voice.mp3')+1.3)) if voiced else 19)
    fps=args.fps
    frames=int(secs*fps)
    silent=OUT/'silent.mp4'
    ff=['ffmpeg','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24',
        '-video_size',f'{W}x{H}','-framerate',str(fps),'-i','pipe:0',
        '-an','-c:v','libx264','-preset','veryfast','-crf','19',
        '-vf','scale=1080:1920:flags=lanczos','-pix_fmt','yuv420p',
        '-movflags','+faststart',str(silent)]
    print('Rendering',frames,'frames,',secs,'seconds at',fps,'fps',flush=True)
    proc=subprocess.Popen(ff,stdin=subprocess.PIPE)
    try:
        for i in range(frames):
            im=BASE.copy()
            scene(im,topic,points,i/fps,secs)
            proc.stdin.write(im.tobytes())
            if i%max(1,fps*3)==0: print('Frame',i,'/',frames,flush=True)
    except BrokenPipeError:
        raise RuntimeError('FFmpeg stopped unexpectedly')
    finally:
        proc.stdin.close()
    if proc.wait(): raise RuntimeError('FFmpeg failed')
    video=OUT/'short.mp4'
    if voiced:
        subprocess.run(['ffmpeg','-loglevel','error','-y','-i',str(silent),
                        '-i',str(OUT/'voice.mp3'),'-filter_complex','[1:a]apad[a]',
                        '-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac',
                        '-t',str(secs),'-movflags','+faststart',str(video)],check=True)
    else:
        shutil.copy2(silent,video)
    print('DONE:',video,'voice=',voiced,'size=',video.stat().st_size,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--topic',default='Future of creative work')
    parser.add_argument('--points',default='',help='Three short ideas separated by |')
    parser.add_argument('--seconds',type=float,default=0)
    parser.add_argument('--fps',type=int,default=24)
    parser.add_argument('--no-voice',action='store_true')
    render(parser.parse_args())

#!/usr/bin/env python3
"""Mobile-first procedural 2.5D Short renderer. No paid AI key required."""
import argparse, asyncio, math, os, re, shutil, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BG=(247,247,245); DARK=(23,24,26); GREY=(104,106,111); ORANGE=(224,100,63); BORDER=(225,227,224)
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

def headline(d,text,y,maxsize=68,maxwidth=610):
    """Fit punchy headlines into 2-3 lines, retaining visual hierarchy."""
    size=maxsize
    while size>29:
        lines=wrap(d,text,maxwidth,font(text,size,True),5)
        if len(lines)<=3:break
        size-=4
    return center_text(d,text,y,size,True,max_w=maxwidth,line_height=int(size*1.13))

def animated_card(im,name,cx,cy,t,phase,angle=0,scale=1):
    p=appear(phase,.02,.22)
    paste_float(im,name,cx+10*math.sin(t*4.5),cy+(1-p)*250+7*math.sin(t*5),
                t,angle=angle+3*math.sin(t*3),scale=scale)

def scene(im,topic,points,t,seconds,timeline=None,captions=None):
    d=ImageDraw.Draw(im)
    timeline=timeline or [i*seconds/8 for i in range(9)]
    j=max(0,min(7,__import__('bisect').bisect_right(timeline,t)-1))
    start=timeline[j];span=max(.15,timeline[j+1]-start)
    q=clamp((t-start)/span)
    lift=(1-appear(q,0,.23))*100
    # Intro + 7 punchy shots; beat changes on each sentence.
    if j==0:
        badge(im,45,106,'DON’T BLINK',True)
        orange_sun(d,562,262+8*math.sin(t*4),65)
        headline(d,'ONE BIG IDEA',364+lift*.2,76)
        center_text(d,'in seconds, not minutes',528,27,False,GREY)
        animated_card(im,'analytics',330,862,t,q,angle=-9,scale=.92)
        animated_card(im,'small',565,945,t,q,angle=13,scale=.67)
    elif j==1:
        badge(im,45,106,'TODAY’S TOPIC',True)
        orange_sun(d,547,234,61)
        headline(d,topic.upper(),320+lift*.25,66)
        animated_card(im,'phone',347,837,t,q,angle=-4,scale=.96)
    elif j==2:
        badge(im,45,106,'THE PLAYBOOK',True)
        center_text(d,'3 MOVES.',250+lift*.2,82,True)
        center_text(d,'ZERO FLUFF.',352+lift*.2,57,True,ORANGE)
        for k,p in enumerate(points):
            y=520+k*144+(1-appear(q,.04+k*.12,.19))*65
            rounded(d,(48,y,670,y+116),20,(255,255,255),BORDER,2)
            d.ellipse((69,y+33,119,y+83),fill=ORANGE if k==0 else DARK)
            d.text((85,y+44),str(k+1),font=font('1',24,True),fill='white')
            for r,line in enumerate(wrap(d,p,485,font(p,28,True),2)):
                d.text((139,y+25+r*35),line,font=font(line,28,True),fill=DARK)
    elif j in [3,4,5]:
        k=j-3
        badge(im,45,106,'MOVE 0'+str(k+1),True)
        d.text((48,216),'0'+str(k+1),font=font('01',86,True),fill=ORANGE)
        headline(d,points[k].upper(),390+lift*.18,58)
        cardname=['workflow','analytics','phone'][k]
        animated_card(im,cardname,346,831,t,q,angle=[-6,6,-4][k],scale=[1.1,1.1,.9][k])
        orange_sun(d,575,248,35)
    elif j==6:
        badge(im,45,106,'THE DIFFERENCE',True)
        center_text(d,'LESS NOISE.',341+lift*.20,73,True)
        center_text(d,'MORE IMPACT.',442+lift*.20,69,True,ORANGE)
        animated_card(im,'workflow',290,848,t,q,angle=-10,scale=.91)
        animated_card(im,'analytics',524,896,t,q,angle=9,scale=.72)
    else:
        badge(im,45,106,'YOUR NEXT MOVE',True)
        orange_sun(d,545,253,81)
        center_text(d,'MAKE IT',381+lift*.20,84,True)
        center_text(d,'MEMORABLE.',494+lift*.20,69,True,ORANGE)
        animated_card(im,'small',237,840,t,q,angle=-10,scale=.89)
        animated_card(im,'analytics',500,866,t,q,angle=10,scale=.70)
    # Whip-style fast visual transition, without blowing up GPU usage.
    enter=1-appear(q,0,.09)
    if enter>.02:
        band_w=int(enter*800)
        d.polygon(((0,0),(band_w,0),(band_w-185,190),(0,290)),fill=DARK)
        d.polygon(((W-band_w,H),(W,H),(W,H-60),(W-band_w+140,H-270)),fill=ORANGE)
    rounded(d,(36,1220,684,1225),2,(227,227,223))
    rounded(d,(36,1220,36+648*clamp(t/seconds),1225),2,ORANGE)
    if captions:
        words=[x for x in captions if x[0]<=t]
        if words:
            idx=len(words)-1
            group=captions[(idx//4)*4:(idx//4+1)*4]
            text=' '.join(x[2] for x in group).upper()
            ft=font(text,25,True)
            while width(d,text,ft)>W-140 and len(text)>5:text=text[:-2]
            textwidth=width(d,text,ft);x=(W-textwidth)/2
            rounded(d,(x-16,1040,x+textwidth+16,1093),12,DARK)
            d.text((x,1052),text,font=ft,fill='white')

def narration_segments(topic,points):
    return ['Here is one idea worth your attention.',
            f'Let us talk about {topic}.',
            'Three quick moves. Zero fluff.',
            f'First, {points[0]}.',
            f'Next, {points[1]}.',
            f'Then, {points[2]}.',
            'Less noise. More impact.',
            'Make every second count.']

def get_audio(text,hi,path,voice='en-US-AndrewNeural',speed='+15%'):
    """Returns (success, word offsets in seconds). TTS endpoint is unofficial."""
    try:
        import edge_tts
        async def synth():
            boundaries=[]
            choice='hi-IN-SwaraNeural' if hi else voice
            c=edge_tts.Communicate(text,voice=choice,rate=speed,boundary='WordBoundary')
            with path.open('wb') as audio:
                async for msg in c.stream():
                    if msg['type']=='audio': audio.write(msg['data'])
                    elif msg['type']=='WordBoundary':
                        boundaries.append((msg['offset']/10000000,
                                          (msg['offset']+msg['duration'])/10000000,
                                          msg['text']))
            return boundaries
        offsets=asyncio.run(synth())
        return (path.exists() and path.stat().st_size>1000,offsets)
    except Exception as exc:
        print(f'Optional neural voice unavailable: {exc}',file=sys.stderr)
        return False, []

def scene_times(segments,word_times,secs):
    weights=[len(x.split()) for x in segments]
    total=sum(weights)
    if len(word_times)>int(total*.70):
        times=[0];pos=0
        for w in weights[:-1]:
            pos+=w
            times.append(word_times[min(len(word_times)-1,pos)][0])
        times.append(secs)
        if all(times[i+1]-times[i]>.4 for i in range(8)):
            return times
    times=[0];acc=0
    for w in weights:
        acc+=w
        times.append(secs*acc/total)
    return times

def audio_duration(path):
    try:
        raw=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],text=True)
        return float(raw.strip())
    except Exception: return 0

def render(args):
    topic=re.sub(r'\s+',' ',args.topic.strip())[:110] or 'BUILD SOMETHING BETTER'
    hi=bool(re.search(r'[\u0900-\u097f]',topic))
    defaults=['साफ़ सोच','बेहतर अनुभव','नई शुरुआत'] if hi else ['Read the details','Build with purpose','Make it memorable']
    points=(args.points.split('|') if args.points else defaults)
    points=[x.strip()[:72] for x in points if x.strip()][:3]
    while len(points)<3:points.append(defaults[len(points)])
    segments=narration_segments(topic,points)
    narration=' '.join(segments)
    (OUT/'narration.txt').write_text(narration,encoding='utf-8')
    voiced,word_times=(False,[]) if args.no_voice else get_audio(narration,hi,OUT/'voice.mp3',args.voice,args.speed)
    secs=args.seconds or ((audio_duration(OUT/'voice.mp3')+.5) if voiced else 19)
    if secs<4 or secs>80: secs=19
    times=scene_times(segments,word_times,secs)
    (OUT/'metadata.json').write_text(__import__('json').dumps(
        {'topic':topic,'points':points,'voice':args.voice,'speed':args.speed,
         'duration':secs,'voice_generated':voiced,'scenes':times},indent=2),encoding='utf-8')
    frames=int(secs*args.fps)
    raw_video=OUT/'silent.mp4'
    ff=['ffmpeg','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24',
        '-video_size',f'{W}x{H}','-framerate',str(args.fps),'-i','pipe:0',
        '-an','-c:v','libx264','-preset','veryfast','-crf','19',
        '-vf','scale=1080:1920:flags=lanczos','-pix_fmt','yuv420p',
        '-movflags','+faststart',str(raw_video)]
    print(f'V2: {secs:.1f} seconds, 8 fast scenes, voice={voiced}, words={len(word_times)}',flush=True)
    proc=subprocess.Popen(ff,stdin=subprocess.PIPE)
    try:
        for i in range(frames):
            im=BASE.copy()
            scene(im,topic,points,i/args.fps,secs,times,word_times if voiced else None)
            proc.stdin.write(im.tobytes())
            if i%max(1,args.fps*4)==0:print(f'{i}/{frames}',flush=True)
    except BrokenPipeError:
        raise RuntimeError('FFmpeg stopped while encoding')
    finally:
        proc.stdin.close()
    if proc.wait():raise RuntimeError('FFmpeg encoder failed')
    video=OUT/'short.mp4'
    if voiced:
        subprocess.run(['ffmpeg','-loglevel','error','-y','-i',str(raw_video),
                        '-i',str(OUT/'voice.mp3'),'-map','0:v:0','-map','1:a:0','-c:v','copy',
                        '-c:a','aac','-b:a','128k','-t',str(secs),
                        '-movflags','+faststart',str(video)],check=True)
    else:shutil.copy2(raw_video,video)
    print('DONE:',video,'voice=',voiced,'size=',video.stat().st_size,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--topic',default='Three coding habits that matter')
    parser.add_argument('--points',default='Read the error first|Test one thing at a time|Ship smaller changes')
    parser.add_argument('--seconds',type=float,default=0)
    parser.add_argument('--fps',type=int,default=24)
    parser.add_argument('--voice',choices=['en-US-AndrewNeural','en-US-BrianNeural','en-US-EmmaNeural'],
                        default='en-US-AndrewNeural')
    parser.add_argument('--speed',choices=['+8%','+15%','+22%','+28%'],default='+15%')
    parser.add_argument('--no-voice',action='store_true')
    render(parser.parse_args())

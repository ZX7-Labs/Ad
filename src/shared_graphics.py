"""Open-source AD Studio drawing utilities. MIT-licensed project code."""
import re,os
from PIL import ImageFont

def font_path(text,bold=False):
    paths=[]
    if re.search(r'[\u0900-\u097f]',text):
        paths += ['/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf' if bold else '/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf']
    paths += ['/usr/share/fonts/truetype/lato/Lato-Heavy.ttf' if bold else '/usr/share/fonts/truetype/lato/Lato-Regular.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for candidate in paths:
        if os.path.exists(candidate):return candidate
    raise RuntimeError('Install Lato or Noto fonts')
def font(text,size,bold=False):return ImageFont.truetype(font_path(str(text),bold),size)
def clamp(x,a=0,b=1):return max(a,min(b,x))
def ease(x):return 1-(1-clamp(x))**3
def appear(t,start,length=.55):return ease((t-start)/max(length,1e-6))
def width(d,text,f):return d.textbbox((0,0),str(text),font=f)[2]
def wrap(d,text,max_width,f,max_lines=5):
    words=str(text).split()
    if not words:return ['']
    lines=[];current=''
    for word in words:
        cand=(current+' '+word).strip()
        if width(d,cand,f)<=max_width or not current:current=cand
        else:lines.append(current);current=word
    if current:lines.append(current)
    return lines[:max_lines]
def rounded(d,box,r,fill,outline=None,stroke=1):
    d.rounded_rectangle(tuple(map(int,box)),radius=r,fill=fill,outline=outline,width=stroke)

"""Original short film regression: actual PIXELS→MediaVault→BODY→MP4→verify.

The design is original programmatic graphics and original synthesized PCM;
no external footage, unlicensed sound, actors or hallucinated image model.
A constrained example only; not proof that professional BODY is complete.
"""
import argparse
import json
import math
import subprocess
import wave
from pathlib import Path

from .body_integration import run_body_project
from .media_vault import MediaVault,sha256_file
from .production_qc import full_decode_inspection

W,H,FPS,DURATION=640,360,24,11.0


def render(original_path):
    from PIL import Image,ImageDraw,ImageFont
    import numpy as np
    root=Path(original_path).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError("Never rewrite a previously rendered studio film")
    root.mkdir(parents=True,exist_ok=True)
    vault=MediaVault(root/"vault")
    font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    bold=lambda size:ImageFont.truetype(font,size)

    def graphic(name,title,subtitle,which):
        base=Image.new("RGBA",(W,H),(0,0,0,0))
        d=ImageDraw.Draw(base,"RGBA")
        if which=="base":
            for y in range(H):
                r=int(8+12*(1-y/H));g=int(14+17*(1-y/H))
                d.line((0,y,W,y),fill=(r,g,37,255),width=1)
            for x in range(0,W,52):
                d.line((x,0,x,H),fill=(104,157,174,14))
            for y in range(0,H,52):
                d.line((0,y,W,y),fill=(104,157,174,14))
        elif which=="gold":
            for i in range(12):
                edge=17*i
                d.arc((265-edge,43-edge,530+edge,308+edge),22,303,
                      fill=(246,194,112,max(20,190-i*13)),width=2)
            d.line((343,293,536,100),fill=(255,205,132,190),width=3)
        elif which=="cyan":
            for i in range(11):
                edge=12*i
                d.rounded_rectangle((347-edge,80-edge,533+edge,263+edge),
                    radius=10,outline=(70,220,216,max(12,170-i*13)),width=2)
        elif which=="closing":
            for i in range(10):
                d.arc((220-i*17,45-i*11,550+i*18,320+i*12),202,337,
                      fill=(250,191,106,max(18,185-i*15)),width=2)
        if title:
            d.text((46,119),title,font=bold(45),fill=(244,245,239,255))
            d.text((47,177),subtitle,font=bold(40),
                   fill=(102,236,222,255) if which=="cyan" else
                        (245,191,110,255))
            d.rectangle((49,251,112,254),fill=(246,194,112,255))
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);base.save(p)
        return p

    media=[
        graphic("night.png","","","base"),
        graphic("gold.png","","","gold"),
        graphic("first.png","EVERY IDEA","BEGINS SMALL.","title"),
        graphic("cyan.png","","","cyan"),
        graphic("second.png","A LINE","BECOMES MOTION.","cyan"),
        graphic("closing.png","","","closing"),
        graphic("final.png","IDEAS FIND","THEIR FORM.","title")]

    rate=48000
    time=np.arange(int(DURATION*rate))/rate
    audio=np.zeros(len(time),dtype=np.float64)
    for hz in (110,164.8,196,261.6):
        audio+=.043*(np.sin(2*np.pi*hz*time)+.28*np.sin(4*np.pi*hz*time))
    for start,hz in ((.6,329),(1.7,392),(2.8,440),(4.1,494),
                     (5.2,587),(6.3,659),(7.8,587),(9.2,784)):
        relative=time-start
        m=(relative>=0)&(relative<.9)
        t=relative[m]
        audio[m]+=.2*(1-np.exp(-t*35))*np.exp(-t*5)*np.sin(2*np.pi*hz*t)
    envelope=np.clip(np.minimum(time/.7,(DURATION-time)/1.1),0,1)
    audio=np.clip(audio*envelope,-.95,.95)
    stereo=np.stack((audio,np.roll(audio,43)*.97),axis=-1)
    song=root/"original-stereo-score.wav"
    with wave.open(str(song),"wb") as stream:
        stream.setnchannels(2);stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes((stereo*32767).astype("<i2").tobytes())

    refs={}
    for path in (*media,song):
        refs[path.name]=vault.ingest(path,
            mime="audio/wav" if path.suffix==".wav" else "image/png",
            rights="generated_original",source_type="trusted_renderer",
            source_id="independent-body-source-20261023",
            evidence="Original procedural pixels and additive PCM, physically generated",
            owner_or_generator="ZX7 original motion proof")
    def visual(name,key,start,length,fade=.45):
        r=refs[name]
        return {"id":key,"source":name,"asset_id":r["asset_id"],
                "attestation_id":r["attestation_id"],
                "source_kind":"still_image","source_in":0,
                "start":start,"duration":length,
                "x":0,"y":0,"width":W,"height":H,"opacity":1,
                "fade_in_seconds":min(fade,length/3),
                "fade_out_seconds":min(fade,length/3)}
    images=[
        visual("night.png","scene-foundation",0,DURATION,.1),
        visual("gold.png","geometry-intro",0,3.7),
        visual("first.png","words-intro",.55,3.2),
        visual("cyan.png","geometry-evolution",3.3,4),
        visual("second.png","words-evolution",3.9,3.4),
        visual("closing.png","geometry-outro",7.2,3.7),
        visual("final.png","words-outro",7.65,3.3)]
    # Director-authored staggered parallax. Actual frames are moved by the
    # installed compositor; the artist's typography stays legible.
    for index,initial,final,span in (
        (1,(-18,-5),(15,10),3.5),
        (3,(14,8),(-25,-5),3.8),
        (5,(-14,6),(22,-12),3.6)):
        images[index]["motion"]=[
            {"at_seconds":0,"x":initial[0],"y":initial[1]},
            {"at_seconds":span,"x":final[0],"y":final[1]}]
    sound=refs[song.name]
    plan={"canvas":{"width":W,"height":H,"fps":FPS,
           "duration":DURATION,"background":"#081025"},
          "video_layers":images,"audio_tracks":[{
          "id":"original-stereo-score","source":song.name,
          "asset_id":sound["asset_id"],"attestation_id":sound["attestation_id"],
          "start":0,"source_in":0,"duration":DURATION,"gain_db":-3.0}]}
    (root/"original-editor-plan.json").write_text(json.dumps(plan,indent=2))
    ir={"project":{"creative_intent":
        "A poetic geometric idea develops through motion and sound, no stock media"},
        "shots":[{"id":"idea","purpose":"The first signal","duration_seconds":3.7},
                 {"id":"motion","purpose":"Signal finds structure","duration_seconds":3.6},
                 {"id":"form","purpose":"Motion becomes form","duration_seconds":3.7}],
        "assets":[],"tool_graph":[
         {"id":"film","tool_id":"body.composite_mix",
          "purpose":"Real seven-layer artistic composition and original authored audio",
          "inputs":{"plan":"original-editor-plan.json","out":"zx7-body-original-film.mp4"},
          "depends_on":[]},
         {"id":"decode","tool_id":"body.full_decode",
          "purpose":"Check entire video and soundtrack, not metadata-only",
          "inputs":{"source":"zx7-body-original-film.mp4",
                    "expected":{"width":W,"height":H,"require_audio":True}},
          "depends_on":["film"]},
         {"id":"custody","tool_id":"body.asset_vault",
          "purpose":"Authorize only actual verified registered BODY output",
          "inputs":{"source_witness":{"$node_output":"film"}},
          "depends_on":["film"]}]}
    (root/"original-film-graph.json").write_text(json.dumps(ir,indent=2))
    first=run_body_project(ir,root)
    if first.get("status")!="all_tool_results_verified":
        raise RuntimeError("Real BODY graph blocked: "+str(first.get("errors")))
    movie=root/"zx7-body-original-film.mp4"
    digest=sha256_file(movie)
    second=run_body_project(ir,root)
    if second.get("status")!="all_tool_results_verified" or sha256_file(movie)!=digest:
        raise RuntimeError("Real film did not survive verified graph recovery")
    qc=full_decode_inspection(movie,expected={
        "width":W,"height":H,"require_audio":True})
    if not qc["technical_delivery_verified"]:
        raise RuntimeError("Entire original film does not actually decode")
    stored=vault.inspect(digest)
    if not any(row["source_type"]=="trusted_renderer"
               for row in stored["rights_attestations"]):
        raise RuntimeError("Physical generated-master provenance not established")
    frames=[]
    for stamp in (1.4,5.1,9.0):
        image=root/("view-%02d.png"%int(stamp*10))
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
          "-ss",str(stamp),"-i",str(movie),"-frames:v","1",str(image)],
          check=True,timeout=40)
        frames.append(image.name)
    evidence={"movie":movie.name,"sha256":digest,"duration_seconds":DURATION,
        "video_layers":len(images),"soundtrack_original":True,
        "fully_decoded":True,"media_vault_custody_verified":True,
        "graph_reused":second.get("reused",[]),
        "independent_human_artistic_acceptance":False,
        "whole_universal_studio_complete":False,"review_images":frames}
    (root/"actual-film-evidence.json").write_text(json.dumps(evidence,indent=2))
    return evidence


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    args=p.parse_args()
    print(json.dumps(render(args.out),indent=2))


if __name__=="__main__":main()

"""Native CGI + actual tracked, occluded, sound-preserving VFX acceptance.

This is an explicit original test commission, never a renderer preset or a
creative-brain result. Run after installing Blender, FFmpeg, Inkscape and
.[production,vfx_tracking]. No inference provider, account or payment needed.
"""
from pathlib import Path
import argparse,json,math,os,subprocess,wave
from .body_integration import body_catalog,run_body_project
from .body_document_schemas import validate_document
from .media_vault import MediaVault,sha256_file

def run(workspace,size=512,frames=36,samples=24):
    import cv2,numpy as np
    root=Path(workspace).resolve();root.mkdir(parents=True,exist_ok=True)
    if hasattr(os,'sched_setaffinity'):os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
    def save(name,obj):
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2));return p
    def ref(name,mime):
        v=MediaVault(root/'vault');p=root/name;h=sha256_file(p)
        try:r=v.inspect(h);att=r['rights_attestations'][0]['attestation_id']
        except ValueError:
            r=v.ingest(p,mime=mime,rights='owner_supplied',source_type='owner_upload',source_id='original-cgi-vfx-test-commission',
                evidence='Original deterministic technical test art/photographic-free assets and original authored geometry, noise texture, foreground masks and PCM; not client footage',owner_or_generator='ZX7 native acceptance fixture author');att=r['attestation_id']
        return {'source':name,'asset_id':h,'attestation_id':att}
    cat=body_catalog(root)
    art=root/'art';art.mkdir(exist_ok=True)
    assets={
      'label':('<rect width="512" height="512" fill="#F5EEDC"/><rect x="22" y="22" width="468" height="468" fill="none" stroke="#9B7338" stroke-width="5"/><text x="256" y="178" text-anchor="middle" font-family="DejaVu Sans" font-size="74" letter-spacing="7" fill="#263D32">AURA</text><path d="M150 225H362" stroke="#9B7338" stroke-width="3"/><text x="256" y="290" text-anchor="middle" font-family="DejaVu Sans" font-size="31" fill="#263D32">ESSENCE / 01</text><text x="256" y="402" text-anchor="middle" font-family="DejaVu Sans" font-size="22" fill="#5A5A50">ORIGINAL CGI TEST</text>',512,512),
      'roughness':('<rect width="128" height="128" fill="#505050"/>'+''.join(f'<rect x="{i}" width="1" height="128" fill="#555555"/>' for i in range(0,128,3)),128,128),
      'normal':('<rect width="16" height="16" fill="#8080FF"/>',16,16),
      'environment':('<defs><linearGradient id="light"><stop stop-color="#252D32"/><stop offset=".32" stop-color="#5E6766"/><stop offset=".45" stop-color="#DBD4C1"/><stop offset=".52" stop-color="#4C554F"/><stop offset="1" stop-color="#171E23"/></linearGradient></defs><rect width="512" height="256" fill="url(#light)"/>',512,256)}
    cgi_assets=[]
    for name,(body,w,h) in assets.items():
        svg=art/(name+'.svg');svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{body}</svg>')
        out='art/'+name+'.png'
        if not (root/out).exists():cat.invoke('body.vector_png',{'source_svg':'art/'+name+'.svg','out':out,'width':w,'height':h},allowed_access={'write'})
        cgi_assets.append({'name':name+'.png','media':ref(out,'image/png')})
    base={'material':'glass','location':[0,0,0],'rotation_degrees':[0,0,0],'scale':[1,1,1]}
    profile=[[.51,.12],[.62,.17],[.65,.25],[.65,1.75],[.61,1.9],[.31,2.08],[.27,2.16],[.27,2.38]]
    vertices=[];faces=[];uv=[];segments=24
    for z in [.52,1.55]:
        for i in range(segments+1):
            a=-math.pi/2-.76+1.52*i/segments;vertices.append([.665*math.cos(a),.665*math.sin(a),z])
    for i in range(segments):
        faces.append([i,i+1,segments+2+i,segments+1+i]);uv.append([[i/segments,0],[(i+1)/segments,0],[(i+1)/segments,1],[i/segments,1]])
    shot={'shot_id':'owned-product-pbr-camera-proof','width':size,'height':size,'fps':18,'frames':frames,'samples':samples,'denoise':True,
      'world':{'color':[.2,.2,.2],'strength':.3,'environment_texture':'environment.png','environment_rotation_degrees':25},
      'camera':{'location':[3.5,-6.3,3.0],'target':[0,0,1.25],'lens_mm':54,
          'animate_location':[{'frame':1,'value':[3.5,-6.3,3.0]},{'frame':frames,'value':[2.5,-6.1,2.7]}],
          'animate_lens_mm':[{'frame':1,'value':[54]},{'frame':frames,'value':[58]}],
          'depth_of_field':{'focus_distance':7,'fstop':7},
          'animate_focus_distance':[{'frame':1,'value':[7]},{'frame':frames,'value':[6.4]}]},
      'materials':[
        {'id':'glass','color':[.9,.96,.92,1],'metallic':0,'roughness':.055,'transmission':1,'ior':1.46,'coat':.22},
        {'id':'liquid','color':[.69,.3,.055,1],'metallic':0,'roughness':.06,'transmission':.65,'ior':1.33},
        {'id':'cap','color':[.27,.21,.12,1],'metallic':.88,'roughness':.25,'coat':.3,'roughness_texture':'roughness.png','normal_texture':'normal.png','normal_strength':.2},
        {'id':'label','color':[1,1,1,1],'metallic':0,'roughness':.6,'base_color_texture':'label.png'},
        {'id':'ground','color':[.07,.12,.1,1],'metallic':.15,'roughness':.32}],
      'objects':[
        {**base,'id':'product-rig','type':'empty','animate':{'rotation_degrees':[{'frame':1,'value':[0,0,-9]},{'frame':frames,'value':[0,0,9]}]},'interpolation':'LINEAR'},
        {**base,'id':'bottle','type':'lathe','profile':profile,'segments':96,'caps':True,'parent':'product-rig','modifiers':[{'kind':'solidify','thickness':.035,'offset':-1}]},
        {**base,'id':'liquid-fill','material':'liquid','type':'lathe','profile':[[.48,.21],[.59,.27],[.59,1.65]],'segments':96,'caps':True,'parent':'product-rig'},
        {**base,'id':'textured-label','material':'label','type':'custom_mesh','vertices':vertices,'faces':faces,'uvs':uv,'parent':'product-rig'},
        {**base,'id':'cap','material':'cap','type':'cylinder','location':[0,0,2.49],'scale':[.31,.31,.15],'parent':'product-rig','modifiers':[{'kind':'bevel','width':.055,'segments':4,'angle_degrees':30}]},
        {**base,'id':'floor','material':'ground','type':'plane','location':[0,0,.08],'scale':[200,200,200]}],
      'lights':[
        {'id':'key-strip','type':'AREA','location':[-3,-4,5],'rotation_degrees':[24,-28,0],'energy':700,'color':[1,.91,.77],'shape':'RECTANGLE','size':1.6,'size_y':5},
        {'id':'rim-strip','type':'AREA','location':[3,1,4],'rotation_degrees':[-20,30,0],'energy':900,'color':[.8,.91,1],'shape':'RECTANGLE','size':1.2,'size_y':4}]}
    plan={'scene':shot,'assets':cgi_assets};validate_document('body.cgi_shot',plan);save('cgi-plan.json',plan)
    graph={'project':{'creative_intent':'Original source-attested CGI execution acceptance, not an autonomous director or a finished customer ad'},
      'shots':[{'id':'cgi-proof','purpose':'Actually render glass, UV label, radial geometry, normal/roughness maps, parent motion, lens and focus','duration_seconds':frames/18}],
      'assets':[],'tool_graph':[
        {'id':'cgi','tool_id':'body.cgi_shot','purpose':'Real native CGI render','inputs':{'plan':'cgi-plan.json','out':'product-cgi.mp4'},'depends_on':[]},
        {'id':'cgi-check','tool_id':'body.full_decode','purpose':'Decode actual whole movie','inputs':{'source':'product-cgi.mp4','expected':{'width':size,'height':size,'duration_seconds':frames/18}},'depends_on':['cgi']},
        {'id':'cgi-vault','tool_id':'body.asset_vault','purpose':'Actual rendered-source custody','inputs':{'source_witness':{'$node_output':'cgi'}},'depends_on':['cgi']}]}
    result=run_body_project(graph,root);save('cgi-receipt.json',result)
    if result['status']!='all_tool_results_verified':raise RuntimeError(result)
    print('CGI_NATIVE_COMPLETE',flush=True)
    # Perspective reference footage uses independently projected 3D geometry,
    # partial foreground occlusion, and original audible PCM. Tracking must
    # recover motion from image features, not read this ground-truth trajectory.
    from .test_cgi_tracking import projected_frames,SETTINGS
    original,quads=projected_frames(24);source_dir=root/'tracking-source';source_dir.mkdir(exist_ok=True)
    for i,frame in enumerate(original):
        mask=np.zeros(frame.shape[:2],np.uint8);mask[165:195,125+i:155+i]=255
        frame[mask>0]=[130,70,25]
        cv2.imwrite(str(source_dir/f'f{i:03}.png'),frame);cv2.imwrite(str(source_dir/f'm{i:03}.png'),mask)
    with wave.open(str(root/'tone.wav'),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);t=np.arange(96000)/48000;w.writeframes((np.sin(2*np.pi*330*t)*3000).astype('<i2').tobytes())
    common=['-c:v','libx264','-crf','15','-pix_fmt','yuv420p','-vf','scale=in_range=full:out_range=tv:out_color_matrix=bt709','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709']
    if not (root/'tracking-source.mp4').exists():subprocess.run(['ffmpeg','-v','error','-framerate','12','-i',str(source_dir/'f%03d.png'),'-i',str(root/'tone.wav'),*common,'-c:a','aac','-n',str(root/'tracking-source.mp4')],check=True)
    if not (root/'foreground.mp4').exists():subprocess.run(['ffmpeg','-v','error','-framerate','12','-i',str(source_dir/'m%03d.png'),*common,'-an','-n',str(root/'foreground.mp4')],check=True)
    planar={'media':ref('tracking-source.mp4','video/mp4'),'overlay':ref('art/label.png','image/png'),
      'quad':quads[0].tolist(),'opacity':.85,'audio':'preserve_source','tracking':SETTINGS,
      'foreground':{'media':ref('foreground.mp4','video/mp4'),'kind':'video'}}
    validate_document('body.planar_insert',planar);save('planar-plan.json',planar)
    graph['shots']=[{'id':'tracking-proof','purpose':'Actual tracking, corner-pin, foreground protection and preserved original sound','duration_seconds':2}]
    graph['tool_graph']=[{'id':'track','tool_id':'body.planar_insert','purpose':'Actually track and composite every source frame','inputs':{'plan':'planar-plan.json','out':'tracked-vfx.mp4'},'depends_on':[]},
      {'id':'track-check','tool_id':'body.full_decode','purpose':'Verify complete tracked movie and original soundtrack','inputs':{'source':'tracked-vfx.mp4','expected':{'width':320,'height':240,'duration_seconds':2,'require_audio':True}},'depends_on':['track']},
      {'id':'track-vault','tool_id':'body.asset_vault','purpose':'Actual native tracked output custody','inputs':{'source_witness':{'$node_output':'track'}},'depends_on':['track']}]
    result=run_body_project(graph,root);save('tracking-receipt.json',result)
    if result['status']!='all_tool_results_verified':raise RuntimeError(result)
    def pcm(name):return subprocess.check_output(['ffmpeg','-v','error','-i',str(root/name),'-vn','-f','s16le','-'])
    assert pcm('tracking-source.mp4')==pcm('tracked-vfx.mp4'),'Original sound changed'
    manifest={'cgi_sha256':sha256_file(root/'product-cgi.mp4'),'tracked_vfx_sha256':sha256_file(root/'tracked-vfx.mp4'),
      'actual_cgi_frames':frames,'actual_tracked_frames':24,'original_audio_decoded_pcm_identical':True,
      'human_acting_generation_proven':False,'general_3d_camera_tracking_proven':False,'autonomous_creative_brain_used':False,
      'proof_scope':'Actual native CGI and planar VFX execution, not world-class artistic approval'}
    save('native-proof.json',manifest);print(json.dumps(manifest,indent=2),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--size',type=int,default=512);p.add_argument('--frames',type=int,default=36);p.add_argument('--samples',type=int,default=24);a=p.parse_args();run(a.workspace,a.size,a.frames,a.samples)
if __name__=='__main__':main()

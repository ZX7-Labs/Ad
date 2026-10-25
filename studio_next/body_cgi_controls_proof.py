"""Real native CGI-control acceptance, NOT a premium-film or neural-brain demo.

Original technical commissions exercise the public BODY graph and trusted
Blender entry point. Rendered pixels, solver poses and exact reuse are checked.
"""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess

from .blender_scene import validate_blender_shot
from .body_document_schemas import validate_document
from .body_integration import run_body_project
from .media_vault import sha256_file
from .body_render_compare import compare_native_rgb


def run(workspace,*,size=160,samples=12):
    import numpy as np
    from PIL import Image
    root=Path(workspace).resolve();root.mkdir(parents=True,exist_ok=True)
    if hasattr(os,'sched_setaffinity'):
        os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
    def save(name,value):
        p=root/name;p.write_text(json.dumps(value,indent=2)+'\n');return p
    shot=json.loads((Path(__file__).parent/'fixtures/advanced_cgi_physics_shot.json').read_text())
    shot.update(width=size,height=size,samples=samples)
    plan={'scene':shot,'assets':[]};validate_document('body.cgi_shot',plan)
    save('plan.json',plan)
    graph={'project':{'creative_intent':'Original CGI physical-control technical acceptance; no artistic quality claim'},
        'shots':[{'id':'physical-controls','purpose':'Native PBR, microdetail, optics and Bullet collisions','duration_seconds':1}],
        'assets':[],'tool_graph':[
            {'id':'cgi','tool_id':'body.cgi_shot','purpose':'Original controlled physical CGI','inputs':{'plan':'plan.json','out':'controls.mp4'},'depends_on':[]},
            {'id':'decode','tool_id':'body.full_decode','purpose':'Decode every original frame','inputs':{'source':'controls.mp4','expected':{'width':size,'height':size,'duration_seconds':1}},'depends_on':['cgi']},
            {'id':'vault','tool_id':'body.asset_vault','purpose':'Native producer lineage','inputs':{'source_witness':{'$node_output':'cgi'}},'depends_on':['cgi']}]}
    save('graph.json',graph);first=run_body_project(graph,root);save('graph-result.json',first)
    if first['status']!='all_tool_results_verified':raise RuntimeError(first)
    with sqlite3.connect(root/'production.sqlite3') as db:
        native=json.loads(db.execute('SELECT output_json FROM node_results WHERE project_key=? AND node_id=?',
            (first['project_key'],'cgi')).fetchone()[0])
    report=native['native_controls'];save('native-control-report.json',report)
    positions=report['physics']['positions']['ball']
    assert positions[0]['location'][2]-positions[-1]['location'][2]>1
    assert .37<positions[-1]['location'][2]<.44,'Sphere did not settle on the real collider'
    assert report['procedural_materials']==['metal'] and report['volume_materials']==['glass']
    assert report['motion_blur_enabled'] and report['bounces']['transmission_bounces']==6
    assert report['camera']['focus_object']=='ball' and report['camera']['aperture_blades']==7
    assert abs(report['camera']['aperture_ratio']-1.1)<.00001
    assert report['animated_materials']==['metal'] and report['animated_lights']==[shot['lights'][0]['id']]
    before=sha256_file(root/'controls.mp4');stat=(root/'controls.mp4').stat().st_mtime_ns
    again=run_body_project(graph,root);save('graph-reuse.json',again)
    assert set(again['reused'])=={'cgi','decode','vault'} and all(t['state']=='reused' for t in again['trace']),again
    assert before==sha256_file(root/'controls.mp4') and stat==(root/'controls.mp4').stat().st_mtime_ns

    def render(name,s,first=None,last=None):
        validate_blender_shot(s);scene_path=save(name+'.json',s);out=root/name
        cmd=['blender','-b','-t','4','--factory-startup','--python-exit-code','1',
             '--python',str(Path(__file__).parent/'blender_scene.py'),'--','--scene',str(scene_path),'--out',str(out)]
        if first is not None:cmd+=['--frame-start',str(first),'--frame-end',str(last)]
        with (root/(name+'.log')).open('w') as log:subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        return out
    full=render('whole-clock',shot)
    subset=render('resumed-clock',shot,6,6)
    def pixels(path):return np.asarray(Image.open(path).convert('RGB'),dtype=np.float64)
    comparison=compare_native_rgb(full/'frame_0006.png',subset/'frame_0006.png')
    assert comparison['within_quantization_tolerance'], 'Frame-range resume changed actual picture beyond sparse one-code-value roundoff: '+str(comparison)
    assert json.loads((subset/'render-report.json').read_text())['physics']==report['physics']

    neutral=copy.deepcopy(shot);neutral.pop('physics')
    for obj in neutral['objects']:obj.pop('rigid_body',None)
    neutral['materials'][1]['volume']['absorption']['density']=0
    neutral['materials'][1]['volume']['scatter']['density']=0
    colored=copy.deepcopy(neutral)
    colored['materials'][1]['volume']=copy.deepcopy(shot['materials'][1]['volume'])
    a=render('clear-volume',neutral,1,1);b=render('colored-volume',colored,1,1)
    volume_difference=float(np.abs(pixels(a/'frame_0001.png')-pixels(b/'frame_0001.png')).mean())
    assert volume_difference>.05, 'Volume control has no measured effect on real pixels'
    no_detail=copy.deepcopy(colored);no_detail['materials'][0].pop('surface_noise')
    c=render('plain-surface',no_detail,1,1)
    detail_difference=float(np.abs(pixels(c/'frame_0001.png')-pixels(b/'frame_0001.png')).mean())
    assert detail_difference>.05, 'Surface detail control has no measured effect on real pixels'

    # Independent controlled experiment: a self-lit object traverses the lens.
    # The shutter must change its actual image support, not only a JSON flag.
    shutter=copy.deepcopy(shot);shutter.pop('physics')
    shutter.update(shot_id='original-shutter-experiment',frames=3,samples=max(16,samples),denoise=False)
    shutter['render_settings']={'seed':421,'view_transform':'Standard','max_bounces':2}
    shutter['world']={'color':[0,0,0],'strength':0}
    shutter['camera']={'location':[0,-6,0],'target':[0,0,0],'lens_mm':45}
    shutter['materials']=[{'id':'signal','color':[1,1,1,1],'metallic':0,'roughness':1,'emission_color':[1,1,1],'emission_strength':1}]
    shutter['objects']=[{'id':'moving-signal','type':'uv_sphere','material':'signal','location':[-1.2,0,0],
        'rotation_degrees':[0,0,0],'scale':[.15,.15,.15],'interpolation':'LINEAR',
        'animate':{'location':[{'frame':1,'value':[-1.2,0,0]},{'frame':3,'value':[1.2,0,0]}]}}]
    for light in shutter['lights']:
        light['energy']=0
        for key in ('animate','animate_energy','animate_color'):light.pop(key,None)
    clean=render('shutter-closed',shutter,2,2)
    shutter['render_settings']['motion_blur']={'shutter':1,'position':'CENTER'}
    blurred=render('shutter-open',shutter,2,2)
    def support(p):
        columns=np.flatnonzero((pixels(p).max(axis=2)>20).any(axis=0))
        assert len(columns)>0
        return int(columns[-1]-columns[0]+1)
    gain=support(blurred/'frame_0002.png')-support(clean/'frame_0002.png')
    assert gain>2, 'Physical shutter did not broaden actual moving-object image'
    proof={'all_checks_passed':True,'public_body_cgi_graph':True,'full_mp4_decode':True,
        'native_renderer_version':report['blender_version'],'original_cgi_frames':12,
        'actual_dynamic_body_settled_on_collider':True,'original_clock_subset_pixels_identical':comparison['pixels_identical'],
        'original_clock_subset_physics_identical':True,'original_clock_subset_picture_within_quantization_tolerance':True,
        'original_clock_subset_picture_comparison':comparison,
        'all_three_dag_nodes_reused_without_render':True,'volume_control_mean_pixel_difference':volume_difference,
        'surface_detail_mean_pixel_difference':detail_difference,'motion_blur_support_gain_pixels':gain,
        'movie_sha256':before,'live_creative_model_used':False,'premium_artist_approval':False}
    save('controls-proof.json',proof)
    return proof


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True)
    p.add_argument('--size',type=int,default=160);p.add_argument('--samples',type=int,default=12)
    a=p.parse_args();print(json.dumps(run(a.workspace,size=a.size,samples=a.samples),indent=2))


if __name__=='__main__':main()

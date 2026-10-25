"""Original cloth, mesh-morph and liquid technical commissions; no creative LLM.

Uses public BODY graph render/decode/custody and trusted native frame ranges.
Liquid acceptance is mandatory by default and needs verified Blender 4.5+.
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


def run(workspace,*,size=128,samples=6,include_liquid=True):
    import numpy as np
    from PIL import Image
    root=Path(workspace).resolve();root.mkdir(parents=True,exist_ok=True)
    if hasattr(os,'sched_setaffinity'):os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
    def save(name,value):
        p=root/name;p.write_text(json.dumps(value,indent=2)+'\n');return p
    scenes={}
    names={'cloth':'cloth_drape_shot.json','morph':'mesh_morph_shot.json'}
    if include_liquid:names['liquid']='liquid_impact_shot.json'
    graph={'project':{'creative_intent':'Original technical cloth/morph/liquid acceptance; no premium-film or model-brain claim'},'assets':[],'shots':[],'tool_graph':[]}
    for name,fixture in names.items():
        scene=json.loads((Path(__file__).parent/'fixtures'/fixture).read_text());scene.update(width=size,height=size,samples=samples)
        scenes[name]=scene;plan={'scene':scene,'assets':[]};validate_document('body.cgi_shot',plan);save(name+'-plan.json',plan)
        graph['shots'].append({'id':name,'purpose':'Actual native '+name,'duration_seconds':scene['frames']/scene['fps']})
        graph['tool_graph'] +=[
            {'id':name,'tool_id':'body.cgi_shot','purpose':'Original native '+name,'inputs':{'plan':name+'-plan.json','out':name+'.mp4'},'depends_on':[]},
            {'id':name+'-decode','tool_id':'body.full_decode','purpose':'Decode every rendered frame','inputs':{'source':name+'.mp4','expected':{'width':size,'height':size,'duration_seconds':scene['frames']/scene['fps']}},'depends_on':[name]},
            {'id':name+'-vault','tool_id':'body.asset_vault','purpose':'Native source custody','inputs':{'source_witness':{'$node_output':name}},'depends_on':[name]}]
    save('graph.json',graph);result=run_body_project(graph,root);save('graph-result.json',result)
    if result['status']!='all_tool_results_verified':raise RuntimeError(result)
    with sqlite3.connect(root/'production.sqlite3') as db:
        reports={name:json.loads(db.execute('SELECT output_json FROM node_results WHERE project_key=? AND node_id=?',
            (result['project_key'],name)).fetchone()[0])['native_controls'] for name in names}
    save('native-reports.json',reports)
    before={name:(sha256_file(root/(name+'.mp4')),(root/(name+'.mp4')).stat().st_mtime_ns) for name in names}
    again=run_body_project(graph,root);save('graph-reuse.json',again)
    assert len(again['reused'])==3*len(names) and all(t['state']=='reused' for t in again['trace'])
    assert before=={name:(sha256_file(root/(name+'.mp4')),(root/(name+'.mp4')).stat().st_mtime_ns) for name in names}
    cloth=reports['cloth']['cloth'];rows=cloth['meshes']['fabric']
    displacement=cloth['maximum_vertex_displacement']['fabric'];assert displacement>.5
    for row in rows:
        assert row['vertices']==169
        for actual,start in zip(row['pins'],rows[0]['pins']):
            assert np.linalg.norm(np.array(actual['position'])-start['position'])<.00001,'Cloth pin drifted'
    morph=reports['morph']['shape_keys']['morph'];assert morph[0]['vertices']==morph[-1]['vertices']==6
    assert abs(morph[-1]['bounds_max'][2]-2.3)<.00001
    # Distinct per-key interpolation: vertical LINEAR, horizontal BEZIER.
    assert abs(morph[1]['bounds_max'][2]-(1.8+.5*5/11))<.00001
    assert abs(morph[1]['bounds_max'][0]-(.6+.45*5/11))>.003
    def render(name,scene,first=None,last=None):
        validate_blender_shot(scene);p=save(name+'.json',scene);out=root/name
        cmd=['blender','-b','-t','4','--factory-startup','--python-exit-code','1','--python',str(Path(__file__).parent/'blender_scene.py'),'--','--scene',str(p),'--out',str(out)]
        if first is not None:cmd+=['--frame-start',str(first),'--frame-end',str(last)]
        with (root/(name+'.log')).open('w') as stream:subprocess.run(cmd,check=True,stdout=stream,stderr=subprocess.STDOUT,timeout=240)
        return out
    matches={}
    for name,scene in scenes.items():
        full=render(name+'-whole-clock',scene);n=scene['frames'];partial=render(name+'-late-clock',scene,n,n)
        def pixels(folder):return np.asarray(Image.open(folder/f'frame_{n:04d}.png').convert('RGB'))
        assert np.array_equal(pixels(full),pixels(partial)),name+' frame subset changed actual picture'
        a=json.loads((full/'render-report.json').read_text());b=json.loads((partial/'render-report.json').read_text())
        field={'morph':'shape_keys'}.get(name,name)
        assert a[field]==b[field],name+' original-clock geometry changed'
        matches[name]=True
    without_contact=copy.deepcopy(scenes['cloth']);without_contact['objects'][0]['cloth']['collisions']=False
    free=render('cloth-without-contact',without_contact,24,24)
    free_report=json.loads((free/'render-report.json').read_text())['cloth']['meshes']['fabric'][-1]
    collision_lift=rows[-1]['bounds_min'][2]-free_report['bounds_min'][2]
    assert collision_lift>.15,'Actual contact control did not prevent cloth penetration'
    liquid_proof=None
    if include_liquid:
        liquid=reports['liquid']['liquid'];mesh=liquid['meshes']
        assert liquid['cache_mesh_frames']==12 and all(x['polygons']>0 for x in mesh)
        assert mesh[-1]['bounds_min'][2]<mesh[0]['bounds_min'][2]-.5
        assert len({r['vertices'] for r in mesh})>1,'Liquid topology did not change'
        viscous=copy.deepcopy(scenes['liquid']);viscous['objects'][0]['liquid_domain']['viscosity']=.08
        changed=render('viscous-liquid',viscous,12,12)
        visc=json.loads((changed/'render-report.json').read_text())['liquid']
        assert abs(visc['viscosity']-.08)<.00001
        assert visc['meshes'][-1]['geometry_sha256']!=mesh[-1]['geometry_sha256'],'Viscosity did not change solved mesh'
        liquid_proof={'native_mesh_cache_frames':12,'varying_topology':True,'gravity_changed_actual_surface':True,'viscosity_changed_actual_mesh':True}
    proof={'all_requested_checks_passed':True,'native_renderer':reports['cloth']['blender_version'],
        'public_body_graph_render_decode_and_custody':True,'all_nodes_reused':3*len(names),
        'cloth_maximum_vertex_displacement':displacement,'cloth_pins_preserved':True,'cloth_collision_lift':collision_lift,
        'independent_shape_key_interpolation_preserved':True,'original_clock_pixels_and_geometry_identical':matches,
        'liquid_requested':include_liquid,'liquid_native_executed':include_liquid,'liquid':liquid_proof,
        'movie_sha256':{name:value[0] for name,value in before.items()},'live_creative_model_used':False,'premium_film_quality_approved':False}
    save('deform-proof.json',proof);return proof


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True)
    p.add_argument('--size',type=int,default=128);p.add_argument('--samples',type=int,default=6)
    p.add_argument('--cloth-morph-only',action='store_true',help='Explicitly omit liquid; does not count it as passed')
    a=p.parse_args();print(json.dumps(run(a.workspace,size=a.size,samples=a.samples,include_liquid=not a.cloth_morph_only),indent=2))


if __name__=='__main__':main()

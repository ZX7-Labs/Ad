"""Declarative cloth/morph/liquid boundaries and actual native cloth acceptance."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from types import ModuleType,SimpleNamespace
from unittest.mock import patch
import sys
from studio_next.blender_scene import validate_blender_shot,Invalid3DShot
from studio_next.body_document_schemas import validate_document,document_contract


def fixture(name):
    return json.loads((Path(__file__).parent/'fixtures'/name).read_text())


class DeformContracts(unittest.TestCase):
    def test_all_three_commissions_are_queryable_native_data(self):
        for name in ('cloth_drape_shot.json','mesh_morph_shot.json','liquid_impact_shot.json'):
            s=fixture(name);self.assertIs(validate_blender_shot(s),s)
            self.assertTrue(validate_document('body.cgi_shot',{'scene':s,'assets':[]}))
        schema=document_contract('body.cgi_shot')['json_schema']
        self.assertNotIn('default',json.dumps(schema))
        self.assertIn('liquid_domain',json.dumps(schema));self.assertIn('shape_keys',json.dumps(schema))

    def test_cloth_pins_are_finite_unique_actual_vertex_indices(self):
        for pin in ({'vertex':9999,'weight':1},{'vertex':True,'weight':1},{'vertex':0,'weight':float('nan')}):
            s=fixture('cloth_drape_shot.json');s['objects'][0]['cloth']['pins']=[pin]
            with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=fixture('cloth_drape_shot.json');s['objects'][0]['cloth']['pins']*=2
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)

    def test_shape_keys_cannot_replace_topology_or_execute_code(self):
        s=fixture('mesh_morph_shot.json');s['objects'][0]['shape_keys'][0]['vertices'].pop()
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        for part in ('cloth','liquid_domain','shape_keys'):
            name={'cloth':'cloth_drape_shot.json','liquid_domain':'liquid_impact_shot.json','shape_keys':'mesh_morph_shot.json'}[part]
            s=fixture(name);target=s['objects'][0][part]
            if isinstance(target,list):target=target[0]
            target['python']='untrusted code'
            with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
            with self.assertRaises(ValueError):validate_document('body.cgi_shot',{'scene':s,'assets':[]})

    def test_competing_transform_and_simulation_roles_are_rejected(self):
        s=fixture('cloth_drape_shot.json');s['objects'][0]['animate']={'location':[{'frame':1,'value':[0,0,0]}]}
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=fixture('liquid_impact_shot.json');s['objects'][0]['liquid_flow']=s['objects'][1]['liquid_flow']
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=fixture('cloth_drape_shot.json');s.pop('physics')
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)

    def test_invalid_liquid_grid_open_source_and_source_clock_fail(self):
        s=fixture('liquid_impact_shot.json');s['objects'][0]['liquid_domain']['resolution']=True
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=fixture('liquid_impact_shot.json');s['objects'][1]['type']='plane'
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=fixture('liquid_impact_shot.json');s['objects'][0]['liquid_domain']['cache_directory']='../../outside'
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=fixture('liquid_impact_shot.json');s['objects'][1]['animate']={'location':[{'frame':1,'value':[0,0,0]}]}
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)

    def test_liquid_cannot_silently_export_empty_vectors_or_unimplemented_blur(self):
        s=fixture('liquid_impact_shot.json')
        with self.assertRaisesRegex(Invalid3DShot,'velocity-aware EXR'):validate_blender_shot(s,require_vector_passes=True)
        s['render_settings']['motion_blur']={'shutter':.5,'position':'CENTER'}
        with self.assertRaisesRegex(Invalid3DShot,'velocity-aware render'):validate_blender_shot(s)

    def test_old_liquid_runtime_is_rejected_before_native_initialization(self):
        from studio_next.blender_scene import render_blender_shot
        bpy=ModuleType('bpy');bpy.app=SimpleNamespace(version=(4,0,2))
        mathutils=ModuleType('mathutils');mathutils.Vector=object
        with tempfile.TemporaryDirectory() as temp,patch.dict(sys.modules,{'bpy':bpy,'mathutils':mathutils}):
            out=Path(temp)/'not-created'
            with self.assertRaisesRegex(Invalid3DShot,'Blender 4.5'):
                render_blender_shot(fixture('liquid_impact_shot.json'),out)
            self.assertFalse(out.exists())

    def test_public_mp4_adapter_reports_liquid_setup_before_launch(self):
        from studio_next.native_body_engines import render_original_blender
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'scene.json';p.write_text(json.dumps(fixture('liquid_impact_shot.json')))
            with patch('shutil.which',return_value='/installed/native'),patch('subprocess.check_output',return_value='Blender 4.0.2\n'),patch('subprocess.run') as launched:
                with self.assertRaisesRegex(RuntimeError,'Blender 4.5'):
                    render_original_blender(p,root/'never-created.mp4')
                launched.assert_not_called()
            self.assertFalse((root/'never-created.mp4').exists())


@unittest.skipUnless(shutil.which('blender') and shutil.which('ffmpeg') and shutil.which('ffprobe') and importlib.util.find_spec('numpy') and importlib.util.find_spec('PIL'),
                     'Real Blender, FFmpeg, numpy and Pillow required')
class NativeClothMorphAcceptance(unittest.TestCase):
    def test_public_cloth_morph_collisions_frame_subsets_and_reuse(self):
        from studio_next.body_deform_proof import run
        with tempfile.TemporaryDirectory() as temp:
            root=Path(os.environ.get('ZX7_DEFORM_PROOF',temp))
            proof=run(root,size=96,samples=4,include_liquid=False)
            self.assertTrue(proof['all_requested_checks_passed'])
            self.assertFalse(proof['liquid_native_executed'])
            self.assertTrue(proof['cloth_pins_preserved'])
            self.assertEqual(proof['all_nodes_reused'],6)


if __name__=='__main__':unittest.main()

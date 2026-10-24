"""Regression and physical-media tests; scripted fixtures are NOT creative AI proof."""
import copy
import io
import importlib.machinery
import importlib.util
import http.client
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
import wave
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from studio_next.body_document_schemas import document_contract,validate_document
from studio_next.body_service import LocalBodyCoordinator,make_body_http_handler
from studio_next.body_signal import BodyAuthority,LiveBodySignal
from studio_next.providers import LocalCreativeModel,LocalModelSettings
from studio_next.voice_contract import voice_inventory


class LocalTransportRegression(unittest.TestCase):
    def test_real_local_model_bypasses_proxy_and_refuses_redirects(self):
        seen=[]; proxied=[]
        class Origin(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                seen.append(self.rfile.read(int(self.headers['Content-Length'])))
                if self.server.redirect:
                    self.send_response(307)
                    self.send_header('Location',self.server.destination)
                    self.end_headers();return
                raw=json.dumps({'choices':[{'message':{'content':'{"kind":"question","question":"test"}'}}]}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        class Proxy(Origin):
            def do_POST(self):
                proxied.append(self.path);self.send_error(500)
        origin=ThreadingHTTPServer(('127.0.0.1',0),Origin)
        proxy=ThreadingHTTPServer(('127.0.0.1',0),Proxy)
        origin.redirect=False;origin.destination='http://127.0.0.1:'+str(proxy.server_port)+'/stolen'
        threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (origin,proxy)]
        for t in threads:t.start()
        try:
            with patch.dict(os.environ,{'http_proxy':'http://127.0.0.1:'+str(proxy.server_port),
                    'HTTP_PROXY':'http://127.0.0.1:'+str(proxy.server_port),'no_proxy':'','NO_PROXY':''}):
                model=LocalCreativeModel(LocalModelSettings(base_url='http://127.0.0.1:'+str(origin.server_port)))
                self.assertEqual(model.decide({'private':'synthetic test context'})['kind'],'question')
                origin.redirect=True
                with self.assertRaisesRegex(ValueError,'redirect'):
                    model.decide({'private':'synthetic test context'})
            self.assertEqual(len(seen),2)
            self.assertEqual(proxied,[])
        finally:
            for server in (origin,proxy):server.shutdown();server.server_close()
            for t in threads:t.join(3)


class CreativeAudioContracts(unittest.TestCase):
    def test_new_voice_identity_and_per_scene_language_speed_reach_actual_adapter(self):
        from motion_studio.voice import main
        calls=[];voices=[]
        class TTSFixture:
            voice_style_names=['new_narrator','other_narrator']
            def __init__(self,**kwargs):self.kwargs=kwargs
            def get_voice_style(self,voice_name):voices.append(voice_name);return voice_name
            def synthesize(self,**kwargs):calls.append(kwargs);return b'fixture',.4
            def save_audio(self,audio,path):
                with wave.open(path,'wb') as w:
                    w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(bytes(12800))
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);project=root/'project.json'
            project.write_text(json.dumps({'voice':'new_narrator','voice_settings':{'speed':1.3,'lang':'hi'},
                'scenes':[{'id':'first','narration':'पहला वाक्य'},
                          {'id':'next','narration':'A different speaker','voice':'other_narrator',
                           'voice_settings':{'speed':.8,'lang':'en','silence_duration':.6}}]}))
            module=types.ModuleType('supertonic');module.TTS=TTSFixture
            module.__spec__=importlib.machinery.ModuleSpec('supertonic',None)
            with patch.dict(sys.modules,{'supertonic':module}),patch.object(
                    sys,'argv',['voice','--project',str(project),'--out',str(root/'out'),'--model-dir',str(root)]):
                main()
            self.assertEqual(set(voices),{'new_narrator','other_narrator'})
            self.assertEqual([(c['voice_style'],c['lang'],c['speed']) for c in calls],
                [('new_narrator','hi',1.3),('other_narrator','en',.8)])
            self.assertEqual(calls[1]['silence_duration'],.6)
            self.assertEqual(json.loads((root/'out/voice-timing.json').read_text())[1]['voice'],'other_narrator')

    def test_voice_discovery_only_lists_real_local_style_documents(self):
        with tempfile.TemporaryDirectory() as root:
            styles=Path(root)/'voice_styles';styles.mkdir()
            (styles/'custom.json').write_text('{"style_ttl":[],"style_dp":[]}')
            (styles/'bad.json').write_text('not json')
            (styles/'alias.json').symlink_to(styles/'custom.json')
            result=voice_inventory(root)
            self.assertEqual([v['id'] for v in result['voices']],['custom'])
            self.assertFalse(result['synthesis_verified'])

    def test_model_queries_actual_voice_inventory_through_registered_read_tool(self):
        from studio_next.body_integration import body_catalog,validate_witness
        with tempfile.TemporaryDirectory() as root:
            styles=Path(root)/'model/voice_styles';styles.mkdir(parents=True)
            file=styles/'new_identity.json';file.write_text('{"style_ttl":[],"style_dp":[]}')
            catalog=body_catalog(root)
            receipt=catalog.invoke('body.voice_inventory',{'voice_assets':'model'},allowed_access={'read'})
            self.assertEqual(receipt['inventory']['voices'][0]['id'],'new_identity')
            self.assertTrue(validate_witness('body.voice_inventory',receipt))
            file.write_text('{"style_ttl":[1],"style_dp":[]}')
            self.assertFalse(validate_witness('body.voice_inventory',receipt))
            with self.assertRaises(ValueError):
                catalog.invoke('body.voice_inventory',{'voice_assets':'../outside'},allowed_access={'read'})

    @unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("PIL"),"Real numeric/image dependencies required")
    def test_arbitrary_spectrum_envelope_noise_and_no_imposed_mix_fade(self):
        import numpy as np
        from studio_next.sound_synthesis import synthesize
        from motion_studio.render import mix_audio
        cue={'type':'synth','at':0,'seconds':1,'gain':.2,'noise_gain':0,'seed':137,
             'partials':[{'start_hz':731,'end_hz':731,'amplitude':1,'phase_radians':0}],
             'envelope':[[0,1],[1,1]]}
        first=synthesize(cue,48000)
        second=synthesize({**cue,'noise_gain':.3},48000)
        self.assertTrue(np.array_equal(second,synthesize({**cue,'noise_gain':.3},48000)))
        self.assertFalse(np.array_equal(first,second))
        self.assertEqual(int(np.argmax(np.abs(np.fft.rfft(first)))),731)
        with tempfile.TemporaryDirectory() as root:
            wav=Path(root)/'mix.wav'
            mix_audio({'audio_mix':{}},[{'seconds':1,'cues':[cue]}],wav)
            with wave.open(str(wav)) as w:
                actual=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2)[:,0]/32767
            self.assertLess(float(np.max(np.abs(actual-first))),1/32767+.00001)
            with self.assertRaisesRegex(ValueError,'clips'):
                mix_audio({'audio_mix':{}},[{'seconds':1,'cues':[{**cue,'gain':3}]}],wav)


class DocumentContractRegression(unittest.TestCase):
    def test_discovered_motion_schema_authors_native_valid_original_document(self):
        from studio_next.test_motion_bridge import case
        from studio_next.motion_bridge import compile_motion_project
        plan=case();plan['project']['voice']='new_narrator'
        plan['shots'][0]['voice_settings']={'lang':'hi','speed':.9}
        self.assertTrue(validate_document('body.motion2d',plan))
        self.assertEqual(compile_motion_project(plan)['voice'],'new_narrator')
        descriptor=document_contract('body.motion2d')
        self.assertEqual(descriptor['input_name'],'original_film_ir')
        self.assertNotIn('default',json.dumps(descriptor))

    def test_all_3d_fixture_fields_and_secondary_editor_operation_are_queryable(self):
        from studio_next.body_document_schemas import document_contracts
        fixture=Path(__file__).parent/'fixtures/three_dimensional_shot.json'
        self.assertTrue(validate_document('body.blender3d',json.loads(fixture.read_text())))
        self.assertIn('operation',document_contracts('body.timeline_revision'))
        self.assertTrue(validate_document('body.timeline_revision',{'operations':[
            {'kind':'slip','clip':0,'delta':2}]},'operation'))
        with self.assertRaises(ValueError):
            validate_document('body.timeline_revision',{'operations':[
                {'kind':'shell','command':'untrusted'}]},'operation')

    def test_compositor_structure_error_is_exact_and_no_plan_published(self):
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root)
            try:
                s=LiveBodySignal(c,authority=BodyAuthority(workspace_ids=frozenset({'film'}),
                    operations=frozenset({'author_plan'}),tool_access=frozenset({'read','write'})))
                schema=s.describe('film','body.composite_mix')['document_contracts']['plan']['json_schema']
                self.assertIn('audio_tracks',schema['properties'])
                with self.assertRaisesRegex(ValueError,'/canvas: missing'):
                    s.command('author_plan',{'workspace_id':'film','tool_id':'body.composite_mix',
                        'document':{'canvas':{},'video_layers':[],'audio_tracks':[]}})
                self.assertFalse((c._workspace('film')/'brain-authored').exists())
            finally:c.close()


class UploadAdmissionRegression(unittest.TestCase):
    def test_real_http_stalled_media_read_expires_and_releases_staging_reservation(self):
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root,upload_timeout_seconds=1)
            token='synthetic-upload-deadline-test-token-123456'
            server=ThreadingHTTPServer(('127.0.0.1',0),make_body_http_handler(c,token))
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=4)
            try:
                connection.putrequest('POST','/v1/workspaces/film/assets/incomplete.bin')
                for name,value in {'Authorization':'Bearer '+token,'Content-Length':'8',
                    'Content-Type':'application/octet-stream','X-Source-Id':'fixture',
                    'X-Rights-Evidence':'Synthetic original fixture'}.items():connection.putheader(name,value)
                connection.endheaders() # No declared body bytes arrive.
                response=connection.getresponse()
                self.assertEqual(response.status,400)
                self.assertIn('timed out',response.read().decode())
                self.assertFalse(c._active_uploads)
                self.assertEqual(c._reserved_upload_bytes,0)
                self.assertFalse(list(Path(root).rglob('.zx7-import-*')))
            finally:
                connection.close();server.shutdown();server.server_close();worker.join(3);c.close()

    def test_stalled_upload_does_not_block_other_workspace_and_snapshot_refuses_it(self):
        entered=threading.Event();release=threading.Event();submitted=threading.Event();errors=[]
        class Stream:
            def read(self,n):entered.set();release.wait(4);return b'invalid'
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root,execute=lambda ir,w:{'status':'blocked','errors':['test only']})
            def upload():
                try:c.upload_owner_media('film','source.bin',Stream(),7,mime='application/octet-stream',
                                         source_id='test',rights_evidence='synthetic test original')
                except Exception as e:errors.append(e)
            t=threading.Thread(target=upload);t.start()
            try:
                self.assertTrue(entered.wait(3))
                def submit():
                    c.submit({'tool_graph':[]},workspace_id='unrelated');submitted.set()
                other=threading.Thread(target=submit);other.start()
                self.assertTrue(submitted.wait(2),'Unrelated job admission blocked by upload')
                other.join(2)
                with self.assertRaisesRegex(RuntimeError,'upload'):
                    c.create_recovery_snapshot(Path(root)/'snapshot.tar.gz')
            finally:release.set();t.join(5);c.close()
            self.assertFalse(c._active_uploads)
            self.assertEqual(c._reserved_upload_bytes,0)
            self.assertFalse(list(Path(root).rglob('.zx7-import-*')))


if __name__=='__main__':unittest.main()

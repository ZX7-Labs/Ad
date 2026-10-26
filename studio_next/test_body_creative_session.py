"""Scripted local-model protocol fixtures + real codecs, not live LLM artistry."""
import copy
import importlib.util
import json
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

from studio_next.body_creative_session import SESSION_SYSTEM
from studio_next.body_service import LocalBodyCoordinator
from studio_next.body_signal import BodyAuthority,LiveBodySignal
from studio_next.providers import LocalCreativeModel,LocalModelSettings


class SessionControlRegression(unittest.TestCase):
    def test_owner_stop_during_inference_prevents_new_body_action_and_snapshot_refuses_active_session(self):
        entered=threading.Event();release=threading.Event()
        class SlowModel:
            def decide(self,context):
                entered.set();release.wait(4)
                return {'action':'submit','arguments':{'film_ir':execution('no-plan.json')},'reason':'Fixture only'}
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root,creative_model=SlowModel())
            try:
                created=c.creative_sessions.create('film','Synthetic stop test',{})
                self.assertTrue(entered.wait(3))
                with self.assertRaisesRegex(RuntimeError,'creative session'):
                    c.create_recovery_snapshot(Path(root)/'snapshot.tar.gz')
                c.creative_sessions.stop(created['session_id']);release.set()
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    state=c.creative_sessions.inspect(created['session_id'])
                    if state['status']=='stopped':break
                    time.sleep(.02)
                self.assertEqual(state['status'],'stopped')
                self.assertEqual(state['jobs'],[])
                self.assertEqual(state['events'],[])
            finally:release.set();c.close()

    def test_nonfinite_model_response_is_persisted_as_blocked_not_left_running(self):
        class InvalidModel:
            def decide(self,context):
                return {'action':'finish','arguments':{'summary':float('nan')},'reason':'Invalid fixture'}
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root,creative_model=InvalidModel())
            try:
                created=c.creative_sessions.create('film','Test invalid structured model output',{})
                c.creative_sessions.close()
                state=c.creative_sessions.inspect(created['session_id'])
                self.assertEqual(state['status'],'blocked')
                self.assertIsNone(state['pending'])
                self.assertEqual(state['jobs'],[])
            finally:c.close()


def tiny_motion(gain):
    return {'project':{'title':'Protocol fixture','creative_intent':'Test an original pixel and sound change',
        'width':320,'height':320,'voice':'no_voice','background':'#172636'},
        'assets':[{'id':'shape','status':'verified','rights':'generated_original',
                   'location':'inline://shape','artwork':{'size':[64,64],
                   'items':[{'type':'rect','box':[0,0,63,63],'fill':'#F3B454'}]}}],
        'shots':[{'id':'one','purpose':'Exercise real timed pixels and authored sound',
                  'duration_seconds':.5,'narration':'','asset_refs':['shape'],'fact_refs':[],
                  'layers':[{'asset':'shape','x':160,'y':160}],
                  'cues':[{'type':'synth','at':0,'seconds':.5,'gain':gain,'noise_gain':0,'seed':321,
                    'partials':[{'start_hz':647,'end_hz':647,'amplitude':1,'phase_radians':0}],
                    'envelope':[[0,1],[.5,1]]}]}],
        'tool_graph':[{'id':'paint','tool_id':'motion_studio.composite','purpose':'Draw actual original test art',
                       'inputs':{},'depends_on':[]}]}


def execution(plan_path,second_path=None):
    nodes=[{'id':'original','tool_id':'body.motion2d','purpose':'Actual original test render',
            'inputs':{'original_film_ir':plan_path,'out':'original.mp4','width':320,'fps':12},'depends_on':[]}]
    if second_path:
        nodes.append({'id':'revised','tool_id':'body.motion2d','purpose':'Test revised sound amplitude',
            'inputs':{'original_film_ir':second_path,'out':'revised.mp4','width':320,'fps':12},'depends_on':[]})
    return {'project':{'creative_intent':'Protocol fixture for actual original and revised media'},
            'owner_facts':{},'shots':[{'id':'one','purpose':'Physical media verification','duration_seconds':.5}],
            'assets':[],'tool_graph':nodes}


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe') and all(
    importlib.util.find_spec(x) for x in ('numpy','PIL','fontTools')),'Real FFmpeg and motion dependencies required')
class CreativeSessionPhysicalAcceptance(unittest.TestCase):
    def test_ordinary_brief_local_http_model_contract_real_render_observation_and_revision(self):
        # This server returns known test decisions, not a neural model response.
        requests=[]; paths=[]; jobs=[]
        def choose(context):
            step=len(requests)-1
            if step==0:return 'describe',{'tool_id':'body.motion2d'}
            if step==1:
                schema=context['recent_events'][-1]['result']['document_contracts']['original_film_ir']
                self.assertIn('cues',schema['json_schema']['properties']['shots']['items']['properties'])
                return 'author_plan',{'tool_id':'body.motion2d','document':tiny_motion(.2)}
            if step==2:
                paths.append(context['recent_events'][-1]['result']['path'])
                return 'submit',{'film_ir':execution(paths[0])}
            if step==3:
                jobs.append(context['recent_events'][-1]['result']['job_id'])
                return 'wait',{'job_id':jobs[0],'seconds':10}
            if step==4:return 'read',{'tool_id':'body.full_decode','inputs':{'source':'original.mp4'}}
            if step==5:
                self.assertTrue(context['recent_events'][-1]['result']['full_picture_and_sound_decoder_completed'])
                return 'author_plan',{'tool_id':'body.motion2d','document':tiny_motion(.1)}
            if step==6:
                paths.append(context['recent_events'][-1]['result']['path'])
                return 'submit',{'film_ir':execution(paths[0],paths[1])}
            if step==7:
                jobs.append(context['recent_events'][-1]['result']['job_id'])
                return 'wait',{'job_id':jobs[1],'seconds':10}
            if step==8:
                result=context['recent_events'][-1]['result']
                self.assertEqual(result['status'],'completed',result)
                self.assertIn('original',result['result']['reused'])
                return 'read',{'tool_id':'body.full_decode','inputs':{'source':'revised.mp4'}}
            return 'finish',{'summary':'Synthetic protocol test rendered and revised. No artistic acceptance claimed.'}
        class FixtureServer(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(payload)
                action,args=choose(json.loads(payload['messages'][1]['content']))
                decision={'action':action,'arguments':args,'reason':'Scripted protocol regression fixture'}
                raw=json.dumps({'choices':[{'message':{'content':json.dumps(decision)},'finish_reason':'stop'}]}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),FixtureServer)
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            with tempfile.TemporaryDirectory() as root:
                model=LocalCreativeModel(LocalModelSettings(base_url='http://127.0.0.1:'+str(server.server_port),
                    model_id='scripted-protocol-fixture',timeout_seconds=20),system_prompt=SESSION_SYSTEM)
                c=LocalBodyCoordinator(root,creative_model=model)
                try:
                    created=c.creative_sessions.create('film','Test only: create, observe and revise original sound.',{})
                    deadline=time.monotonic()+65
                    while time.monotonic()<deadline:
                        state=c.creative_sessions.inspect(created['session_id'])
                        if state['status'] not in ('queued','running'):break
                        time.sleep(.1)
                    self.assertEqual(state['status'],'model_finished',state)
                    self.assertFalse(state['artistic_quality_approved'])
                    self.assertFalse(state['audio_semantically_reviewed'])
                    self.assertEqual(state['model_identity']['model_id'],'scripted-protocol-fixture')
                    self.assertEqual(len(state['jobs']),2)
                    self.assertFalse([event for event in state['events'] if 'error' in event['result']])
                    import numpy as np
                    def rms(path):
                        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-ac','1','pipe:1'],timeout=15)
                        return float(np.sqrt(np.mean(np.frombuffer(raw,dtype='<f4')**2)))
                    workspace=c._workspace('film')
                    self.assertAlmostEqual(rms(workspace/'original.mp4')/rms(workspace/'revised.mp4'),2,delta=.15)
                finally:c.close()
                reopened=LocalBodyCoordinator(root)
                try:
                    from studio_next.body_creative_session import CreativeSessions
                    manager=CreativeSessions(reopened,model)
                    self.assertEqual(manager.inspect(created['session_id'])['status'],'model_finished')
                    manager.close()
                finally:reopened.close()
        finally:server.shutdown();server.server_close();t.join(3)

    def test_replayed_host_submission_after_receipt_loss_reuses_one_original_job(self):
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root,execute=lambda ir,w:{'status':'blocked','errors':['Fixture only']})
            try:
                signal=LiveBodySignal(c,authority=BodyAuthority(workspace_ids=frozenset({'film'}),
                    operations=frozenset({'submit'}),tool_access=frozenset({'read','write'})))
                ir=execution('missing.json')
                args={'workspace_id':'film','film_ir':ir}
                first=signal.command('submit',args,submission_key='a'*64)
                replay=signal.command('submit',args,submission_key='a'*64)
                self.assertEqual(first['job_id'],replay['job_id'])
                self.assertTrue(replay['existing_submission_reused'])
                changed=copy.deepcopy(ir);changed['project']['creative_intent']='Changed original intent'
                with self.assertRaisesRegex(ValueError,'conflicts'):
                    signal.command('submit',{'workspace_id':'film','film_ir':changed},submission_key='a'*64)
            finally:c.close()


if __name__=='__main__':unittest.main()

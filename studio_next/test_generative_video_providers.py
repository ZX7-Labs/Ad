import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from studio_next.generative_video_providers import (
    discover_local_generators,measured_gpu_vram_mb,safe_local_api,generator_material_identity)


def installed_workflow(folder,kind):
    graph={'generate':{'class_type':kind,'inputs':{k:0 for k in ('prompt','frames','width','height','fps')}},
           'save':{'class_type':'SaveVideo','inputs':{'video':['generate',0]}}}
    (folder/'workflow.json').write_text(json.dumps(graph))
    (folder/'bindings.json').write_text(json.dumps({'model_id':folder.name,'output_node':'save',
        'inputs':{k:{'node':'generate','key':k} for k in ('prompt','frames','width','height','fps')}}))


class ActualVideoGeneratorDiscoveryTests(unittest.TestCase):
    def test_additional_owned_engine_is_discovered_without_editing_candidate_code(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'owned-audiovisual-engine';p.mkdir()
            blob=p/'checkpoint.safetensors';blob.write_bytes(b'contract-only-not-real-model'*128)
            digest=hashlib.sha256(blob.read_bytes()).hexdigest()
            data={'model_id':p.name,'weight_sha256':digest,'license_accepted_or_verified':True,
                'required_weight_roles':['checkpoint'],'weight_files':[{'role':'checkpoint','path':blob.name,'sha256':digest}],
                'minimum_locally_verified_vram_mb':12000,'required_comfyui_nodes':['OwnedVideoNode','SaveVideo'],
                'model_metadata':{'repo':'owner/verified-local-engine','license_metadata':'owner-verified-test-license','capabilities':['image_to_video','dialogue_video']}}
            (p/'deployment.json').write_text(json.dumps(data))
            installed_workflow(p,'OwnedVideoNode')
            def fetch(url):return {'devices':[]} if url.endswith('/system_stats') else {'OwnedVideoNode':{},'SaveVideo':{}}
            state=discover_local_generators(gpu_mb=16000,deployed_root=root,comfy_endpoint='http://localhost:8188',fetch=fetch)
            custom=next(x for x in state['video_generation_options'] if x['id']==p.name)
            self.assertTrue(custom['ready_for_independent_execution_trial']);self.assertIsNotNone(custom['verified_weight_set_sha256'])
            self.assertFalse(custom['actual_movie_generated_and_ffprobed'])
            identity=generator_material_identity(root,p.name)
            (p/'workflow.json').write_text((p/'workflow.json').read_text()+'\n')
            self.assertNotEqual(identity,generator_material_identity(root,p.name))
            broken=p/'bad-deployment';broken.mkdir();(broken/'deployment.json').write_text('{broken')
            (p/'bindings.json').write_text('{broken')
            invalid=discover_local_generators(gpu_mb=16000,deployed_root=root,comfy_endpoint='http://localhost:8188',fetch=fetch)
            self.assertFalse(next(x for x in invalid['video_generation_options'] if x['id']==p.name)['ready_for_independent_execution_trial'])
            installed_workflow(p,'OwnedVideoNode')
            zero=discover_local_generators(gpu_mb=0,deployed_root=root,comfy_endpoint='http://localhost:8188',fetch=fetch)
            self.assertFalse(next(x for x in zero['video_generation_options'] if x['id']==p.name)['ready_for_independent_execution_trial'])
            blob.write_bytes(b'changed-weights'*256)
            self.assertFalse(any(x['id']==p.name for x in discover_local_generators(gpu_mb=16000,deployed_root=root,comfy_endpoint='http://localhost:8188',fetch=fetch)['video_generation_options']))

    def test_cpu_runner_cannot_falsely_claim_real_video_generation(self):
        with tempfile.TemporaryDirectory() as root:
            state=discover_local_generators(gpu_mb=0,deployed_root=root)
            self.assertFalse(state["gpu_is_real_hardware"])
            self.assertEqual(len(state["video_generation_options"]),3)
            self.assertFalse(any(x["ready_for_independent_execution_trial"]
                                 for x in state["video_generation_options"]))
            self.assertFalse(state["all_video_generation_operational"])

    def test_no_remote_paid_endpoint_or_credential_leak(self):
        for url in ("https://api.provider.com","http://evil.example:8188",
                    "http://user:pass@localhost:8188","file:///etc/passwd"):
            with self.assertRaises(ValueError):
                safe_local_api(url)
        self.assertEqual(safe_local_api("http://127.0.0.1:8188"),
                         "http://127.0.0.1:8188")

    def test_genuine_cuda_without_weight_does_not_pretend_generate(self):
        with tempfile.TemporaryDirectory() as root:
            def reachable(url):
                if url.endswith("/system_stats"):return {"devices":[{"name":"Nvidia GPU"}]}
                return {"WanVideoModelLoader":{},"SaveVideo":{}}
            state=discover_local_generators(gpu_mb=24000,deployed_root=root,
                comfy_endpoint="http://localhost:8188",fetch=reachable)
            self.assertTrue(state["comfyui"]["service_reachable"])
            self.assertFalse(any(x["ready_for_independent_execution_trial"]
                                 for x in state["video_generation_options"]))

    def test_only_true_weights_nodes_gpu_enable_trial_not_quality_claim(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"wan21-t2v-13b"
            p.mkdir()
            weights=[]
            for role in ("diffusion","vae","text_encoder"):
                file=p/(role+".safetensors")
                file.write_bytes(role.encode("utf-8")*256)
                weights.append({"role":role,"path":file.name,
                    "sha256":hashlib.sha256(file.read_bytes()).hexdigest()})
            (p/"deployment.json").write_text(json.dumps({
                "model_id":"wan21-t2v-13b",
                "weight_sha256":weights[0]["sha256"],
                "weight_files":weights,
                "license_accepted_or_verified":True,
                "required_comfyui_nodes":["WanVideoModelLoader","SaveVideo"]}))
            installed_workflow(p,'WanVideoModelLoader')
            def fake(url):
                return {"devices":[{"name":"Nvidia GPU"}]} if url.endswith("/system_stats") else {
                    "WanVideoModelLoader":{},"SaveVideo":{}}
            a=discover_local_generators(gpu_mb=9000,deployed_root=root,
                  comfy_endpoint="http://localhost:8188",fetch=fake)
            choice=a["video_generation_options"][0]
            self.assertTrue(choice["ready_for_independent_execution_trial"])
            self.assertFalse(choice["actual_movie_generated_and_ffprobed"])
            self.assertFalse(a["all_video_generation_operational"])
            (p/'workflow.json').unlink()
            missing=discover_local_generators(gpu_mb=9000,deployed_root=root,comfy_endpoint='http://localhost:8188',fetch=fake)
            self.assertFalse(missing['video_generation_options'][0]['ready_for_independent_execution_trial'])


if __name__=="__main__":
    unittest.main()

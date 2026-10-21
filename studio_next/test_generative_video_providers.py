import json
import tempfile
import unittest
from pathlib import Path
from studio_next.generative_video_providers import (
    discover_local_generators,measured_gpu_vram_mb,safe_local_api)


class ActualVideoGeneratorDiscoveryTests(unittest.TestCase):
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
            (p/"deployment.json").write_text(json.dumps({
                "model_id":"wan21-t2v-13b","weight_sha256":"a"*64,
                "weight_file_is_hash_verified":True,
                "license_accepted_or_verified":True,
                "required_comfyui_nodes":["WanVideoModelLoader","SaveVideo"]}))
            def fake(url):
                return {"devices":[{"name":"Nvidia GPU"}]} if url.endswith("/system_stats") else {
                    "WanVideoModelLoader":{},"SaveVideo":{}}
            a=discover_local_generators(gpu_mb=9000,deployed_root=root,
                  comfy_endpoint="http://localhost:8188",fetch=fake)
            choice=a["video_generation_options"][0]
            self.assertTrue(choice["ready_for_independent_execution_trial"])
            self.assertFalse(choice["actual_movie_generated_and_ffprobed"])
            self.assertFalse(a["all_video_generation_operational"])


if __name__=="__main__":
    unittest.main()

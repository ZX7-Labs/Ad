import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from studio_next.comfy_video_runtime import (
    validate_video_job, _approved_graph,LocalComfyVideoClient,
    render_actual_generated_scene)


def job():
    return {"model_id":"wan21-t2v-13b",
            "prompt":"A real actor opens a notebook in a busy city, physically grounded",
            "negative_prompt":"","width":832,"height":480,"frames":49,
            "fps":12,"seed":123456}


class SafeLocalVideoDiffusionAdapterTests(unittest.TestCase):
    def test_model_owns_acting_prompt_format_timing_no_template_or_default(self):
        x=job()
        self.assertEqual(validate_video_job(x)["frames"],49)
        x["width"]=1500
        x["fps"]=24
        x["seed"]=929292929
        self.assertEqual(validate_video_job(x)["width"],1500)
        x["__python__"]="unsafe"
        with self.assertRaisesRegex(ValueError,"exact technical fields"):
            validate_video_job(x)

    def test_trusted_workflow_binds_artistic_values_without_changing_graph(self):
        with tempfile.TemporaryDirectory() as root:
            dir=Path(root)/"wan21-t2v-13b";dir.mkdir()
            graph={"1":{"class_type":"CLIPTextEncode","inputs":{"text":"old"}},
                   "2":{"class_type":"EmptyHunyuanLatentVideo","inputs":{
                       "width":300,"height":200,"length":12}},
                   "3":{"class_type":"CreateVideo","inputs":{"fps":20}},
                   "4":{"class_type":"SaveVideo","inputs":{"video":["3",0]}}}
            (dir/"workflow.json").write_text(json.dumps(graph))
            bind={"model_id":"wan21-t2v-13b","output_node":"4",
                  "inputs":{
                  "prompt":{"node":"1","key":"text"},
                  "frames":{"node":"2","key":"length"},
                  "width":{"node":"2","key":"width"},
                  "height":{"node":"2","key":"height"},
                  "fps":{"node":"3","key":"fps"}}}
            (dir/"bindings.json").write_text(json.dumps(bind))
            new,meta,signature=_approved_graph(root,job())
            self.assertEqual(new["1"]["inputs"]["text"],job()["prompt"])
            self.assertEqual(new["2"]["inputs"]["width"],832)
            self.assertEqual(new["2"]["inputs"]["length"],49)
            self.assertEqual(new["3"]["inputs"]["fps"],12)
            self.assertEqual(new["4"],graph["4"])
            self.assertEqual(len(signature),64)

    def test_actual_local_service_generates_real_output_only_after_history(self):
        calls=[]
        def request(method,path,data,binary):
            calls.append((method,path))
            if path=="/prompt":
                self.assertEqual(data["prompt"]["a"]["inputs"],{})
                return {"prompt_id":"task-123"}
            if path=="/history/task-123":
                return {"task-123":{"outputs":{"99":{"videos":[{
                    "filename":"filmed.mp4","subfolder":"","type":"output"}]}}}}
            if path.startswith("/view?"):
                self.assertTrue(binary)
                return b"real-video-result"*100
            raise AssertionError(path)
        engine=LocalComfyVideoClient("http://127.0.0.1:8188",request=request)
        name,raw=engine.wait(engine.create({"a":{"inputs":{}}}),"99",
                             poll_seconds=0.0,max_seconds=2)
        self.assertEqual(name,"filmed.mp4")
        self.assertEqual(raw,b"real-video-result"*100)
        self.assertEqual(len(calls),3)

    def test_gpu_weight_service_missing_prevents_fabricated_mp4(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,"actual connected"):
                render_actual_generated_scene(job(),root)
            with patch("studio_next.comfy_video_runtime.discover_local_generators",
                       return_value={"video_generation_options":[{
                           "id":"wan21-t2v-13b",
                           "ready_for_independent_execution_trial":False}]}):
                with self.assertRaisesRegex(ValueError,"GPU, weight-proved"):
                    render_actual_generated_scene(job(),root,
                        comfy_endpoint="http://127.0.0.1:8188")


if __name__=="__main__":
    unittest.main()

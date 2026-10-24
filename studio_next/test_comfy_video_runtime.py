import json
import os
import shutil
import subprocess
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
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
    def test_local_model_credentials_and_prompts_ignore_ambient_http_proxy(self):
        import os
        from unittest.mock import patch
        from studio_next.generative_video_providers import (
            _LOCAL_ONLY_HTTP, open_verified_local_api)
        from urllib.request import ProxyHandler
        proxies=[handler.proxies for handler in _LOCAL_ONLY_HTTP.handlers
                 if isinstance(handler,ProxyHandler)]
        # urllib intentionally omits an empty ProxyHandler from its final
        # handler list on some runtimes. The real live request with poisoned
        # HTTP_PROXY below is the authoritative no-exfiltration test.
        self.assertTrue(all(not entries for entries in proxies))
        class LocalApi(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"local":"verified"}')
            def log_message(self,*args):return
        server=ThreadingHTTPServer(("127.0.0.1",0),LocalApi)
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            from urllib.error import URLError
            url="http://127.0.0.1:"+str(server.server_port)+"/system_stats"
            with patch.dict(os.environ,{
                    "http_proxy":"http://127.0.0.1:1",
                    "HTTP_PROXY":"http://127.0.0.1:1",
                    "no_proxy":"","NO_PROXY":""}):
                with open_verified_local_api(url,timeout=4) as reply:
                    self.assertEqual(json.loads(reply.read()),
                                     {"local":"verified"})
            with self.assertRaisesRegex(ValueError,"local HTTP"):
                open_verified_local_api("http://example.com:8765/model",timeout=4)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_live_local_comfy_api_does_not_follow_redirects_to_other_paths(self):
        from studio_next.generative_video_providers import inspect_comfyui
        observed=[]
        class Redirect(BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append(("GET",self.path))
                self.send_response(302)
                self.send_header("Location",
                    "http://127.0.0.1:"+str(self.server.server_port)+"/unapproved")
                self.end_headers()
            def do_POST(self):
                observed.append(("POST",self.path))
                self.send_response(302)
                self.send_header("Location",
                    "http://127.0.0.1:"+str(self.server.server_port)+"/unapproved")
                self.end_headers()
            def log_message(self,*args):
                return
        server=ThreadingHTTPServer(("127.0.0.1",0),Redirect)
        worker=Thread(target=server.serve_forever,daemon=True)
        worker.start()
        try:
            endpoint="http://127.0.0.1:"+str(server.server_port)
            self.assertFalse(inspect_comfyui(endpoint)["service_reachable"])
            local=LocalComfyVideoClient(endpoint)
            with self.assertRaisesRegex(ValueError,"redirect"):
                local.call("GET","/system_stats")
            with self.assertRaisesRegex(ValueError,"redirect"):
                local.call("POST","/prompt",{"prompt":{"safe":{"inputs":{}}}})
            self.assertEqual(observed,[
                ("GET","/system_stats"),
                ("GET","/system_stats"),
                ("POST","/prompt")])
            self.assertFalse(any("/unapproved" in path for _,path in observed))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_untrusted_comfy_task_id_is_not_an_http_path(self):
        api=LocalComfyVideoClient("http://127.0.0.1:8188",
            request=lambda method,path,data,binary:{
                "prompt_id":"../../other-project"} if path=="/prompt" else {})
        with self.assertRaisesRegex(ValueError,"path-safe"):
            api.create({"node":{"inputs":{}}})
        with self.assertRaisesRegex(ValueError,"path-safe"):
            api.wait("../private-workspace","node",max_seconds=1)

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

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "Requires actual independent video decoder")
    def test_gpu_adapter_receipt_requires_actual_full_decode_and_never_clobbers_movie(self):
        # Mock the GPU availability and model API transport ONLY: video bytes
        # below are real FFmpeg encoded media, not an AI-generated actor.
        # The test proves strict codec and concurrent publication behavior;
        # it must not be cited as proof of an installed diffusion model.
        class FakeLocalRenderer:
            def __init__(self,media):self.media=media
            def create(self,graph):return "licensed-local-gpu-transport-test"
            def wait(self,prompt_id,output_node):return "filmed.mp4",self.media
        with tempfile.TemporaryDirectory() as workspace:
            root=Path(workspace)
            fixture=root/"physical-camera-fixture.mp4"
            command=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
                "-f","lavfi","-i","testsrc2=size=96x64:rate=12:duration=1",
                "-c:v","libx264","-pix_fmt","yuv420p",str(fixture)]
            output=subprocess.run(command,capture_output=True,text=True,timeout=45)
            self.assertEqual(output.returncode,0,output.stderr)
            actual=job();actual.update({"width":96,"height":64,"frames":12,"fps":12})
            graph={"valid-installed-workflow":{"inputs":{}}}
            metadata={"output_node":"valid-installed-workflow"}
            availability={"video_generation_options":[{"id":actual["model_id"],
                            "ready_for_independent_execution_trial":True}]}
            fake=FakeLocalRenderer(fixture.read_bytes())
            with patch("studio_next.comfy_video_runtime._approved_graph",
                       return_value=(graph,metadata,"a"*64)),patch(
                       "studio_next.comfy_video_runtime.discover_local_generators",
                       return_value=availability):
                with patch("studio_next.comfy_video_runtime.os.link") as link:
                    # Reject bogus bytes despite an injected optimistic
                    # ffprobe stub; no public film is created.
                    false=FakeLocalRenderer(b"fabricated-comfy-video-blob"*60)
                    with self.assertRaises((ValueError,RuntimeError)):
                        render_actual_generated_scene(actual,root/"fake",
                            comfy_endpoint="http://127.0.0.1:8188",
                            client=false,probe=lambda path:{"seconds":1})
                    # A durable private prompt checkpoint may correctly be
                    # published even when the returned video is invalid.
                    # The public director film must NEVER be published.
                    self.assertFalse((root/"fake"/"filmed.mp4").exists())
                original=render_actual_generated_scene(actual,root/"true",
                    comfy_endpoint="http://127.0.0.1:8188",client=fake)
                accepted=Path(original["clip"])
                self.assertTrue(original["full_original_video_and_sound_decoded"])
                self.assertTrue(accepted.is_file())
                previous=accepted.read_bytes()
                with self.assertRaises(FileExistsError):
                    render_actual_generated_scene(actual,root/"true",
                        comfy_endpoint="http://127.0.0.1:8188",client=fake)
                self.assertEqual(accepted.read_bytes(),previous)
                self.assertFalse(list((root/"true").glob(".zx7-comfy-stage-*")))
                import studio_next.comfy_video_runtime as runtime
                original_link=os.link
                first=False
                concurrent=root/"collision"
                def race(source,destination,*args,**kwargs):
                    nonlocal first
                    if Path(destination)==concurrent/"filmed.mp4":
                        shutil.copyfile(fixture,destination)
                        first=True
                    return original_link(source,destination,*args,**kwargs)
                with patch.object(runtime.os,"link",side_effect=race):
                    with self.assertRaises(FileExistsError):
                        render_actual_generated_scene(actual,concurrent,
                            comfy_endpoint="http://127.0.0.1:8188",client=fake)
                self.assertTrue(first)
                self.assertEqual((concurrent/"filmed.mp4").read_bytes(),previous)
                self.assertFalse(list(concurrent.glob(".zx7-comfy-stage-*")))

    def test_untrusted_local_comfy_video_filename_never_escapes_owner_workspace(self):
        class MaliciousLocalClient:
            def create(self,graph):return "task-id"
            def wait(self,task,node):return "../someone-elses-finished-film.mp4",b"bad"
        with tempfile.TemporaryDirectory() as project:
            root=Path(project)
            with patch("studio_next.comfy_video_runtime._approved_graph",
                       return_value=({"node":{"inputs":{}}},
                                     {"output_node":"node"},"f"*64)),patch(
                       "studio_next.comfy_video_runtime.discover_local_generators",
                       return_value={"video_generation_options":[{
                           "id":job()["model_id"],
                           "ready_for_independent_execution_trial":True}]}):
                with self.assertRaisesRegex(ValueError,"Untrusted ComfyUI"):
                    render_actual_generated_scene(job(),root/"movies",
                         comfy_endpoint="http://127.0.0.1:8188",
                         client=MaliciousLocalClient())
            self.assertFalse((root/"someone-elses-finished-film.mp4").exists())

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

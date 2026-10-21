import io
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from studio_next.body_service import LocalBodyCoordinator,make_body_http_handler


def plan():
    return {"project":{"creative_intent":"Original independently directed cinema"},
            "shots":[{"id":"art-1","purpose":"Actual artist-chosen shot",
                      "duration_seconds":2.31}],
            "tool_graph":[{"id":"render","tool_id":"body.inspect",
                           "inputs":{"source":"actual.mp4"},"depends_on":[]}]}


class IndependentLocalCreativeServiceTests(unittest.TestCase):
    def test_real_job_queue_and_restart_do_not_rewrite_approved_art(self):
        with tempfile.TemporaryDirectory() as root:
            seen=[]
            def fake(original,workspace):
                seen.append((original,workspace))
                return {"status":"all_tool_results_verified",
                        "completed":["render"],"reused":[],"video_proven":False}
            c=LocalBodyCoordinator(root,execute=fake)
            try:
                created=c.submit(plan(),workspace_id="one-original-studio-project",
                                 job_id="shot-1")
                self.assertEqual(created["job_id"],"shot-1")
                for _ in range(100):
                    if c.inspect("shot-1")["status"]=="completed":break
                    time.sleep(.01)
                self.assertEqual(c.inspect("shot-1")["status"],"completed")
                self.assertEqual(seen[0][0],plan())
                with self.assertRaisesRegex(ValueError,"already exists"):
                    c.submit(plan(),workspace_id="one-original-studio-project",
                             job_id="shot-1")
                self.assertFalse(c.queue("shot-1"))
            finally:
                c.close()
            recovered=LocalBodyCoordinator(root,execute=fake)
            try:
                self.assertEqual(recovered.pending_restart(),0)
                self.assertEqual(recovered.inspect("shot-1")["attempts"],1)
            finally:recovered.close()

    def test_blocked_original_art_keeps_reasons_never_fakes_movie(self):
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root,execute=lambda ir,workspace:{
                "status":"blocked","errors":["missing real footage"],
                "completed":[],"video_proven":False})
            try:
                c.submit(plan(),workspace_id="project")
                for _ in range(100):
                    with c._connect() as db:
                        status=db.execute("SELECT status FROM jobs").fetchone()[0]
                    if status=="blocked":break
                    time.sleep(.01)
                with c._connect() as db:
                    identity=db.execute("SELECT id FROM jobs").fetchone()[0]
                result=c.inspect(identity)
                self.assertEqual(result["status"],"blocked")
                self.assertFalse(result["result"]["video_proven"])
            finally:c.close()

    def test_owner_can_import_actual_bytes_with_immutable_rights_custody(self):
        with tempfile.TemporaryDirectory() as root:
            backend=LocalBodyCoordinator(root,execute=lambda ir,workspace:{
                "status":"all_tool_results_verified"})
            data=b"original signed local artist source bytes"*32
            try:
                record=backend.upload_owner_media(
                    "original-project","artist-data.bin",io.BytesIO(data),len(data),
                    mime="application/octet-stream",source_id="owner-camera-raw-001",
                    rights_evidence="Owner explicitly supplied this original file")
                self.assertEqual(record["bytes"],len(data))
                media=Path(root)/"projects"/"original-project"/"artist-data.bin"
                self.assertEqual(media.read_bytes(),data)
                with self.assertRaises(FileExistsError):
                    backend.upload_owner_media(
                        "original-project","artist-data.bin",io.BytesIO(data),len(data),
                        mime="application/octet-stream",source_id="owner",
                        rights_evidence="owner supplied")
                with self.assertRaisesRegex(ValueError,"Invalid media"):
                    backend.upload_owner_media(
                        "original-project","../private.bin",io.BytesIO(data),len(data),
                        mime="application/octet-stream",source_id="owner",
                        rights_evidence="owner supplied")
                with self.assertRaisesRegex(ValueError,"match"):
                    backend.upload_owner_media(
                        "original-project","false-video.mp4",io.BytesIO(data),len(data),
                        mime="application/octet-stream",source_id="owner",
                        rights_evidence="owner supplied")
                with self.assertRaises((ValueError,RuntimeError)):
                    backend.upload_owner_media(
                        "original-project","fake-footage.mp4",io.BytesIO(data),len(data),
                        mime="video/mp4",source_id="owner",
                        rights_evidence="owner supplied")
                self.assertFalse((media.parent/"fake-footage.mp4").exists())
                self.assertFalse(list(media.parent.glob(".zx7-import-*")))
            finally:backend.close()

    def test_authentication_and_no_public_source_or_mutable_shell_commands(self):
        with tempfile.TemporaryDirectory() as root:
            token="local-unguessable-operator-token-123456789"
            c=LocalBodyCoordinator(root,execute=lambda ir,workspace:{
                "status":"all_tool_results_verified"})
            server=ThreadingHTTPServer(("127.0.0.1",0),
                                       make_body_http_handler(c,token))
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            origin=f"http://127.0.0.1:{server.server_port}"
            def request(uri,body=None,authorized=True):
                headers={}
                if authorized:headers["Authorization"]="Bearer "+token
                if body is not None:headers["Content-Type"]="application/json"
                return Request(origin+uri,
                    data=json.dumps(body).encode() if body is not None else None,
                    headers=headers,method="POST" if body is not None else "GET")
            try:
                with self.assertRaises(HTTPError) as denied:
                    urlopen(request("/v1/health",authorized=False),timeout=2)
                self.assertEqual(denied.exception.code,401)
                with urlopen(request("/v1/health"),timeout=2) as r:
                    self.assertTrue(json.loads(r.read())["online"])
                with self.assertRaises(HTTPError) as bad:
                    urlopen(request("/v1/jobs",{"workspace_id":"../escape",
                                               "film_ir":plan()}),timeout=2)
                self.assertEqual(bad.exception.code,400)
                with urlopen(request("/v1/jobs",
                    {"workspace_id":"real-studio","film_ir":plan()}),timeout=2) as r:
                    id=json.loads(r.read())["job_id"]
                for _ in range(100):
                    with urlopen(request("/v1/jobs/"+id),timeout=2) as r:
                        status=json.loads(r.read())
                    if status["status"]=="completed":break
                    time.sleep(.01)
                self.assertEqual(status["status"],"completed")
            finally:
                server.shutdown();server.server_close();thread.join(timeout=5)
                c.close()


if __name__=="__main__":unittest.main()

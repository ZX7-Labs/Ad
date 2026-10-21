import hashlib
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from studio_next.body_client import ZX7BodyClient
from studio_next.body_service import LocalBodyCoordinator,make_body_http_handler


class StandaloneNoAssistantLocalBodyClientTests(unittest.TestCase):
    def test_remote_endpoint_cannot_receive_private_film_or_bearer_token(self):
        for endpoint in ("https://studio.example","http://example.org:8765",
                         "http://user:password@127.0.0.1:8765",
                         "http://127.0.0.1:8765/other"):
            with self.assertRaises(ValueError):
                ZX7BodyClient(endpoint=endpoint,token="secure-local-token-"+"y"*32)

    def test_operator_can_run_and_download_real_files_without_chatgpt(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)
            service=LocalBodyCoordinator(folder/"runtime",execute=lambda ir,w:{
                "status":"all_tool_results_verified","completed":["media"],
                "video_proven":False})
            token="zx7-production-owner-"+("a"*48)
            server=ThreadingHTTPServer(("127.0.0.1",0),
                                       make_body_http_handler(service,token))
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                client=ZX7BodyClient(endpoint=f"http://127.0.0.1:{server.server_port}",
                                     token=token)
                original=folder/"original-takes.bin"
                payload=b"artistic original camera materials"*4096
                original.write_bytes(payload)
                receipt=client.upload("film-owner",original,
                    mime="application/octet-stream",source_id="studio-मूल-स्रोत",
                    rights_evidence="परीक्षण सामग्री का हिंदी विवरण")
                self.assertEqual(receipt["asset_id"],hashlib.sha256(payload).hexdigest())
                screenplay={
                    "project":{"creative_intent":"An original artistic film"},
                    "shots":[{"id":"original","purpose":"True acting","duration_seconds":4.5}],
                    "tool_graph":[{"id":"owned-source","tool_id":"body.inspect",
                        "inputs":{"source":"original-takes.bin"},"depends_on":[]}]}
                created=folder/"original-film-ir.json"
                created.write_text(json.dumps(screenplay),encoding="utf-8")
                run=client.submit(created,"film-owner")
                status=client.wait(run["job_id"],poll_seconds=.1,max_seconds=4)
                self.assertEqual(status["status"],"completed")
                self.assertEqual(status["attempts"],1)
                artifacts=client.artifacts(run["job_id"])
                self.assertIn("original-takes.bin",[x["path"] for x in artifacts["assets"]])
                target=folder/"received-original.bin"
                delivered=client.download(run["job_id"],"original-takes.bin",target)
                self.assertEqual(delivered["sha256"],receipt["asset_id"])
                self.assertEqual(target.read_bytes(),payload)
                with self.assertRaises(FileExistsError):
                    client.download(run["job_id"],"original-takes.bin",target)
                bad=ZX7BodyClient(endpoint=f"http://127.0.0.1:{server.server_port}",
                                   token="different-trusted-local-token-"+"z"*36)
                with self.assertRaises(RuntimeError):
                    bad.status(run["job_id"])
            finally:
                server.shutdown();server.server_close()
                thread.join(timeout=5)
                service.close()


if __name__=="__main__":unittest.main()

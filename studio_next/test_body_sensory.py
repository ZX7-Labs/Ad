"""Trusted small feedback snapshot must not hallucinate finished video or style."""
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from studio_next.body_sensory import sense_body_job
from studio_next.body_service import LocalBodyCoordinator,make_body_http_handler


def original_ir():
    return {"project":{"creative_intent":"Real independently authored original work"},
      "shots":[{"id":"artist1","purpose":"Performer requested; source may be blocked"}],
      "tool_graph":[]}


class FilmBodySensoryReceiptTests(unittest.TestCase):
    def test_blocked_original_shot_yields_facts_not_a_hallucinated_movie(self):
        with tempfile.TemporaryDirectory() as root:
            seen=[]
            def work(ir,location):
                seen.append(ir)
                return {"status":"blocked","errors":["Original real performer source not available"],
                        "video_proven":False,"completed":[]}
            owner=LocalBodyCoordinator(root,execute=work)
            try:
                owner.submit(original_ir(),workspace_id="original-film",job_id="first")
                for _ in range(200):
                    if owner.inspect("first")["status"]=="blocked":break
                    time.sleep(.01)
                sensed=sense_body_job(owner,"first")
                self.assertEqual(sensed["job_state"],"blocked")
                self.assertEqual(sensed["failure_reasons"],
                                 ["Original real performer source not available"])
                self.assertFalse(sensed["movie_physically_decoded_by_this_observation"])
                self.assertFalse(sensed["cinematic_or_narrative_quality_certified"])
                self.assertEqual(seen[0],original_ir())
                self.assertFalse(sensed["actual_durable_stage_database_found"])
                self.assertEqual(sensed["stage_observation_scope"],
                                 "no_verified_project_lineage")
                self.assertTrue(
                    sensed["stage_entries_are_shared_film_cache_not_job_attempt_receipts"])
                self.assertEqual(sensed["recent_native_stages"],[])
                for bad in ("../../../etc/shadow","","fake job with spaces"):
                    with self.assertRaises(ValueError):
                        sense_body_job(owner,bad)
            finally:
                owner.close()

    def test_completed_executor_does_not_imply_media_or_aesthetic_quality(self):
        with tempfile.TemporaryDirectory() as root:
            owner=LocalBodyCoordinator(root,execute=lambda ir,w:{
                "status":"all_tool_results_verified",
                "completed":["text-only"],"video_proven":True})
            try:
                owner.submit(original_ir(),workspace_id="different",
                             job_id="no-actual-film")
                for _ in range(200):
                    if owner.inspect("no-actual-film")["status"]=="completed":break
                    time.sleep(.01)
                sensed=sense_body_job(owner,"no-actual-film")
                self.assertEqual(sensed["job_state"],"completed")
                self.assertFalse(sensed["movie_physically_decoded_by_this_observation"])
                self.assertNotIn("video_proven",sensed)
                self.assertIsNotNone(sensed["persisted_result_sha256"])
            finally:owner.close()


    def test_sensory_does_not_misattribute_other_film_stages_in_shared_workspace(self):
        from studio_next.durable_graph import DurableFilmGraph,durable_project_key
        with tempfile.TemporaryDirectory() as root:
            owner=LocalBodyCoordinator(root,execute=lambda ir,w:{
                "status":"blocked","errors":["Original shot unrenderable"]})
            try:
                a=original_ir()
                b=original_ir()
                b["project"]={"creative_intent":"Different creative original"}
                a["tool_graph"]=[{"id":"shot","tool_id":"body.inspect",
                                 "inputs":{"source":"not-used.mp4"},"depends_on":[]}]
                b["tool_graph"]=[{"id":"shot","tool_id":"body.inspect",
                                 "inputs":{"source":"not-used.mp4"},"depends_on":[]}]
                own=owner._workspace("shared-workspace");own.mkdir(parents=True)
                ledger=DurableFilmGraph(own/"production.sqlite3")
                bkey=durable_project_key(b,fact_ids=set(),allowed_access={"read","write"})
                ledger.start_or_reuse(bkey,"shot","b-hash",
                       trusted_idempotent=True,existing_result_verifier=lambda _:True,
                       lease_seconds=120)
                owner.submit(a,workspace_id="shared-workspace",job_id="original-a")
                for _ in range(200):
                    if owner.inspect("original-a")["status"]=="blocked":break
                    time.sleep(.01)
                observation=sense_body_job(owner,"original-a")
                self.assertEqual(observation["recent_native_stages"],[])
                self.assertEqual(observation["stage_observation_scope"],
                                 "no_verified_project_lineage")
                self.assertFalse(observation["actual_durable_stage_database_found"])
                self.assertFalse(observation["movie_physically_decoded_by_this_observation"])
            finally:
                owner.close()

    def test_authenticated_phone_api_exposes_bounded_sensor_without_file_leak(self):
        with tempfile.TemporaryDirectory() as root:
            owner=LocalBodyCoordinator(root,execute=lambda ir,w:{
                "status":"blocked","errors":["No legally verified visual source"]})
            owner.submit(original_ir(),workspace_id="my-movie",job_id="legal-block")
            for _ in range(200):
                if owner.inspect("legal-block")["status"]=="blocked":break
                time.sleep(.01)
            token="local-owner-"+("z"*48)
            server=ThreadingHTTPServer(("127.0.0.1",0),
                         make_body_http_handler(owner,token))
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base=f"http://127.0.0.1:{server.server_port}"
            try:
                with self.assertRaises(HTTPError) as err:
                    urlopen(base+"/v1/jobs/legal-block/sense",timeout=5)
                self.assertEqual(err.exception.code,401)
                req=Request(base+"/v1/jobs/legal-block/sense",
                       headers={"Authorization":"Bearer "+token})
                with urlopen(req,timeout=5) as response:
                    output=json.loads(response.read())
                self.assertEqual(output["job_state"],"blocked")
                self.assertEqual(output["failure_reasons"],
                                 ["No legally verified visual source"])
                self.assertNotIn("original_ir",str(output))
                self.assertFalse(output["movie_physically_decoded_by_this_observation"])
            finally:
                server.shutdown();server.server_close();thread.join(timeout=4)
                owner.close()

if __name__=="__main__":
    unittest.main()

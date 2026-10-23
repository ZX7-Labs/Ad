"""Cross-branch unified brain-to-BODY interface, actual owner/job boundary."""
import tempfile
import time
import unittest
from pathlib import Path

from studio_next.body_service import LocalBodyCoordinator
from studio_next.body_signal import BodyAuthority,LiveBodySignal,BodyCommandRejected


def authored_film():
    return {"project":{"creative_intent":"Independent original cinema, no aesthetic presets"},
       "shots":[{"id":"shot-original","purpose":"One self-directed source inspection"}],
       "tool_graph":[{"id":"inspect","tool_id":"body.resolve_asset",
           "purpose":"Read actual original media properties",
           "inputs":{"asset_id":"0000000000000000000000000000000000000000000000000000000000000000","attestation_id":"owner-has-not-provided"},"depends_on":[]}]}


class OneBrainConnectedBodyRegression(unittest.TestCase):
    def test_authority_and_unguessed_schema_are_real_and_bounded(self):
        with tempfile.TemporaryDirectory() as root:
            coordinator=LocalBodyCoordinator(root,execute=lambda ir,w:{
                "status":"blocked","errors":["Real frame material unavailable"]})
            try:
                readonly=LiveBodySignal(coordinator,authority=BodyAuthority(
                    workspace_ids=frozenset({"director-a"})))
                abilities=readonly.discover("director-a",limit=1)
                self.assertEqual(len(abilities["affordances"]),1)
                self.assertNotIn("input_schema",str(abilities))
                view=readonly.describe("director-a","body.resolve_asset")
                self.assertEqual(view["status"],"ready_to_preflight")
                self.assertIn("asset_id",view["input_schema"]["required"])
                with self.assertRaises(PermissionError):
                    readonly.describe("director-a","body.render_edit_owned")
                with self.assertRaises(PermissionError):
                    readonly.discover("director-b")
                with self.assertRaises(PermissionError):
                    readonly.command("submit",{
                        "film_ir":authored_film(),"workspace_id":"director-a"})
                with self.assertRaises(ValueError):
                    BodyAuthority(workspace_ids=frozenset({"director-a"}),
                      operations=frozenset({"submit"}),tool_access=frozenset({"read"}))
                with self.assertRaises(TypeError):
                    LiveBodySignal(coordinator,authority={"all":"write"})
            finally:
                coordinator.close()

    def test_host_scope_prevents_cross_workspace_job_inspection_and_writes(self):
        with tempfile.TemporaryDirectory() as root:
            owner=LocalBodyCoordinator(root,execute=lambda ir,w:{
                "status":"blocked","errors":["Genuine creative original unavailable"]})
            try:
                owner.submit(authored_film(),workspace_id="private-b",
                             job_id="job-b")
                def done(name,status):
                    for _ in range(180):
                        if owner.inspect(name)["status"]==status:
                            return
                        time.sleep(.01)
                    self.fail("Job never reached observed state")
                done("job-b","blocked")
                allowed=BodyAuthority(workspace_ids=frozenset({"studio-a"}),
                    operations=frozenset({"submit","retry","pause"}),
                    tool_access=frozenset({"read","write"}))
                nerve=LiveBodySignal(owner,authority=allowed)
                with self.assertRaises(PermissionError):
                    nerve.observe("job-b",include_artifacts=True)
                with self.assertRaises(PermissionError):
                    nerve.command("retry",{"job_id":"job-b"})
                with self.assertRaises(PermissionError):
                    nerve.command("submit",{
                        "film_ir":authored_film(),"workspace_id":"private-b"})
                with self.assertRaises(BodyCommandRejected):
                    nerve.command("submit",{"film_ir":authored_film(),
                        "workspace_id":"studio-a","paid":True})
                with self.assertRaises(BodyCommandRejected):
                    nerve.command("submit",{"film_ir":{},
                        "workspace_id":"studio-a"})
                permitted=nerve.command("submit",{
                    "film_ir":authored_film(),"workspace_id":"studio-a"})
                done(permitted["job_id"],"blocked")
                observed=nerve.observe(permitted["job_id"],include_artifacts=True)
                self.assertEqual(observed["job_state"],"blocked")
                self.assertFalse(observed["movie_physically_decoded_by_this_observation"])
                self.assertFalse(observed["cinematic_or_narrative_quality_certified"])
                self.assertEqual(observed["workspace_media"],[])
                self.assertTrue(observed["workspace_media_is_not_job_specific_receipt"])
                retry=nerve.command("retry",{"job_id":permitted["job_id"]})
                self.assertTrue(retry["original_film_ir_unchanged"])
                done(permitted["job_id"],"blocked")
                with self.assertRaises(PermissionError):
                    nerve.command("cancel",{"job_id":permitted["job_id"]})
            finally:
                owner.close()

    def test_no_claim_about_generators_or_uninstalled_tools(self):
        with tempfile.TemporaryDirectory() as root:
            c=LocalBodyCoordinator(root,execute=lambda ir,w:{"status":"blocked"})
            try:
                nerve=LiveBodySignal(c,authority=BodyAuthority(
                    workspace_ids=frozenset({"a"}),
                    tool_access=frozenset({"read","write"})))
                available=nerve.discover("a",include_unavailable=True)
                self.assertFalse(available["complete_studio_certified"])
                for item in available["affordances"]:
                    if item["tool_id"]=="body.generate_video" and item["status"]=="needs_setup":
                        desc=nerve.describe("a","body.generate_video")
                        self.assertEqual(desc["status"],"needs_setup")
                        break
                with self.assertRaises(BodyCommandRejected):
                    nerve.command("run-shell",{"command":"false"})
            finally:c.close()




@unittest.skipUnless(__import__("shutil").which("ffmpeg") and
                     __import__("shutil").which("ffprobe"),
                     "Actual native video and sound required for model-facing physical loop")
class RealConnectedBrainToOwnedCinemaTests(unittest.TestCase):
    def test_host_authorized_model_interface_executes_and_observes_actual_decoded_film(self):
        import json
        import subprocess
        from studio_next.media_vault import MediaVault,sha256_file
        from studio_next.production_qc import full_decode_inspection
        with tempfile.TemporaryDirectory() as root:
            service=LocalBodyCoordinator(root)
            try:
                workspace=service._workspace("real-owner-film")
                workspace.mkdir(parents=True,exist_ok=True)
                source=workspace/"true-camera.mp4"
                generated=subprocess.run(["ffmpeg","-hide_banner",
                    "-loglevel","error","-nostdin","-y",
                    "-f","lavfi","-i","color=c=0x2060aa:s=160x90:r=24:d=0.75",
                    "-f","lavfi","-i",
                    "sine=frequency=460:sample_rate=48000:duration=0.75",
                    "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",
                    "-shortest",str(source)],capture_output=True,text=True,timeout=55)
                self.assertEqual(generated.returncode,0,generated.stderr)
                vault=MediaVault(workspace/"vault")
                custody=vault.ingest(source,mime="video/mp4",
                    rights="owner_supplied",source_type="owner_upload",
                    source_id="model-nerve-actual-camera",
                    evidence="Actual decoded original source plus soundtrack",
                    owner_or_generator="authorized-owner")
                edit={"format":{"width":160,"height":90,"fps":24,
                         "framing":"fit","background":"#080F1C"},
                    "clips":[{"id":"actual-scene","source":source.name,
                      "rights":"owner_supplied","audio":"preserve_source",
                      "asset_id":custody["asset_id"],
                      "attestation_id":custody["attestation_id"]}]}
                (workspace/"owner-cut.json").write_text(json.dumps(edit))
                authored={"project":{"creative_intent":
                          "One model-authored original cinematic cut with real rights"},
                          "shots":[{"id":"actual-scene","purpose":
                              "Decode original camera movement and recorded sound",
                              "duration_seconds":0.75}],"assets":[],
                          "tool_graph":[
                            {"id":"original-edit","tool_id":"body.render_edit_owned",
                             "purpose":"Physically cut only licensed original footage",
                             "inputs":{"edit":"owner-cut.json",
                                       "out":"accepted-model-film.mp4"},
                             "depends_on":[]},
                            {"id":"audited-original","tool_id":"body.asset_vault",
                             "purpose":"Preserve graph-proven actual edited original",
                             "inputs":{"source_witness":{"$node_output":"original-edit"}},
                             "depends_on":["original-edit"]}]}
                host=BodyAuthority(workspace_ids=frozenset({"real-owner-film"}),
                    tool_access=frozenset({"read","write"}),
                    operations=frozenset({"submit"}))
                model_interface=LiveBodySignal(service,authority=host)
                chosen=model_interface.describe("real-owner-film","body.render_edit_owned")
                self.assertEqual(chosen["status"],"ready_to_preflight")
                preview=model_interface.preflight("real-owner-film",
                    "body.render_edit_owned",{"edit":"owner-cut.json",
                                               "out":"accepted-model-film.mp4"})
                self.assertEqual(preview["readiness"],"preflight_checked_not_executed")
                self.assertFalse(preview["real_movie_rendered"])
                job=model_interface.command("submit",{
                    "film_ir":authored,"workspace_id":"real-owner-film"})
                for _ in range(220):
                    observed=model_interface.observe(job["job_id"])
                    if observed["job_state"] in ("completed","failed","blocked"):
                        break
                    time.sleep(.04)
                self.assertEqual(observed["job_state"],"completed",observed)
                self.assertFalse(observed["movie_physically_decoded_by_this_observation"])
                movie=workspace/"accepted-model-film.mp4"
                physical=full_decode_inspection(movie,expected={
                    "width":160,"height":90,"require_audio":True})
                self.assertTrue(physical["full_picture_and_sound_decoder_completed"])
                self.assertTrue(physical["technical_delivery_verified"])
                self.assertEqual(vault.inspect(sha256_file(movie))["asset_id"],
                                 sha256_file(movie))
                with self.assertRaises(PermissionError):
                    model_interface.command("retry",{"job_id":job["job_id"]})
                with self.assertRaises(PermissionError):
                    model_interface.observe("some-other-job")
            finally:
                service.close()


if __name__=="__main__":
    unittest.main()

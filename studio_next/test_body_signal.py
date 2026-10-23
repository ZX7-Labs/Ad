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


if __name__=="__main__":
    unittest.main()

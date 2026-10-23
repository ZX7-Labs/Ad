"""Cross-branch unified brain-to-BODY interface, actual owner/job boundary."""
import json
import os
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
                self.assertEqual(abilities["host_authorized_commands"],[])
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

    def test_creative_model_can_publish_immutable_typed_plan_without_exec_or_licensing(self):
        with tempfile.TemporaryDirectory() as root:
            coordinator=LocalBodyCoordinator(root,execute=lambda ir,w:{
                "status":"blocked","errors":["physical film unavailable"]})
            try:
                access=BodyAuthority(
                    workspace_ids=frozenset({"authorized-editor"}),
                    operations=frozenset({"author_plan"}),
                    tool_access=frozenset({"read","write"}))
                author=LiveBodySignal(coordinator,authority=access)
                advertised=author.discover("authorized-editor")
                self.assertEqual(advertised["host_authorized_commands"],[
                    {"action":"author_plan","required_arguments":[
                        "workspace_id","tool_id","document"]}])
                self.assertFalse(advertised["complete_studio_certified"])
                document={"format":{"width":128,"height":96,"fps":12,
                                     "framing":"fit","background":"#111111"},
                          "clips":[],"story":"This is artist data, not approved footage"}
                arguments={"workspace_id":"authorized-editor",
                           "tool_id":"body.render_edit_owned",
                           "document":document}
                first=author.command("author_plan",arguments)
                second=author.command("author_plan",arguments)
                self.assertEqual(first["path"],second["path"])
                self.assertEqual(first["sha256"],second["sha256"])
                self.assertFalse(first["film_physically_rendered"])
                self.assertFalse(first["source_legal_rights_certified"])
                source=coordinator._workspace("authorized-editor")/first["path"]
                self.assertTrue(source.is_file())
                self.assertEqual(json.loads(source.read_text()),document)
                self.assertEqual(len(list(source.parent.glob("*.json"))),1)
                self.assertFalse(list(source.parent.glob(".zx7-plan-*")))
                with self.assertRaises(PermissionError):
                    author.command("author_plan",{**arguments,
                        "workspace_id":"another-owner"})
                with self.assertRaises(PermissionError):
                    author.command("author_plan",{**arguments,
                        "tool_id":"body.render_edit"})
                with self.assertRaises(BodyCommandRejected):
                    author.command("author_plan",{**arguments,
                        "document":{"unbounded":"x"*262145}})
                with self.assertRaises(BodyCommandRejected):
                    author.command("author_plan",{**arguments,
                        "document":{"invalid_float":float("nan")}})
                with self.assertRaises(BodyCommandRejected):
                    author.command("author_plan",{**arguments,
                        "tool_id":"body.resolve_asset"})
                source.write_text('{"tampered":"previous approved media"}')
                with self.assertRaises(PermissionError):
                    author.command("author_plan",arguments)
                with self.assertRaises(PermissionError):
                    author.command("submit",{
                        "workspace_id":"authorized-editor","film_ir":authored_film()})
            finally:
                coordinator.close()

    def test_cross_editor_symlink_cannot_author_into_another_owner_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            coordinator=LocalBodyCoordinator(root,execute=lambda ir,w:{"status":"blocked"})
            try:
                other=coordinator._workspace("editor-b")
                other.mkdir()
                (other/"protected-film.txt").write_text("original owner B film")
                (coordinator.projects/"editor-a").symlink_to(
                    other,target_is_directory=True)
                signal=LiveBodySignal(coordinator,authority=BodyAuthority(
                    workspace_ids=frozenset({"editor-a"}),
                    operations=frozenset({"author_plan"}),
                    tool_access=frozenset({"read","write"})))
                with self.assertRaisesRegex(ValueError,"alias"):
                    signal.command("author_plan",{
                        "workspace_id":"editor-a",
                        "tool_id":"body.render_edit_owned",
                        "document":{"original":"untrusted cross-owner overwrite"}})
                self.assertFalse((other/"brain-authored").exists())
                self.assertEqual((other/"protected-film.txt").read_text(),
                                 "original owner B film")
            finally:
                coordinator.close()

    def test_model_cannot_discover_or_execute_legacy_unattested_editors(self):
        with tempfile.TemporaryDirectory() as root:
            owner=LocalBodyCoordinator(root,execute=lambda ir,w:{
                "status":"blocked","errors":["No original physical movie"]})
            try:
                signal=LiveBodySignal(owner,authority=BodyAuthority(
                    workspace_ids=frozenset({"trusted-director"}),
                    operations=frozenset({"submit"}),
                    tool_access=frozenset({"read","write"})))
                discovered=[]
                cursor=None
                while True:
                    page=signal.discover("trusted-director",limit=40,
                                         include_unavailable=True,cursor=cursor)
                    discovered.extend(x["tool_id"] for x in page["affordances"])
                    cursor=page["next_cursor"]
                    if cursor is None:break
                self.assertNotIn("body.render_edit",discovered)
                self.assertNotIn("body.otio",discovered)
                self.assertIn("body.render_edit_owned",discovered)
                for old in ("body.render_edit","body.otio"):
                    with self.subTest(tool=old):
                        with self.assertRaises(PermissionError):
                            signal.describe("trusted-director",old)
                        with self.assertRaises(PermissionError):
                            signal.preflight("trusted-director",old,{})
                        attempted=authored_film()
                        attempted["tool_graph"][0]["tool_id"]=old
                        with self.assertRaises(BodyCommandRejected):
                            signal.command("submit",{
                                "workspace_id":"trusted-director",
                                "film_ir":attempted})
            finally:
                owner.close()

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
    def test_authorized_brain_authors_multilayer_mask_sound_plan_and_body_makes_real_film(self):
        # A stand-in test caller supplies artistic data; no AI inference is
        # claimed. All media engines, pixels, source rights, temporal masking,
        # soundtrack, physical decoding and durable render are real.
        import importlib.util
        import json
        import subprocess
        if importlib.util.find_spec("PIL") is None:
            self.skipTest("A true native PNG pixel generator is required")
        from PIL import Image
        from studio_next.media_vault import MediaVault,sha256_file
        from studio_next.production_qc import full_decode_inspection
        with tempfile.TemporaryDirectory() as home:
            body=LocalBodyCoordinator(home)
            try:
                root=body._workspace("original-director-project")
                root.mkdir(parents=True,exist_ok=True)
                vault=MediaVault(root/"vault")
                red=root/"original-animated-graphic.png"
                Image.new("RGBA",(64,64),(240,40,25,255)).save(red)
                mask=root/"original-artist-alpha.png"
                art=Image.new("L",(64,64),0)
                for y in range(64):
                    for x in range(30):
                        art.putpixel((x,y),255)
                art.save(mask)
                track=root/"original-composer-note.wav"
                rendered=subprocess.run(["ffmpeg","-hide_banner","-loglevel",
                    "error","-nostdin","-y","-f","lavfi","-i",
                    "sine=frequency=440:sample_rate=48000:duration=1",
                    "-c:a","pcm_s16le",str(track)],
                    capture_output=True,text=True,timeout=50)
                self.assertEqual(rendered.returncode,0,rendered.stderr)
                def attest(src,mime,ident):
                    return vault.ingest(src,mime=mime,
                        rights="owner_supplied",source_type="owner_upload",
                        source_id=ident,evidence="Physical owner original verified source",
                        owner_or_generator="authorized-original-artist")
                image=attest(red,"image/png","real-original-red")
                matte=attest(mask,"image/png","real-original-opacity")
                sound=attest(track,"audio/wav","real-original-audio")
                directives={
                    "canvas":{"width":96,"height":64,"fps":12,"duration":1,
                              "background":"#061B48"},
                    "video_layers":[{
                        "id":"artist-painted-layer","source":red.name,
                        "asset_id":image["asset_id"],
                        "attestation_id":image["attestation_id"],
                        "source_kind":"still_image","start":0,"source_in":0,
                        "duration":1,"x":14,"y":0,"width":64,"height":64,
                        "opacity":1,
                        "matte":{"source":mask.name,
                                 "asset_id":matte["asset_id"],
                                 "attestation_id":matte["attestation_id"],
                                 "source_kind":"still_image","source_in":0,
                                 "invert":False}}],
                    "audio_tracks":[{
                        "id":"director-left-score","source":track.name,
                        "asset_id":sound["asset_id"],
                        "attestation_id":sound["attestation_id"],
                        "start":0,"source_in":0,"duration":1,
                        "gain_db":-3,"stereo_balance":-1}]}
                host=BodyAuthority(
                    workspace_ids=frozenset({"original-director-project"}),
                    operations=frozenset({"author_plan","submit"}),
                    tool_access=frozenset({"read","write"}))
                brain=LiveBodySignal(body,authority=host)
                found=brain.describe("original-director-project",
                                     "body.composite_mix")
                self.assertEqual(found["status"],"ready_to_preflight")
                written=brain.command("author_plan",{
                    "workspace_id":"original-director-project",
                    "tool_id":"body.composite_mix","document":directives})
                self.assertTrue(written["tool_ready_to_execute_now"])
                self.assertFalse(written["film_physically_rendered"])
                path=written["path"]
                review=brain.preflight("original-director-project",
                    "body.composite_mix",
                    {"plan":path,"out":"brain-physically-directed-film.mp4"})
                self.assertEqual(review["readiness"],
                                 "preflight_checked_not_executed")
                project={
                    "project":{"creative_intent":
                        "Author-directed original graphic roto, music balance and visual timeline"},
                    "shots":[{"id":"artist-shot","purpose":
                        "Actual rights checked masked motion scene and original sound"}],
                    "tool_graph":[{
                        "id":"composite","tool_id":"body.composite_mix",
                        "purpose":"Physically compose licensed image, mask and sound",
                        "inputs":{"plan":path,
                                  "out":"brain-physically-directed-film.mp4"},
                        "depends_on":[]},{
                        "id":"rights_archive","tool_id":"body.asset_vault",
                        "purpose":"Preserve exact genuine renderer movie in durable source custody",
                        "inputs":{"source_witness":{"$node_output":"composite"}},
                        "depends_on":["composite"]}]}
                job=brain.command("submit",{
                    "workspace_id":"original-director-project",
                    "film_ir":project})
                observation=None
                for _ in range(300):
                    observation=brain.observe(job["job_id"])
                    if observation["job_state"] in ("completed","blocked","failed"):
                        break
                    time.sleep(.04)
                self.assertEqual(observation["job_state"],"completed",observation)
                film=root/"brain-physically-directed-film.mp4"
                proof=full_decode_inspection(film,expected={
                    "width":96,"height":64,"require_audio":True})
                self.assertTrue(proof["technical_delivery_verified"])
                self.assertTrue(proof["full_picture_and_sound_decoder_completed"])
                self.assertEqual(vault.inspect(sha256_file(film))["asset_id"],
                                 sha256_file(film))
                self.assertEqual(sha256_file(red),image["asset_id"])
                self.assertEqual(sha256_file(mask),matte["asset_id"])
                self.assertEqual(sha256_file(track),sound["asset_id"])
                self.assertFalse(written["independent_artistic_quality_approved"])
            finally:
                body.close()

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
                authored={"project":{"creative_intent":
                          "One model-authored original cinematic cut with real rights"},
                          "shots":[{"id":"actual-scene","purpose":
                              "Decode original camera movement and recorded sound",
                              "duration_seconds":0.75}],"assets":[],
                          "tool_graph":[
                            {"id":"original-edit","tool_id":"body.render_edit_owned",
                             "purpose":"Physically cut only licensed original footage",
                             "inputs":{"edit":"awaiting-model-plan",
                                       "out":"accepted-model-film.mp4"},
                             "depends_on":[]},
                            {"id":"audited-original","tool_id":"body.asset_vault",
                             "purpose":"Preserve graph-proven actual edited original",
                             "inputs":{"source_witness":{"$node_output":"original-edit"}},
                             "depends_on":["original-edit"]}]}
                host=BodyAuthority(workspace_ids=frozenset({"real-owner-film"}),
                    tool_access=frozenset({"read","write"}),
                    operations=frozenset({"submit","author_plan"}))
                model_interface=LiveBodySignal(service,authority=host)
                plan_receipt=model_interface.command("author_plan",{
                    "workspace_id":"real-owner-film",
                    "tool_id":"body.render_edit_owned",
                    "document":edit})
                self.assertTrue(plan_receipt["immutable_editor_document_published"])
                self.assertFalse(plan_receipt["film_physically_rendered"])
                authored["tool_graph"][0]["inputs"]["edit"]=plan_receipt["path"]
                chosen=model_interface.describe("real-owner-film","body.render_edit_owned")
                self.assertEqual(chosen["status"],"ready_to_preflight")
                preview=model_interface.preflight("real-owner-film",
                    "body.render_edit_owned",{"edit":plan_receipt["path"],
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
            finally:
                service.close()


if __name__=="__main__":
    unittest.main()

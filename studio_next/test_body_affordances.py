"""Body sensorimotor interface: bounded discovery, permission and real source facts."""
import hashlib
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request,urlopen

from studio_next.body_affordances import BodyAffordanceSurface
from studio_next.body_tool_contracts import real_operation_schema
from studio_next.contracts import ToolSpec
from studio_next.registry import ToolCatalog
from studio_next.body_service import LocalBodyCoordinator,make_body_http_handler


def sample():
    catalog=ToolCatalog()
    for id,cap,access,status in [
       ("artist.camera","scene.camera","write","installed"),
       ("artist.cut","edit.timeline","write","installed"),
       ("artist.source","media.inspect","read","installed"),
       ("artist.unavailable","visual.model.3d","write","needs_setup"),
    ]:
        schema=real_operation_schema(id,["source","out"] if access=="write" else ["source"])
        catalog.register(ToolSpec(id,cap,"Physical installed operator",access,
                    status=status,license="MIT",resource="test host",
                    operation_schema=schema),
                    (lambda inputs:{"physical":True}) if status=="installed" else None,
                    idempotent=True,
                    implementation_revision="sha256:"+"b"*64 if status=="installed" else None,
                    material_fingerprint=(lambda inputs:[{"source_sha256":
                          hashlib.sha256(Path(inputs["source"]).read_bytes()).hexdigest()}])
                        if status=="installed" else None)
    return catalog


class MachineNativeSomaticContractTests(unittest.TestCase):
    def test_paged_real_capabilities_and_precise_no_preset_lookup(self):
        nerve=BodyAffordanceSurface(sample())
        first=nerve.discover(allowed_access={"read","write"},limit=1)
        self.assertEqual(first["matched"],3)
        second=nerve.discover(allowed_access={"read","write"},limit=1,
                               cursor=first["next_cursor"])
        self.assertNotEqual(first["affordances"][0]["tool_id"],
                            second["affordances"][0]["tool_id"])
        chosen=nerve.discover(capability="scene.camera",
                              allowed_access={"read","write"})
        self.assertEqual([x["tool_id"] for x in chosen["affordances"]],
                         ["artist.camera"])
        self.assertFalse(nerve.discover(capability="scene.make.up",
                    allowed_access={"read","write"})["affordances"])
        self.assertNotIn("input_schema",str(first))
        self.assertFalse(first["complete_studio_certified"])

    def test_denies_uninstalled_billing_and_model_granted_rights(self):
        nerve=BodyAffordanceSurface(sample())
        self.assertEqual(nerve.discover()["matched"],1)
        self.assertEqual(nerve.discover(allowed_access={"read","write"},
                                      include_unavailable=True)["matched"],4)
        with self.assertRaises(PermissionError):
            nerve.describe("artist.cut")
        with self.assertRaises(RuntimeError):
            nerve.preflight("artist.unavailable",{},allowed_access={"read","write"})
        for forged in (
            {"allow":"write"},["read"],set(),{"bitcoin"},None):
            with self.subTest(permission=forged),self.assertRaises(ValueError):
                nerve.discover(allowed_access=forged)
        with self.assertRaises(ValueError):
            nerve.discover(allowed_access={"read","write"},cursor="0.fake")
        with self.assertRaises(ValueError):
            nerve.discover(allowed_access={"read"},limit=0)

    def test_lazy_schema_technical_preflight_real_bytes_and_no_execution(self):
        with tempfile.TemporaryDirectory() as root:
            data=Path(root)/"actual-original.bin"
            data.write_bytes(b"original-shot-intent"*100)
            catalog=sample()
            nerve=BodyAffordanceSurface(catalog)
            described=nerve.describe("artist.source")
            self.assertEqual(described["input_schema"]["required"],["source"])
            witness=nerve.preflight("artist.source",{"source":str(data)})
            self.assertEqual(witness["material_witness_count"],1)
            self.assertFalse(witness["owner_authorization_to_execute_granted"])
            self.assertFalse(witness["real_movie_rendered"])
            data.write_bytes(b"changed-original-art"*100)
            mutated=nerve.preflight("artist.source",{"source":str(data)})
            self.assertNotEqual(witness["observed_material_sha256"],
                                mutated["observed_material_sha256"])
            for fake in (
               {"source":str(data),"cmd":"rm -rf /"},
               {"source":1},
               {"no_source":str(data)}):
                with self.assertRaises((TypeError,ValueError)):
                    nerve.preflight("artist.source",fake)

    def test_stale_cursor_fails_when_physical_tool_install_changes(self):
        catalog=sample()
        nerve=BodyAffordanceSurface(catalog)
        old=nerve.discover(allowed_access={"read","write"},limit=1)["next_cursor"]
        catalog.register(ToolSpec("artist.new","original.motion",
                       "New installed operation","read",operation_schema={
                         "type":"object","required":[],"properties":{} }),
                       lambda _:{"status":"ok"},idempotent=False,
                       implementation_revision="sha256:"+"1"*64,
                       material_fingerprint=lambda _:[])
        with self.assertRaisesRegex(ValueError,"changed"):
            nerve.discover(allowed_access={"read","write"},limit=1,cursor=old)


class LocalOwnerAffordanceHttpTests(unittest.TestCase):
    def test_real_authenticated_live_discovery_and_preflight_no_tool_execution(self):
        with tempfile.TemporaryDirectory() as root:
            owner=LocalBodyCoordinator(root,execute=lambda ir,workspace:{
                "status":"blocked"})
            token="test-owner-"+("s"*60)
            server=ThreadingHTTPServer(("127.0.0.1",0),
                         make_body_http_handler(owner,token))
            thr=threading.Thread(target=server.serve_forever,daemon=True)
            thr.start()
            base=f"http://127.0.0.1:{server.server_port}"
            def request(path,body=None,auth=True):
                headers={"Authorization":"Bearer "+token} if auth else {}
                if body is not None:headers["Content-Type"]="application/json"
                req=Request(base+path,headers=headers,
                    data=json.dumps(body).encode() if body is not None else None)
                with urlopen(req,timeout=10) as response:
                    return json.loads(response.read())
            try:
                with self.assertRaises(HTTPError) as unauthorized:
                    request("/v1/affordances",auth=False)
                self.assertEqual(unauthorized.exception.code,401)
                summary=request("/v1/affordances?limit=1")
                self.assertEqual(len(summary["affordances"]),1)
                info=request("/v1/affordances/body.resolve_asset")
                self.assertEqual(info["status"],"ready_to_preflight")
                self.assertIn("asset_id",info["input_schema"]["required"])
                workspace=Path(root)/"projects"/"test-film"
                workspace.mkdir()
                with self.assertRaises(HTTPError) as bad:
                    request("/v1/affordances/preflight",{
                        "workspace_id":"test-film","tool_id":"body.resolve_asset",
                        "inputs":{"asset_id":"0"*64,"attestation_id":"forged"}})
                self.assertEqual(bad.exception.code,400)
                from studio_next.media_vault import MediaVault
                original=workspace/"licensed-owner-asset.bin"
                original.write_bytes(b"physically owned original bytes"*150)
                v=MediaVault(workspace/"vault")
                admitted=v.ingest(original,mime="application/octet-stream",
                    rights="owner_supplied",source_type="owner_upload",
                    source_id="original-local-owner",
                    evidence="Independent owner-authenticated source proof",
                    owner_or_generator="owner")
                good=request("/v1/affordances/preflight",{
                        "workspace_id":"test-film","tool_id":"body.resolve_asset",
                        "inputs":{"asset_id":admitted["asset_id"],
                                  "attestation_id":admitted["attestation_id"]}})
                self.assertEqual(good["material_witness_count"],1)
                self.assertFalse(good["owner_authorization_to_execute_granted"])
                with self.assertRaises(HTTPError) as fake:
                    request("/v1/affordances/preflight",{
                        "workspace_id":"test-film","tool_id":"body.resolve_asset",
                        "inputs":{"asset_id":admitted["asset_id"],
                                  "attestation_id":"forged"}})
                self.assertEqual(fake.exception.code,400)
                self.assertFalse(any(workspace.glob("*.mp4")))
                with self.assertRaises(HTTPError) as badcap:
                    request("/v1/affordances?limit=500")
                self.assertEqual(badcap.exception.code,400)
            finally:
                server.shutdown();server.server_close()
                thr.join(timeout=3)
                owner.close()


if __name__=="__main__":unittest.main()

import copy
import tempfile
import unittest
from studio_next.body_project_revision import revise_document,selected_value
from studio_next.body_service import LocalBodyCoordinator
from studio_next.body_signal import BodyAuthority,LiveBodySignal,BodyCommandRejected


class CreativeDocumentRevisionTests(unittest.TestCase):
    def test_transaction_preserves_source_and_handles_escaped_keys_arrays(self):
        original={"layer/name":{"opacity":.5,"points":[1,2,3]},"~control":9};before=copy.deepcopy(original)
        changed=revise_document(original,[{"op":"test","path":"/layer~1name/opacity","value":.5},
            {"op":"replace","path":"/layer~1name/opacity","value":.8},{"op":"remove","path":"/layer~1name/points/1"},
            {"op":"add","path":"/layer~1name/points/-","value":7},{"op":"replace","path":"/~0control","value":4}])
        self.assertEqual(original,before);self.assertEqual(selected_value(changed,"/layer~1name/points"),[1,3,7])
        self.assertEqual(changed["~control"],4)
        with self.assertRaisesRegex(ValueError,"precondition"):
            revise_document(original,[{"op":"test","path":"/~0control","value":8}])

    def test_test_compares_numbers_without_confusing_booleans(self):
        self.assertEqual(revise_document({"x":1},[{"op":"test","path":"/x","value":1.0}]),{"x":1})
        with self.assertRaises(ValueError):revise_document({"x":1},[{"op":"test","path":"/x","value":True}])

    def test_invalid_target_never_partially_modifies_original(self):
        original={"list":[1,2],"value":3}
        for op in ({"op":"remove","path":""},{"op":"replace","path":"/missing","value":1},
                   {"op":"add","path":"/list/03","value":1},{"op":"add","path":"/list/9","value":1},
                   {"op":"replace","path":"/value/sub","value":1},{"op":"remove","path":"/invalid~2"},
                   {"op":"exec","path":"/value","value":"anything"},{"op":"replace","path":"/value","value":float("nan")}):
            with self.subTest(op=op),self.assertRaises(ValueError):
                revise_document(original,[{"op":"replace","path":"/value","value":4},op])
            self.assertEqual(original,{"list":[1,2],"value":3})

    def test_inspect_revision_schema_authority_and_immutable_history(self):
        with tempfile.TemporaryDirectory() as home:
            c=LocalBodyCoordinator(home)
            try:
                signal=LiveBodySignal(c,authority=BodyAuthority(workspace_ids=frozenset({"artist"}),
                    operations=frozenset({"author_plan","revise_plan"}),tool_access=frozenset({"read","write"})))
                doc={"format":{"width":128,"height":96,"fps":12,"framing":"fit","background":"#111111"},
                    "clips":[{"id":"a","source":"unprovided.mp4","rights":"owner_supplied","audio":"preserve_source",
                        "asset_id":"0"*64,"attestation_id":"not-yet-attested"}]}
                base=signal.command("author_plan",{"workspace_id":"artist","tool_id":"body.render_edit_owned","document":doc})
                self.assertEqual(signal.inspect_plan("artist",base["sha256"],pointer="/format/width")["value"],128)
                args={"workspace_id":"artist","tool_id":"body.render_edit_owned","base_sha256":base["sha256"],
                    "operations":[{"op":"replace","path":"/format/width","value":640}]}
                revised=signal.command("revise_plan",args)
                self.assertNotEqual(base["sha256"],revised["sha256"])
                self.assertTrue(revised["original_document_preserved"]);self.assertFalse(revised["body_implementation_changed"])
                self.assertEqual(signal.inspect_plan("artist",base["sha256"],pointer="/format/width")["value"],128)
                self.assertEqual(signal.inspect_plan("artist",revised["sha256"],pointer="/format/width")["value"],640)
                with self.assertRaises(BodyCommandRejected):signal.command("revise_plan",{**args,"operations":[{"op":"add","path":"/shell","value":"false"}]})
                readonly=LiveBodySignal(c,authority=BodyAuthority(workspace_ids=frozenset({"artist"})))
                with self.assertRaises(PermissionError):readonly.command("revise_plan",args)
                with self.assertRaises(PermissionError):signal.inspect_plan("other-owner",base["sha256"])
                (c._workspace("artist")/base["path"]).write_text('{"changed":true}')
                with self.assertRaises(BodyCommandRejected):signal.inspect_plan("artist",base["sha256"])
            finally:c.close()

    def test_revision_requires_host_write_authority(self):
        with self.assertRaises(ValueError):BodyAuthority(workspace_ids=frozenset({"artist"}),operations=frozenset({"revise_plan"}))

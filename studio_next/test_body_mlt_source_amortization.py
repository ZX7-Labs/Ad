"""Physical original-source verification is linear in unique CAS media, not cuts.

The model can reuse 128 shots of a large original file; the rights and source
bytes must still be validated without 128 full-file SHA scans per track.
No cross-request cache or stale custodial approval is permitted.
"""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.media_vault import MediaVault,sha256_file
from studio_next.body_mlt_editor import (
    validate_mlt_edit,export_owned_mlt,verify_owned_mlt_project)
from studio_next.body_mlt_roundtrip import recover_original_mlt_plan
from studio_next import test_body_mlt_editor as fixtures


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Physical attested source validation requires the real decoder")
class RepeatedNativeSourceCustodyTests(unittest.TestCase):
    @staticmethod
    def _case(root):
        plan,authored=fixtures.VerifiedMLTEditorialTests()._case(root)
        for track in plan["tracks"]:
            original=copy.deepcopy(track["clips"][0])
            track["clips"]=[{**original,"first_frame":0,"end_frame":2,
                            "position_frame":i*2}
                           for i in range(48)]
        authored.write_text(json.dumps(plan))
        return plan,authored

    def test_96_picture_cuts_hash_two_actual_cas_sources_once_per_preflight(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,authored=self._case(root)
            original_inspect=MediaVault.inspect
            counts={}
            def counted(vault,digest,*,attestation_id=None):
                counts[(digest,attestation_id)]=counts.get((digest,attestation_id),0)+1
                return original_inspect(vault,digest,attestation_id=attestation_id)
            with patch.object(MediaVault,"inspect",counted):
                checked=validate_mlt_edit(plan,root,root/"vault")
            self.assertEqual(checked["frames"],96)
            self.assertEqual(len(checked["tracks"][0]),48)
            self.assertEqual(len(checked["tracks"][1]),48)
            self.assertEqual(len(counts),2)
            self.assertEqual(list(counts.values()),[1,1])
            original=authored.read_bytes()
            dest=root/"source-reused-96-cuts.mlt"
            export_owned_mlt(authored,root,root/"vault",dest)
            self.assertEqual(recover_original_mlt_plan(dest,root,root/"vault")["plan"],plan)
            self.assertEqual(authored.read_bytes(),original)

    def test_repeated_original_does_not_hide_changed_source_between_verification_and_return(self):
        from studio_next import body_mlt_editor
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,authored=self._case(root)
            dest=root/"original-reused.mlt"
            export_owned_mlt(authored,root,root/"vault",dest)
            native=dest.read_bytes()
            original_probe=body_mlt_editor._probe_details
            asset_ids=[track["clips"][0]["asset_id"] for track in plan["tracks"]]
            original_red=Path(MediaVault(root/"vault").inspect(
                asset_ids[0],attestation_id=plan["tracks"][0]["clips"][0]["attestation_id"])["path"])
            original_red_bytes=original_red.read_bytes()
            triggered=[]
            def adversarial_probe(path):
                result=original_probe(path)
                # Both sources have already passed an individual custody
                # check when their producer is visited. Once the last source
                # enters video stream probing, swap the earlier verified
                # original. End-of-transaction original SHA recheck must fail.
                if Path(path).name==asset_ids[1] and not triggered:
                    triggered.append(True)
                    original_red.write_bytes(b"mutated CAS source during verification")
                return result
            with patch("studio_next.body_mlt_editor._probe_details",
                       side_effect=adversarial_probe):
                try:
                    with self.assertRaises(ValueError):
                        verify_owned_mlt_project(dest)
                finally:
                    original_red.write_bytes(original_red_bytes)
            self.assertEqual(triggered,[True])
            self.assertEqual(sha256_file(original_red),asset_ids[0])
            self.assertEqual(dest.read_bytes(),native)
            self.assertTrue(verify_owned_mlt_project(dest)["verified_original_sources"]>=2)

    def test_standalone_preflight_rehashes_every_original_after_later_source_probes(self):
        from studio_next import body_mlt_editor
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,_=self._case(root)
            ids=[track["clips"][0]["asset_id"] for track in plan["tracks"]]
            file=Path(MediaVault(root/"vault").inspect(
                ids[0],attestation_id=plan["tracks"][0]["clips"][0]["attestation_id"])["path"])
            pristine=file.read_bytes()
            measured=body_mlt_editor._source_timebase
            fired=[]
            def swapped_during_probe(source):
                observed=measured(source)
                if Path(source).name==ids[1] and not fired:
                    fired.append(True)
                    file.write_bytes(b"untrusted replacement during native preflight")
                return observed
            with patch("studio_next.body_mlt_editor._source_timebase",
                       side_effect=swapped_during_probe):
                try:
                    with self.assertRaisesRegex(ValueError,"changed during native preflight"):
                        validate_mlt_edit(plan,root,root/"vault")
                finally:
                    file.write_bytes(pristine)
            self.assertEqual(fired,[True])
            self.assertEqual(sha256_file(file),ids[0])

    def test_alternate_rights_attestation_never_reuses_another_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,_=self._case(root)
            first=plan["tracks"][0]["clips"][0]
            vault=MediaVault(root/"vault")
            original_path=Path(vault.inspect(first["asset_id"],
                attestation_id=first["attestation_id"])["path"])
            second=vault.ingest(original_path,mime="video/mp4",rights="appropriately_licensed",
                source_type="licensed_library",source_id="alternate-contract",
                evidence="Independent licensed copy of same original bytes",
                owner_or_generator="test-license-holder")
            self.assertEqual(first["asset_id"],second["asset_id"])
            self.assertNotEqual(first["attestation_id"],second["attestation_id"])
            amended=copy.deepcopy(plan)
            amended["tracks"][0]["clips"][1]["attestation_id"]=second["attestation_id"]
            counts={}
            actual=MediaVault.inspect
            def count(vault,digest,*,attestation_id=None):
                counts[(digest,attestation_id)]=counts.get((digest,attestation_id),0)+1
                return actual(vault,digest,attestation_id=attestation_id)
            with patch.object(MediaVault,"inspect",count):
                with self.assertRaisesRegex(ValueError,"conflicting exact rights"):
                    validate_mlt_edit(amended,root,root/"vault")
            self.assertEqual(counts[(first["asset_id"],first["attestation_id"])],1)
            self.assertEqual(counts[(first["asset_id"],second["attestation_id"])],1)
            # The producer binds one exact attestation to the original source;
            # a genuine different grant is valid ONLY when explicitly chosen
            # consistently across all uses of that native producer.
            for clip in amended["tracks"][0]["clips"]:
                clip["attestation_id"]=second["attestation_id"]
            counts.clear()
            with patch.object(MediaVault,"inspect",count):
                self.assertEqual(validate_mlt_edit(amended,root,root/"vault")["frames"],96)
            self.assertEqual(len(counts),2)
            self.assertEqual(counts[(first["asset_id"],second["attestation_id"])],1)
            amended["tracks"][0]["clips"][2]["attestation_id"]="0"*64
            with self.assertRaises(ValueError):
                validate_mlt_edit(amended,root,root/"vault")


if __name__=="__main__":
    unittest.main()

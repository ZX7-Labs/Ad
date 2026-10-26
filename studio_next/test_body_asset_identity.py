"""Genuine model-neutral asset identity acquisition; never hallucinate a file path."""
from __future__ import annotations

import shutil
import tempfile
import unittest
import wave
from pathlib import Path

from studio_next.body_integration import body_catalog,validate_witness
from studio_next.media_vault import MediaVault,MediaCustodyError
from studio_next.body_materials import fingerprint_physical_inputs


class OriginalMediaIdentityTests(unittest.TestCase):
    def test_live_cas_identity_tool_resolves_existing_rights_and_exact_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            sound=root/"verified-voice.wav"
            with wave.open(str(sound),"wb") as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000)
                wav.writeframes(b"\x00\x00"*8000)
            vault=MediaVault(root/"vault")
            att=vault.ingest(sound,mime="audio/wav",rights="owner_supplied",
                source_type="owner_upload",source_id="original-owner-audio",
                evidence="Original owner recording obtained through authenticated upload",
                owner_or_generator="owner")
            tools=body_catalog(root)
            discovery={x["id"]:x for x in tools.discover()}
            self.assertEqual(discovery["body.resolve_asset"]["status"],"installed")
            self.assertEqual(discovery["body.resolve_asset"]["access"],"read")
            self.assertEqual(discovery["body.resolve_asset"]["schema"]["required"],
                             ["asset_id","attestation_id"])
            result=tools.invoke("body.resolve_asset",{
                "asset_id":att["asset_id"],
                "attestation_id":att["attestation_id"]})
            self.assertTrue(validate_witness("body.resolve_asset",result))
            self.assertEqual(result["rights"],"owner_supplied")
            self.assertEqual(result["mime"],"audio/wav")
            self.assertEqual(result["portable_uri"],"zx7:sha256:"+att["asset_id"])
            self.assertEqual(result["sha256"],att["asset_id"])
            self.assertEqual(result["bytes"],sound.stat().st_size)
            recorded=fingerprint_physical_inputs("body.resolve_asset",
                {"asset_id":att["asset_id"],"attestation_id":att["attestation_id"]},root)
            self.assertEqual(len(recorded),1)
            self.assertEqual(recorded[0]["sha256"],att["asset_id"])
            with self.assertRaises(MediaCustodyError):
                fingerprint_physical_inputs("body.resolve_asset",
                    {"asset_id":att["asset_id"],"attestation_id":"forged"},root)
            # Changed original working file does NOT poison already immutable CAS.
            sound.write_bytes(b"different post-ingest original source")
            self.assertTrue(validate_witness("body.resolve_asset",result))
            # But an actually altered stored CAS cannot masquerade as prior source.
            Path(result["path"]).write_bytes(b"tampered storage")
            self.assertFalse(validate_witness("body.resolve_asset",result))
            with self.assertRaises(MediaCustodyError):
                tools.invoke("body.resolve_asset",{
                    "asset_id":att["asset_id"],"attestation_id":att["attestation_id"]})

    def test_fake_attestation_forgery_or_billing_permissions_denied(self):
        with tempfile.TemporaryDirectory() as td:
            tools=body_catalog(td)
            entries={s["id"]:s for s in tools.discover()}
            self.assertIn("body.resolve_asset",entries)
            with self.assertRaises(PermissionError):
                tools.invoke("body.resolve_asset",{"asset_id":"0"*64,
                    "attestation_id":"0"*64},allowed_access={"write"})
            with self.assertRaises((ValueError,MediaCustodyError)):
                tools.invoke("body.resolve_asset",{"asset_id":"0"*64,
                    "attestation_id":"0"*64})
            with self.assertRaises(ValueError):
                tools.invoke("body.resolve_asset",{"asset_id":"0"*64,
                    "attestation_id":"0"*64,"paid_provider":"unapproved"})
            self.assertNotIn("body.generate_video",tools.executable_ids({"read"}))


if __name__=="__main__":
    unittest.main()

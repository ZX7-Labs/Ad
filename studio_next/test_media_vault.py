import tempfile
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from studio_next.media_vault import MediaVault,MediaCustodyError


class MediaVaultProductionTests(unittest.TestCase):
    def test_original_photography_survives_move_or_restart(self):
        with tempfile.TemporaryDirectory() as root:
            input=Path(root)/"camera.mov"
            input.write_bytes(b"original user-shot film bytes"*200)
            v=MediaVault(Path(root)/"vault")
            ref=v.ingest(input,mime="application/octet-stream",rights="owner_supplied",
                   source_type="owner_upload",source_id="owner-20261021",
                   evidence="Owner directly supplied this file",owner_or_generator="account-owner")
            input.unlink()
            restarted=MediaVault(Path(root)/"vault")
            verified=restarted.inspect(ref["asset_id"],attestation_id=ref["attestation_id"])
            self.assertEqual(verified["rights_attestations"][0]["rights"],"owner_supplied")
            self.assertTrue(Path(verified["path"]).is_file())
            target=Path(root)/"restored"/"clip.mov"
            restarted.checkout(ref["asset_id"],ref["attestation_id"],target)
            self.assertTrue(target.is_file())
            with self.assertRaises(MediaCustodyError):
                restarted.checkout(ref["asset_id"],ref["attestation_id"],target)

    def test_competing_immutable_vault_cas_is_not_overwritten(self):
        from studio_next import media_vault
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);input=root/"source.bin"
            input.write_bytes(b"genuine-artist-bytes"*220)
            store=MediaVault(root/"vault")
            from studio_next.media_vault import sha256_file
            digest=sha256_file(input)
            target=store._loc(digest)
            native=os.link
            raced=False
            def competing_writer(stage,dest,*args,**kwargs):
                nonlocal raced
                if Path(dest)==target:
                    # A conflicting writer publishes physically wrong data at
                    # the same CAS address. We must never overwrite that file.
                    target.write_bytes(b"another-unapproved-blob"*90)
                    raced=True
                return native(stage,dest,*args,**kwargs)
            with patch.object(media_vault.os,"link",side_effect=competing_writer):
                with self.assertRaises(FileExistsError):
                    store.ingest(input,mime="application/octet-stream",
                        rights="owner_supplied",source_type="owner_upload",
                        source_id="owned-clip-a",evidence="Owner recorded this",
                        owner_or_generator="owner")
            self.assertTrue(raced)
            self.assertTrue(target.read_bytes().startswith(b"another-unapproved"))
            with self.assertRaises(MediaCustodyError):
                store.inspect(digest)

    def test_rival_original_checkout_survives_no_replace_publication(self):
        from studio_next import media_vault
        from studio_next.media_vault import sha256_file
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);original=root/"source.bin"
            original.write_bytes(b"verified-owner-original"*170)
            store=MediaVault(root/"vault")
            receipt=store.ingest(original,mime="application/octet-stream",
                rights="owner_supplied",source_type="owner_upload",
                source_id="creator-clip",evidence="Real uploaded asset",
                owner_or_generator="owner")
            output=root/"colliding-original.bin"
            other=root/"different-director-source.bin"
            other.write_bytes(b"other-artist-original-footage"*155)
            known=sha256_file(other)
            native=os.link
            raced=False
            def competing_publication(stage,dest,*args,**kwargs):
                nonlocal raced
                if Path(dest)==output:
                    self.assertIn(".zx7-vault-checkout-",str(stage))
                    shutil.copyfile(other,output)
                    raced=True
                return native(stage,dest,*args,**kwargs)
            with patch.object(media_vault.os,"link",side_effect=competing_publication):
                with self.assertRaises(FileExistsError):
                    store.checkout(receipt["asset_id"],receipt["attestation_id"],output)
            self.assertTrue(raced)
            self.assertEqual(sha256_file(output),known)
            self.assertFalse(list(root.glob(".zx7-vault-checkout-*")))

    def test_real_content_hash_blocks_corrupted_asset(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"art.png";p.write_bytes(b"original hand painting"*50)
            vault=MediaVault(Path(root)/"vault")
            ref=vault.ingest(p,mime="application/octet-stream",rights="generated_original",
                   source_type="trusted_renderer",source_id="zx7-render-step",
                   evidence="Built by actual compositor",owner_or_generator="zx7-compositor")
            Path(vault.inspect(ref["asset_id"])["path"]).write_bytes(b"corrupted")
            with self.assertRaisesRegex(MediaCustodyError,"altered"):
                vault.inspect(ref["asset_id"])

    def test_forged_exr_zip_cannot_acquire_native_generated_rights(self):
        import zipfile
        with tempfile.TemporaryDirectory() as root:
            project=Path(root)
            forged=project/"claimed-vfx-frame-pass.zip"
            with zipfile.ZipFile(forged,"w") as archive:
                archive.writestr("manifest.json",
                    '{"schema":1,"frames":[{"file":"frames/frame_0001.exr",'
                    '"sha256":"0000","bytes":5,"channels":["Combined.R"]}]}')
                archive.writestr("frames/frame_0001.exr",b"FAKE!")
            vault=MediaVault(project/"vault")
            with self.assertRaises(MediaCustodyError):
                vault.ingest(forged,mime="application/x-zx7-exr-bundle",
                    rights="generated_original",source_type="trusted_renderer",
                    source_id="unverified-blender",
                    evidence="A made-up EXR bundle is not actual VFX",
                    owner_or_generator="fake-operator")
            self.assertFalse(list(vault.objects.rglob("*")))

    def test_real_video_media_claim_requires_a_decodable_video_not_text(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"invented-video.mp4"
            p.write_bytes(b"this is a fabricated video title"*100)
            vault=MediaVault(Path(root)/"vault")
            with self.assertRaises((ValueError,RuntimeError,subprocess.CalledProcessError)):
                vault.ingest(p,mime="video/mp4",rights="generated_original",
                    source_type="trusted_renderer",source_id="fake-video",
                    evidence="No real decoding",owner_or_generator="sample")
            self.assertEqual(list(vault.objects.rglob("*")),[])

    def test_unverified_libraries_and_invented_rights_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"unknown.mp4";p.write_bytes(b"real bytes"*50)
            store=MediaVault(Path(root)/"vault")
            for bogus in ("found online","",None):
                with self.assertRaises(MediaCustodyError):
                    store.ingest(p,mime="video/mp4",rights=bogus,
                        source_type="licensed_library",source_id="bad",
                        evidence="unverified",owner_or_generator="no")
            with self.assertRaisesRegex(MediaCustodyError,"disagree"):
                store.ingest(p,mime="video/mp4",rights="generated_original",
                    source_type="licensed_library",source_id="unverified",
                    evidence="no license",owner_or_generator="not-our-renderer")
            self.assertFalse(list((Path(root)/"vault"/"objects").rglob("*")))

    def test_distinct_rights_attestations_are_not_laundered(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"sample.wav";p.write_bytes(b"sound"*100)
            v=MediaVault(Path(root)/"vault")
            a=v.ingest(p,mime="application/octet-stream",rights="owner_supplied",
                source_type="owner_upload",source_id="owner-upload-1",
                evidence="Client-supplied",owner_or_generator="client")
            b=v.ingest(p,mime="application/octet-stream",rights="appropriately_licensed",
                source_type="licensed_library",source_id="sample-library-license-id",
                evidence="Rights recorded in external receipt",owner_or_generator="licensed-asset-import")
            self.assertEqual(a["asset_id"],b["asset_id"])
            self.assertNotEqual(a["attestation_id"],b["attestation_id"])
            self.assertEqual(v.inspect(a["asset_id"],attestation_id=a["attestation_id"])
                    ["rights_attestations"][0]["rights"],"owner_supplied")


if __name__=="__main__":unittest.main()

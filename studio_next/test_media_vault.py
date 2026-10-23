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
                with self.assertRaises(MediaCustodyError):
                    store.ingest(input,mime="application/octet-stream",
                        rights="owner_supplied",source_type="owner_upload",
                        source_id="owned-clip-a",evidence="Owner recorded this",
                        owner_or_generator="owner")
            self.assertTrue(raced)
            self.assertTrue(target.read_bytes().startswith(b"another-unapproved"))
            with self.assertRaises(MediaCustodyError):
                store.inspect(digest)

    def test_media_objects_cannot_escape_owner_cas_through_symlinked_shard(self):
        from studio_next.media_vault import sha256_file
        with tempfile.TemporaryDirectory() as p:
            workspace=Path(p)
            asset=workspace/"legal-owner-media.bin"
            asset.write_bytes(b"original-creator-byte-evidence"*180)
            vault=MediaVault(workspace/"vault")
            prefix=sha256_file(asset)[:2]
            foreign=workspace/"outside-vault"
            foreign.mkdir()
            (vault.objects/prefix).symlink_to(foreign,target_is_directory=True)
            with self.assertRaisesRegex(MediaCustodyError,"symlink"):
                vault.ingest(asset,mime="application/octet-stream",
                    rights="owner_supplied",source_type="owner_upload",
                    source_id="creator-camera",evidence="Owner actual source",
                    owner_or_generator="owner")
            self.assertFalse(list(foreign.iterdir()))

    def test_media_vault_refuses_linked_external_provenance_db(self):
        with tempfile.TemporaryDirectory() as p:
            workspace=Path(p)
            outside=workspace/"foreign.sqlite3"
            outside.write_bytes(b"forged-database")
            store=workspace/"vault"
            store.mkdir()
            (store/"assets.sqlite3").symlink_to(outside)
            with self.assertRaisesRegex(MediaCustodyError,"linked object or database"):
                MediaVault(store)
            self.assertEqual(outside.read_bytes(),b"forged-database")

    def test_simultaneous_identical_verified_blob_is_reused_not_damaged(self):
        from studio_next import media_vault
        from studio_next.media_vault import sha256_file
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            camera=root/"trusted-footage.bin"
            camera.write_bytes(b"true-director-original-asset"*145)
            store=MediaVault(root/"vault")
            digest=sha256_file(camera)
            location=store._loc(digest)
            native_link=os.link
            raced=False
            def first_cas_writer_wins(stage,dest,*args,**kwargs):
                nonlocal raced
                if Path(dest)==location:
                    shutil.copyfile(camera,location)
                    raced=True
                return native_link(stage,dest,*args,**kwargs)
            with patch.object(media_vault.os,"link",side_effect=first_cas_writer_wins):
                proof=store.ingest(camera,mime="application/octet-stream",
                    rights="owner_supplied",source_type="owner_upload",
                    source_id="actual-owner",evidence="Owner-supplied physical bytes",
                    owner_or_generator="owner")
            self.assertTrue(raced)
            self.assertEqual(proof["asset_id"],digest)
            self.assertEqual(sha256_file(location),digest)
            self.assertTrue(store.inspect(
                proof["asset_id"],attestation_id=proof["attestation_id"]))
            self.assertFalse(list(location.parent.glob("."+digest[:10]+"-*")))

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

    def test_actual_font_uses_real_sfnt_unicode_glyph_tables_not_magic_header(self):
        from studio_next.media_vault import verify_media_container
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)
            ttf=folder/"invented-art-direction.ttf"
            ttf.write_bytes(bytes((0,1,0,0))+b"fake-artist-glyphs"*90)
            otf=folder/"invented-other-typeface.otf"
            otf.write_bytes(b"OTTO"+b"fake-otf-tables"*80)
            for path,mime in ((ttf,"font/ttf"),(otf,"font/otf")):
                with self.subTest(mime=mime):
                    with self.assertRaises(MediaCustodyError):
                        verify_media_container(path,mime)
            font=Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
            import importlib.util
            if font.is_file() and importlib.util.find_spec("fontTools"):
                self.assertTrue(
                    verify_media_container(font,"font/ttf")["actual_file_bytes_checked"])
                with self.assertRaises(MediaCustodyError):
                    verify_media_container(font,"font/otf")

    def test_real_mesh_glb_requires_physical_buffer_and_bounded_buffer_views(self):
        import json
        import struct
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            original=root/"artist-mesh.glb"
            vault=MediaVault(root/"vault")
            geometry=struct.pack("<fff",0.25,0.5,-1.0)+bytes(4)
            base={"asset":{"version":"2.0"},"scenes":[{"nodes":[0]}],
                  "nodes":[{"mesh":0}],
                  "meshes":[{"primitives":[{"attributes":{"POSITION":0}}]}],
                  "buffers":[{"byteLength":len(geometry)}],
                  "bufferViews":[{"buffer":0,"byteOffset":0,
                                  "byteLength":len(geometry)}],
                  "accessors":[{"bufferView":0,"componentType":5126,
                                "count":1,"type":"VEC3"}]}
            def encoded(document,embed=True):
                metadata=json.dumps(document,separators=(",",":")).encode()
                metadata+=b" "*((-len(metadata))%4)
                chunks=struct.pack("<I4s",len(metadata),b"JSON")+metadata
                if embed:
                    chunks+=struct.pack("<I4s",len(geometry),
                                        bytes((66,73,78,0)))+geometry
                return struct.pack("<4sII",b"glTF",2,12+len(chunks))+chunks
            original.write_bytes(encoded(base))
            verified=vault.ingest(original,mime="model/gltf-binary",
                rights="owner_supplied",source_type="owner_upload",
                source_id="actual-original-3d-geometry",
                evidence="Owner physical mesh and bounded glTF buffer",
                owner_or_generator="owner")
            self.assertEqual(vault.inspect(verified["asset_id"])["mime"],
                             "model/gltf-binary")
            forged={**base,"buffers":[{"byteLength":len(geometry)+16}]}
            escaped={**base,"bufferViews":[{"buffer":0,"byteOffset":12,
                                            "byteLength":16}]}
            for fake in (encoded(base,embed=False),encoded(forged),
                         encoded(escaped)):
                original.write_bytes(fake)
                with self.assertRaises(MediaCustodyError):
                    vault.ingest(original,mime="model/gltf-binary",
                        rights="owner_supplied",source_type="owner_upload",
                        source_id="claimed-unbounded-geometry",
                        evidence="Unverified requested mesh",
                        owner_or_generator="owner")

    def test_real_glb_json_chunk_and_complete_native_length_are_required(self):
        import json
        import struct
        def package(scene,*,version=2,append=b""):
            body=json.dumps(scene,separators=(",",":")).encode("utf-8")
            body+=b" "*((-len(body))%4)
            chunk=struct.pack("<I4s",len(body),b"JSON")+body
            return struct.pack("<4sII",b"glTF",version,12+len(chunk))+chunk+append
        film={"asset":{"version":"2.0"},"scenes":[{"nodes":[0]}],
              "nodes":[{"camera":0}],
              "cameras":[{"type":"perspective","perspective":{
                  "yfov":0.9,"znear":0.01}}]}
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            source=root/"owner-camera.glb"
            good=package(film)
            source.write_bytes(good)
            store=MediaVault(root/"vault")
            receipt=store.ingest(source,mime="model/gltf-binary",
                rights="owner_supplied",source_type="owner_upload",
                source_id="owner-camera-3d",
                evidence="Real glTF version two binary scene topology",
                owner_or_generator="source-owner")
            self.assertTrue(store.inspect(receipt["asset_id"],
                          attestation_id=receipt["attestation_id"]))
            for bad in (
                    b"glTF"+b"\\0"*8,
                    package(film,version=1),
                    good+b"HIDDEN-WRONG-BYTES",
                    good[:-3],
                    package({"asset":{"version":"2.0"}}),
                    package(film,append=b"FAKE")
                    ):
                with self.subTest(size=len(bad)):
                    source.write_bytes(bad)
                    with self.assertRaises(MediaCustodyError):
                        store.ingest(source,mime="model/gltf-binary",
                            rights="owner_supplied",source_type="owner_upload",
                            source_id="forged-scene",
                            evidence="Magic data alone lacks valid 3D frames",
                            owner_or_generator="source-owner")
            self.assertEqual(len([x for x in store.objects.rglob("*")
                         if x.is_file()]),1)

    def test_magic_only_exr_does_not_acquire_original_media_rights(self):
        with tempfile.TemporaryDirectory() as root:
            workspace=Path(root)
            fake=workspace/"claimed-original.exr"
            fake.write_bytes(bytes((0x76,0x2f,0x31,0x01))+b"FAKE PIXELS"*90)
            vault=MediaVault(workspace/"vault")
            with self.assertRaises(MediaCustodyError):
                vault.ingest(fake,mime="image/x-exr",
                    rights="owner_supplied",source_type="owner_upload",
                    source_id="source-owner",
                    evidence="Unverified claimed HDR pixels",
                    owner_or_generator="owner")
            self.assertFalse(list(vault.objects.rglob("*")))

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

    def test_wav_cannot_claim_unrecorded_pcm_audio_samples(self):
        import wave
        import struct
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            original=root/"recorded-owner-dialogue.wav"
            with wave.open(str(original),"wb") as recording:
                recording.setnchannels(1)
                recording.setsampwidth(2)
                recording.setframerate(48000)
                recording.writeframes(b"\0"*48000)
            actual=bytearray(original.read_bytes())
            self.assertEqual(actual[36:40],b"data")
            # A forged WAVE length claims twice the recorded samples.
            struct.pack_into("<I",actual,40,96000)
            struct.pack_into("<I",actual,4,96036)
            original.write_bytes(actual)
            vault=MediaVault(root/"vault")
            with self.assertRaisesRegex(MediaCustodyError,"more PCM samples"):
                vault.ingest(original,mime="audio/wav",
                    rights="owner_supplied",source_type="owner_upload",
                    source_id="claimed-speech",
                    evidence="User-supplied recording with invalid source extent",
                    owner_or_generator="owner")
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

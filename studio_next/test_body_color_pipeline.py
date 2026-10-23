"""Real recorded H264 soundtrack + lawful 3D cube + 10-bit display-referred master.

Tests deliberately separate verified BT.709 SDR LUTs from unsupported ACES,
camera-log/linear transforms and HDR. Every tested color difference is decoded
from *actual* frames, not inferred from an FFmpeg success status.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from studio_next.body_color_pipeline import (
    render_verified_color_job, validate_color_job, validate_cube_bytes)
from studio_next.body_integration import body_catalog
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.delivery_audit import _probe_details


def _run(argv,*,timeout=90):
    return subprocess.run(argv,check=True,timeout=timeout,capture_output=True)


def _lut_original():
    lines=["TITLE \"Original artist-selected red-green channel exchange\"",
           "LUT_3D_SIZE 2","DOMAIN_MIN 0.0 0.0 0.0",
           "DOMAIN_MAX 1.0 1.0 1.0"]
    # Original CUBE order is red fastest, green next, blue slowest.
    for b in (0,1):
        for g in (0,1):
            for r in (0,1):
                lines.append(f"{g:.6f} {r:.6f} {b:.6f}")
    return ("\n".join(lines)+"\n").encode("utf-8")


class OriginalLutContracts(unittest.TestCase):
    def test_rejects_partial_cube_nonfinite_domain_and_overflow(self):
        original=_lut_original()
        self.assertEqual(validate_cube_bytes(original)["samples"],8)
        for corrupted in (
            b"",b"not a genuine 3D LUT",
            original.replace(b"LUT_3D_SIZE 2",b"LUT_3D_SIZE 0"),
            original.replace(b"LUT_3D_SIZE 2",b"LUT_3D_SIZE 3"),
            original.replace(b"DOMAIN_MAX 1.0 1.0 1.0",b"DOMAIN_MAX 9 9 9"),
            original.replace(b"0.000000 0.000000 0.000000",
                             b"nan 0.000000 0.000000"),
            original.replace(b"0.000000 0.000000 0.000000",
                             b"1e309 0.000000 0.000000"),
            original+b"0.1 0.1 0.1\n",
            original.rsplit(b"\n",2)[0]+b"\n"):
            with self.assertRaises(ValueError):
                validate_cube_bytes(corrupted)

    def test_never_claims_adapted_aces_from_random_cube(self):
        original=_lut_original()
        self.assertIn("Iridas",validate_cube_bytes(original)["type"])
        with self.assertRaises(ValueError):
            validate_cube_bytes(original.replace(b"DOMAIN_MIN 0.0 0.0 0.0",
                                                b"DOMAIN_MIN -1 -1 -1"))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Requires actual native encoder and decoder")
class PhysicalFilmColorLutTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.camera=self.root/"owner-first-shot.mp4"
        _run(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
              "-f","lavfi","-i","color=red:size=160x90:rate=12:duration=1",
              "-f","lavfi","-i","sine=frequency=430:sample_rate=48000:duration=1",
              "-c:v","libx264","-x264-params",
              "colorprim=bt709:transfer=bt709:colormatrix=bt709",
              "-pix_fmt","yuv420p",
              "-color_primaries","bt709","-color_trc","bt709",
              "-colorspace","bt709",
              "-c:a","aac","-shortest",str(self.camera)])
        self.vault=MediaVault(self.root/"vault")
        self.camera_proof=self.vault.ingest(self.camera,mime="video/mp4",
            rights="owner_supplied",source_type="owner_upload",
            source_id="verified-owner-camera",
            evidence="Real original red camera and audio test fixture",
            owner_or_generator="owner")
        self.cube=self.root/"author-original-look.cube"
        self.cube.write_bytes(_lut_original())
        self.cube_proof=self.vault.ingest(self.cube,mime="application/octet-stream",
            rights="owner_supplied",source_type="owner_upload",
            source_id="original-grade-lookup",
            evidence="Verified owner's original self-authored LUT",
            owner_or_generator="owner")
        self.plan={
          "media":{"source":"zx7:sha256:"+self.camera_proof["asset_id"],
                   "asset_id":self.camera_proof["asset_id"],
                   "attestation_id":self.camera_proof["attestation_id"]},
          "color_transform":{"kind":"display_referred_3d_lut",
                   "input_color_space":"bt709","output_color_space":"bt709",
                   "interpolation":"tetrahedral",
                   "cube":{"source":"zx7:sha256:"+self.cube_proof["asset_id"],
                      "asset_id":self.cube_proof["asset_id"],
                      "attestation_id":self.cube_proof["attestation_id"]}},
          "output_profile":"h264_8bit_sdr"}
        self.planfile=self.root/"original_color_job.json"
        self.save()

    def tearDown(self):self.tmp.cleanup()
    def save(self):self.planfile.write_text(json.dumps(self.plan),encoding="utf-8")
    def _pixel(self,path):
        raw=_run(["ffmpeg","-hide_banner","-loglevel","error",
             "-i",str(path),"-frames:v","1","-f","rawvideo",
             "-pix_fmt","rgb24","pipe:1"]).stdout
        idx=(45*160+80)*3
        return tuple(raw[idx:idx+3])

    def test_actually_changes_original_pixels_and_preserves_sound_rights(self):
        self.assertGreater(self._pixel(self.camera)[0],self._pixel(self.camera)[1]+100)
        verified=validate_color_job(self.plan,self.root,self.root/"vault")
        self.assertEqual(verified["cube_sha256"],self.cube_proof["asset_id"])
        physical=fingerprint_physical_inputs(
            "body.color_lut",{"plan":self.planfile.name,"out":"grading.mp4"},self.root)
        digests=[x["sha256"] for x in physical]
        self.assertIn(self.camera_proof["asset_id"],digests)
        self.assertIn(self.cube_proof["asset_id"],digests)
        new=self.root/"original-color-graded.mp4"
        receipt=render_verified_color_job(self.planfile,self.root,
                                          self.root/"vault",new)
        self.assertEqual(receipt["original_cube_sha256"],self.cube_proof["asset_id"])
        self.assertFalse(receipt["claimed_aces_hdr_or_scene_linear"])
        self.assertTrue(receipt["audio_present"])
        red,green,blue=self._pixel(new)
        self.assertGreater(green,red+80,(red,green,blue))
        self.assertGreater(green,blue+80)
        self.assertTrue(_probe_details(new)["audio_stream_present"])
        _run(["ffmpeg","-hide_banner","-loglevel","error","-xerror",
             "-i",str(new),"-map","0:v:0","-map","0:a:0",
             "-f","null","-"])
        self.assertEqual(sha256_file(self.camera),self.camera_proof["asset_id"])
        self.assertEqual(sha256_file(self.cube),self.cube_proof["asset_id"])
        with self.assertRaises(ValueError):
            render_verified_color_job(self.planfile,self.root,self.root/"vault",new)

    def test_actual_lut_grade_decodes_frozen_cas_while_mutable_original_is_swapped(self):
        from unittest.mock import patch
        self.plan["media"]["source"]=self.camera.name
        self.save()
        owner_original=self.camera.read_bytes()
        previous=self.root/"actual-owner-color-secure.mp4"
        actual_run=subprocess.run
        inputs=[]
        def source_swap(argv,**kwargs):
            if argv and argv[0]=="ffmpeg" and any(
                   "lut3d=file=lookup.cube" in a for a in argv):
                src=Path(argv[argv.index("-i")+1])
                self.assertIn(".zx7-owned-sources-",str(src))
                self.assertFalse(src.stat().st_mode & 0o222)
                self.assertEqual(sha256_file(src),self.camera_proof["asset_id"])
                private=Path(kwargs["cwd"])
                lut=private/"lookup.cube"
                self.assertEqual(sha256_file(lut),self.cube_proof["asset_id"])
                inputs.extend((src,lut))
                self.camera.write_bytes(b"attacker supplies a different shot during real LUT transform")
                try:return actual_run(argv,**kwargs)
                finally:self.camera.write_bytes(owner_original)
            return actual_run(argv,**kwargs)
        with patch("studio_next.body_color_pipeline.subprocess.run",side_effect=source_swap):
            proof=render_verified_color_job(self.planfile,self.root,
                                              self.root/"vault",previous)
        self.assertTrue(proof["full_picture_and_sound_decoder_completed"])
        self.assertTrue(proof["sealed_original_cas_and_original_cube_during_decode"])
        self.assertTrue(proof["audio_present"])
        self.assertEqual(sha256_file(self.camera),self.camera_proof["asset_id"])
        self.assertEqual(len(inputs),2)
        self.assertTrue(all(not src.exists() for src in inputs))
        self.assertFalse(list(self.root.glob(".zx7-owned-sources-*")))
        red,green,blue=self._pixel(previous)
        self.assertGreater(green,red+80)

    def test_lut_grade_cannot_destroy_already_published_concurrent_artist_master(self):
        from unittest.mock import patch
        published=self.root/"another-artists-approved-film.mp4"
        approved=b"APPROVED-CINEMATIC-SOURCE-DO-NOT-DESTROY"
        real=subprocess.run
        def competing_artist(argv,**kwargs):
            completed=real(argv,**kwargs)
            if argv and argv[0]=="ffmpeg" and any(
                  "lut3d=file=lookup.cube" in a for a in argv):
                published.write_bytes(approved)
            return completed
        with patch("studio_next.body_color_pipeline.subprocess.run",
                   side_effect=competing_artist):
            with self.assertRaises(FileExistsError):
                render_verified_color_job(self.planfile,self.root,
                                          self.root/"vault",published)
        self.assertEqual(published.read_bytes(),approved)
        self.assertFalse(list(self.root.glob(".zx7-owned-sources-*")))

    def test_rec709_10bit_real_prores_mezzanine_profile(self):
        allowed=subprocess.run(["ffmpeg","-hide_banner","-encoders"],
            capture_output=True,text=True,timeout=20)
        if "prores_ks" not in allowed.stdout:
            self.skipTest("Production runner lacks actual 10-bit ProRes encoder")
        self.plan["output_profile"]="prores_10bit_sdr";self.save()
        dest=self.root/"original-10bit-color-master.mov"
        result=render_verified_color_job(self.planfile,self.root,self.root/"vault",dest)
        self.assertTrue(result["audio_present"])
        self.assertEqual(result["output_profile"],"prores_10bit_sdr")
        data=json.loads(_run(["ffprobe","-v","error","-select_streams","v:0",
              "-show_entries","stream=pix_fmt,codec_name",
              "-of","json",str(dest)]).stdout)
        stream=data["streams"][0]
        self.assertIn("10",stream["pix_fmt"])
        self.assertEqual(stream["codec_name"],"prores")
        self.assertTrue(_probe_details(dest)["audio_stream_present"])

    def test_bad_rights_transform_identity_or_unverified_color_tags_denied(self):
        cases=[
           ("color_transform","input_color_space","ACEScg"),
           ("color_transform","output_color_space","bt2020"),
           ("color_transform","interpolation","shell=rm -rf /"),
        ]
        for key,field,value in cases:
            changed=json.loads(json.dumps(self.plan))
            changed[key][field]=value
            with self.assertRaises(ValueError):
                validate_color_job(changed,self.root,self.root/"vault")
        wrong=json.loads(json.dumps(self.plan))
        wrong["color_transform"]["cube"]["asset_id"]="0"*64
        with self.assertRaises(ValueError):
            validate_color_job(wrong,self.root,self.root/"vault")
        self.assertFalse((self.root/"unsafe.mp4").exists())

    def test_registered_color_tool_has_actual_render_revision_and_source_fingerprints(self):
        tools=body_catalog(self.root)
        specs={t["id"]:t for t in tools.discover()}
        self.assertEqual(specs["body.color_lut"]["status"],"installed")
        self.assertEqual(specs["body.color_lut"]["schema"]["required"],["plan","out"])
        out=tools.invoke("body.color_lut",{"plan":self.planfile.name,
                                          "out":"registered-master.mp4"},
                         allowed_access={"read","write"})
        self.assertTrue((self.root/"registered-master.mp4").exists())
        self.assertEqual(out["sha256"],sha256_file(self.root/"registered-master.mp4"))
        self.assertTrue(_probe_details(self.root/"registered-master.mp4")["audio_stream_present"])


if __name__=="__main__":unittest.main()

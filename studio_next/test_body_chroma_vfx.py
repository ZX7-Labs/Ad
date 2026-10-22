"""Physical VFX matte: only actually owned video and sound, observed pixels."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from studio_next.composite_mix import actual_composite_command,render_composition
from studio_next.media_vault import MediaVault
from studio_next.delivery_audit import _probe_details
from studio_next.body_materials import fingerprint_physical_inputs


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                    "Native alpha VFX rendering requires actual FFmpeg")
class ActualChromaMatteFilmmaking(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.original=self.root/"camera-original-green-screen.mp4"
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i","color=c=green:s=160x90:r=12:d=1",
            "-f","lavfi","-i","sine=frequency=680:duration=1",
            "-filter_complex","[0:v]drawbox=x=55:y=25:w=50:h=40:color=red:t=fill[v]",
            "-map","[v]","-map","1:a:0","-c:v","libx264",
            "-x264-params","colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-color_primaries","bt709","-color_trc","bt709",
            "-colorspace","bt709","-pix_fmt","yuv420p",
            "-c:a","aac","-shortest",str(self.original)],
            capture_output=True,check=True,timeout=60)
        self.vault=MediaVault(self.root/"vault")
        self.evidence=self.vault.ingest(self.original,mime="video/mp4",
                rights="owner_supplied",source_type="owner_upload",
                source_id="original-owner-green-screen",
                evidence="Actual original physically rendered actor matte footage fixture",
                owner_or_generator="owner")
        shared={"source":"zx7:sha256:"+self.evidence["asset_id"],
                "asset_id":self.evidence["asset_id"],
                "attestation_id":self.evidence["attestation_id"],
                "start":0,"source_in":0,"duration":1}
        self.film={
          "canvas":{"width":160,"height":90,"fps":12,"duration":1,
                    "background":"#0000FF",
                    "color_semantics":{"input":"bt709","output":"bt709"}},
          "video_layers":[{"id":"actor_matting","x":0,"y":0,"width":160,
                           "height":90,"opacity":1,
                           "chroma_key":{"color":"#008000",
                                         "similarity":0.14,"blend":0},
                            **shared}],
          "audio_tracks":[{"id":"recorded_sound","gain_db":0,**shared}]}
        self.file=self.root/"director-original-compositing.json"
        self.save()
    def tearDown(self):self.temp.cleanup()
    def save(self):self.file.write_text(json.dumps(self.film),encoding="utf-8")
    def pixel(self,path,x,y):
        raw=subprocess.check_output(["ffmpeg","-hide_banner","-loglevel","error",
            "-i",str(path),"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],
            timeout=30)
        at=(y*160+x)*3
        return tuple(raw[at:at+3])

    def test_physically_keyed_red_actor_on_blue_backdrop_and_original_audio(self):
        output=self.root/"owner-matte.mp4"
        command=actual_composite_command(self.film,self.root,self.vault,output)
        graph=command[command.index("-filter_complex")+1]
        self.assertIn("colorkey=0x008000:similarity=0.14:blend=0",graph)
        output_info=render_composition(self.file,self.root,self.root/"vault",output)
        self.assertTrue(output_info["audio_present"])
        self.assertEqual(output_info["video_layers"],1)
        original=self.pixel(self.original,7,7)
        keyed=self.pixel(output,7,7)
        foreground=self.pixel(output,80,50)
        self.assertGreater(original[1],original[2]+40,original)
        self.assertGreater(keyed[2],keyed[1]+70,keyed)
        self.assertGreater(keyed[2],keyed[0]+70,keyed)
        self.assertGreater(foreground[0],foreground[1]+60,foreground)
        self.assertTrue(_probe_details(output)["audio_stream_present"])
        from studio_next.body_color_pipeline import _actual_bt709_source
        self.assertEqual(_actual_bt709_source(output)["color_primaries"],"bt709")
        inputs=fingerprint_physical_inputs("body.composite_mix",
                    {"plan":self.file.name},self.root)
        self.assertIn(self.evidence["asset_id"],[x["sha256"] for x in inputs])

    def test_physical_original_vfx_then_rights_checked_color_grade_prores_audio(self):
        """Prove real original camera -> matte -> CAS -> LUT -> 10-bit sound."""
        from studio_next.body_color_pipeline import render_verified_color_job
        from studio_next.test_body_color_pipeline import _lut_original
        from studio_next.media_vault import sha256_file
        from studio_next.body_color_pipeline import _actual_bt709_source
        original_master=self.root/"step-one-original-keyed-film.mp4"
        initial=render_composition(self.file,self.root,self.root/"vault",
                                   original_master)
        self.assertTrue(initial["audio_present"])
        self.assertEqual(_actual_bt709_source(original_master)["color_space"],"bt709")
        source=self.vault.ingest(original_master,mime="video/mp4",
                        rights="generated_original",source_type="trusted_renderer",
                        source_id=initial["sha256"],
                        evidence="Actual physically verified original keyed camera film",
                        owner_or_generator="zx7-verified-native-editor")
        original_sha=sha256_file(original_master)
        lut=self.root/"artist-original-color-look.cube"
        lut.write_bytes(_lut_original())
        color_proof=self.vault.ingest(lut,mime="application/octet-stream",
                        rights="owner_supplied",source_type="owner_upload",
                        source_id="original-editor-approved-lut",
                        evidence="Authored original red/green LUT technical fixture",
                        owner_or_generator="owner")
        color_plan={
             "media":{"source":"zx7:sha256:"+source["asset_id"],
                      "asset_id":source["asset_id"],
                      "attestation_id":source["attestation_id"]},
             "color_transform":{"kind":"display_referred_3d_lut",
                 "input_color_space":"bt709","output_color_space":"bt709",
                 "cube":{"source":"zx7:sha256:"+color_proof["asset_id"],
                         "asset_id":color_proof["asset_id"],
                         "attestation_id":color_proof["attestation_id"]},
                 "interpolation":"tetrahedral"},
             "output_profile":"prores_10bit_sdr"}
        spec=self.root/"director-matched-color-plan.json"
        spec.write_text(json.dumps(color_plan),encoding="utf-8")
        output=self.root/"final-vfx-graded-master.mov"
        final=render_verified_color_job(spec,self.root,self.root/"vault",output)
        self.assertEqual(final["output_profile"],"prores_10bit_sdr")
        self.assertEqual(final["source_movie_sha256"],source["asset_id"])
        self.assertTrue(final["audio_present"])
        self.assertFalse(final["claimed_aces_hdr_or_scene_linear"])
        self.assertEqual(sha256_file(original_master),original_sha)
        self.assertTrue(_probe_details(output)["audio_stream_present"])
        _actual_bt709_source(output)
        before=self.pixel(original_master,80,50)
        # Decode 10-bit ProRes back into RGB pixels, never use JSON claims.
        after=self.pixel(output,80,50)
        self.assertGreater(before[0],before[1]+60,before)
        self.assertGreater(after[1],after[0]+40,after)
        self.assertGreater(self.pixel(output,7,7)[2],120)
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-xerror",
                        "-i",str(output),"-map","0:v:0","-map","0:a:0",
                        "-f","null","-"],check=True,timeout=45)
        self.assertTrue(original_master.exists())
        self.assertTrue(self.original.exists())
        # Preserve a physically decodable pair of real test movies and their
        # source-to-pixel evidence in one GitHub Actions review artifact.
        # Technical VFX/color acceptance is NOT creative human acceptance.
        evidence_dir=os.getenv("ZX7_COLOR_VFX_PROOF")
        if evidence_dir:
            destination=Path(evidence_dir).resolve()
            destination.mkdir(parents=True,exist_ok=True)
            def archive_original(path):
                target=destination/path.name
                if target.exists():
                    raise FileExistsError("Never overwrite accepted original media evidence")
                shutil.copyfile(path,target)
                return {"file":target.name,"sha256":sha256_file(target),
                        "bytes":target.stat().st_size,
                        "video_and_real_original_audio":_probe_details(target)["audio_stream_present"]}
            files=[archive_original(x) for x in (
                self.original,original_master,output)]
            screenshot=destination/"actual-verified-10bit-grade-frame.png"
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                "-i",str(output),"-frames:v","1",str(screenshot)],
                capture_output=True,check=True,timeout=30)
            (destination/"physical-color-vfx-evidence.json").write_text(
                json.dumps({"schema":1,"rights_verified_by_MediaVault":True,
                    "actual_VFX_matting_pixels_compared":True,
                    "actual_lut_pixels_compared":True,
                    "source_movie_original_sha256":original_sha,
                    "original_LUT_sha256":color_proof["asset_id"],
                    "bt709_tag_checked_through_output":True,
                    "ten_bit_prores_original_sound_decoded":True,
                    "scene_linear_OCIO_ACES_claimed":False,
                    "artist_human_quality_approved":False,
                    "original_files":files,
                    "decoded_frame":{"file":screenshot.name,
                        "sha256":sha256_file(screenshot)}},indent=2)+"\n",
                encoding="utf-8")

    def test_false_key_parameters_unlicensed_media_or_shell_injection_blocked(self):
        layer=self.film["video_layers"][0]
        for field,value in (("similarity",0),("similarity",2),
                             ("similarity","x; rm -rf /"),
                             ("blend",-1),("blend",float("inf")),
                             ("color","#00ff00';rm -rf /")):
            old=layer["chroma_key"][field]
            layer["chroma_key"][field]=value
            with self.assertRaises((ValueError,TypeError)):
                actual_composite_command(self.film,self.root,self.vault,
                                         self.root/"unsafe.mp4")
            layer["chroma_key"][field]=old
        layer["asset_id"]="0"*64
        with self.assertRaises(ValueError):
            actual_composite_command(self.film,self.root,self.vault,
                                     self.root/"unsafe.mp4")
        self.assertFalse((self.root/"unsafe.mp4").exists())


if __name__=="__main__":unittest.main()

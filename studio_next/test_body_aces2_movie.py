"""Real two-frame Blender->owned EXR->ACES2 16-bit raster->10-bit ProRes proof."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_aces2_movie import render_aces2_scene_movie
from studio_next.body_aces2_preview import SOURCE_COLOR,DISPLAY,VIEW
from studio_next.body_exr_passes import render_original_exr_passes
from studio_next.body_integration import body_catalog,validate_witness
from studio_next.body_publication import physical_tool_attempt
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.test_blender_scene import sample

_READY=(shutil.which("blender") and shutil.which("ffmpeg") and
        importlib.util.find_spec("OpenEXR") and
        importlib.util.find_spec("PyOpenColorIO") and
        importlib.util.find_spec("numpy"))


@unittest.skipUnless(_READY,"Real Blender/OpenEXR/OCIO/FFmpeg native film stack required")
class ActualNativeSceneToProRes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        scene=sample()
        scene["shot_id"]="native-two-frame-aces2-prores-scene"
        scene["width"]=96;scene["height"]=64
        scene["frames"]=2;scene["fps"]=12;scene["samples"]=2
        scene["camera"]["animate_location"][-1]["frame"]=2
        for obj in scene["objects"]:
            for curve in obj.get("animate",{}).values():
                if curve:curve[-1]["frame"]=2
        self.scene=self.root/"owned-director-shot.json"
        self.scene.write_text(json.dumps(scene))
        self.archive=self.root/"verified-original-32f-exr.zip"
        render_original_exr_passes(self.scene,self.root,self.archive)
        with physical_tool_attempt("original-cinema","original-exr",
                                   "blender-native-proof","body.asset_vault"):
            proof=body_catalog(self.root).invoke(
                "body.asset_vault",{"source_witness":{
                    "path":str(self.archive),
                    "sha256":sha256_file(self.archive),
                    "bytes":self.archive.stat().st_size}},
                allowed_access={"read","write"})
        self.proof=proof
        self.plan={"source":{
            "source":"zx7:sha256:"+proof["asset_id"],
            "asset_id":proof["asset_id"],
            "attestation_id":proof["attestation_id"]},
            "source_color_space":SOURCE_COLOR,
            "alpha_association":"associated_scene_linear",
            "scene_linear_background_rgb":[.025,.045,.09],
            "display":DISPLAY,"view":VIEW}
        self.planfile=self.root/"real-director-color.json"
        self.planfile.write_text(json.dumps(self.plan))
    def tearDown(self):self.temp.cleanup()

    def test_all_actual_linear_frames_produce_decoded_10bit_sdr_movie(self):
        listed={x["id"]:x for x in body_catalog(self.root).discover()}
        self.assertEqual(listed["body.aces2_movie"]["status"],"installed")
        args={"plan":self.planfile.name,"out":"real-aces2-prores.mov"}
        response=body_catalog(self.root).invoke(
            "body.aces2_movie",args,allowed_access={"read","write"})
        self.assertTrue(validate_witness("body.aces2_movie",response))
        observed=subprocess.run(["ffprobe","-v","error","-count_frames",
            "-show_entries","stream=codec_name,pix_fmt,nb_read_frames,color_space,color_transfer,color_primaries,color_range",
            "-of","json",str(self.root/"real-aces2-prores.mov")],
            capture_output=True,text=True,check=True,timeout=60)
        streams=json.loads(observed.stdout)["streams"]
        self.assertEqual(len(streams),1)
        self.assertEqual(streams[0]["codec_name"],"prores")
        self.assertEqual(streams[0]["pix_fmt"],"yuv422p10le")
        self.assertEqual(streams[0]["nb_read_frames"],"2")
        self.assertEqual(streams[0].get("color_space"),"bt709")
        self.assertEqual(streams[0].get("color_primaries"),"bt709")
        self.assertFalse(list(self.root.glob(".zx7-aces2-movie-*")))

    def test_native_aces2_movie_enters_real_generated_license_and_resumes(self):
        from studio_next.body_integration import run_body_project
        graph={"project":{"creative_intent":
                     "Actual 32f Blender scene graded to independent SDR MOV"},
               "assets":[],
               "shots":[{"id":"scene","purpose":"Physically color manage complete CG shot",
                         "duration_seconds":2/12}],
               "tool_graph":[
                   {"id":"movie","tool_id":"body.aces2_movie",
                    "purpose":"Original every-frame ACES2 scene conversion",
                    "inputs":{"plan":self.planfile.name,
                              "out":"full-director-ACES2.mov"},
                    "depends_on":[]},
                   {"id":"rights","tool_id":"body.asset_vault",
                    "purpose":"Custody of actual decoded original color-managed MOV",
                    "inputs":{"source_witness":{"$node_output":"movie"}},
                    "depends_on":["movie"]}]}
        first=run_body_project(graph,self.root)
        self.assertEqual(first["status"],"all_tool_results_verified",first)
        self.assertEqual(first["completed"],["movie","rights"])
        result=self.root/"full-director-ACES2.mov"
        digest=sha256_file(result)
        asset=MediaVault(self.root/"vault").inspect(digest)
        self.assertEqual(asset["mime"],"video/quicktime")
        self.assertTrue(any(x["rights"]=="generated_original" and
                            x["source_type"]=="trusted_renderer"
                            for x in asset["rights_attestations"]))
        second=run_body_project(graph,self.root)
        self.assertEqual(second["status"],"all_tool_results_verified",second)
        self.assertEqual(second["reused"],["movie","rights"])
        self.assertEqual(sha256_file(result),digest)
        self.assertFalse(second["video_proven"])

    def test_production_movie_does_not_allow_swapped_rights_or_source_primaries(self):
        self.plan["source_color_space"]="ACEScg (unproven source)"
        self.planfile.write_text(json.dumps(self.plan))
        with self.assertRaisesRegex(ValueError,"Only pinned ACES2"):
            render_aces2_scene_movie(self.planfile,self.root,self.root/"vault",
                                     self.root/"untrustworthy.mov")
        self.assertFalse((self.root/"untrustworthy.mov").exists())

    def test_another_artist_wins_prores_output_without_truncation(self):
        existing=self.root/"first-approved-aces.mov"
        render_aces2_scene_movie(self.planfile,self.root,self.root/"vault",existing)
        expected_sha=sha256_file(existing)
        target=self.root/"other-approved-master.mov"
        real_link=os.link
        collided=False
        from studio_next import body_aces2_movie as movie
        def first_artist_wins(src,dst,*a,**k):
            nonlocal collided
            if Path(dst)==target:
                shutil.copyfile(existing,target)
                collided=True
            return real_link(src,dst,*a,**k)
        with patch.object(movie.os,"link",side_effect=first_artist_wins):
            with self.assertRaises(FileExistsError):
                render_aces2_scene_movie(self.planfile,self.root,
                                         self.root/"vault",target)
        self.assertTrue(collided)
        self.assertEqual(sha256_file(target),expected_sha)

"""Physical VFX matte: only actually owned video and sound, observed pixels."""
from __future__ import annotations

import json
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
            "-map","[v]","-map","1:a:0","-c:v","libx264","-pix_fmt","yuv420p",
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
                    "background":"#0000FF"},
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
        inputs=fingerprint_physical_inputs("body.composite_mix",
                    {"plan":self.file.name},self.root)
        self.assertIn(self.evidence["asset_id"],[x["sha256"] for x in inputs])

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

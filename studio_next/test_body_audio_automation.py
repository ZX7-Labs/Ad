"""Genuine artist-keyframed multiple-track AUDIO amplitude on real film timeline.

Verifies actual H264/AAC director cut has an audible -24 dB relative region
in the specified audio track, not just an FFmpeg string or mocked command.
Actual sample-by-sample FFmpeg aeval interpolation is independently checked.
"""
from __future__ import annotations
import json
import array
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from studio_next.composite_mix import actual_composite_command,render_composition
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.body_observation import _snapshot_window
from studio_next.delivery_audit import _probe_details

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "Native FFmpeg movie + soundtrack decoder required")
class OriginalKeyframedSoundtrackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.sound=self.root/"original-artist-sine.wav"
        result=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                 "-f","lavfi","-i","sine=frequency=550:sample_rate=48000:duration=2",
                 "-c:a","pcm_s16le",str(self.sound)],
                 capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        self.vault=MediaVault(self.root/"vault")
        self.rights=self.vault.ingest(self.sound,mime="audio/wav",
            rights="owner_supplied",source_type="owner_upload",
            source_id="sine-test-recording",
            evidence="Original sound generated for physical licensed audio test",
            owner_or_generator="owner")
        self.film={
          "canvas":{"width":160,"height":90,"fps":12,"duration":2,
                    "background":"#151515"},
          "video_layers":[],
          "audio_tracks":[{
            "id":"original_narration","source":"zx7:sha256:"+self.rights["asset_id"],
            "asset_id":self.rights["asset_id"],
            "attestation_id":self.rights["attestation_id"],
            "start":0,"source_in":0,"duration":2,"gain_db":0,
            "gain_keyframes":[
              {"at_seconds":0,"gain_db":0},
              {"at_seconds":0.3,"gain_db":0},
              {"at_seconds":0.65,"gain_db":-24},
              {"at_seconds":1.2,"gain_db":-24},
              {"at_seconds":1.55,"gain_db":0},
              {"at_seconds":2,"gain_db":0}]}]}
        self.plan=self.root/"artist-audio-automation.json"
        self.save()
    def tearDown(self):self.tmp.cleanup()
    def save(self):self.plan.write_text(json.dumps(self.film),encoding="utf-8")
    def test_real_audio_envelope_attentuates_measured_audio_without_changing_original(self):
        orig_sha=sha256_file(self.sound)
        filter_args=actual_composite_command(
            self.film,self.root,self.vault,self.root/"original-decision.mp4")
        filter_graph=filter_args[filter_args.index("-filter_complex")+1]
        self.assertIn("aeval=exprs='val(ch)*(if(lt(t,",filter_graph)
        self.assertIn(":c=same",filter_graph)
        self.assertIn("volume=0dB",filter_graph)
        output=self.root/"original-decision.mp4"
        result=render_composition(self.plan,self.root,self.root/"vault",output)
        self.assertTrue(result["verified_physically"])
        self.assertTrue(_probe_details(output)["audio_stream_present"])
        a=_snapshot_window(output,0.05,0.2)
        b=_snapshot_window(output,0.85,1.1)
        c=_snapshot_window(output,1.78,1.93)
        self.assertGreater(a["mean_dbfs"]-b["mean_dbfs"],16,(a,b,c))
        self.assertGreater(c["mean_dbfs"]-b["mean_dbfs"],16,(a,b,c))
        self.assertEqual(sha256_file(self.sound),orig_sha)
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-xerror",
            "-i",str(output),"-map","0:v:0","-map","0:a:0",
            "-f","null","-"],check=True,capture_output=True,timeout=30)
    def test_raw_physical_pcm_gain_matches_individual_sample_interpolation(self):
        # FFmpeg volume=eval=frame would apply one gain per AUDIO BLOCK;
        # this regression asserts the absolute 48 kHz sample 24000 and
        # adjacent sample 24001 have independent correct interpolation.
        from studio_next.composite_mix import _gain_automation_expression
        envelope={"gain_keyframes":[{"at_seconds":0,"gain_db":0},
                                    {"at_seconds":1,"gain_db":-20}]}
        actual_filter=_gain_automation_expression(envelope)
        self.assertIn("aeval=exprs=",actual_filter)
        self.assertNotIn("eval=frame",actual_filter)
        def decoded(filter_string):
            cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                 "-f","lavfi","-i",
                 "aevalsrc=0.5:sample_rate=48000:duration=1",
                 "-af",filter_string,"-ar","48000","-ac","2",
                 "-c:a","pcm_f32le","-f","f32le","pipe:1"]
            output=subprocess.run(cmd,capture_output=True,timeout=35)
            self.assertEqual(output.returncode,0,output.stderr.decode()[-900:])
            pcm=array.array("f")
            pcm.frombytes(output.stdout)
            self.assertEqual(len(pcm),48000*2)
            return pcm
        reference=decoded("aformat=channel_layouts=stereo")
        changed=decoded("aformat=channel_layouts=stereo,"+actual_filter)
        for sample in (0,1,12000,24000,24001,36000,47999):
            with self.subTest(sample=sample):
                expected=1-0.9*sample/48000
                amplitude=changed[sample*2]/reference[sample*2]
                self.assertAlmostEqual(amplitude,expected,delta=0.00005)
                self.assertAlmostEqual(changed[sample*2+1]/reference[sample*2+1],
                                       expected,delta=0.00005)
        self.assertNotEqual(changed[24000*2],changed[24001*2])

    def test_bad_artist_gains_and_shot_timeline_escapes_refused_without_render(self):
        line=self.film["audio_tracks"][0]
        cases=[
          [{"at_seconds":0,"gain_db":0},{"at_seconds":0,"gain_db":-12}],
          [{"at_seconds":0,"gain_db":0},{"at_seconds":3,"gain_db":-12}],
          [{"at_seconds":0,"gain_db":float("nan")}],
          [{"at_seconds":0,"gain_db":"rm -rf /"}],
          [{"at_seconds":0,"gain_db":True}],
          [{"at_seconds":0,"gain_db":0},{"at_seconds":1.2,"gain_db":-125}],
          [{"at_seconds":0,"gain_db":0},{"at_seconds":-0.5,"gain_db":0}],
          [{"at_seconds":0,"gain_db":0,"untrusted_shell":"echo fake"}],
          "not a list"
        ]
        original=line["gain_keyframes"]
        for bad in cases:
            line["gain_keyframes"]=bad
            with self.assertRaises(ValueError):
                actual_composite_command(self.film,self.root,self.vault,
                                         self.root/"never-written.mp4")
        line["gain_keyframes"]=original
        self.assertFalse((self.root/"never-written.mp4").exists())

if __name__=="__main__":
    unittest.main()

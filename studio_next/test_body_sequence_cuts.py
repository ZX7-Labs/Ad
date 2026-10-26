"""Original licensed camera multishot frame-accurate timeline: physical MP4 proof.

Real 24 fps original red then blue source with independent owner attestations
and different actual sound pitches. Director explicitly selects an interior
12-frame span then a separate 24-frame shot. The final film must have
36 decoded frames, the intended RGB picture edit and one real audio stream.

The color/pitch choices are test fixtures only, never a studio style preset.
"""
from __future__ import annotations
import copy
import array
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_sequence_cuts import plan_verified_sequence,render_verified_sequence
from studio_next.body_integration import body_catalog,validate_witness
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.precision_retime import _source_timebase
from studio_next.delivery_audit import _probe_details

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Actual native original picture and sound engines required")
class RealOwnedSequenceCuts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.vault=MediaVault(self.root/"vault")
        self.originals=[]
        for index,color,pitch in ((1,"red",410),(2,"blue",690)):
            movie=self.root/f"original_camera_{index}.mp4"
            cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
                 "-f","lavfi","-i",f"color=c={color}:s=160x90:r=24:d=1.5",
                 "-f","lavfi","-i",f"sine=frequency={pitch}:sample_rate=48000:duration=1.5",
                 "-c:v","libx264","-pix_fmt","yuv420p",
                 "-x264-params","colorprim=bt709:transfer=bt709:colormatrix=bt709",
                 "-color_primaries","bt709","-color_trc","bt709","-colorspace","bt709",
                 "-c:a","aac","-b:a","128k","-shortest",str(movie)]
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
            self.assertEqual(p.returncode,0,p.stderr)
            receipt=self.vault.ingest(movie,mime="video/mp4",
                   rights="owner_supplied",source_type="owner_upload",
                   source_id=f"original-camera_{index}",
                   evidence="Real original self-rendered filmed-with-sound test footage",
                   owner_or_generator="owner")
            self.originals.append((movie,receipt))
        def clip(i,a,b):
            movie,receipt=self.originals[i]
            return {"source":"zx7:sha256:"+receipt["asset_id"],
                    "asset_id":receipt["asset_id"],
                    "attestation_id":receipt["attestation_id"],
                    "first_frame":a,"end_frame":b,"audio":"preserve_source"}
        self.plan={
            "frame_rate":{"numerator":24,"denominator":1},
            "frame_size":{"width":160,"height":90},
            "clips":[clip(0,6,18),clip(1,0,24)]
        }
        self.document=self.root/"owner-frame-cut.json"
        self.save()
    def tearDown(self):self.temp.cleanup()
    def save(self):self.document.write_text(json.dumps(self.plan),encoding="utf-8")
    def _pixel(self,movie,stamp):
        proc=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
          "-ss",str(stamp),"-i",str(movie),"-frames:v","1","-pix_fmt","rgb24",
          "-f","rawvideo","pipe:1"],capture_output=True,timeout=30)
        self.assertEqual(proc.returncode,0,proc.stderr[-700:])
        return tuple(proc.stdout[(45*160+80)*3:(45*160+80)*3+3])

    def test_actual_licensed_36_frame_audio_visual_edit_with_original_sources_unchanged(self):
        identities=[sha256_file(x[0]) for x in self.originals]
        checked=plan_verified_sequence(self.plan,self.root,self.root/"vault")
        self.assertEqual(checked["frames"],36)
        self.assertAlmostEqual(checked["seconds"],1.5)
        output=self.root/"genuine-creator-two-shot.mp4"
        result=render_verified_sequence(self.document,self.root,self.root/"vault",output)
        self.assertEqual(result["physical_original_frames_delivered"],36)
        self.assertEqual(result["actual_cut_operations"],2)
        self.assertTrue(result["physically_verified_BT709_CFR"])
        self.assertFalse(result["creative_story_quality_certified"])
        self.assertEqual(_source_timebase(output)[1],36)
        self.assertTrue(_probe_details(output)["audio_stream_present"])
        self.assertGreater(self._pixel(output,0.25)[0],self._pixel(output,0.25)[2]+90)
        self.assertGreater(self._pixel(output,0.85)[2],self._pixel(output,0.85)[0]+90)
        self.assertEqual([sha256_file(x[0]) for x in self.originals],identities)
        with self.assertRaises(ValueError):
            render_verified_sequence(self.document,self.root,self.root/"vault",output)
        self.assertEqual(sha256_file(output),result["sha256"])
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-xerror",
            "-i",str(output),"-map","0:v:0","-map","0:a:0",
            "-f","null","-"],capture_output=True,check=True,timeout=40)
    def test_real_picture_cut_preserves_each_separate_source_sound_frequency(self):
        result=render_verified_sequence(self.document,self.root,self.root/"vault",
                    self.root/"audited-source-sound.mp4")
        self.assertEqual(result["physical_original_frames_delivered"],36)
        def sound_hz(start,period=0.20):
            raw=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                "-ss",str(start),"-i",str(self.root/"audited-source-sound.mp4"),
                "-vn","-t",str(period),"-ar","48000","-ac","1",
                "-c:a","pcm_s16le","-f","s16le","pipe:1"],
                capture_output=True,timeout=40)
            self.assertEqual(raw.returncode,0,raw.stderr)
            pcm=array.array("h")
            pcm.frombytes(raw.stdout)
            self.assertGreater(len(pcm),4800)
            crossing=sum(1 for before,after in zip(pcm,pcm[1:])
                         if before<=0<after)
            return crossing/(len(pcm)/48000)
        original_first=sound_hz(.12)
        different_second=sound_hz(.90)
        self.assertAlmostEqual(original_first,410,delta=20)
        self.assertAlmostEqual(different_second,690,delta=25)

    def test_original_camera_picture_longer_than_recorded_sound_cannot_claim_preserved_audio(self):
        source=self.root/"picture-2s-sound-1s.mp4"
        command=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
            "-f","lavfi","-i","color=c=green:s=160x90:r=24:d=2",
            "-f","lavfi","-i",
            "sine=frequency=590:sample_rate=48000:duration=1",
            "-c:v","libx264","-pix_fmt","yuv420p",
            "-x264-params","colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-color_primaries","bt709","-color_trc","bt709","-colorspace","bt709",
            "-c:a","aac",str(source)]
        proc=subprocess.run(command,capture_output=True,text=True,timeout=60)
        self.assertEqual(proc.returncode,0,proc.stderr)
        proof=self.vault.ingest(source,mime="video/mp4",
            rights="owner_supplied",source_type="owner_upload",
            source_id="original-camera-with-short-recorded-dialogue",
            evidence="Actual original two-second picture with one-second original audio",
            owner_or_generator="owner")
        self.plan["clips"][0].update({
            "source":"zx7:sha256:"+proof["asset_id"],
            "asset_id":proof["asset_id"],
            "attestation_id":proof["attestation_id"],
            "first_frame":16,"end_frame":36,"audio":"preserve_source"})
        with self.assertRaisesRegex(ValueError,"outlasts recorded original audio"):
            plan_verified_sequence(self.plan,self.root,self.root/"vault")
        self.plan["clips"][0]["audio"]="intentional_silence"
        audited=plan_verified_sequence(self.plan,self.root,self.root/"vault")
        self.assertEqual(audited["frames"],44)
        self.plan["clips"][0].update({"first_frame":0,"end_frame":20,
                                      "audio":"preserve_source"})
        checked=plan_verified_sequence(self.plan,self.root,self.root/"vault")
        self.assertEqual(checked["frames"],44)

    def test_encoder_only_reads_sealed_rights_attested_original_sources_despite_checkout_swap(self):
        real_run=subprocess.run
        original=self.originals[0][0]
        owner_bytes=original.read_bytes()
        alternate=self.originals[1][0].read_bytes()
        consumed=[]
        def adversarial_encoder(argv,**kwargs):
            if argv and argv[0]=="ffmpeg" and "-filter_complex" in argv:
                inputs=[Path(argv[i+1]) for i,arg in enumerate(argv[:-1])
                        if arg=="-i"]
                self.assertEqual(len(inputs),2)
                for path in inputs:
                    self.assertIn(".zx7-owned-sources-",str(path))
                    self.assertFalse(path.stat().st_mode & 0o222)
                    self.assertIn(sha256_file(path),
                        {record["asset_id"] for _,record in self.originals})
                consumed.extend(inputs)
                # Modify the mutable owner-visible editor checkout for the
                # whole real native FFmpeg process, then restore originals.
                original.write_bytes(alternate)
                try:
                    return real_run(argv,**kwargs)
                finally:
                    original.write_bytes(owner_bytes)
            return real_run(argv,**kwargs)
        out=self.root/"actual-sealed-original-multicut.mp4"
        with patch("studio_next.body_sequence_cuts.subprocess.run",
                   side_effect=adversarial_encoder):
            evidence=render_verified_sequence(self.document,self.root,
                                                 self.root/"vault",out)
        self.assertTrue(evidence["full_picture_and_sound_decoder_completed"])
        self.assertTrue(evidence["sealed_original_cas_during_decode"])
        self.assertEqual(evidence["physical_original_frames_delivered"],36)
        self.assertEqual(sha256_file(original),self.originals[0][1]["asset_id"])
        self.assertGreater(self._pixel(out,.25)[0],self._pixel(out,.25)[2]+90)
        self.assertEqual(len(consumed),2)
        self.assertTrue(all(not p.exists() for p in consumed))
        self.assertFalse(list(self.root.glob(".zx7-owned-sources-*")))

    def test_concurrent_accepted_movie_cannot_be_unlinked_when_new_encode_loses_race(self):
        previous=self.root/"protected-director-master.mp4"
        original_bytes=b"DO-NOT-REPLACE-DIRECTOR-APPROVED-CREATIVE"
        actual_run=subprocess.run
        def concurrent_creator(argv,**kwargs):
            result=actual_run(argv,**kwargs)
            if argv and argv[0]=="ffmpeg" and "-filter_complex" in argv:
                previous.write_bytes(original_bytes)
            return result
        with patch("studio_next.body_sequence_cuts.subprocess.run",
                   side_effect=concurrent_creator):
            with self.assertRaises(FileExistsError):
                render_verified_sequence(self.document,self.root,
                                          self.root/"vault",previous)
        self.assertEqual(previous.read_bytes(),original_bytes)
        self.assertFalse(list(self.root.glob(".zx7-owned-sources-*")))

    def test_timeline_changed_while_real_encoder_runs_is_not_accepted(self):
        actual_run=subprocess.run
        altered=False
        def race(argv,**kwargs):
            nonlocal altered
            result=actual_run(argv,**kwargs)
            if not altered and argv and argv[0]=="ffmpeg":
                altered=True
                edited=copy.deepcopy(self.plan)
                edited["clips"][0]["first_frame"]=7
                self.document.write_text(json.dumps(edited),encoding="utf-8")
            return result
        with patch("studio_next.body_sequence_cuts.subprocess.run",side_effect=race):
            with self.assertRaisesRegex(ValueError,"timeline changed"):
                render_verified_sequence(self.document,self.root,self.root/"vault",
                    self.root/"never-accept-raced-cut.mp4")
        self.assertTrue(altered)
        self.assertFalse((self.root/"never-accept-raced-cut.mp4").exists())

    def test_actual_original_audio_can_be_explicitly_silenced_for_separate_shot(self):
        self.plan["clips"][0]["audio"]="intentional_silence";self.save()
        output=self.root/"author-chose-silence.mp4"
        result=render_verified_sequence(self.document,self.root,self.root/"vault",output)
        self.assertEqual(result["physical_original_frames_delivered"],36)
        self.assertTrue(_probe_details(output)["audio_stream_present"])
    def test_forged_source_hash_missing_rights_wrong_clock_or_out_of_range_denied(self):
        original=copy.deepcopy(self.plan)
        cases=[
            ("asset_id","0"*64),("attestation_id","forged-license"),
            ("first_frame",-1),("end_frame",1234),
            ("audio","pretend_preserve_stock_song"),("source","../../secret.mp4"),
        ]
        for field,value in cases:
            with self.subTest(field=field):
                self.plan=copy.deepcopy(original)
                self.plan["clips"][0][field]=value
                with self.assertRaises((ValueError,RuntimeError)):
                    plan_verified_sequence(self.plan,self.root,self.root/"vault")
        self.plan=copy.deepcopy(original)
        self.plan["frame_rate"]={"numerator":30,"denominator":1}
        with self.assertRaisesRegex(ValueError,"timebase"):
            plan_verified_sequence(self.plan,self.root,self.root/"vault")
        self.assertFalse((self.root/"unlicensed.mp4").exists())
    def test_installed_body_operation_records_cas_inputs_and_actual_movie(self):
        catalog=body_catalog(self.root)
        listing={x["id"]:x for x in catalog.discover()}
        self.assertEqual(listing["body.sequence_cuts"]["status"],"installed")
        self.assertEqual(listing["body.sequence_cuts"]["schema"]["required"],["plan","out"])
        physical=fingerprint_physical_inputs(
            "body.sequence_cuts",{"plan":self.document.name,"out":"editor.mp4"},self.root)
        hashes=[f["sha256"] for f in physical]
        for _,receipt in self.originals:
            self.assertIn(receipt["asset_id"],hashes)
        result=catalog.invoke("body.sequence_cuts",
              {"plan":self.document.name,"out":"editor.mp4"},
              allowed_access={"read","write"})
        self.assertTrue(validate_witness("body.sequence_cuts",result))
        self.assertEqual(result["sha256"],sha256_file(self.root/"editor.mp4"))

if __name__=="__main__":unittest.main()

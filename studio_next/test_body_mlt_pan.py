"""True original-source native stereo bus placement, keyframes and fail-closed XML.

MLT panner C source requires a 'start' property for animated 'split' to be
evaluated. Test actual left/right recorded PCM, not merely XML attributes or
an encoded MP4 that could silently ignore the plugin. No artist pan presets.
"""
import copy
import hashlib
import json
import math
import shutil
import struct
import subprocess
import tempfile
import unittest
from array import array
from pathlib import Path

from studio_next.body_document_schemas import validate_document
from studio_next.body_mlt_editor import (
    _pan_animation,_verify_native_pan,build_mlt_xml,
    verify_owned_mlt_project,validate_mlt_edit)
from studio_next.body_mlt_roundtrip import recover_original_mlt_plan
from studio_next.body_mlt_linked_actions import apply_linked_editor_actions
from studio_next.media_vault import MediaVault


class NativeStereoPanTests(unittest.TestCase):
    def test_pan_is_explicit_finite_typed_source_animation_not_filter_syntax(self):
        self.assertEqual(_pan_animation({},12),"0.5")
        self.assertEqual(_pan_animation({"pan":0},12),"0")
        self.assertEqual(_pan_animation({"pan":1},12),"1")
        self.assertEqual(_pan_animation({"pan_keyframes":[
            {"frame":0,"pan":0},{"frame":11,"pan":1}]},12),"0=0;11=1")
        self.assertEqual(_verify_native_pan("0=0;11=1",12),"0=0;11=1")
        for invalid in (True,None,math.nan,math.inf,-.01,1.01,"0.5",
                        "1;exec",{"channel":1}):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                _pan_animation({"pan":invalid},12)
        for invalid in ("0.5;rm -rf /","float(0.5)","nan","Infinity",
                        "0=0;0=1","0=0;12=1","1=0;11=1",
                        "00=0;11=1","0=0;11=2","0.5000000000000"):
            with self.subTest(encoded=invalid),self.assertRaises(ValueError):
                _verify_native_pan(invalid,12)
        for invalid in (
            {"pan":0.25,"pan_keyframes":[{"frame":0,"pan":0},{"frame":11,"pan":1}]},
            {"pan_keyframes":[{"frame":1,"pan":0},{"frame":11,"pan":1}]},
            {"pan_keyframes":[{"frame":0,"pan":0},{"frame":0,"pan":1}]},
            {"pan_keyframes":[{"frame":0,"pan":0},{"frame":11,"pan":1},
                               {"frame":12,"pan":0}]},
        ):
            with self.subTest(control=invalid),self.assertRaises(ValueError):
                _pan_animation(invalid,12)

    def test_ripple_keeps_original_stereo_position_at_every_source_frame(self):
        source={"frame_rate":{"numerator":12,"denominator":1},
             "frame_size":{"width":64,"height":48},
             "tracks":[{"clips":[{"source":"zx7:sha256:video",
                "asset_id":"video","attestation_id":"original-video",
                "first_frame":0,"end_frame":12,"position_frame":0,
                "audio":"intentional_silence"}]}],
             "audio_tracks":[{"clips":[{"source":"zx7:sha256:sound",
                "asset_id":"sound","attestation_id":"original-audio",
                "first_frame":0,"end_frame":12,"position_frame":0}],
                "pan_keyframes":[{"frame":0,"pan":0},
                                 {"frame":11,"pan":1}],
                "gain_keyframes":[{"frame":0,"gain_db":-12},
                                  {"frame":11,"gain_db":0}]}]}
        edits={"edits":[{
            "kind":"ripple_insert","frame":5,"frames":2,
            "picture_tracks":[0],"audio_tracks":[0],
            "automation":"preserve_source_frame_values"}]}
        after,evidence=apply_linked_editor_actions(source,edits)
        self.assertNotEqual(after,source)
        self.assertEqual(source["audio_tracks"][0]["pan_keyframes"][1]["frame"],11)
        for field,name in (("pan","pan_keyframes"),("gain_db","gain_keyframes")):
            before_curve=source["audio_tracks"][0][name]
            after_curve=after["audio_tracks"][0][name]
            def at(keys,frame):
                if frame<=keys[0]["frame"]:return keys[0][field]
                for l,r in zip(keys,keys[1:]):
                    if frame<=r["frame"]:
                        t=(frame-l["frame"])/(r["frame"]-l["frame"])
                        return l[field]+t*(r[field]-l[field])
                return keys[-1][field]
            for frame in range(12):
                moved=frame if frame<5 else frame+2
                self.assertAlmostEqual(at(before_curve,frame),
                                       at(after_curve,moved),delta=1e-9)
        self.assertLess(evidence["largest_interpolated_key_rounding"],1e-8)

    def test_500_random_pan_gain_curves_survive_exact_linked_audio_revisions(self):
        """Original authored sound levels and spatial position survive source edit algebra."""
        import random
        rng=random.Random(20261028)
        for case in range(500):
            source={"frame_rate":{"numerator":12,"denominator":1},
                "frame_size":{"width":64,"height":48},
                "tracks":[{"clips":[{"source":"zx7:sha256:video",
                    "asset_id":"video","attestation_id":"video-owner",
                    "first_frame":0,"end_frame":12,"position_frame":0,
                    "audio":"intentional_silence"}]}],
                "audio_tracks":[{"clips":[{"source":"zx7:sha256:sound",
                    "asset_id":"sound","attestation_id":"sound-owner",
                    "first_frame":0,"end_frame":12,"position_frame":0}]}]}
            locations=[0]+sorted(rng.sample(range(1,12),rng.randrange(1,8)))
            for prop,field,lo,hi in (("pan_keyframes","pan",0,1),
                                      ("gain_keyframes","gain_db",-80,20)):
                source["audio_tracks"][0][prop]=[
                    {"frame":f,field:rng.uniform(lo,hi)} for f in locations]
            frame=rng.randrange(1,11)
            amount=rng.randrange(1,8)
            actions={"edits":[
                {"kind":"ripple_insert","frame":frame,"frames":amount,
                 "picture_tracks":[0],"audio_tracks":[0],
                 "automation":"preserve_source_frame_values"},
                {"kind":"ripple_delete","frame":frame,"frames":amount,
                 "picture_tracks":[0],"audio_tracks":[0],
                 "automation":"preserve_source_frame_values"}]}
            restored,proof=apply_linked_editor_actions(source,actions)
            self.assertEqual(len(proof["operations"]),2)
            # Razor/ripple may legitimately retain different editable clip
            # partitions after undo, even while every physical source frame
            # is identical. Compare the actual media address per film frame.
            from studio_next.body_mlt_compare import _clip_intervals,_source_at
            old_intervals=_clip_intervals(source["audio_tracks"][0]["clips"])
            new_intervals=_clip_intervals(restored["audio_tracks"][0]["clips"])
            for pos in range(12):
                self.assertEqual(_source_at(old_intervals,pos),
                                 _source_at(new_intervals,pos),msg=(case,pos))
            for key,field in (("pan_keyframes","pan"),
                              ("gain_keyframes","gain_db")):
                def sample(keys,at):
                    if at<=keys[0]["frame"]:return keys[0][field]
                    for prev,next_ in zip(keys,keys[1:]):
                        if at<=next_["frame"]:
                            w=(at-prev["frame"])/(next_["frame"]-prev["frame"])
                            return prev[field]+w*(next_[field]-prev[field])
                    return keys[-1][field]
                actual=restored["audio_tracks"][0]
                self.assertIn(key,actual)
                for at in range(12):
                    self.assertAlmostEqual(
                        sample(source["audio_tracks"][0][key],at),
                        sample(actual[key],at),delta=1e-8,
                        msg=(case,key,frame,amount,at))

    @unittest.skipUnless(shutil.which("melt"),
                         "Require actual native MLT and FFmpeg for stereo proof")
    def test_brain_authored_native_pan_moves_real_pcm_channels_and_reverses_exactly(self):
        from math import sqrt
        from studio_next.body_integration import body_catalog
        from studio_next.test_body_mlt_editor import VerifiedMLTEditorialTests
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            fixture=VerifiedMLTEditorialTests()
            plan,plan_file=fixture._case(root)
            original_sound=root/"actual-stereo.wav"
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                "-nostdin","-f","lavfi","-i",
                "sine=frequency=620:sample_rate=48000:duration=1",
                "-ac","2","-c:a","pcm_s16le","-y",str(original_sound)],
                check=True,timeout=35)
            wav_bytes=original_sound.read_bytes()
            sound=MediaVault(root/"vault").ingest(original_sound,
                mime="audio/wav",rights="owner_supplied",
                source_type="owner_upload",source_id="actual-two-channel-620hz",
                evidence="Independent actual recorded stereo PCM fixture",
                owner_or_generator="fixture-creator")
            plan["audio_tracks"]=[{"clips":[{
                "source":"zx7:sha256:"+sound["asset_id"],
                "asset_id":sound["asset_id"],
                "attestation_id":sound["attestation_id"],
                "first_frame":0,"end_frame":12,"position_frame":0}]}]
            plan_file.write_text(json.dumps(plan))
            catalog=body_catalog(root)
            catalog.invoke("body.mlt_owned_export",{
                "plan":plan_file.name,"out":"center-original.mlt"},
                allowed_access={"write"})
            untouched=(root/"center-original.mlt").read_bytes()
            first=recover_original_mlt_plan(root/"center-original.mlt",
                                             root,root/"vault")["plan"]
            self.assertNotIn("pan",first["audio_tracks"][0])

            revisions={
                "left":{"operations":[{"op":"add",
                    "path":"/audio_tracks/0/pan","value":0}]},
                "right":{"operations":[{"op":"add",
                    "path":"/audio_tracks/0/pan","value":1}]},
                "animated":{"operations":[{"op":"add",
                    "path":"/audio_tracks/0/pan_keyframes","value":[
                        {"frame":0,"pan":0},{"frame":11,"pan":1}]}]},
            }
            for name,decision in revisions.items():
                (root/(name+".json")).write_text(json.dumps(decision))
                result=catalog.invoke("body.mlt_owned_revision",{
                    "edit":"center-original.mlt","operation":name+".json",
                    "out":name+"-native.mlt"},allowed_access={"write"})
                self.assertEqual(result["prior_mlt_sha256"],
                                 hashlib.sha256(untouched).hexdigest())
                restored=recover_original_mlt_plan(
                    root/(name+"-native.mlt"),root,root/"vault")["plan"]
                self.assertEqual(restored["tracks"],first["tracks"])
                self.assertEqual(restored["audio_tracks"][0]["clips"],
                                 first["audio_tracks"][0]["clips"])
                if name=="animated":
                    self.assertEqual(restored["audio_tracks"][0]["pan_keyframes"],
                                     decision["operations"][0]["value"])
                else:
                    self.assertEqual(restored["audio_tracks"][0]["pan"],
                                     decision["operations"][0]["value"])
                review=catalog.invoke("body.mlt_owned_compare",{
                    "before_edit":"center-original.mlt",
                    "after_edit":name+"-native.mlt"},allowed_access={"read"})
                self.assertEqual(len(review["sound_changes"]),1)
                self.assertIsNotNone(
                    review["sound_changes"][0]["native_track_controls"])
                self.assertEqual(
                    review["sound_changes"][0]["source_frame_spans"],[])
                self.assertTrue(review["exact_source_rights_and_native_roundtrips_rechecked"])
            def channels(name):
                catalog.invoke("body.mlt_owned_render",{
                    "edit":name+"-native.mlt","out":name+".mp4"},
                    allowed_access={"write"})
                raw=subprocess.check_output(["ffmpeg","-hide_banner",
                    "-loglevel","error","-nostdin","-xerror",
                    "-i",str(root/(name+".mp4")),"-map","0:a:0",
                    "-ac","2","-ar","48000","-f","s16le","-"],
                    timeout=50)
                samples=array("h");samples.frombytes(raw)
                self.assertGreaterEqual(len(samples),90000)
                return samples
            left,right,animated=(channels(name) for name in
                                  ("left","right","animated"))
            def rms(samples,channel,lo,hi):
                vals=samples[2*lo+channel:2*hi:2]
                return sqrt(sum(v*v for v in vals)/len(vals))
            lo=12000;hi=18000
            ll=rms(left,0,lo,hi);lr=rms(left,1,lo,hi)
            rl=rms(right,0,lo,hi);rr=rms(right,1,lo,hi)
            self.assertGreater(ll,300)
            self.assertGreater(rr,300)
            self.assertGreater(ll,lr*8)
            self.assertGreater(rr,rl*8)
            first_l=rms(animated,0,3500,8500)
            first_r=rms(animated,1,3500,8500)
            last_l=rms(animated,0,39000,44000)
            last_r=rms(animated,1,39000,44000)
            self.assertGreater(first_l,first_r*3)
            self.assertGreater(last_r,last_l*3)
            self.assertEqual(original_sound.read_bytes(),wav_bytes)
            self.assertEqual((root/"center-original.mlt").read_bytes(),untouched)
            forged=(root/"left-native.mlt").read_text()
            wrong=forged.replace(
                '<property name="channel">-1</property>',
                '<property name="channel">0</property>')
            self.assertNotEqual(wrong,forged)
            (root/"untrusted-panner.mlt").write_text(wrong)
            with self.assertRaises(ValueError):
                verify_owned_mlt_project(root/"untrusted-panner.mlt")
            self.assertEqual((root/"left-native.mlt").read_text(),forged)


    @unittest.skipUnless(shutil.which("melt"),
                         "Genuine two-original-audio-bus MLT stereo evidence required")
    def test_two_original_sound_buses_keep_distinct_panned_tones_with_native_gain(self):
        """Real frequencies prove one bus was not silently routed to the other."""
        from math import cos,sin,pi,sqrt
        from studio_next.body_integration import body_catalog
        from studio_next.test_body_mlt_editor import VerifiedMLTEditorialTests
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            base,source_plan=VerifiedMLTEditorialTests()._case(root)
            sources=[]
            raw_bytes={}
            for frequency in (440,880):
                original=root/f"recorded-{frequency}.wav"
                subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                    "-nostdin","-f","lavfi","-i",
                    f"sine=frequency={frequency}:sample_rate=48000:duration=1",
                    "-ac","2","-c:a","pcm_s16le","-y",str(original)],
                    check=True,timeout=35)
                raw_bytes[str(original)]=original.read_bytes()
                sources.append(MediaVault(root/"vault").ingest(original,
                    mime="audio/wav",rights="owner_supplied",
                    source_type="owner_upload",
                    source_id=f"self-created-independent-{frequency}-tone",
                    evidence="Physical original stereo sound source",
                    owner_or_generator="fixture-creator"))
            base["audio_tracks"]=[]
            for record,position in zip(sources,(0,1)):
                base["audio_tracks"].append({
                    "clips":[{
                        "source":"zx7:sha256:"+record["asset_id"],
                        "asset_id":record["asset_id"],
                        "attestation_id":record["attestation_id"],
                        "first_frame":0,"end_frame":12,"position_frame":0}],
                    "gain_db":-6,"pan":position})
            source_plan.write_text(json.dumps(base))
            catalog=body_catalog(root)
            catalog.invoke("body.mlt_owned_export",{
                "plan":source_plan.name,"out":"separate-native-stereo-buses.mlt"},
                allowed_access={"write"})
            native=root/"separate-native-stereo-buses.mlt"
            preserved=native.read_bytes()
            edited=recover_original_mlt_plan(native,root,root/"vault")["plan"]
            self.assertEqual(edited["audio_tracks"],base["audio_tracks"])
            catalog.invoke("body.mlt_owned_render",{
                "edit":native.name,"out":"separate-native-stereo-buses.mp4"},
                allowed_access={"write"})
            raw=subprocess.check_output(["ffmpeg","-hide_banner",
                "-loglevel","error","-nostdin","-xerror",
                "-i",str(root/"separate-native-stereo-buses.mp4"),
                "-map","0:a:0","-ar","48000","-ac","2",
                "-f","s16le","-"],timeout=60)
            pcm=array("h");pcm.frombytes(raw)
            self.assertGreaterEqual(len(pcm),92000)
            def energy(channel,freq):
                start=12000
                count=12000
                phase=2*pi*freq/48000
                real=sum(pcm[2*i+channel]*cos(phase*i)
                         for i in range(start,start+count))
                imag=sum(pcm[2*i+channel]*sin(phase*i)
                         for i in range(start,start+count))
                return sqrt(real*real+imag*imag)/count
            left440=energy(0,440)
            right440=energy(1,440)
            left880=energy(0,880)
            right880=energy(1,880)
            self.assertGreater(left440,70)
            self.assertGreater(right880,70)
            self.assertGreater(left440,right440*5)
            self.assertGreater(right880,left880*5)
            self.assertGreater(left440,left880*4)
            self.assertGreater(right880,right440*4)
            self.assertEqual(native.read_bytes(),preserved)
            for filename,old in raw_bytes.items():
                self.assertEqual(Path(filename).read_bytes(),old)


if __name__=="__main__":
    unittest.main()

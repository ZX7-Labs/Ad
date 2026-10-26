"""True Academy OpenTimelineIO round-trip, source rights and audio loss adversary."""
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from studio_next.body_sequence_otio import (
    export_verified_sequence_otio,import_verified_sequence_otio)
from studio_next.media_vault import MediaVault


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Real original-frame codec required")
class OwnedOriginalOTIOContract(unittest.TestCase):
    def setUp(self):
        try:import opentimelineio as otio
        except ImportError:self.skipTest("Actual professional OTIO library not installed")
        self.otio=otio
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        vault=MediaVault(self.root/"vault")
        clips=[]
        for i,(shade,tone) in enumerate((("red",440),("blue",680))):
            source=self.root/f"actual-take-{i}.mp4"
            command=["ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                "-y","-f","lavfi","-i",
                f"color=c={shade}:s=160x90:r=24:d=1.5",
                "-f","lavfi","-i",
                f"sine=frequency={tone}:sample_rate=48000:duration=1.5",
                "-c:v","libx264","-pix_fmt","yuv420p",
                "-x264-params","colorprim=bt709:transfer=bt709:colormatrix=bt709",
                "-color_primaries","bt709","-color_trc","bt709","-colorspace","bt709",
                "-c:a","aac","-shortest",str(source)]
            result=subprocess.run(command,capture_output=True,text=True,timeout=70)
            self.assertEqual(result.returncode,0,result.stderr)
            proof=vault.ingest(source,mime="video/mp4",rights="owner_supplied",
                source_type="owner_upload",source_id=f"artist-take-{i}",
                evidence="Real owner's test take and native soundtrack",
                owner_or_generator="test-owner")
            clips.append({"source":"zx7:sha256:"+proof["asset_id"],
                "asset_id":proof["asset_id"],"attestation_id":proof["attestation_id"],
                "first_frame":4+i*2,"end_frame":17+i*3,
                "audio":"intentional_silence" if i==1 else "preserve_source"})
        self.plan={"frame_rate":{"numerator":24,"denominator":1},
            "frame_size":{"width":160,"height":90},"clips":clips}
        self.source=self.root/"original.json";self.source.write_text(json.dumps(self.plan))
        self.timeline=self.root/"original.otio"
    def tearDown(self):self.tmp.cleanup()
    def export(self):
        return export_verified_sequence_otio(self.source,self.root,
                                               self.root/"vault",self.timeline)
    def test_export_import_source_proofs_and_original_picture_sound(self):
        receipt=self.export()
        self.assertEqual(receipt["frame_count"],27)
        loaded=import_verified_sequence_otio(self.timeline,self.root,
                                             self.root/"vault")
        self.assertEqual(loaded["plan"],self.plan)
        self.assertTrue(loaded["all_audio_positions_and_sources_matched"])
        self.assertFalse(loaded["unrepresentable_effects_silently_dropped"])
        timeline=self.otio.adapters.read_from_file(str(self.timeline))
        self.assertEqual(len(timeline.video_tracks()),1)
        self.assertEqual(len(timeline.audio_tracks()),1)
        self.assertIsInstance(timeline.audio_tracks()[0][0],self.otio.schema.Clip)
        self.assertIsInstance(timeline.audio_tracks()[0][1],self.otio.schema.Gap)
        with self.assertRaises(ValueError):
            self.export()

    def test_independent_registered_body_can_export_and_import_actual_rights_checked_cut(self):
        from studio_next.body_integration import body_catalog,validate_witness
        from studio_next.body_materials import fingerprint_physical_inputs
        catalog=body_catalog(self.root)
        self.assertEqual({p["id"]:p["status"] for p in catalog.discover()}[
            "body.otio_owned_export"],"installed")
        exported=catalog.invoke("body.otio_owned_export",{
            "plan":"original.json","out":"registered-original.otio"},
            allowed_access={"write"})
        self.assertTrue(validate_witness("body.otio_owned_export",exported))
        self.assertTrue(exported["original_audio_kept_synchronized"])
        inputs=fingerprint_physical_inputs("body.otio_owned_import",{
            "edit":"registered-original.otio","out":"imported-cut.json"},self.root)
        self.assertGreaterEqual(len(inputs),3)
        result=catalog.invoke("body.otio_owned_import",{
            "edit":"registered-original.otio","out":"imported-cut.json"},
            allowed_access={"write"})
        self.assertTrue(result["industry_otio_edit_preserved_without_silent_drop"])
        self.assertEqual(json.loads((self.root/"imported-cut.json").read_text()),self.plan)
        with self.assertRaises(FileExistsError):
            catalog.invoke("body.otio_owned_import",{
                "edit":"registered-original.otio","out":"imported-cut.json"},
                allowed_access={"write"})

    def test_native_nle_reorder_preserves_audio_and_source_attestations(self):
        self.export()
        timeline=self.otio.adapters.read_from_file(str(self.timeline))
        for track in (timeline.video_tracks()[0],timeline.audio_tracks()[0]):
            first=track[0].deepcopy();second=track[1].deepcopy()
            track.clear();track.append(second);track.append(first)
        updated=self.root/"reordered.otio"
        self.otio.adapters.write_to_file(timeline,str(updated))
        result=import_verified_sequence_otio(updated,self.root,self.root/"vault")
        self.assertEqual(result["plan"]["clips"],list(reversed(self.plan["clips"])))
        self.assertEqual(result["frame_count"],27)

    def test_professionally_reordered_otio_becomes_real_27_frame_original_movie(self):
        from studio_next.body_sequence_cuts import render_verified_sequence
        from studio_next.media_vault import sha256_file
        from studio_next.precision_retime import _source_timebase
        self.export()
        original_videos=[self.root/f"actual-take-{i}.mp4" for i in range(2)]
        originals=[sha256_file(p) for p in original_videos]
        editable=self.otio.adapters.read_from_file(str(self.timeline))
        for track in (editable.video_tracks()[0],editable.audio_tracks()[0]):
            before=track[0].deepcopy()
            after=track[1].deepcopy()
            track.clear()
            track.append(after)
            track.append(before)
        edited=self.root/"director-reordered-original.otio"
        self.otio.adapters.write_to_file(editable,str(edited))
        actual=import_verified_sequence_otio(edited,self.root,self.root/"vault")
        self.assertEqual(actual["frame_count"],27)
        cut=self.root/"director-reordered-owned-cut.json"
        cut.write_text(json.dumps(actual["plan"]),encoding="utf-8")
        movie=self.root/"real-physical-editor-roundtrip.mp4"
        proof=render_verified_sequence(cut,self.root,self.root/"vault",movie)
        self.assertEqual(proof["physical_original_frames_delivered"],27)
        self.assertEqual(_source_timebase(movie)[1],27)
        for at,dominant,subordinate in ((.2,2,0),(.78,0,2)):
            frame=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                "-ss",str(at),"-i",str(movie),"-frames:v","1",
                "-pix_fmt","rgb24","-f","rawvideo","pipe:1"],
                capture_output=True,timeout=30,check=True).stdout
            rgb=frame[(45*160+80)*3:(45*160+80)*3+3]
            self.assertGreater(rgb[dominant],rgb[subordinate]+90)
        full=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-xerror",
              "-i",str(movie),"-map","0:v:0","-map","0:a:0",
              "-f","null","-"],capture_output=True,timeout=40)
        self.assertEqual(full.returncode,0,full.stderr)
        self.assertEqual([sha256_file(p) for p in original_videos],originals)

    def test_trims_and_synchronised_audio_must_change_together(self):
        self.export()
        timeline=self.otio.adapters.read_from_file(str(self.timeline))
        video=timeline.video_tracks()[0][0]
        video.source_range=self.otio.opentime.TimeRange(
            self.otio.opentime.RationalTime(5,24),
            self.otio.opentime.RationalTime(8,24))
        file=self.root/"drift.otio"
        self.otio.adapters.write_to_file(timeline,str(file))
        with self.assertRaisesRegex(ValueError,"drift"):
            import_verified_sequence_otio(file,self.root,self.root/"vault")
        audio=timeline.audio_tracks()[0][0]
        audio.source_range=video.source_range
        aligned=self.root/"aligned.otio"
        self.otio.adapters.write_to_file(timeline,str(aligned))
        recovered=import_verified_sequence_otio(aligned,self.root,self.root/"vault")
        self.assertEqual(recovered["plan"]["clips"][0]["first_frame"],5)
        self.assertEqual(recovered["plan"]["clips"][0]["end_frame"],13)

    def test_unknown_relinked_source_wrong_rights_and_dropped_audio_are_rejected(self):
        self.export()
        timeline=self.otio.adapters.read_from_file(str(self.timeline))
        timeline.video_tracks()[0][0].media_reference.target_url="file:///stolen/source.mp4"
        bad=self.root/"relink.otio"
        self.otio.adapters.write_to_file(timeline,str(bad))
        with self.assertRaisesRegex(ValueError,"CAS"):
            import_verified_sequence_otio(bad,self.root,self.root/"vault")
        timeline=self.otio.adapters.read_from_file(str(self.timeline))
        timeline.video_tracks()[0][0].metadata["zx7"]["attestation_id"]="fake"
        bad=self.root/"rights.otio"
        self.otio.adapters.write_to_file(timeline,str(bad))
        with self.assertRaises(ValueError):
            import_verified_sequence_otio(bad,self.root,self.root/"vault")
        timeline=self.otio.adapters.read_from_file(str(self.timeline))
        timeline.audio_tracks()[0].clear()
        bad=self.root/"lost-audio.otio"
        self.otio.adapters.write_to_file(timeline,str(bad))
        with self.assertRaisesRegex(ValueError,"unaligned"):
            import_verified_sequence_otio(bad,self.root,self.root/"vault")

    def test_nontrivial_effects_timewarps_disabled_clips_and_artist_markers_never_disappear(self):
        self.export()
        film=self.otio.adapters.read_from_file(str(self.timeline))
        original=film.video_tracks()[0][0]
        original.effects.append(self.otio.schema.LinearTimeWarp(time_scalar=1.75))
        altered=self.root/"unrepresented-timewarp.otio"
        self.otio.adapters.write_to_file(film,str(altered))
        with self.assertRaisesRegex(ValueError,"effects"):
            import_verified_sequence_otio(altered,self.root,self.root/"vault")

        film=self.otio.adapters.read_from_file(str(self.timeline))
        film.audio_tracks()[0][0].enabled=False
        altered=self.root/"muted-production-sound.otio"
        self.otio.adapters.write_to_file(film,str(altered))
        with self.assertRaisesRegex(ValueError,"Disabled"):
            import_verified_sequence_otio(altered,self.root,self.root/"vault")

        film=self.otio.adapters.read_from_file(str(self.timeline))
        frame=self.otio.opentime.RationalTime(1,24)
        film.video_tracks()[0][0].markers.append(self.otio.schema.Marker(
             name="Director's edit note",
             marked_range=self.otio.opentime.TimeRange(frame,frame)))
        altered=self.root/"lost-creative-note.otio"
        self.otio.adapters.write_to_file(film,str(altered))
        with self.assertRaisesRegex(ValueError,"markers"):
            import_verified_sequence_otio(altered,self.root,self.root/"vault")

    def test_unsupported_nle_transition_and_fractional_frame_refused(self):
        self.export()
        timeline=self.otio.adapters.read_from_file(str(self.timeline))
        timeline.video_tracks()[0][0].source_range=self.otio.opentime.TimeRange(
            self.otio.opentime.RationalTime(4.5,24),
            self.otio.opentime.RationalTime(9,24))
        bad=self.root/"fractional.otio";self.otio.adapters.write_to_file(timeline,str(bad))
        with self.assertRaisesRegex(ValueError,"Fractional"):
            import_verified_sequence_otio(bad,self.root,self.root/"vault")
        timeline=self.otio.adapters.read_from_file(str(self.timeline))
        timeline.video_tracks()[0].append(self.otio.schema.Gap(
            source_range=self.otio.opentime.TimeRange(
                self.otio.opentime.RationalTime(0,24),
                self.otio.opentime.RationalTime(5,24))))
        bad=self.root/"picture-gap.otio";self.otio.adapters.write_to_file(timeline,str(bad))
        with self.assertRaises(ValueError):
            import_verified_sequence_otio(bad,self.root,self.root/"vault")

"""Physical, adversarial verified cross-host OTIO media-link integration."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_archive import create_body_archive,restore_body_archive
from studio_next.body_asset_links import relink_verified_otio
from studio_next.media_vault import MediaVault,sha256_file

try:
    import opentimelineio as otio
except ImportError:
    otio=None


@unittest.skipUnless(otio is not None and shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Requires installed real OpenTimelineIO and FFmpeg")
class VerifiedProfessionalRelinkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.base=Path(self.temp.name)
        self.old=self.base/"original-compute"/"zx7-body"
        self.project=self.old/"projects"/"editorial"
        self.project.mkdir(parents=True)
        self.original_video=self.project/"camera-original.mp4"
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i","testsrc2=size=160x90:rate=24:duration=1",
            "-f","lavfi","-i","sine=frequency=600:duration=1",
            "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",
            str(self.original_video)],check=True,timeout=40)
        self.vault=MediaVault(self.project/"vault")
        self.proof=self.vault.ingest(self.original_video,mime="video/mp4",
            rights="owner_supplied",source_type="owner_upload",
            source_id="camera-asset-001",
            evidence="Owner filmed original on camera fixture",
            owner_or_generator="owner")
        self.src_otio=self.project/"unmodified_director_original.otio"
        film=otio.schema.Timeline(name="A real private owner edit")
        video=otio.schema.Track(name="Camera source",kind=otio.schema.TrackKind.Video)
        sound=otio.schema.Track(name="Original audio",kind=otio.schema.TrackKind.Audio)
        for name,track in (("Camera",video),("Original Sound",sound)):
            cut=otio.schema.Clip(name=name,media_reference=otio.schema.ExternalReference(
                target_url=self.original_video.as_uri()))
            cut.metadata["zx7"]={
                "source_artifact_sha256":self.proof["asset_id"],
                "source_path":self.original_video.name,
                "rights_class":"owner_supplied",
                "audio_director_choice":"preserve_source"}
            start=otio.opentime.RationalTime(4,24)
            duration=otio.opentime.RationalTime(13,24)
            cut.source_range=otio.opentime.TimeRange(start,duration)
            track.append(cut)
        sound.append(otio.schema.Gap(
            source_range=otio.opentime.TimeRange(
                otio.opentime.RationalTime(0,24),
                otio.opentime.RationalTime(2,24))))
        film.tracks.append(video)
        film.tracks.append(sound)
        film.metadata["original-director-intent"]="retain two separate tracks, clip trims and silence"
        otio.adapters.write_to_file(film,str(self.src_otio))
        self.sha_before=sha256_file(self.src_otio)
        self.saved=create_body_archive(self.old,self.base/"artist-media-backup.tar.gz")
        self.new=self.base/"new-machine"/"zx7-body"
        restore_body_archive(self.saved["archive"],self.new,
            expected_sha256=self.saved["sha256"],relocate=True)
        self.relinked=self.new/"projects"/"editorial"/"linked-after-moving.otio"
        self.source=self.new/"projects"/"editorial"/self.src_otio.name

    def tearDown(self):
        self.temp.cleanup()

    def run_relink(self):
        return relink_verified_otio(self.source,self.new,self.old,self.relinked)

    def test_real_video_sound_timing_tracks_preserved_and_bytes_proven(self):
        info=self.run_relink()
        self.assertEqual(info["source_clips"],2)
        self.assertEqual(sha256_file(self.source),self.sha_before)
        self.assertTrue(info["original_rights_verified_through_media_vault"])
        self.assertFalse(info["prior_host_render_jobs_reused"])
        self.assertTrue(self.relinked.is_file())
        old=otio.adapters.read_from_file(str(self.source))
        recent=otio.adapters.read_from_file(str(self.relinked))
        self.assertEqual(old.name,recent.name)
        self.assertEqual(old.metadata,recent.metadata)
        self.assertEqual([track.name for track in old.tracks],
                         [track.name for track in recent.tracks])
        self.assertEqual(len(old.audio_tracks()[0]),len(recent.audio_tracks()[0]))
        self.assertIsInstance(recent.audio_tracks()[0][-1],otio.schema.Gap)
        expected_video=self.new/"projects"/"editorial"/self.original_video.name
        self.assertEqual(sha256_file(expected_video),self.proof["asset_id"])
        for a,b in zip(old.find_clips(),recent.find_clips()):
            self.assertEqual(a.metadata,b.metadata)
            self.assertEqual(a.source_range,b.source_range)
            self.assertEqual(b.media_reference.target_url,expected_video.as_uri())
        from studio_next.delivery_audit import _probe_details
        physical=_probe_details(expected_video)
        self.assertTrue(physical["audio_stream_present"])
        self.assertEqual(physical["width"],160)

    def test_changed_original_media_forbids_rebinding_without_mutating_original(self):
        clip=self.new/"projects"/"editorial"/self.original_video.name
        clip.write_bytes(clip.read_bytes()+b"unapproved pixels")
        with self.assertRaisesRegex(ValueError,"differs"):
            self.run_relink()
        self.assertFalse(self.relinked.exists())
        self.assertEqual(sha256_file(self.source),self.sha_before)

    def test_fake_rights_class_or_missing_vault_rejected(self):
        film=otio.adapters.read_from_file(str(self.source))
        for clip in film.find_clips():
            clip.metadata["zx7"]={
                "source_artifact_sha256":self.proof["asset_id"],
                "source_path":self.original_video.name,
                "rights_class":"appropriately_licensed"}
        attack=self.new/"projects"/"editorial"/"malicious.otio"
        otio.adapters.write_to_file(film,str(attack))
        with self.assertRaisesRegex(ValueError,"rights differ"):
            relink_verified_otio(attack,self.new,self.old,self.relinked)
        self.assertFalse(self.relinked.exists())

    def test_outside_old_source_url_and_wrong_old_host_blocked(self):
        film=otio.adapters.read_from_file(str(self.source))
        for clip in film.find_clips():
            clip.media_reference.target_url="file:///other-user/secrets-original.mp4"
        attack=self.new/"projects"/"editorial"/"unowned.otio"
        otio.adapters.write_to_file(film,str(attack))
        with self.assertRaisesRegex(ValueError,"outside"):
            relink_verified_otio(attack,self.new,self.old,self.relinked)
        with self.assertRaisesRegex(ValueError,"host identity"):
            relink_verified_otio(self.source,self.new,self.base/"some-fake-original",
                                 self.relinked)
        self.assertFalse(self.relinked.exists())

    def test_replay_does_not_overwrite_existing_work(self):
        self.run_relink()
        previous=sha256_file(self.relinked)
        with self.assertRaises(FileExistsError):
            self.run_relink()
        self.assertEqual(sha256_file(self.relinked),previous)

    def test_tampered_original_otio_at_native_relink_publish_is_not_accepted(self):
        from studio_next import body_asset_links as links
        writer=otio.adapters.write_to_file
        mutated=False
        def adversarial_artist_write(timeline,destination,*args,**kwargs):
            nonlocal mutated
            result=writer(timeline,destination,*args,**kwargs)
            if str(destination).endswith(".otio") and not mutated:
                # Changes AFTER native adapter emitted a verified new edit,
                # BEFORE its proposed publication is accepted.
                self.source.write_bytes(self.source.read_bytes()+b"untrusted-change")
                mutated=True
            return result
        with patch.object(otio.adapters,"write_to_file",
                          side_effect=adversarial_artist_write):
            with self.assertRaisesRegex(RuntimeError,"changed during relocation"):
                self.run_relink()
        self.assertTrue(mutated)
        self.assertFalse(self.relinked.exists())

    def test_competing_relinked_edit_is_preserved_on_last_moment_race(self):
        from studio_next import body_asset_links as links
        expected=self.new/"independent-approved-project.otio"
        self.run_relink()
        shutil.copyfile(self.relinked,expected)
        wanted=sha256_file(expected)
        self.relinked.unlink()
        native_link=os.link
        raced=False
        def another_operator_wins(private,public,*args,**kwargs):
            nonlocal raced
            if Path(public)==self.relinked:
                shutil.copyfile(expected,self.relinked)
                raced=True
            return native_link(private,public,*args,**kwargs)
        with patch.object(links.os,"link",side_effect=another_operator_wins):
            with self.assertRaises(FileExistsError):
                self.run_relink()
        self.assertTrue(raced)
        self.assertEqual(sha256_file(self.relinked),wanted)
        self.assertEqual(sha256_file(self.source),self.sha_before)

    def test_no_verified_relocation_receipt_means_no_external_rebind(self):
        (self.new/".zx7-relocation-report.json").unlink()
        with self.assertRaisesRegex(ValueError,"relocation"):
            self.run_relink()
        self.assertFalse(self.relinked.exists())


if __name__=="__main__":
    unittest.main()

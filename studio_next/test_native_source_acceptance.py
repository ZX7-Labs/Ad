"""Prove real licensed source footage rather than a synthetic empty edit."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from studio_next.native_source_acceptance import (
    verify_original_footage_on_native_timeline)


class PhysicalNativeSourceAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sources = self.root / "staging"
        self.projects = self.root / "projects"
        self.sources.mkdir()
        self.projects.mkdir()
        self.src = self.sources / "original.mp4"
        self.src.write_bytes(b"original-owner-footage-content")
        self.owned = self.projects / "Movie"
        self.owned.mkdir()
        (self.owned / "media").mkdir()
        self.copy = self.owned / "media" / "original.mp4"
        self.copy.write_bytes(self.src.read_bytes())
        self.saved = self.owned / "project.comfystudio"
        self.manifest = [{"path": str(self.src),
                          "sha256": hashlib.sha256(
                              self.src.read_bytes()).hexdigest(),
                          "rights": "generated original owner media"}]
        self.project = {
            "assets": [{"id": "native-asset-12", "name": "Original",
                        "type": "video", "absolutePath": str(self.copy),
                        "settings": {"sourcePath": str(self.src),
                                     "importedViaMcp": True}}],
            "currentTimelineId": "native-timeline-1",
            "timelines": [{"id": "native-timeline-1",
                           "tracks": [{"id": "video-1", "type": "video",
                                       "visible": True}], "clips": [{
                "id": "native-clip-88", "assetId": "native-asset-12",
                "type": "video", "trackId": "video-1",
                "startTime": 0, "duration": 4.0}]}],
        }
        self.save()
        self._original_project = copy.deepcopy(self.project)

    def save(self):
        self.saved.write_text(json.dumps(self.project), encoding="utf-8")

    def verify(self):
        return verify_original_footage_on_native_timeline(
            self.projects, [self.saved], self.manifest)

    def test_original_imported_video_must_have_physical_project_copy_and_clip(self):
        receipt = self.verify()
        self.assertTrue(receipt["actual_original_video_used_on_native_timeline"])
        self.assertEqual(receipt["physically_verified_native_source_clip_count"], 1)
        self.assertFalse(receipt["professional_artistic_quality_approved"])
        self.assertEqual(receipt["verified_native_source_clip_proof"][0][
            "source_sha256"], self.manifest[0]["sha256"])

    def test_original_media_in_project_but_not_on_timeline_is_not_editing(self):
        self.project["timelines"][0]["clips"] = []
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_markers_text_titles_and_synthetic_visuals_cannot_replace_source(self):
        self.project["timelines"][0]["clips"] = [{
            "id": "text-clip", "type": "text", "assetId": "native-asset-12",
            "startTime": 0, "duration": 4.0}]
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_dormant_timeline_is_not_the_current_delivered_movie(self):
        self.project["timelines"][0]["id"] = "unused-timeline"
        self.project["timelines"].append({
            "id": "native-timeline-1",
            "tracks": [{"id": "video-1", "type": "video", "visible": True}],
            "clips": []})
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_disabled_clip_or_hidden_track_does_not_prove_visible_source(self):
        current = self.project["timelines"][0]
        current["clips"][0]["enabled"] = False
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])
        current["clips"][0]["enabled"] = True
        current["tracks"][0]["visible"] = False
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])
        current["tracks"][0]["visible"] = True
        current["clips"][0]["trackId"] = "invented-video-track"
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_spoofed_provenance_without_import_refused(self):
        self.project["assets"][0]["settings"]["importedViaMcp"] = False
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_wrong_or_missing_copy_refused_even_if_asset_path_looks_native(self):
        self.copy.write_bytes(b"other-content")
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])
        self.copy.unlink()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_external_symlink_or_direct_source_path_is_not_project_copy(self):
        self.project["assets"][0]["absolutePath"] = str(self.src)
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])
        link = self.owned / "media" / "link.mp4"
        link.symlink_to(self.src)
        self.project["assets"][0]["absolutePath"] = str(link)
        self.save()
        self.assertFalse(self.verify()["actual_original_video_used_on_native_timeline"])

    def test_untrusted_project_metadata_cannot_select_extra_host_paths(self):
        self.project["assets"][0]["settings"]["sourcePath"] = (
            "/not-owner-provided/unrelated-private-file.mp4")
        self.save()
        result = self.verify()
        self.assertFalse(result["actual_original_video_used_on_native_timeline"])

    def test_changed_original_hash_fails_closed(self):
        self.src.write_bytes(b"changed-after-attestation")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.verify()

    def test_empty_or_invented_manifest_never_approves_film(self):
        self.assertFalse(verify_original_footage_on_native_timeline(
            self.projects, [self.saved], [])[
                "actual_original_video_used_on_native_timeline"])
        with self.assertRaises(ValueError):
            verify_original_footage_on_native_timeline(
                self.projects, [self.saved],
                [{"path": str(self.src), "sha256": "x" * 64}])

    def test_ambiguous_native_asset_timeline_track_and_clip_ids_are_not_proof(self):
        # An editor may resolve duplicate IDs differently from the acceptance
        # verifier. Reject every ambiguity instead of selecting a favorable one.
        for category in ("asset", "timeline", "track", "clip"):
            with self.subTest(category=category):
                project = copy.deepcopy(self.project)
                timeline = project["timelines"][0]
                if category == "asset":
                    project["assets"].append({
                        "id": project["assets"][0]["id"],
                        "type": "video", "settings": {}})
                elif category == "timeline":
                    project["timelines"].append({
                        "id": timeline["id"], "tracks": [], "clips": []})
                elif category == "track":
                    timeline["tracks"].append({
                        "id": timeline["tracks"][0]["id"],
                        "type": "video", "visible": False})
                else:
                    timeline["clips"].append({
                        "id": timeline["clips"][0]["id"], "type": "text",
                        "startTime": 0, "duration": 4.0})
                self.project = project
                self.save()
                with self.assertRaisesRegex(ValueError, "ambiguous"):
                    self.verify()

    def test_nonboolean_visibility_and_enabled_values_are_not_visible_proof(self):
        # JSON 0, empty string and null are falsey to JavaScript, but were
        # previously counted as visible because they are not Python False.
        for field in ("track", "clip"):
            for falsey_value in (0, "", None, []):
                with self.subTest(field=field, value=falsey_value):
                    self.project = copy.deepcopy(self._original_project)
                    timeline = self.project["timelines"][0]
                    if field == "track":
                        timeline["tracks"][0]["visible"] = falsey_value
                    else:
                        timeline["clips"][0]["enabled"] = falsey_value
                    self.save()
                    self.assertFalse(
                        self.verify()["actual_original_video_used_on_native_timeline"])

    def test_project_path_escape_and_corrupt_native_project_refused(self):
        outside = self.root / "project.comfystudio"
        outside.write_text(json.dumps(self.project))
        with self.assertRaisesRegex(ValueError, "outside"):
            verify_original_footage_on_native_timeline(
                self.projects, [outside], self.manifest)
        self.saved.write_text('{"assets":[],"timelines":null}')
        with self.assertRaises(ValueError):
            self.verify()


if __name__ == "__main__":
    unittest.main()

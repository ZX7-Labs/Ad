"""Independent native source footage sampling from actual imported source bytes."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from studio_next.body_editor_client import EditorAccessError
from studio_next.body_editor_policy import EditorPathPolicy
from studio_next.body_editor_source_frame import observe_authorized_native_source_frame
from studio_next.body_editor_frame import _verified_png_dimensions


class NativeSnapshot:
    def __init__(self, project_path, relative="assets/video/shot.mp4"):
        self.allowed_tools = {"get_project": "read", "get_assets": "read"}
        self.project_path = str(project_path)
        self.relative = relative
        self.asset_id = "asset_original_001"
        self.total = 1
        self.extra = {}
        self.calls = []

    def call(self, name, args, *, allowed_access):
        self.calls.append((name, args))
        if "read" not in allowed_access or name not in self.allowed_tools:
            raise EditorAccessError("Host-granted editor reads missing")
        if name == "get_project":
            payload = {"project": {"name": "Real native video", "path": self.project_path}}
        elif name == "get_assets":
            asset = {"id": self.asset_id, "name": "shot.mp4", "type": "video",
                     "isImported": True, "path": self.relative, **self.extra}
            payload = {"assets": [asset], "totalAssetCount": self.total,
                       "returnedAssetCount": 1}
        else:
            raise AssertionError("Unexpected native operation")
        return {"isError": False, "content": [{"type": "text", "text": json.dumps(payload)}]}


class SourceFrameCustodyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.projects = self.base / "projects"
        self.staging = self.base / "staging"
        self.outputs = self.base / "outputs"
        for root in (self.projects, self.staging, self.outputs):
            root.mkdir()
        self.project = self.projects / "Real native video"
        (self.project / "assets/video").mkdir(parents=True)
        self.source = self.project / "assets/video/shot.mp4"
        self.policy = EditorPathPolicy(self.projects, self.staging, self.outputs)
        self.native = NativeSnapshot(self.project)

    def observe(self, at=0.5, client=None):
        return observe_authorized_native_source_frame(
            client if client is not None else self.native,
            "asset_original_001", at,
            allowed_access=frozenset({"read", "write"}), policy=self.policy)

    def real_source(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("Install real independent FFmpeg and FFprobe decoder/encoder")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=2",
                        "-c:v", "mpeg4", "-q:v", "4", str(self.source)],
                       check=True, timeout=30)

    def test_real_original_source_frame_bound_to_native_asset_and_original_sha(self):
        self.real_source()
        original = hashlib.sha256(self.source.read_bytes()).hexdigest()
        png, proof = self.observe()
        self.assertEqual(proof["kind"], "verified_native_editor_source_asset_frame")
        self.assertEqual(proof["asset_id"], self.native.asset_id)
        self.assertEqual(proof["source_sha256"], original)
        self.assertEqual(proof["png_sha256"], hashlib.sha256(png).hexdigest())
        self.assertEqual(_verified_png_dimensions(png), (320, 180))
        self.assertTrue(proof["physical_frame_verified"])
        self.assertFalse(proof["source_rights_independently_verified"])
        self.assertFalse(proof["composited_timeline_or_artistic_quality_approved"])
        self.assertEqual([c[0] for c in self.native.calls], ["get_project", "get_assets"])

    def test_bad_time_and_unregistered_asset_never_read_untrusted_path(self):
        self.real_source()
        for time in (-1, float("nan"), float("inf"), 10, 2):
            with self.subTest(time=time), self.assertRaises(ValueError):
                self.observe(time)
        with self.assertRaisesRegex(EditorAccessError, "native asset ID"):
            observe_authorized_native_source_frame(
                self.native, "../outside", 0.5,
                allowed_access={"read"}, policy=self.policy)

    def test_no_arbitrary_paths_or_symlinks_and_no_source_overwrite(self):
        self.real_source()
        with tempfile.TemporaryDirectory() as external:
            outsider=Path(external) / "shot.mp4"
            shutil.copy2(self.source, outsider)
            linked=self.project / "assets/video/linked.mp4"
            linked.symlink_to(outsider)
            self.native.relative = "assets/video/linked.mp4"
            with self.assertRaisesRegex(EditorAccessError,"escaped|linked|source"):
                self.observe()
            self.native.relative = "../outside/shot.mp4"
            with self.assertRaisesRegex(EditorAccessError,"relative"):
                self.observe()
            self.native.relative = str(outsider)
            with self.assertRaisesRegex(EditorAccessError,"relative"):
                self.observe()
            self.native.relative = "assets/video/../../shot.mp4"
            with self.assertRaisesRegex(EditorAccessError,"relative"):
                self.observe()
        self.native.relative = "assets/video/shot.mp4"
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.observe()
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), before)

    def test_missing_grants_or_incomplete_inventory_are_denied(self):
        self.real_source()
        client=NativeSnapshot(self.project)
        client.allowed_tools.pop("get_assets")
        with self.assertRaisesRegex(EditorAccessError,"granted"):
            self.observe(client=client)
        self.assertEqual(client.calls, [])
        self.native.total=2
        with self.assertRaisesRegex(EditorAccessError,"truncated"):
            self.observe()

    def test_native_video_metadata_cannot_overrule_filesystem(self):
        self.real_source()
        self.native.extra["absolutePath"] = "/etc/shadow"
        self.native.extra["settings"] = {"sourcePath": "/etc/passwd"}
        png, proof=self.observe()
        self.assertEqual(proof["source_sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(_verified_png_dimensions(png), (320,180))

    def test_source_must_remain_within_owner_project_root(self):
        self.real_source()
        self.native.project_path = str(self.outputs)
        with self.assertRaisesRegex(EditorAccessError,"owner-granted root"):
            self.observe()
        self.native.project_path = str(self.projects)
        with self.assertRaisesRegex(EditorAccessError,"owner-granted root"):
            self.observe()


if __name__ == "__main__":
    unittest.main()

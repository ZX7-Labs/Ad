"""Physical proof that HTTP sends only the same bytes that were hash-verified."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from studio_next.body_verified_delivery import verified_artifact_snapshot


class VerifiedDeliveryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.file=self.root/"movie.mp4"
        self.original=b"frame"*16384+b"original soundtrack"
        self.file.write_bytes(self.original)
        self.media={"path":self.file,"bytes":len(self.original),
                    "sha256":hashlib.sha256(self.original).hexdigest()}
    def tearDown(self):self.tmp.cleanup()

    def test_same_fd_hash_and_snapshot_freezes_exact_authorized_bytes(self):
        with verified_artifact_snapshot(self.media,scratch=self.root) as source:
            self.file.write_bytes(b"x"*len(self.original))
            self.assertEqual(source.read(),self.original)
            source.seek(0)
            self.assertEqual(hashlib.sha256(source.read()).hexdigest(),
                             self.media["sha256"])

    def test_same_size_mutation_is_not_mistaken_for_verified_movie(self):
        self.file.write_bytes(b"x"*len(self.original))
        with self.assertRaisesRegex(ValueError,"SHA256"):
            with verified_artifact_snapshot(self.media,scratch=self.root):
                self.fail("Never stream forged media")

    def test_truncated_media_and_symlink_are_not_verified(self):
        self.file.write_bytes(self.original[:-10])
        with self.assertRaisesRegex(ValueError,"size differs"):
            with verified_artifact_snapshot(self.media,scratch=self.root):pass
        self.file.unlink()
        self.file.symlink_to("/etc/hosts")
        with self.assertRaises(OSError):
            with verified_artifact_snapshot(self.media,scratch=self.root):pass

    def test_scratch_resource_boundary_and_reject_false_input(self):
        with self.assertRaisesRegex(RuntimeError,"Insufficient physical"):
            with verified_artifact_snapshot(self.media,scratch=self.root,
                                            free_space=len(self.original)):pass
        for size in (-1,True,0,"1212"):
            with self.assertRaises(ValueError):
                with verified_artifact_snapshot({**self.media,"bytes":size},
                      scratch=self.root):pass
        with self.assertRaises(ValueError):
            with verified_artifact_snapshot({**self.media,"sha256":"0"*64+"bad"},
                  scratch=self.root):pass

    def test_replaced_file_never_passes_earlier_proof(self):
        swapped=self.root/"next-original.mp4"
        swapped.write_bytes(b"\x00"*len(self.original))
        os.replace(swapped,self.file)
        with self.assertRaisesRegex(ValueError,"SHA256"):
            with verified_artifact_snapshot(self.media,scratch=self.root):pass


if __name__=="__main__":unittest.main()

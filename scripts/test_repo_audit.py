"""Reality-based tests for the full Git source integrity/AST audit."""
import tempfile
import unittest
from pathlib import Path

from repo_audit import audit


class EntireTrackedSourceAudit(unittest.TestCase):
    def test_exact_digest_and_line_number_for_native_file_publication(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)
            (source/"native_movie.py").write_text(
                "import os\ndef publish(stage,master):\n    os.link(stage,master)\n")
            (source/"plan.json").write_text('{"original":true}')
            report=audit(source,["native_movie.py","plan.json"])
            self.assertEqual(report["blocking_source_format_errors"],[])
            self.assertEqual(report["total_file_count"],2)
            self.assertEqual(report["counts"]["python"],1)
            self.assertEqual(report["counts"]["json"],1)
            self.assertEqual(report["static_source_change_sites"][0]["call"],"os.link")
            self.assertEqual(report["static_source_change_sites"][0]["line"],3)
            self.assertFalse(report["film_release_production_approved"])

    def test_corrupted_original_source_prevents_clean_repository_audit(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)
            (folder/"broken.py").write_text("def missing(:\n")
            (folder/"invalid.json").write_bytes(b"not json")
            report=audit(folder,["broken.py","invalid.json","missing.otio"])
            self.assertEqual(len(report["blocking_source_format_errors"]),3)
            self.assertFalse(report["all_twelve_quality_gates_complete"])

    def test_unapproved_shell_and_destructive_path_is_visible_as_risk_not_approval(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)
            (folder/"editor.py").write_text(
                "import subprocess\n"
                "def edit(movie):\n"
                "    subprocess.run('echo hi', shell=True)\n"
                "    movie.unlink()\n")
            report=audit(folder,["editor.py"])
            risky=report["static_source_change_sites"]
            self.assertEqual(len(risky),2)
            self.assertTrue(risky[0]["shell_true"])
            self.assertFalse(risky[1]["independently_security_reviewed"])


if __name__=="__main__":
    unittest.main()

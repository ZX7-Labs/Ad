"""Reconcile real repo sources with CI triggers: no hidden untested BODY modules."""
import unittest
from pathlib import Path


class NativeStudioCodeCoverageGates(unittest.TestCase):
    def test_every_body_module_change_runs_full_native_suite(self):
        root=Path(__file__).resolve().parent.parent
        native=(root/".github/workflows/studio-body-mobile-full-proof.yml").read_text()
        fast=(root/".github/workflows/studio-mobile-contracts.yml").read_text()
        for kind,data in (("full native",native),("quick security",fast)):
            self.assertIn('      - "studio_next/**"',data,
                         kind+" silently misses new or modified studio tool modules")
        self.assertIn("unittest discover -s studio_next -p 'test_*.py'",native)
        self.assertIn("body_signal",fast)
        self.assertIn("test_body_sequence_cuts",fast)
        # The full suite is the only source of all-module release evidence;
        # per-tool focused checks may not substitute fake 100% certification.
        self.assertIn("output/body-release-proof/all-tests.log",native)


if __name__=="__main__":
    unittest.main()

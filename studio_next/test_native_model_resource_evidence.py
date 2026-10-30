"""Linux per-process memory evidence: honest scope and failure modes."""
import os
import sys
import unittest
from unittest.mock import patch

from scripts.run_native_model_trial import (
    parse_linux_proc_peak_rss, read_live_linux_model_peak_rss,
)


class NativeModelMemoryProofTests(unittest.TestCase):
    def test_valid_linux_vm_hwm_reports_bytes_not_kibibytes(self):
        self.assertEqual(parse_linux_proc_peak_rss(
            "Name:\tllama-server\nVmRSS:\t  400 kB\nVmHWM:\t 123456 kB\n"),
            123456 * 1024)
        # Peak stays larger than current RSS after memory is released.
        self.assertEqual(parse_linux_proc_peak_rss(
            "VmHWM:\t  8192 kB\nVmRSS:\t 1024 kB\n"), 8192 * 1024)

    def test_absent_inconsistent_or_untrusted_procfs_is_not_measurement(self):
        bad = [
            "", "VmRSS:\t10 kB", "VmHWM:\t0 kB", "VmHWM: -1 kB",
            "VmHWM: 1 MB", "VmHWM: NaN kB", "VmHWM: 42",
            "VmHWM: 4 kB\nVmHWM: 5 kB",
            "VmHWM: 9999999999999 kB", "notVmHWM: 1234 kB",
        ]
        for raw in bad:
            with self.subTest(raw=raw):
                self.assertIsNone(parse_linux_proc_peak_rss(raw))
        self.assertIsNone(parse_linux_proc_peak_rss(None))

    def test_live_process_read_does_not_infer_memory_from_pid_errors(self):
        for pid in (-1, 0, True, "not-a-pid"):
            with self.subTest(pid=pid):
                self.assertIsNone(read_live_linux_model_peak_rss(pid))
        if sys.platform == "linux" and os.name == "posix":
            with patch("scripts.run_native_model_trial.Path.read_text",
                       side_effect=FileNotFoundError("model already exited")):
                self.assertIsNone(read_live_linux_model_peak_rss(os.getpid()))
            with patch("scripts.run_native_model_trial.Path.read_text",
                       return_value="VmHWM:\t128 kB\n"):
                self.assertEqual(read_live_linux_model_peak_rss(os.getpid()),
                                 128 * 1024)
            # Physical read of the active current process exercises procfs.
            self.assertGreater(read_live_linux_model_peak_rss(os.getpid()), 0)


if __name__ == "__main__":
    unittest.main()

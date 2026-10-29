"""Regression tests for the release evidence's unittest result parser."""
import unittest

from release_test_summary import parse_unittest_summary


class ReleaseTestSummaryTests(unittest.TestCase):
    def test_unittest_success_with_skips_is_a_successful_release_test_run(self):
        log = ("test_one (Tests.test_one) ... ok\n"
               "test_two (Tests.test_two) ... skipped 'optional engine'\n"
               "\n----------------------------------------------------------------------\n"
               "Ran 2 tests in 0.042s\n\nOK (skipped=1)\n")
        self.assertEqual(parse_unittest_summary(log), (2, 1))

    def test_success_without_skips(self):
        self.assertEqual(parse_unittest_summary(
            "test_one (Tests.test_one) ... ok\nRan 1 test in 0.1s\n\nOK\n"), (1, 0))

    def test_reject_failed_missing_or_truncated_results(self):
        logs = (
            "test_one (Tests.test_one) ... FAIL\nRan 1 test in 1s\nFAILED (failures=1)",
            "test_one (Tests.test_one) ... ok\nRan 1 test in 1s\n",
            "test_one (Tests.test_one) ... ok\nOK",
            "Ran 0 tests in 0.1s\nOK",
            "test_one (Tests.test_one) ... skipped 'not installed'\nRan 1 test in 1s\nOK",
            "Ran 1 test in 1s\nOK (skipped=1)",
            "test_one (Tests.test_one) ... skipped 'not installed'\nRan 1 test in 1s\nOK (skipped=2)",
        )
        for log in logs:
            with self.subTest(log=log), self.assertRaises(ValueError):
                parse_unittest_summary(log)

    def test_uses_final_unittest_run_not_prior_nested_result(self):
        log = ("Ran 1 test in 0.1s\nOK\n"
               "test_a (Outer.test_a) ... ok\n"
               "test_b (Outer.test_b) ... skipped 'platform'\n"
               "Ran 2 tests in 0.2s\nOK (skipped=1)\n")
        self.assertEqual(parse_unittest_summary(log), (2, 1))


if __name__ == "__main__":
    unittest.main()

"""Adversarial free-compute placement checks with no external access."""
import unittest
from dataclasses import replace
from studio_next.compute_offers import ResourceOffer, TaskNeed, assess, assess_all


def offer(**overrides):
    fields = dict(provider_id="trusted-local", capabilities=frozenset({"image", "video", "cinematography"}),
                  kind="local", status="available", ram_gb=16, gpu_vram_gb=0,
                  quota_seconds_remaining=600, estimated_cost_usd=0,
                  runtime_installed=True, license_approved=True, terms_verified=True,
                  user_permission=True)
    fields.update(overrides)
    return ResourceOffer(**fields)


class ResourcePreflightTests(unittest.TestCase):
    def test_free_local_cpu_can_qualify(self):
        self.assertTrue(assess(TaskNeed("image"), offer()).eligible)

    def test_gpu_requirement_not_masked_by_cpu_ram(self):
        d = assess(TaskNeed("video", gpu_vram_gb=8), offer())
        self.assertIn("insufficient_gpu_vram", d.blockers)

    def test_remote_requires_specific_authorization(self):
        d = assess(TaskNeed("cinematography"), offer(kind="remote"))
        self.assertIn("remote_transfer_not_authorized", d.blockers)

    def test_remote_private_media_requires_both_permissions(self):
        req = TaskNeed("cinematography", private_media=True, permit_remote=True)
        external = offer(kind="remote", private_media_allowed=True)
        self.assertIn("private_media_remote_blocked", assess(req, external).blockers)
        self.assertTrue(assess(replace(req, permit_private_remote=True), external).eligible)

    def test_unknown_quota_and_price_are_not_zero(self):
        d = assess(TaskNeed("image"), offer(quota_seconds_remaining=None,
                                            estimated_cost_usd=None))
        self.assertIn("quota_unknown", d.blockers)
        self.assertIn("price_unknown", d.blockers)

    def test_exhausted_quota_blocks(self):
        self.assertIn("quota_exhausted", assess(TaskNeed("image", estimated_seconds=90),
                      offer(quota_seconds_remaining=30)).blockers)

    def test_paid_service_denied_on_zero_budget(self):
        self.assertIn("paid_not_authorized", assess(TaskNeed("image"),
                      offer(estimated_cost_usd=0.05)).blockers)
        self.assertIn("cost_exceeds_limit",
                      assess(TaskNeed("image", owner_authorized_spend=True),
                             offer(estimated_cost_usd=0.05)).blockers)

    def test_explicit_cost_authorization_is_separate(self):
        req = TaskNeed("image", max_usd=0.10, owner_authorized_spend=True)
        self.assertTrue(assess(req, offer(estimated_cost_usd=0.05)).eligible)

    def test_uninstalled_unlicensed_unpermitted_models_fail(self):
        d = assess(TaskNeed("video"), offer(runtime_installed=False,
            license_approved=False, terms_verified=False, user_permission=False))
        self.assertEqual(set(d.blockers), {"no_installed_adapter", "license_not_cleared",
                                          "terms_not_verified", "user_permission_missing"})

    def test_not_assume_backend_exists_from_name(self):
        self.assertIn("resource_not_available",
                      assess(TaskNeed("image"), offer(status="busy")).blockers)
        self.assertIn("capability_missing",
                      assess(TaskNeed("speech"), offer()).blockers)

    def test_no_fixed_creative_limits(self):
        req = TaskNeed("video", estimated_seconds=72000)
        self.assertIn("quota_exhausted", assess(req, offer()).blockers)
        self.assertTrue(assess(req, offer(quota_seconds_remaining=80000)).eligible)

    def test_invalid_and_unbounded_numbers_rejected(self):
        for invalid in (float("nan"), float("inf"), -1, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                TaskNeed("image", estimated_seconds=invalid)
        with self.assertRaises(ValueError):
            offer(estimated_cost_usd=float("nan"))

    def test_duplicate_provider_identity_rejected(self):
        with self.assertRaises(ValueError):
            assess_all(TaskNeed("image"), [offer(), offer()])


if __name__ == "__main__":
    unittest.main()

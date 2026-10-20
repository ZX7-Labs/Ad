"""Read-only deployment eligibility checks; never creates/runs a cloud resource.

Offers are supplied by trusted, *current* registry discovery, not invented by an
LLM or inferred from a model card. This module cannot grant permissions.
Creative direction and shot count belong to the Director, not this scheduler.
"""
from dataclasses import dataclass, field
import math


def _number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'}")


@dataclass(frozen=True)
class TaskNeed:
    capability: str
    ram_gb: float = 0
    gpu_vram_gb: float = 0
    estimated_seconds: float = 1
    private_media: bool = False
    permit_remote: bool = False
    permit_private_remote: bool = False
    max_usd: float = 0
    owner_authorized_spend: bool = False

    def __post_init__(self):
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("Specific capability required")
        for name in ("ram_gb", "gpu_vram_gb", "max_usd"):
            _number(getattr(self, name), name)
        _number(self.estimated_seconds, "estimated_seconds", positive=True)


@dataclass(frozen=True)
class ResourceOffer:
    provider_id: str
    capabilities: frozenset[str]
    kind: str  # local or remote
    status: str  # available, busy, unavailable
    ram_gb: float
    gpu_vram_gb: float
    quota_seconds_remaining: float | None
    estimated_cost_usd: float | None
    # Only the trusted registry is allowed to set these flags after verification.
    runtime_installed: bool = False
    license_approved: bool = False
    terms_verified: bool = False
    user_permission: bool = False
    private_media_allowed: bool = False

    def __post_init__(self):
        if not isinstance(self.provider_id, str) or not self.provider_id.strip():
            raise ValueError("Provider ID required")
        if not isinstance(self.capabilities, frozenset) or not self.capabilities or any(
            not isinstance(c, str) or not c.strip() for c in self.capabilities
        ):
            raise ValueError("Capabilities must be nonempty immutable set")
        if self.kind not in ("local", "remote"):
            raise ValueError("Invalid resource kind")
        if self.status not in ("available", "busy", "unavailable"):
            raise ValueError("Invalid resource status")
        for name in ("ram_gb", "gpu_vram_gb"):
            _number(getattr(self, name), name)
        if self.quota_seconds_remaining is not None:
            _number(self.quota_seconds_remaining, "quota_seconds_remaining")
        if self.estimated_cost_usd is not None:
            _number(self.estimated_cost_usd, "estimated_cost_usd")
        for name in ("runtime_installed", "license_approved", "terms_verified",
                     "user_permission", "private_media_allowed"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be boolean")


@dataclass(frozen=True)
class OfferDecision:
    provider_id: str
    eligible: bool
    blockers: tuple[str, ...] = field(default_factory=tuple)


def assess(need: TaskNeed, offer: ResourceOffer) -> OfferDecision:
    """Pure preflight: no booking, activation, network call, or money movement."""
    if not isinstance(need, TaskNeed) or not isinstance(offer, ResourceOffer):
        raise TypeError("Typed need and verified offer required")
    errors = []
    if need.capability not in offer.capabilities:
        errors.append("capability_missing")
    if offer.status != "available":
        errors.append("resource_not_available")
    if not offer.runtime_installed:
        errors.append("no_installed_adapter")
    if not offer.license_approved:
        errors.append("license_not_cleared")
    if not offer.terms_verified:
        errors.append("terms_not_verified")
    if not offer.user_permission:
        errors.append("user_permission_missing")
    if need.ram_gb > offer.ram_gb:
        errors.append("insufficient_ram")
    if need.gpu_vram_gb > offer.gpu_vram_gb:
        errors.append("insufficient_gpu_vram")
    if offer.quota_seconds_remaining is None:
        errors.append("quota_unknown")
    elif need.estimated_seconds > offer.quota_seconds_remaining:
        errors.append("quota_exhausted")
    if offer.estimated_cost_usd is None:
        errors.append("price_unknown")
    elif offer.estimated_cost_usd > 0 and not need.owner_authorized_spend:
        errors.append("paid_not_authorized")
    elif offer.estimated_cost_usd > need.max_usd:
        errors.append("cost_exceeds_limit")
    if offer.kind == "remote":
        if not need.permit_remote:
            errors.append("remote_transfer_not_authorized")
        if need.private_media and not (need.permit_private_remote
                                       and offer.private_media_allowed):
            errors.append("private_media_remote_blocked")
    return OfferDecision(offer.provider_id, not errors, tuple(errors))


def assess_all(need: TaskNeed, offers: list[ResourceOffer]) -> list[OfferDecision]:
    """Preserves all choices for artistic routing; never silently picks a style."""
    if not isinstance(offers, list):
        raise TypeError("Offers must be list")
    ids = set()
    result = []
    for offer in offers:
        if offer.provider_id in ids:
            raise ValueError("Duplicate provider IDs cannot be trusted")
        ids.add(offer.provider_id)
        result.append(assess(need, offer))
    return result

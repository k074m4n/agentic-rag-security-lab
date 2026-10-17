"""Cumulative defense profiles for the eval harness.

Each profile is the set of SECURE_LAYERS enabled for a run. They are cumulative
so the sweep shows each layer's marginal effect on attack success and utility.
"""

from __future__ import annotations

PROFILES: dict[str, list[str]] = {
    "baseline": [],
    "d1": ["d1"],
    "d1d2": ["d1", "d2"],
    "d1d2d3": ["d1", "d2", "d3"],
    "full": ["d1", "d2", "d3", "d5"],
}


def layers_for(profile: str) -> str:
    """Return the SECURE_LAYERS value (comma-separated) for a profile name."""
    if profile not in PROFILES:
        raise KeyError(f"Unknown defense profile: {profile}")
    return ",".join(PROFILES[profile])

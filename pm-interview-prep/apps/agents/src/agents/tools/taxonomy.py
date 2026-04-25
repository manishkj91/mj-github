"""Canonical behavioral-question taxonomy.

The Scanner Agent uses this to decide which themes to cover for a given
(company tier, seniority) combination.
"""

from __future__ import annotations

from ..contracts import CompanyTier, Seniority

_BASE_THEMES = [
    "leadership",
    "stakeholder_conflict",
    "ambiguity",
    "failure",
    "prioritization",
    "data_driven_decision",
    "customer_obsession",
    "influence_without_authority",
]

_TIER_OVERLAY: dict[CompanyTier, list[str]] = {
    CompanyTier.FAANG: ["customer_obsession", "ownership", "bias_for_action"],
    CompanyTier.GROWTH: ["scrappiness", "speed_vs_quality"],
    CompanyTier.AI_NATIVE: ["ambiguity", "ethics_in_ai"],
    CompanyTier.OTHER: [],
}

_SENIORITY_OVERLAY: dict[Seniority, list[str]] = {
    Seniority.APM: ["learning_agility"],
    Seniority.PM: [],
    Seniority.SENIOR: ["mentorship"],
    Seniority.GPM: ["mentorship", "org_design", "strategy_under_constraint"],
}


def competency_taxonomy_lookup(tier: CompanyTier, seniority: Seniority) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for theme in _BASE_THEMES + _TIER_OVERLAY[tier] + _SENIORITY_OVERLAY[seniority]:
        if theme not in seen:
            seen.add(theme)
            out.append(theme)
    return out

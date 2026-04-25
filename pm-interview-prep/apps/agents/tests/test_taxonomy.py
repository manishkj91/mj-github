from agents.contracts import CompanyTier, Seniority
from agents.tools import competency_taxonomy_lookup


def test_taxonomy_includes_base_themes():
    themes = competency_taxonomy_lookup(CompanyTier.FAANG, Seniority.SENIOR)
    for required in ("leadership", "stakeholder_conflict", "ambiguity", "failure"):
        assert required in themes


def test_taxonomy_overlays_for_gpm_at_ai_native():
    themes = competency_taxonomy_lookup(CompanyTier.AI_NATIVE, Seniority.GPM)
    assert "ethics_in_ai" in themes
    assert "org_design" in themes
    assert "mentorship" in themes
    assert len(themes) == len(set(themes)), "themes should be deduped"

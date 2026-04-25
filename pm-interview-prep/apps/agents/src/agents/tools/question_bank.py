"""Seed phrasings for each behavioral theme.

Used as exemplars passed to the Scanner Agent so question wording stays in a
recognisable interviewer register and doesn't drift into trivia.
"""

from __future__ import annotations

from ..contracts import CompanyTier

_SEEDS: dict[str, list[str]] = {
    "leadership": [
        "Tell me about a time you led a team through a difficult decision.",
        "Describe a moment you had to take charge without formal authority.",
    ],
    "stakeholder_conflict": [
        "Walk me through a serious disagreement you had with a key stakeholder.",
        "Tell me about a time engineering and design pulled in opposite directions.",
    ],
    "ambiguity": [
        "Describe the most ambiguous problem you've owned. How did you frame it?",
    ],
    "failure": [
        "Tell me about a launch that did not meet expectations.",
        "Walk me through a project you would do differently in hindsight.",
    ],
    "prioritization": [
        "Give me a hard prioritization call you made. What did you say no to?",
    ],
    "data_driven_decision": [
        "Tell me about a decision you made primarily from data.",
    ],
    "customer_obsession": [
        "Describe a time you advocated for a customer when it was unpopular internally.",
    ],
    "influence_without_authority": [
        "Tell me about a time you influenced a team you didn't manage.",
    ],
    "ownership": [
        "Tell me about a time you stepped in to fix something outside your remit.",
    ],
    "bias_for_action": [
        "Describe a moment you chose to act with imperfect information.",
    ],
    "mentorship": [
        "Tell me about a person whose growth you were responsible for.",
    ],
    "ethics_in_ai": [
        "Describe a launch decision involving an ethical or safety trade-off.",
    ],
}


def question_bank_lookup(theme: str, tier: CompanyTier) -> list[str]:
    return _SEEDS.get(theme, [f"Tell me about a time you demonstrated {theme.replace('_', ' ')}."])

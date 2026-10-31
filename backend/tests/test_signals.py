"""
Unit tests for the parts that don't need the network: tactic detection, claim
picking, fact-check rating translation, the verdict maths, and source reputation.
Several tests pin down v1 bugs so they can never come back (e.g. "ai" matching "said").
"""

from app.llm.heuristic_provider import heuristic_claims, match_factchecks, rating_to_verdict
from app.pipeline.aggregate import aggregate
from app.pipeline.orchestrator import locate_span
from app.pipeline.tactics import detect_tactics
from app.schemas import Claim, ClaimResult, Evidence, StyleSignal
from app.services.sources import classify

# ---------------------------------------------------------------- tactics


def test_word_boundaries_avoid_v1_substring_bugs():
    # v1 matched "ai" in "said" and "pass" in "passed"
    tactics, score = detect_tactics("The minister said the bill passed on Tuesday after a long debate.")
    assert tactics == []
    assert score == 0.0


def test_detects_conspiracy_and_virality_with_spans():
    text = "WAKE UP!!! They don't want you to know the truth. Share this before they delete it!"
    tactics, score = detect_tactics(text)
    ids = {t.id for t in tactics}
    assert {"conspiracy", "virality_call", "excess_punctuation"} <= ids
    for t in tactics:
        for s in t.spans:
            assert text[s.start : s.end] == s.text
    assert 0.5 < score <= 1.0


def test_curly_apostrophes_match():
    tactics, _ = detect_tactics("They don’t want you to know this.")
    assert any(t.id == "conspiracy" for t in tactics)


def test_acronyms_are_not_shouting():
    tactics, _ = detect_tactics("NASA and the NHS published COVID data with NATO partners.")
    assert all(t.id != "shouting" for t in tactics)


# ---------------------------------------------------------------- claims


def test_heuristic_claims_skip_questions_and_opinions():
    text = (
        "Is this real? I think we should all calm down. The WHO reported 7 million deaths from the disease in 2023. Please share."
    )
    claims = heuristic_claims(text, 5)
    assert len(claims) == 1
    assert "7 million" in claims[0].text


def test_locate_span_exact_and_case_insensitive():
    text = "Breaking: Water boils at 100 degrees at sea level."
    s = locate_span(text, "water boils at 100 degrees", "")
    assert s and text[s.start : s.end].lower() == "water boils at 100 degrees"


# ---------------------------------------------------------------- fact-check ratings


def test_rating_mapping():
    assert rating_to_verdict("False") == "REFUTED"
    assert rating_to_verdict("Pants on Fire!") == "REFUTED"
    assert rating_to_verdict("Mostly False") == "REFUTED"
    assert rating_to_verdict("Half True") == "MIXED"
    assert rating_to_verdict("Missing context") == "MIXED"
    assert rating_to_verdict("True") == "SUPPORTED"
    assert rating_to_verdict("Correct attribution") == "SUPPORTED"
    assert rating_to_verdict("") == "UNVERIFIABLE"


def test_factcheck_matching_requires_similarity():
    ev = [
        Evidence(kind="factcheck", rating="False", snippet="5G towers spread the coronavirus", credibility=0.9),
        Evidence(kind="factcheck", rating="True", snippet="The Eiffel Tower is in Paris", credibility=0.9),
    ]
    m = match_factchecks("5G masts are spreading coronavirus", ev)
    assert len(m) == 1 and m[0][0] == 0


# ---------------------------------------------------------------- aggregation


def _cr(verdict, conf, cw=0.8, i=0):
    return ClaimResult(claim=Claim(id=i, text=f"c{i}", checkworthiness=cw), verdict=verdict, confidence=conf)


def test_refuted_claim_drives_likely_false():
    overall, risk, conf = aggregate([_cr("REFUTED", 0.9), _cr("SUPPORTED", 0.8, i=1)], 0.0, StyleSignal())
    assert overall == "LIKELY_FALSE"
    assert risk >= 0.7
    assert conf > 0.6


def test_wording_alone_can_never_make_content_false():
    overall, risk, conf = aggregate(
        [_cr("UNVERIFIABLE", 0.1)], tactics_score=1.0, style=StyleSignal(available=True, probability=0.99)
    )
    assert overall == "UNVERIFIED"
    assert conf < 0.25  # low evidence -> low confidence


def test_all_supported_looks_reliable():
    overall, risk, _ = aggregate([_cr("SUPPORTED", 0.9), _cr("SUPPORTED", 0.85, i=1)], 0.2, StyleSignal())
    assert overall == "LOOKS_RELIABLE"
    assert risk < 0.2


def test_no_claims():
    overall, _, conf = aggregate([], 0.0, StyleSignal())
    assert overall == "NO_CLAIMS" and conf <= 0.3


def test_mixed_needs_context():
    overall, _, _ = aggregate([_cr("MIXED", 0.8)], 0.0, StyleSignal())
    assert overall == "NEEDS_CONTEXT"


# ---------------------------------------------------------------- sources


def test_source_classification():
    assert classify("https://www.snopes.com/fact-check/x")[0] == "factcheck"
    assert classify("https://www.reuters.com/fact-check/abc")[0] == "factcheck"
    assert classify("https://www.reuters.com/world/abc")[0] == "news"
    assert classify("https://www.cdc.gov/flu")[0] == "government"
    assert classify("https://www.nhs.uk/conditions")[0] == "government"
    assert classify("https://pubmed.ncbi.nlm.nih.gov/123")[0] in {"science", "government"}
    assert classify("https://www.infowars.com/x")[1] < 0.2
    assert classify("https://evil-reuters.com.example.net/x")[0] == "web"


def test_unreliable_style_model_barely_moves_score():
    # A style model that is no better than a coin flip on unseen datasets gets no say.
    base = aggregate([_cr("UNVERIFIABLE", 0.1)], 0.0, StyleSignal())[1]
    coin = aggregate([_cr("UNVERIFIABLE", 0.1)], 0.0, StyleSignal(available=True, probability=0.99, reliability=0.0))[1]
    good = aggregate([_cr("UNVERIFIABLE", 0.1)], 0.0, StyleSignal(available=True, probability=0.99, reliability=1.0))[1]
    assert coin == base
    assert good > base

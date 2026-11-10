from sift.match import evaluate, load_profile
from sift.models import Posting, Requirements


def posting(title="Data Scientist", location="Munich", employment="permanent / full-time", company="Staburo"):
    return Posting(source="t", company=company, external_id="1", title=title, location=location,
                   url="https://example.org", employment_type=employment, description_text="")


def req(**kw):
    base = dict(role_family="Data Scientist", seniority="junior", min_years_experience=None, phd_mentioned=False,
                llm_experience_required=False, languages=[], remote_policy="hybrid", permanent=True,
                salary_text="", must_haves=[], nice_to_haves=[])
    base.update(kw)
    return Requirements(**base)


PROFILE = load_profile("profile.example.yaml")


def test_good_fit_passes_and_scores_high():
    m = evaluate(posting(), req(phd_mentioned=True, must_haves=["clinical statistics"]), PROFILE)
    assert m.hard_filter_passed
    assert m.score >= 0.8
    assert any("Fachrichtung" in r for r in m.reasons)


def test_llm_requirement_fails_filter():
    m = evaluate(posting(), req(llm_experience_required=True), PROFILE)
    assert not m.hard_filter_passed
    assert "LLM-Praxis ist Pflicht" in m.reasons


def test_senior_and_years_fail():
    m = evaluate(posting(title="Senior Data Scientist"), req(seniority="senior", min_years_experience=5), PROFILE)
    assert not m.hard_filter_passed
    assert any("Level senior" in r for r in m.reasons)
    assert any("5+ Jahre" in r for r in m.reasons)


def test_intern_fails():
    m = evaluate(posting(title="Data Science Intern", employment="Full-Time"), req(), PROFILE)
    assert not m.hard_filter_passed


def test_bad_location_fails_but_unclear_passes():
    bad = evaluate(posting(location="USA"), req(), PROFILE)
    assert not bad.hard_filter_passed
    unclear = evaluate(posting(location="Europe (hybrid)"), req(remote_policy="unclear"), PROFILE)
    assert unclear.hard_filter_passed
    assert "Ort unklar" in unclear.reasons

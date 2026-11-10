from pathlib import Path

from jobradar.evaluate import Label, compare, format_report, load_labels, run
from jobradar.extract import ExtractionRecord
from jobradar.match import load_profile
from jobradar.models import Posting, Requirements


def rec(**kw):
    base = dict(role_family="Data Scientist", seniority="junior", min_years_experience=None, phd_mentioned=False,
                llm_experience_required=False, languages=[], remote_policy="hybrid", permanent=True,
                salary_text="", must_haves=[], nice_to_haves=[])
    base.update(kw)
    return ExtractionRecord(prompt_version="test", model="fake", requirements=Requirements(**base))


def test_compare_counts_only_labeled_fields():
    label = Label("k", seniority="junior", min_years=None, llm_required=True, phd_mentioned=None, fit=None)
    out = compare(label, rec(llm_experience_required=False))
    assert set(out) == {"seniority", "llm_required"}
    assert out["seniority"][0] is True
    assert out["llm_required"][0] is False


def test_run_reports_accuracy_and_fit(tmp_path):
    posting = Posting(source="personio:x", company="Staburo", external_id="1", title="(Senior) Data Scientist",
                      location="Munich", url="https://e.org", employment_type="permanent / full-time")
    records = {posting.key: rec(seniority="mid", phd_mentioned=True)}
    labels = [Label(posting.key, seniority="mid", min_years=0, llm_required=False, phd_mentioned=True, fit=True)]
    report = run(labels, [posting], records, load_profile("profile.yaml"))
    assert report.fields["seniority"].accuracy == 1.0
    assert report.fields["min_years"].accuracy == 1.0
    assert report.fit_yes_passed == 1 and report.fit_yes_total == 1
    text = format_report(report)
    assert "seniority" in text and "fit=yes" in text


def test_labels_file_parses():
    labels = load_labels(Path("data/labels.csv"))
    assert len(labels) >= 10
    staburo = next(l for l in labels if l.posting_key == "personio:staburo:765770")
    assert staburo.seniority == "mid" and staburo.fit is True and staburo.phd_mentioned is True

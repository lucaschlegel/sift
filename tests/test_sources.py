import json
from pathlib import Path

from jobradar.sources.lever import LeverSource
from jobradar.sources.personio import PersonioSource
from jobradar.store import diff_new

FIX = Path(__file__).parent / "fixtures"


def test_lever_parse():
    items = json.loads((FIX / "lever_sample.json").read_text(encoding="utf-8"))
    src = LeverSource("quantco-", "QuantCo")
    postings = [src.parse(i) for i in items]
    assert len(postings) == 2
    ds = postings[0]
    assert ds.company == "QuantCo"
    assert ds.title == "Data Scientist"
    assert ds.location == "Europe"
    assert ds.url.endswith("3e18574e-ab5a-46a2-8714-a0221fb937e7")
    assert "causal inference" in ds.description_text
    assert "<li>" not in ds.description_text
    assert ds.key == "lever:quantco-:3e18574e-ab5a-46a2-8714-a0221fb937e7"


def test_personio_parse():
    xml_text = (FIX / "personio_sample.xml").read_text(encoding="utf-8")
    postings = PersonioSource("staburo", "Staburo").parse(xml_text)
    assert len(postings) == 1
    p = postings[0]
    assert p.title.startswith("(Senior) Data Scientist")
    assert p.location == "Munich"
    assert p.url == "https://staburo.jobs.personio.com/job/765770"
    assert p.employment_type == "permanent / full-time"
    assert "Customer consulting" in p.description_text
    assert "SAS, R" in p.description_text
    assert str(p.posted_at) == "2024-09-10"


def test_diff_new():
    items = json.loads((FIX / "lever_sample.json").read_text(encoding="utf-8"))
    src = LeverSource("quantco-", "QuantCo")
    current = [src.parse(i) for i in items]
    previous = current[:1]
    new = diff_new(current, previous)
    assert [p.title for p in new] == ["AI Applied Scientist"]

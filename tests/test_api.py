import json
from pathlib import Path

from fastapi.testclient import TestClient

from jobradar import api
from jobradar.extract import ExtractionRecord
from jobradar.models import Posting, Requirements


def seed(tmp_path: Path):
    p = Posting(source="personio:staburo", company="Staburo", external_id="765770", title="(Senior) Data Scientist",
                location="Munich", url="https://staburo.jobs.personio.com/job/765770", employment_type="permanent / full-time",
                description_text="text")
    (tmp_path / "postings_2026-11-10_1200.json").write_text(json.dumps([p.model_dump(mode="json")]), encoding="utf-8")
    rec = ExtractionRecord(prompt_version="v3", model="fake", requirements=Requirements(
        role_family="Data Scientist", seniority="mid", min_years_experience=None, phd_mentioned=True,
        llm_experience_required=False, languages=[], remote_policy="hybrid", permanent=True, salary_text="",
        must_haves=["statistics"], nice_to_haves=[]))
    (tmp_path / "requirements.json").write_text(json.dumps({p.key: rec.model_dump(mode="json")}), encoding="utf-8")
    return p


def test_api_endpoints(tmp_path, monkeypatch):
    p = seed(tmp_path)
    monkeypatch.setattr(api, "DATA_DIR", tmp_path)
    client = TestClient(api.app)
    assert client.get("/health").json()["runs"] == 1
    posts = client.get("/postings").json()
    assert posts[0]["title"] == "(Senior) Data Scientist" and "description_text" not in posts[0]
    detail = client.get(f"/postings/{p.key}").json()
    assert detail["requirements"]["requirements"]["seniority"] == "mid"
    matches = client.get("/matches").json()
    assert matches and matches[0]["hard_filter_passed"] is True
    assert client.get("/assessments").json() == []
    assert client.get("/postings/does-not-exist").status_code == 404

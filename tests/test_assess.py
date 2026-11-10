import json
from types import SimpleNamespace

from jobradar.assess import AnthropicAssessor, Assessment, RECORD_TOOL, build_user_message
from jobradar.match import Match, load_profile
from jobradar.models import Posting, Requirements
from jobradar.tools import check_posting_live, lookup_watchlist, run_tool


def posting():
    return Posting(source="personio:staburo", company="Staburo", external_id="765770",
                   title="(Senior) Data Scientist with focus Clinical Statistics", location="Munich",
                   url="https://staburo.jobs.personio.com/job/765770", employment_type="permanent / full-time",
                   description_text="Analysis of trial data. Master or PhD in statistics or mathematics.")


def req():
    return Requirements(role_family="Data Scientist", seniority="mid", min_years_experience=None, phd_mentioned=True,
                        llm_experience_required=False, languages=["English"], remote_policy="hybrid", permanent=True,
                        salary_text="", must_haves=["statistics"], nice_to_haves=[])


FINAL = {"verdict": "apply", "fit_score": 0.8, "rationale": "Statistics role in Munich, PhD welcome.",
         "main_gap": "SAS and clinical trials", "still_live": True}


class ScriptedMessages:
    """Erste Antwort: zwei Werkzeugaufrufe. Zweite Antwort: record_assessment."""

    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return SimpleNamespace(content=[
                SimpleNamespace(type="text", text="Let me check."),
                SimpleNamespace(type="tool_use", id="t1", name="lookup_watchlist", input={"company": "Staburo"}),
                SimpleNamespace(type="tool_use", id="t2", name="check_posting_live", input={"url": "https://staburo.jobs.personio.com/job/765770"}),
            ])
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", id="t3", name="record_assessment", input=FINAL)])


class ScriptedClient:
    def __init__(self):
        self.messages = ScriptedMessages()


def fake_runner(name, args):
    return {"tool": name, "args": args, "live": True, "note": "fake"}


def test_tool_loop_runs_tools_and_returns_assessment():
    client = ScriptedClient()
    assessor = AnthropicAssessor(model="test", client=client, tool_runner=fake_runner)
    match = Match(posting_key=posting().key, hard_filter_passed=True, score=0.9, reasons=["Ort passt"])
    rec = assessor.assess(posting(), req(), match, load_profile("profile.yaml"))
    assert rec.assessment.verdict == "apply"
    assert len(rec.tool_calls) == 2 and rec.tool_calls[0].startswith("lookup_watchlist")
    # zweiter API-Aufruf enthält die Werkzeugergebnisse als tool_result
    second = client.messages.calls[1]["messages"]
    assert second[-1]["role"] == "user"
    assert all(block["type"] == "tool_result" for block in second[-1]["content"])
    assert {b["tool_use_id"] for b in second[-1]["content"]} == {"t1", "t2"}


def test_record_tool_schema_has_verdict_enum():
    props = RECORD_TOOL["input_schema"]["properties"]
    assert set(props["verdict"]["enum"]) == {"apply", "maybe", "skip"}


def test_user_message_contains_everything():
    match = Match(posting_key="x", hard_filter_passed=True, score=0.5, reasons=[])
    msg = build_user_message(posting(), req(), match, load_profile("profile.yaml"))
    for needle in ("CANDIDATE PROFILE", "Staburo", "EXTRACTED REQUIREMENTS", "RULE-BASED RESULT", "POSTING TEXT"):
        assert needle in msg


def test_check_posting_live_detects_closed_and_redirect():
    closed = SimpleNamespace(status_code=200, text="Sorry, this position has been filled.", url="https://x/job/1")
    assert check_posting_live("https://x/job/1", _get=lambda u: closed)["live"] is False
    redirected = SimpleNamespace(status_code=200, text="jobs list", url="https://x/en/jobs/")
    assert check_posting_live("https://x/job/1", _get=lambda u: redirected)["live"] is False
    live = SimpleNamespace(status_code=200, text="Apply now", url="https://x/job/1")
    assert check_posting_live("https://x/job/1", _get=lambda u: live)["live"] is True


def test_lookup_watchlist_fuzzy():
    assert lookup_watchlist("QuantCo Deutschland GmbH")["note"]
    assert lookup_watchlist("TNG Technology Consulting")["note"]
    assert lookup_watchlist("Unknown Corp")["note"] is None
    assert run_tool("lookup_watchlist", {"company": "Staburo"})["note"]

import json
from pathlib import Path
from types import SimpleNamespace

from jobradar.extract import (
    AnthropicExtractor,
    TOOL_NAME,
    build_tool,
    build_user_message,
    extract_missing,
    load_requirements,
    parse_tool_response,
    save_requirements,
)
from jobradar.models import Requirements
from jobradar.sources.lever import LeverSource

FIX = Path(__file__).parent / "fixtures"


def sample_posting():
    items = json.loads((FIX / "lever_sample.json").read_text(encoding="utf-8"))
    return LeverSource("quantco-", "QuantCo").parse(items[0])


SAMPLE_OUTPUT = {
    "role_family": "Data Scientist",
    "seniority": "junior",
    "min_years_experience": None,
    "phd_mentioned": False,
    "llm_experience_required": False,
    "languages": ["English"],
    "remote_policy": "hybrid",
    "permanent": None,
    "salary_text": "",
    "must_haves": ["degree in mathematics or similar", "statistics behind ML"],
    "nice_to_haves": ["SQL", "Tensorflow", "Git"],
}


class FakeMessages:
    """Spielt die Anthropic-API nach: gibt immer denselben Werkzeugaufruf zurück."""

    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        block = SimpleNamespace(type="tool_use", name=TOOL_NAME, input=SAMPLE_OUTPUT)
        return SimpleNamespace(content=[block])


class FakeClient:
    def __init__(self):
        self.messages = FakeMessages()


def test_tool_schema_matches_model():
    tool = build_tool()
    assert tool["name"] == TOOL_NAME
    props = tool["input_schema"]["properties"]
    for field in ("role_family", "seniority", "min_years_experience", "llm_experience_required", "must_haves"):
        assert field in props


def test_user_message_contains_posting():
    msg = build_user_message(sample_posting())
    assert "QuantCo" in msg and "Data Scientist" in msg and "causal inference" in msg


def test_extract_with_fake_client():
    client = FakeClient()
    extractor = AnthropicExtractor(model="test-model", client=client)
    req = extractor.extract(sample_posting())
    assert isinstance(req, Requirements)
    assert req.seniority == "junior"
    assert req.llm_experience_required is False
    call = client.messages.calls[0]
    assert call["model"] == "test-model"
    assert call["tool_choice"] == {"type": "tool", "name": TOOL_NAME}


def test_parse_rejects_missing_tool_call():
    response = SimpleNamespace(content=[SimpleNamespace(type="text", text="hello")])
    try:
        parse_tool_response(response)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_cache_roundtrip(tmp_path):
    posting = sample_posting()
    cache = extract_missing([posting], AnthropicExtractor(model="x", client=FakeClient()), {}, log=lambda m: None)
    path = tmp_path / "requirements.json"
    save_requirements(cache, path)
    loaded = load_requirements(path)
    assert loaded[posting.key].role_family == "Data Scientist"
    # zweiter Lauf: nichts mehr zu tun, der Fake wird nicht aufgerufen
    client = FakeClient()
    extract_missing([posting], AnthropicExtractor(model="x", client=client), loaded, log=lambda m: None)
    assert client.messages.calls == []

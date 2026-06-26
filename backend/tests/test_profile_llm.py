import json
from datetime import date
from types import SimpleNamespace

from app.resume.profile import (
    HeuristicExtractor,
    LlmExtractor,
    ResumeProfile,
    SeniorityRank,
    select_extractor,
)


class _FakeClient:
    """Stand-in for anthropic.Anthropic — records the call and returns canned text,
    so we exercise the real parsing path with no network/SDK."""

    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(text=self.payload)])


def test_llm_extractor_parses_a_response():
    payload = json.dumps(
        {
            "seniority": "executive",
            "total_years": 18,
            "education_status": "graduated",
            "grad_year": 2008,
            "skills": ["Python", "Kubernetes"],
        }
    )
    client = _FakeClient(payload)
    p = LlmExtractor(client=client, today=date(2026, 6, 26)).extract("…résumé…")
    assert p.seniority == SeniorityRank.EXECUTIVE
    assert p.total_years == 18.0
    assert p.education_status == "graduated"
    assert p.grad_year == 2008
    assert "Kubernetes" in p.skills
    assert client.calls  # the client was actually invoked


def test_llm_extractor_is_fail_open_on_garbage_output():
    p = LlmExtractor(client=_FakeClient("not json"), today=date(2026, 6, 26)).extract("x")
    assert p == ResumeProfile()


def test_select_extractor_defaults_to_heuristic_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(select_extractor(), HeuristicExtractor)


def test_select_extractor_uses_llm_when_key_present(monkeypatch):
    # Construction must not need the SDK (the real client is built lazily on first
    # extract), so this is safe even with anthropic uninstalled.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert isinstance(select_extractor(), LlmExtractor)

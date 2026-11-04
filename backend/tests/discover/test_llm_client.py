"""Tests for the Anthropic-backed arm-B LLM client (spec §16).

All tests inject a fake Anthropic client — no SDK install, no network, no API key
(spec §19: the standard suite never hits a live API). They assert the mapping from
the model's structured output onto the eval contract, and in particular that an
unfaithful model's output is preserved (so the metrics can catch it), not sanitized.
"""

from __future__ import annotations

from datetime import datetime, timezone

from intent_engine.discover.evaluation.baselines import llm_only_arm
from intent_engine.discover.evaluation.contracts import CandidateSnapshot, StatedConstraints
from intent_engine.discover.evaluation.llm_client import (
    AnthropicLLMClient,
    _LLMClaim,
    _LLMResponse,
    _coerce_value,
    default_llm_client,
)
from intent_engine.discover.schemas import AttributeProvenance, ClaimKind, EvidenceStatus


def _prov(value, status, **kw):
    base = dict(
        source="test",
        source_url="https://example.test/x",
        retrieved_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
    )
    if status is EvidenceStatus.VERIFIED:
        base.setdefault("source_field", "field")
    if status is EvidenceStatus.EXTRACTED:
        base.setdefault("extractor", "ext-1")
    base.update(kw)
    return AttributeProvenance(value=value, status=status, **base)


def _snap(cid, **attrs):
    return CandidateSnapshot(candidate_id=cid, attributes=attrs)


def _pool():
    return [
        _snap("a", title=_prov("Zoo", EvidenceStatus.VERIFIED),
              age_min=_prov(5, EvidenceStatus.VERIFIED)),
        _snap("b", title=_prov("Gala", EvidenceStatus.VERIFIED),
              age_min=_prov(None, EvidenceStatus.UNKNOWN)),
    ]


class _Resp:
    def __init__(self, parsed):
        self.parsed_output = parsed


class _FakeMessages:
    def __init__(self, parsed, calls):
        self._parsed = parsed
        self._calls = calls

    def parse(self, **kwargs):
        self._calls.append(kwargs)
        return _Resp(self._parsed)


class _FakeAnthropic:
    def __init__(self, parsed):
        self.calls = []
        self.messages = _FakeMessages(parsed, self.calls)


_STATED = StatedConstraints(children_ages=[6])


def test_happy_path_maps_ranking_claims_and_verified_fact():
    parsed = _LLMResponse(
        ranking=["a", "b"],
        claims=[
            _LLMClaim(candidate_id="a", attribute="min_age", text="min age 5, fits",
                      evidence_status=EvidenceStatus.VERIFIED, kind=ClaimKind.MATCH,
                      asserted_value="5"),
            _LLMClaim(candidate_id="b", attribute="min_age", text="age limit unknown",
                      evidence_status=EvidenceStatus.UNKNOWN, kind=ClaimKind.CAVEAT,
                      asserted_value=None),
        ],
    )
    out = AnthropicLLMClient(client=_FakeAnthropic(parsed)).rank(_pool(), _STATED)

    assert out.ranking == ["a", "b"]
    assert len(out.explanations["a"]) == 1
    # the VERIFIED value is asserted as a coerced int, available to the error metric
    assert any(f.attribute == "min_age" and f.asserted_value == 5
               and f.asserted_as is EvidenceStatus.VERIFIED for f in out.asserted_facts)
    # the UNKNOWN caveat asserts no fact
    assert all(f.candidate_id != "b" for f in out.asserted_facts)


def test_reckless_model_assertion_is_preserved_not_sanitized():
    # Model asserts candidate b's (UNKNOWN) min age as a VERIFIED fact — the arm
    # must surface it so critical_factual_error_count can penalize it.
    parsed = _LLMResponse(
        ranking=["b"],
        claims=[
            _LLMClaim(candidate_id="b", attribute="min_age", text="ages 0+, all welcome",
                      evidence_status=EvidenceStatus.VERIFIED, kind=ClaimKind.MATCH,
                      asserted_value="0"),
        ],
    )
    out = AnthropicLLMClient(client=_FakeAnthropic(parsed)).rank(_pool(), _STATED)
    assert any(f.candidate_id == "b" and f.asserted_as is EvidenceStatus.VERIFIED
               and f.asserted_value == 0 for f in out.asserted_facts)


def test_hallucinated_candidate_ids_dropped_and_ranking_deduped():
    parsed = _LLMResponse(
        ranking=["a", "ghost", "a"],
        claims=[
            _LLMClaim(candidate_id="ghost", attribute="x", text="t",
                      evidence_status=EvidenceStatus.VERIFIED, kind=ClaimKind.MATCH,
                      asserted_value="1"),
        ],
    )
    out = AnthropicLLMClient(client=_FakeAnthropic(parsed)).rank(_pool(), _STATED)
    assert out.ranking == ["a"]
    assert out.asserted_facts == []
    assert "ghost" not in out.explanations


def test_incoherent_caveat_on_verified_is_coerced_not_dropped():
    parsed = _LLMResponse(
        ranking=["a"],
        claims=[
            _LLMClaim(candidate_id="a", attribute="title", text="verified name",
                      evidence_status=EvidenceStatus.VERIFIED, kind=ClaimKind.CAVEAT,
                      asserted_value=None),
        ],
    )
    out = AnthropicLLMClient(client=_FakeAnthropic(parsed)).rank(_pool(), _STATED)
    claim = out.explanations["a"][0]
    assert claim.kind is ClaimKind.MATCH
    assert claim.evidence_status is EvidenceStatus.VERIFIED


def test_request_shape_uses_opus_48_adaptive_and_structured_output():
    fake = _FakeAnthropic(_LLMResponse(ranking=["a"], claims=[]))
    AnthropicLLMClient(client=fake).rank(_pool(), _STATED)
    call = fake.calls[0]
    assert call["model"] == "claude-opus-4-8"
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_format"] is _LLMResponse
    assert isinstance(call["system"], str) and call["system"]


def test_llm_only_arm_consumes_the_client():
    parsed = _LLMResponse(ranking=["b", "a"], claims=[])
    arm = llm_only_arm(_pool(), _STATED, client=AnthropicLLMClient(client=_FakeAnthropic(parsed)))
    assert arm.ranking == ["b", "a"]


def test_default_client_off_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert default_llm_client() is None


def test_default_client_on_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert isinstance(default_llm_client(), AnthropicLLMClient)


def test_coerce_value():
    assert _coerce_value("5") == 5
    assert _coerce_value("4.5") == 4.5
    assert _coerce_value("true") is True
    assert _coerce_value("No") is False
    assert _coerce_value("free entry") == "free entry"
    assert _coerce_value(None) is None
    assert _coerce_value("  ") is None

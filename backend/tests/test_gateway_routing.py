from __future__ import annotations

import pytest

from app.config import OVERSEAS_VENDORS
from app.gateway.protocol import LLMRequest
from app.gateway.router import ModelGateway


def _gw():
    from app.config import get_settings

    return ModelGateway(get_settings())


@pytest.mark.parametrize("task", ["pricing_strategy", "review_reply"])
def test_critical_tasks_never_include_overseas_vendors_even_if_enabled(task):
    gw = _gw()
    req = LLMRequest(task_type=task, messages=[{"role": "user", "content": "x"}])
    chain = gw.route_chain(req, overseas_enabled=True)
    assert "mock" in chain
    assert "deepseek" in chain
    for vendor in OVERSEAS_VENDORS:
        assert vendor not in chain


def test_execution_critical_flag_also_blocks_overseas():
    gw = _gw()
    req = LLMRequest(task_type="assistant_chat", messages=[], execution_critical=True)
    chain = gw.route_chain(req, overseas_enabled=True)
    for vendor in OVERSEAS_VENDORS:
        assert vendor not in chain


def test_non_critical_may_include_overseas_when_enabled():
    gw = _gw()
    req = LLMRequest(task_type="assistant_chat", messages=[])
    off = gw.route_chain(req, overseas_enabled=False)
    on = gw.route_chain(req, overseas_enabled=True)
    assert not any(v in off for v in OVERSEAS_VENDORS)
    assert any(v in on for v in OVERSEAS_VENDORS)


def test_complete_critical_not_outbound_when_overseas_on_and_keys_present(client, auth_header, monkeypatch):
    # Turn the switch on and pretend overseas keys exist, then spy on those adapters.
    from app.gateway.adapters.gemini import GeminiAdapter
    from app.gateway.adapters.grok import GrokAdapter
    from app.gateway.adapters.openai_ad import OpenAIAdapter
    from app.gateway.router import get_gateway, reset_gateway

    called: list[tuple[str, str]] = []

    def boom(self, request):
        called.append((getattr(self, "vendor", "unknown"), request.task_type))
        if request.task_type in {"pricing_strategy", "review_reply"} or request.execution_critical:
            raise AssertionError(f"overseas adapter {self.vendor} must not be called for critical tasks")
        raise RuntimeError("simulated overseas failure for non-critical task")

    monkeypatch.setattr(OpenAIAdapter, "available", lambda self: True)
    monkeypatch.setattr(GeminiAdapter, "available", lambda self: True)
    monkeypatch.setattr(GrokAdapter, "available", lambda self: True)
    monkeypatch.setattr(OpenAIAdapter, "complete", boom)
    monkeypatch.setattr(GeminiAdapter, "complete", boom)
    monkeypatch.setattr(GrokAdapter, "complete", boom)
    reset_gateway()

    resp = client.put("/api/settings", headers=auth_header, json={"overseas_enabled": True})
    assert resp.status_code == 200
    assert resp.json()["overseas_enabled"] is True

    # Generating strategies triggers pricing_strategy (critical).
    gen = client.post("/api/strategies/generate", headers=auth_header, json={})
    assert gen.status_code == 200, gen.text
    assert gen.json()["created"] >= 1
    critical_calls = [c for c in called if c[1] in {"pricing_strategy", "review_reply"}]
    assert critical_calls == [], critical_calls

    logs = client.get("/api/audit/model-calls", headers=auth_header)
    assert logs.status_code == 200
    rows = logs.json()["logs"]
    critical = [r for r in rows if r["task_type"] in {"pricing_strategy", "review_reply"}]
    assert critical, "expected audited pricing_strategy calls"
    assert all(r["outbound"] is False for r in critical)
    assert all(r["vendor"] not in OVERSEAS_VENDORS for r in critical)


def test_review_reply_also_stays_domestic(client, auth_header, monkeypatch):
    from app.gateway.adapters.gemini import GeminiAdapter
    from app.gateway.adapters.grok import GrokAdapter
    from app.gateway.adapters.openai_ad import OpenAIAdapter
    from app.gateway.router import reset_gateway

    called: list[tuple[str, str]] = []

    def boom(self, request):
        called.append((self.vendor, request.task_type))
        if request.task_type in {"pricing_strategy", "review_reply"} or request.execution_critical:
            raise AssertionError("overseas must not handle review_reply")
        raise RuntimeError("simulated overseas failure for non-critical task")

    monkeypatch.setattr(OpenAIAdapter, "available", lambda self: True)
    monkeypatch.setattr(GeminiAdapter, "available", lambda self: True)
    monkeypatch.setattr(GrokAdapter, "available", lambda self: True)
    monkeypatch.setattr(OpenAIAdapter, "complete", boom)
    monkeypatch.setattr(GeminiAdapter, "complete", boom)
    monkeypatch.setattr(GrokAdapter, "complete", boom)
    reset_gateway()

    client.put("/api/settings", headers=auth_header, json={"overseas_enabled": True})
    reviews = client.get("/api/reviews", headers=auth_header).json()["reviews"]
    bad = next(r for r in reviews if r["rating"] <= 2)
    drafted = client.post(f"/api/reviews/{bad['id']}/draft", headers=auth_header)
    assert drafted.status_code == 200, drafted.text
    assert drafted.json()["reply_draft"]
    assert drafted.json()["reply_status"] == "pending_review"
    critical_calls = [c for c in called if c[1] in {"pricing_strategy", "review_reply"}]
    assert critical_calls == [], critical_calls
    logs = client.get("/api/audit/model-calls", headers=auth_header).json()["logs"]
    replies = [r for r in logs if r["task_type"] == "review_reply"]
    assert replies
    assert all(not r["outbound"] and r["vendor"] not in OVERSEAS_VENDORS for r in replies)

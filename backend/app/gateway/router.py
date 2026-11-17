"""Task-based model router with domestic-first fallback and outbound guards."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import CRITICAL_TASKS, OVERSEAS_VENDORS, Settings, get_settings
from app.gateway.adapters.deepseek import DeepSeekAdapter
from app.gateway.adapters.gemini import GeminiAdapter
from app.gateway.adapters.grok import GrokAdapter
from app.gateway.adapters.mock import MockModelAdapter
from app.gateway.adapters.openai_ad import OpenAIAdapter
from app.gateway.adapters.qwen import QwenAdapter
from app.gateway.protocol import LLMRequest, LLMResponse
from app.models import ModelCallLog, SystemSetting

# Simple per-vendor rate limit: 30 calls / rolling minute.
_RATE_LIMIT = 30
_calls: dict[str, deque[float]] = defaultdict(deque)


def _rate_ok(vendor: str) -> bool:
    now = time.time()
    q = _calls[vendor]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= _RATE_LIMIT:
        return False
    q.append(now)
    return True


def read_overseas_enabled(db: Session | None, settings: Settings) -> bool:
    """DB toggle overrides the environment default when present."""
    if db is None:
        return bool(settings.overseas_enabled)
    row = db.get(SystemSetting, "overseas_enabled")
    if row is None:
        return bool(settings.overseas_enabled)
    return row.value.strip().lower() in {"1", "true", "yes", "on"}


def is_critical(request: LLMRequest) -> bool:
    return request.execution_critical or request.task_type in CRITICAL_TASKS


class ModelGateway:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.adapters = {
            "deepseek": DeepSeekAdapter(self.settings),
            "qwen": QwenAdapter(self.settings),
            "openai": OpenAIAdapter(self.settings),
            "gemini": GeminiAdapter(self.settings),
            "grok": GrokAdapter(self.settings),
            "mock": MockModelAdapter(),
        }

    def route_chain(self, request: LLMRequest, overseas_enabled: bool) -> list[str]:
        """
        Return vendor names to try, in order. The model never picks the next hop —
        the gateway does. Critical tasks are barred from overseas vendors even if
        the overseas switch is on.
        """
        critical = is_critical(request)
        allow_overseas = overseas_enabled and not critical

        chain: list[str] = ["deepseek", "qwen"]
        if allow_overseas:
            if request.task_type == "vision_or_longdoc":
                chain.extend(["gemini", "openai", "grok"])
            else:
                chain.extend(["openai", "gemini", "grok"])
        chain.append("mock")

        # Defence in depth: never let an overseas vendor onto a critical chain.
        if critical:
            chain = [v for v in chain if v not in OVERSEAS_VENDORS]
            if "mock" not in chain:
                chain.append("mock")
        return chain

    def complete(self, request: LLMRequest, db: Session | None = None) -> LLMResponse:
        overseas_enabled = read_overseas_enabled(db, self.settings)
        chain = self.route_chain(request, overseas_enabled)
        errors: list[str] = []
        started_chain = time.perf_counter()

        for vendor in chain:
            adapter = self.adapters[vendor]
            # Mock is always available; others need a key.
            if vendor != "mock" and not adapter.available():
                errors.append(f"{vendor}:no_key")
                continue
            if vendor in OVERSEAS_VENDORS:
                # Final hard guard, even if the chain was built incorrectly.
                if is_critical(request) or not overseas_enabled:
                    errors.append(f"{vendor}:blocked_outbound")
                    continue
            if not _rate_ok(vendor):
                errors.append(f"{vendor}:rate_limited")
                continue

            t0 = time.perf_counter()
            try:
                response = adapter.complete(request)
            except Exception as exc:  # noqa: BLE001 — we degrade, then audit
                latency = int((time.perf_counter() - t0) * 1000)
                errors.append(f"{vendor}:{type(exc).__name__}")
                self._audit(
                    db,
                    request,
                    vendor=vendor,
                    model=getattr(adapter, "model", vendor),
                    outbound=vendor in OVERSEAS_VENDORS,
                    degraded=False,
                    status="error",
                    latency_ms=latency,
                    error_code=type(exc).__name__,
                )
                continue

            latency = int((time.perf_counter() - t0) * 1000)
            response.latency_ms = latency
            # If we fell past the primary, mark as degraded.
            used_fallback = vendor != chain[0] or vendor == "mock"
            if used_fallback:
                response.degraded = True
                if not response.degrade_notice:
                    response.degrade_notice = "当前为降级结果"
            # Refuse to return an overseas result for critical tasks.
            if is_critical(request) and response.outbound:
                errors.append(f"{vendor}:rejected_outbound_result")
                continue
            self._audit(
                db,
                request,
                vendor=response.vendor,
                model=response.model,
                outbound=response.outbound,
                degraded=response.degraded,
                status=response.status,
                latency_ms=latency,
                error_code="",
                usage=response.usage,
            )
            return response

        # Should be unreachable because mock is always last and always works,
        # but keep a hard fallback anyway.
        latency = int((time.perf_counter() - started_chain) * 1000)
        response = self.adapters["mock"].complete(request)
        response.degraded = True
        response.degrade_notice = "当前为降级结果（全部上游失败）"
        response.error_code = "all_vendors_failed"
        response.error_message = "; ".join(errors)
        response.latency_ms = latency
        self._audit(
            db,
            request,
            vendor="mock",
            model="mock-deterministic",
            outbound=False,
            degraded=True,
            status="ok",
            latency_ms=latency,
            error_code="all_vendors_failed",
        )
        return response

    def _audit(
        self,
        db: Session | None,
        request: LLMRequest,
        *,
        vendor: str,
        model: str,
        outbound: bool,
        degraded: bool,
        status: str,
        latency_ms: int,
        error_code: str,
        usage: dict | None = None,
    ) -> None:
        if db is None:
            return
        usage = usage or {}
        db.add(
            ModelCallLog(
                vendor=vendor,
                model=model,
                task_type=request.task_type,
                hotel_id=request.hotel_id,
                tenant_key=request.tenant_key,
                outbound=outbound,
                degraded=degraded,
                status=status,
                latency_ms=latency_ms,
                error_code=error_code or "",
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
            )
        )
        try:
            db.commit()
        except Exception:
            db.rollback()

    def describe(self, db: Session | None = None) -> dict:
        settings = self.settings
        overseas_enabled = read_overseas_enabled(db, settings)
        adapters = []
        for name, adapter in self.adapters.items():
            adapters.append(
                {
                    "vendor": name,
                    "role": {
                        "deepseek": "国产主模型",
                        "qwen": "国产备用",
                        "openai": "境外对照（默认关闭）",
                        "gemini": "境外，长上下文与多模态（默认关闭）",
                        "grok": "境外，非收益决策首选（默认关闭）",
                        "mock": "本地演示与降级",
                    }.get(name, name),
                    "available": adapter.available(),
                    "outbound": name in OVERSEAS_VENDORS,
                    "model": getattr(adapter, "model", "mock-deterministic"),
                    "status": (
                        "ready"
                        if adapter.available()
                        else ("always_on" if name == "mock" else "no_key_will_skip")
                    ),
                }
            )
        return {
            "overseas_enabled": overseas_enabled,
            "critical_tasks_blocked_from_overseas": sorted(CRITICAL_TASKS),
            "default_chain": ["deepseek", "qwen", "mock"],
            "adapters": adapters,
            "rules": [
                "按任务路由，不按厂商写业务。",
                "主模型失败则切备用国产模型，再失败则切 Mock，并标明降级。",
                "境外模型默认关闭，需单独授权开启。",
                "pricing_strategy、review_reply 及任何将导致调价/回复/执行的调用，即使境外模型已开启也不得出境。",
                "调用审计不记录密钥。",
            ],
        }


_gateway: ModelGateway | None = None


def get_gateway() -> ModelGateway:
    global _gateway
    if _gateway is None:
        _gateway = ModelGateway()
    return _gateway


def reset_gateway() -> None:
    global _gateway
    _gateway = None

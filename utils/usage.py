from __future__ import annotations

import sys
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator

# USD per million tokens. Approximate — verify at anthropic.com/pricing.
MODEL_PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "default": (3.0, 15.0),
}

# Prompt cache multipliers vs base input price (Anthropic ephemeral cache).
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10


@dataclass
class UsageSnapshot:
    input_tokens: int = 0
    output_tokens: int = 0
    api_calls: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def billable_input_tokens(self) -> int:
        return (
            self.input_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
        )

    @property
    def total_tokens(self) -> int:
        return self.billable_input_tokens + self.output_tokens

    def remaining_tokens(self, budget: int) -> int | None:
        if budget <= 0:
            return None
        return max(0, budget - self.total_tokens)

    def estimated_usd(self, model: str) -> float:
        in_rate, out_rate = MODEL_PRICING_USD_PER_MTOK.get(
            model, MODEL_PRICING_USD_PER_MTOK["default"]
        )
        input_cost = (
            self.input_tokens / 1_000_000 * in_rate
            + self.cache_creation_input_tokens
            / 1_000_000
            * in_rate
            * CACHE_WRITE_MULTIPLIER
            + self.cache_read_input_tokens
            / 1_000_000
            * in_rate
            * CACHE_READ_MULTIPLIER
        )
        output_cost = self.output_tokens / 1_000_000 * out_rate
        return input_cost + output_cost

    def to_dict(self, model: str, budget: int = 0) -> dict[str, Any]:
        remaining = self.remaining_tokens(budget)
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "billable_input_tokens": self.billable_input_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "total_tokens": self.total_tokens,
            "used_tokens": self.total_tokens,
            "remaining_tokens": remaining,
            "api_calls": self.api_calls,
            "estimated_usd": round(self.estimated_usd(model), 6),
        }

    def delta(self, before: UsageSnapshot) -> UsageSnapshot:
        return UsageSnapshot(
            input_tokens=self.input_tokens - before.input_tokens,
            output_tokens=self.output_tokens - before.output_tokens,
            api_calls=self.api_calls - before.api_calls,
            cache_creation_input_tokens=self.cache_creation_input_tokens
            - before.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens
            - before.cache_read_input_tokens,
        )


@dataclass
class UsageLedger:
    input_tokens: int = 0
    output_tokens: int = 0
    api_calls: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    calls: list[dict[str, Any]] = field(default_factory=list)

    def snapshot(self) -> UsageSnapshot:
        return UsageSnapshot(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            api_calls=self.api_calls,
            cache_creation_input_tokens=self.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens,
        )

    def record(
        self,
        input_tokens: int,
        output_tokens: int,
        label: str,
        *,
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
    ) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cache_creation_input_tokens += cache_creation_input_tokens
        self.cache_read_input_tokens += cache_read_input_tokens
        self.api_calls += 1
        self.calls.append(
            {
                "label": label,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_creation_input_tokens,
                "cache_read_input_tokens": cache_read_input_tokens,
            }
        )
        if self is not _SERVER_TOTAL:
            _SERVER_TOTAL.record(
                input_tokens,
                output_tokens,
                label,
                cache_creation_input_tokens=cache_creation_input_tokens,
                cache_read_input_tokens=cache_read_input_tokens,
            )


_ACTIVE_LEDGER: ContextVar[UsageLedger | None] = ContextVar("usage_ledger", default=None)
_SERVER_TOTAL = UsageLedger()


def record_message_usage(message: Any, label: str) -> None:
    ledger = _ACTIVE_LEDGER.get()
    if ledger is None:
        return
    usage = getattr(message, "usage", None)
    if usage is None:
        return
    ledger.record(
        usage.input_tokens,
        usage.output_tokens,
        label,
        cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0)
        or 0,
        cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
    )


@contextmanager
def bind_usage_ledger(ledger: UsageLedger) -> Iterator[UsageLedger]:
    token = _ACTIVE_LEDGER.set(ledger)
    try:
        yield ledger
    finally:
        _ACTIVE_LEDGER.reset(token)


def server_usage() -> UsageSnapshot:
    return _SERVER_TOTAL.snapshot()


def server_usage_snapshot(model: str, budget: int = 0) -> dict[str, Any]:
    return server_usage().to_dict(model, budget)


def format_token_count(n: int | None) -> str:
    if n is None:
        return "∞"
    return f"{n:,}"


def format_usage_terminal(
    *,
    label: str,
    call_in: int,
    call_out: int,
    server: UsageSnapshot,
    budget: int = 0,
) -> str:
    rem = server.remaining_tokens(budget)
    rem_s = format_token_count(rem)
    return (
        f"[tokens] {label}  in={call_in:,} out={call_out:,}  |  "
        f"server in={server.billable_input_tokens:,} "
        f"out={server.output_tokens:,}  "
        f"used={server.total_tokens:,}  rem={rem_s}"
    )


def log_api_usage(message: Any, label: str, *, budget: int = 0) -> None:
    usage = getattr(message, "usage", None)
    if usage is None:
        return
    call_in = (
        usage.input_tokens
        + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        + (getattr(usage, "cache_read_input_tokens", 0) or 0)
    )
    call_out = usage.output_tokens
    server = _SERVER_TOTAL.snapshot()
    print(
        format_usage_terminal(
            label=label,
            call_in=call_in,
            call_out=call_out,
            server=server,
            budget=budget,
        ),
        file=sys.stderr,
        flush=True,
    )


def log_turn_usage(
    *,
    turn: int,
    session: UsageSnapshot,
    server: UsageSnapshot,
    budget: int = 0,
) -> None:
    rem = server.remaining_tokens(budget)
    rem_s = format_token_count(rem)
    print(
        f"[tokens] turn {turn} complete  "
        f"session in={session.billable_input_tokens:,} "
        f"out={session.output_tokens:,}  "
        f"used={session.total_tokens:,}  |  "
        f"server used={server.total_tokens:,}  rem={rem_s}",
        file=sys.stderr,
        flush=True,
    )

"""AI spending visibility and control (Assurant "Take Control of AI").

Keeps a running ledger of every Vital AI request: how many calls, tokens, estimated cost,
how many the safety guard blocked. The charge nurse can turn AI off (template only) or set a
monthly budget; once the budget is spent Vital falls back to templates instead of spending more.

In-memory for the hackathon; in production this is a table keyed by unit and month.
"""
from __future__ import annotations

import os
import threading
import time

_lock = threading.Lock()


def _price(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _fresh() -> dict:
    return {"mode": os.getenv("VITAL_AI_MODE", "on"), "budgetUsd": _price("VITAL_AI_BUDGET_USD", 5.0),
            "calls": 0, "aiCalls": 0, "templateCalls": 0, "blocked": 0,
            "tokensIn": 0, "tokensOut": 0, "costUsd": 0.0, "recent": []}


_S = _fresh()


def reset() -> None:
    global _S
    with _lock:
        _S = _fresh()


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))  # ~4 characters per token


def cost(tokens_in: int, tokens_out: int) -> float:
    """USD, using per-million-token prices (defaults: $3 in / $15 out; override with env vars)."""
    return round(tokens_in * _price("VITAL_PRICE_IN", 3.0) / 1e6 + tokens_out * _price("VITAL_PRICE_OUT", 15.0) / 1e6, 6)


def mode() -> str:
    return _S["mode"]


def over_budget() -> bool:
    return _S["budgetUsd"] >= 0 and _S["costUsd"] >= _S["budgetUsd"]


def set_settings(mode: str | None = None, budget_usd: float | None = None) -> dict:
    with _lock:
        if mode in ("on", "off"):
            _S["mode"] = mode
        if budget_usd is not None and budget_usd >= 0:
            _S["budgetUsd"] = round(float(budget_usd), 2)
    return summary()


def record(meta: dict) -> None:
    with _lock:
        _S["calls"] += 1
        if meta["reason"] == "ai":
            _S["aiCalls"] += 1
            _S["tokensIn"] += meta["tokensIn"]
            _S["tokensOut"] += meta["tokensOut"]
            _S["costUsd"] = round(_S["costUsd"] + meta["costUsd"], 6)
        else:
            _S["templateCalls"] += 1
        if meta["reason"] == "guard":
            _S["blocked"] += 1
        _S["recent"] = ([{"at": time.time(), "kind": meta["kind"], "reason": meta["reason"],
                          "tokens": meta["tokensIn"] + meta["tokensOut"], "costUsd": meta["costUsd"],
                          "deidentified": meta["deidentified"]}] + _S["recent"])[:10]


def summary() -> dict:
    from .llm import available, model_name

    with _lock:
        s = dict(_S, recent=list(_S["recent"]))
    s.update(keyConfigured=available(), model=model_name(), overBudget=over_budget(),
             priceInPerM=_price("VITAL_PRICE_IN", 3.0), priceOutPerM=_price("VITAL_PRICE_OUT", 15.0))
    return s

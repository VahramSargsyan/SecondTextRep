"""Read-only visible L2 execution curves for bounded public market observation.

Cost is relative to the current mid; fees, future market drift and our price
impact on later snapshots are excluded. None means insufficient displayed depth.
"""
from __future__ import annotations
import math
from typing import Any

NOTIONALS_USD = (10_000, 50_000, 100_000, 250_000, 500_000)

def execution_costs_bps(book: Any, quote_to_usdt: float = 1.0) -> dict[str, float | None]:
    mid = book.mid * quote_to_usdt
    if not math.isfinite(mid) or mid <= 0 or not math.isfinite(quote_to_usdt) or quote_to_usdt <= 0:
        return {f"{side}_cost_{n}_bps": None for n in NOTIONALS_USD for side in ("sell", "buy")}
    bids = sorted(book.bids.items(), reverse=True)
    asks = sorted(book.asks.items())
    out: dict[str, float | None] = {}
    for n in NOTIONALS_USD:
        remaining_base = n / mid
        usd_received = 0.0
        for p, qty in bids:
            if remaining_base <= 1e-10:
                break
            if p <= 0 or qty <= 0:
                continue
            take = min(qty, remaining_base)
            usd_received += take * p * quote_to_usdt
            remaining_base -= take
        out[f"sell_cost_{n}_bps"] = (
            10_000 * (1.0 - usd_received / n) if remaining_base <= 1e-9 else None
        )
        remaining_quote_usd = float(n)
        base_received = 0.0
        for p, qty in asks:
            if remaining_quote_usd <= 1e-8:
                break
            if p <= 0 or qty <= 0:
                continue
            take_quote_usd = min(qty * p * quote_to_usdt, remaining_quote_usd)
            base_received += take_quote_usd / (p * quote_to_usdt)
            remaining_quote_usd -= take_quote_usd
        out[f"buy_cost_{n}_bps"] = (
            10_000 * (1.0 - base_received / (n / mid))
            if remaining_quote_usd <= 1e-5 else None
        )
    return out

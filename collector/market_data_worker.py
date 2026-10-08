from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import os
import re
import signal
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from collector.market_liquidity_capacity import execution_costs_bps

CAPABILITY_ID = "EVENT_DRIVEN_MARKET_DATA_WORKER_V1"
REST_BASE = "https://data-api.binance.vision"
WS_BASE = "wss://data-stream.binance.vision/stream?streams="
STABLE_SYMBOL = "USDCUSDT"
DEPTH_LIMIT = 5000
DEPTH_BANDS = (0.0025, 0.005, 0.01, 0.02)
MODE_SAMPLE_SECONDS = {"LIGHT": 60, "WATCH": 10, "BURST": 1}
DEFAULT_SEGMENT_SECONDS = 900
DEFAULT_CONTROL_POLL_SECONDS = 15
SUPPORTED_QUOTES = ("USDT", "USDC")
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,96}$")
MAX_SYMBOLS = 24


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat()


def fetch_json(path: str, **params: Any) -> Any:
    url = REST_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "SecondTextRep-MarketDataWorker/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_mode(value: str) -> str:
    mode = value.strip().upper()
    if mode not in MODE_SAMPLE_SECONDS:
        raise ValueError(f"Unsupported mode {value!r}; expected one of {sorted(MODE_SAMPLE_SECONDS)}")
    return mode


def normalize_symbols(values: str | Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        raw = [part.strip().upper() for part in values.split(",") if part.strip()]
    else:
        raw = [str(part).strip().upper() for part in values if str(part).strip()]
    symbols = tuple(dict.fromkeys(raw))
    if not symbols:
        raise ValueError("At least one symbol is required")
    if len(symbols) > MAX_SYMBOLS:
        raise ValueError(f"At most {MAX_SYMBOLS} symbols are supported in V1")
    for symbol in symbols:
        if not symbol.isalnum():
            raise ValueError(f"Invalid symbol {symbol!r}")
        if not symbol.endswith(SUPPORTED_QUOTES):
            raise ValueError(
                f"Unsupported quote for {symbol}; V1 supports markets ending in USDT or USDC"
            )
    return symbols


def validate_session_id(value: str) -> str:
    session_id = value.strip()
    if not SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("session_id must match [A-Za-z0-9._-] and be at most 96 characters")
    return session_id


def quote_asset(symbol: str) -> str:
    for quote in SUPPORTED_QUOTES:
        if symbol.endswith(quote):
            return quote
    raise ValueError(f"Unsupported quote for {symbol}")


def append_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    fields = list(rows[0].keys())
    if exists:
        with path.open("r", newline="", encoding="utf-8") as handle:
            fields = next(csv.reader(handle))
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


class SequenceGap(RuntimeError):
    pass


@dataclass
class LocalOrderBook:
    symbol: str
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)
    update_id: int = -1

    def apply_snapshot(self, payload: dict[str, Any]) -> None:
        self.bids = {
            float(price): float(qty)
            for price, qty in payload.get("bids", [])
            if float(qty) > 0
        }
        self.asks = {
            float(price): float(qty)
            for price, qty in payload.get("asks", [])
            if float(qty) > 0
        }
        self.update_id = int(payload["lastUpdateId"])

    @property
    def best_bid(self) -> float:
        return max(self.bids) if self.bids else math.nan

    @property
    def best_ask(self) -> float:
        return min(self.asks) if self.asks else math.nan

    @property
    def mid(self) -> float:
        return (self.best_bid + self.best_ask) / 2.0

    @property
    def spread_bps(self) -> float:
        if not math.isfinite(self.best_bid) or self.best_bid <= 0:
            return math.nan
        return (self.best_ask / self.best_bid - 1.0) * 10_000.0

    def apply_depth(self, event: dict[str, Any], quote_to_usdt: float = 1.0) -> dict[str, float]:
        final_id = int(event["u"])
        first_id = int(event["U"])
        if final_id <= self.update_id:
            return _empty_depth_flow()
        if self.update_id >= 0 and first_id > self.update_id + 1:
            raise SequenceGap(
                f"{self.symbol}: expected first update <= {self.update_id + 1}, "
                f"got U={first_id}, u={final_id}"
            )

        changes: list[tuple[str, float, float, float]] = []
        for side_name, key, book in (
            ("bid", "b", self.bids),
            ("ask", "a", self.asks),
        ):
            for raw_price, raw_qty in event.get(key, []):
                price = float(raw_price)
                new_qty = float(raw_qty)
                old_qty = book.get(price, 0.0)
                changes.append((side_name, price, old_qty, new_qty))
                if new_qty <= 0:
                    book.pop(price, None)
                else:
                    book[price] = new_qty
        self.update_id = final_id

        mid = self.mid
        out = _empty_depth_flow()
        if not math.isfinite(mid) or mid <= 0:
            return out
        lower, upper = mid * 0.99, mid * 1.01
        for side_name, price, old_qty, new_qty in changes:
            if not lower <= price <= upper:
                continue
            delta_quote = (new_qty - old_qty) * price * quote_to_usdt
            if delta_quote > 0:
                out[f"{side_name}_add_1pct_usd"] += delta_quote
            elif delta_quote < 0:
                out[f"{side_name}_remove_1pct_usd"] += -delta_quote
        return out

    def depth_quote(self, side: str, band: float, quote_to_usdt: float = 1.0) -> float:
        mid = self.mid
        if not math.isfinite(mid) or mid <= 0:
            return 0.0
        total = 0.0
        if side == "bid":
            boundary = mid * (1.0 - band)
            for price, qty in sorted(self.bids.items(), reverse=True):
                if price < boundary:
                    break
                total += price * qty * quote_to_usdt
        else:
            boundary = mid * (1.0 + band)
            for price, qty in sorted(self.asks.items()):
                if price > boundary:
                    break
                total += price * qty * quote_to_usdt
        return total


def _empty_depth_flow() -> dict[str, float]:
    return {
        "bid_add_1pct_usd": 0.0,
        "ask_add_1pct_usd": 0.0,
        "bid_remove_1pct_usd": 0.0,
        "ask_remove_1pct_usd": 0.0,
    }


@dataclass
class IntervalFlow:
    depth_events: int = 0
    agg_trades: int = 0
    bid_add_1pct_usd: float = 0.0
    ask_add_1pct_usd: float = 0.0
    bid_remove_1pct_usd: float = 0.0
    ask_remove_1pct_usd: float = 0.0
    taker_sell_quote_usd: float = 0.0
    taker_buy_quote_usd: float = 0.0

    def consume(self) -> dict[str, Any]:
        payload = self.__dict__.copy()
        self.depth_events = 0
        self.agg_trades = 0
        self.bid_add_1pct_usd = 0.0
        self.ask_add_1pct_usd = 0.0
        self.bid_remove_1pct_usd = 0.0
        self.ask_remove_1pct_usd = 0.0
        self.taker_sell_quote_usd = 0.0
        self.taker_buy_quote_usd = 0.0
        return payload


@dataclass
class RuntimeCounters:
    reconnect_count: int = 0
    sequence_gap_count: int = 0
    control_poll_error_count: int = 0
    sample_row_count: int = 0


class StopController:
    def __init__(self) -> None:
        self.requested = False
        self.reason = ""

    def request(self, reason: str) -> None:
        self.requested = True
        self.reason = reason


def _stream_url(symbols: tuple[str, ...]) -> str:
    streams: list[str] = []
    for symbol in symbols:
        lower = symbol.lower()
        streams.extend(
            [
                f"{lower}@depth@100ms",
                f"{lower}@aggTrade",
                f"{lower}@bookTicker",
            ]
        )
    if any(quote_asset(symbol) == "USDC" for symbol in symbols):
        streams.append(f"{STABLE_SYMBOL.lower()}@bookTicker")
    return WS_BASE + "/".join(streams)


async def fetch_snapshots(symbols: tuple[str, ...]) -> tuple[dict[str, LocalOrderBook], float]:
    books: dict[str, LocalOrderBook] = {}
    for symbol in symbols:
        payload = await asyncio.to_thread(
            fetch_json,
            "/api/v3/depth",
            symbol=symbol,
            limit=DEPTH_LIMIT,
        )
        book = LocalOrderBook(symbol)
        book.apply_snapshot(payload)
        books[symbol] = book

    stable_mid = 1.0
    if any(quote_asset(symbol) == "USDC" for symbol in symbols):
        stable = await asyncio.to_thread(
            fetch_json,
            "/api/v3/ticker/bookTicker",
            symbol=STABLE_SYMBOL,
        )
        stable_mid = (float(stable["bidPrice"]) + float(stable["askPrice"])) / 2.0
    return books, stable_mid


def read_control_state(url: str, expected_session_id: str) -> dict[str, Any] | None:
    separator = "&" if "?" in url else "?"
    fresh_url = f"{url}{separator}t={int(time.time() * 1000)}"
    request = urllib.request.Request(
        fresh_url,
        headers={
            "User-Agent": "SecondTextRep-MarketDataWorker/1.0",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if str(payload.get("session_id")) != expected_session_id:
        raise ValueError("Control state session_id mismatch")
    return payload


def control_requests_stop(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    return str(payload.get("desired_state", "RUNNING")).upper() in {
        "STOP_REQUESTED",
        "STOPPED",
        "CANCELLED",
    }


def market_rows(
    at: datetime,
    session_id: str,
    mode: str,
    books: dict[str, LocalOrderBook],
    flows: dict[str, dict[str, Any]],
    stable_mid: float,
    book_tickers: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol, book in books.items():
        quote_to_usdt = stable_mid if quote_asset(symbol) == "USDC" else 1.0
        ticker = book_tickers.get(symbol, {})
        row: dict[str, Any] = {
            "timestamp_utc": iso_utc(at),
            "session_id": session_id,
            "mode": mode,
            "symbol": symbol,
            "quote_to_usdt": quote_to_usdt,
            "best_bid": book.best_bid,
            "best_ask": book.best_ask,
            "mid_usdt": book.mid * quote_to_usdt,
            "spread_bps": book.spread_bps,
            "update_id": book.update_id,
            "bookticker_bid": ticker.get("bid"),
            "bookticker_ask": ticker.get("ask"),
            **flows.get(symbol, {}),
        }
        for band in DEPTH_BANDS:
            bps = int(round(band * 10_000))
            row[f"bid_depth_{bps}bps_usd"] = book.depth_quote(
                "bid", band, quote_to_usdt
            )
            row[f"ask_depth_{bps}bps_usd"] = book.depth_quote(
                "ask", band, quote_to_usdt
            )
        row.update(execution_costs_bps(book, quote_to_usdt))
        rows.append(row)
    return rows


def data_path(output_root: Path, session_id: str, at: datetime) -> Path:
    return (
        output_root
        / "sessions"
        / session_id
        / at.strftime("%Y-%m-%d")
        / "market_aggregates.csv"
    )


def install_signal_handlers(controller: StopController) -> None:
    def handler(signum: int, _frame: Any) -> None:
        controller.request(f"signal:{signum}")

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):
            pass


async def collect(
    output_root: Path,
    session_id: str,
    symbols: tuple[str, ...],
    mode: str,
    duration_seconds: int,
    sample_interval_seconds: int | None = None,
    control_url: str | None = None,
    control_poll_seconds: int = DEFAULT_CONTROL_POLL_SECONDS,
) -> dict[str, Any]:
    from websockets.asyncio.client import connect

    session_id = validate_session_id(session_id)
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if control_poll_seconds <= 0:
        raise ValueError("control_poll_seconds must be positive")

    mode = normalize_mode(mode)
    symbols = normalize_symbols(symbols)
    sample_interval = sample_interval_seconds or MODE_SAMPLE_SECONDS[mode]
    if sample_interval <= 0:
        raise ValueError("sample interval must be positive")

    output_root.mkdir(parents=True, exist_ok=True)
    controller = StopController()
    install_signal_handlers(controller)
    counters = RuntimeCounters()
    started_at = utc_now()
    deadline = time.monotonic() + duration_seconds
    flows = {symbol: IntervalFlow() for symbol in symbols}
    book_tickers: dict[str, dict[str, float]] = {}
    last_sample_monotonic = 0.0
    last_control_poll = 0.0
    stop_reason = "segment_complete"
    latest_books: dict[str, LocalOrderBook] = {}
    stable_mid = 1.0

    while time.monotonic() < deadline and not controller.requested:
        counters.reconnect_count += 1
        try:
            async with connect(
                _stream_url(symbols),
                open_timeout=20,
                close_timeout=5,
                ping_interval=20,
                ping_timeout=20,
                max_queue=8192,
            ) as websocket:
                latest_books, stable_mid = await fetch_snapshots(symbols)
                while time.monotonic() < deadline and not controller.requested:
                    now_monotonic = time.monotonic()
                    if control_url and (
                        last_control_poll == 0.0
                        or now_monotonic - last_control_poll >= control_poll_seconds
                    ):
                        try:
                            control = await asyncio.to_thread(
                                read_control_state,
                                control_url,
                                session_id,
                            )
                            if control_requests_stop(control):
                                controller.request("control_stop_requested")
                                stop_reason = controller.reason
                                break
                            control_mode = str((control or {}).get("mode", mode)).upper()
                            control_symbols = tuple((control or {}).get("symbols", list(symbols)))
                            if control_mode != mode or control_symbols != symbols:
                                controller.request("control_update_requested")
                                stop_reason = controller.reason
                                break
                        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
                            counters.control_poll_error_count += 1
                        last_control_poll = now_monotonic

                    timeout = max(0.25, min(5.0, deadline - time.monotonic()))
                    try:
                        raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                    except asyncio.TimeoutError:
                        raw = None

                    if raw is not None:
                        envelope = json.loads(raw)
                        data = envelope.get("data", envelope)
                        stream = str(envelope.get("stream", ""))
                        event_type = data.get("e")
                        symbol = str(data.get("s") or "").upper()

                        if event_type == "depthUpdate" and symbol in latest_books:
                            quote_to_usdt = (
                                stable_mid if quote_asset(symbol) == "USDC" else 1.0
                            )
                            delta = latest_books[symbol].apply_depth(data, quote_to_usdt)
                            flow = flows[symbol]
                            flow.depth_events += 1
                            for key, value in delta.items():
                                setattr(flow, key, getattr(flow, key) + float(value))
                        elif event_type == "aggTrade" and symbol in flows:
                            price, qty = float(data["p"]), float(data["q"])
                            quote_to_usdt = (
                                stable_mid if quote_asset(symbol) == "USDC" else 1.0
                            )
                            quote_value = price * qty * quote_to_usdt
                            flow = flows[symbol]
                            flow.agg_trades += 1
                            if bool(data.get("m")):
                                flow.taker_sell_quote_usd += quote_value
                            else:
                                flow.taker_buy_quote_usd += quote_value
                        elif stream.endswith("@bookTicker") or (
                            "b" in data and "a" in data and "u" in data
                        ):
                            if symbol == STABLE_SYMBOL:
                                stable_mid = (float(data["b"]) + float(data["a"])) / 2.0
                            elif symbol in latest_books:
                                book_tickers[symbol] = {
                                    "bid": float(data["b"]),
                                    "ask": float(data["a"]),
                                }

                    now_monotonic = time.monotonic()
                    if (
                        latest_books
                        and (
                            last_sample_monotonic == 0.0
                            or now_monotonic - last_sample_monotonic >= sample_interval
                        )
                    ):
                        at = utc_now()
                        flow_payload = {symbol: flows[symbol].consume() for symbol in symbols}
                        rows = market_rows(
                            at,
                            session_id,
                            mode,
                            latest_books,
                            flow_payload,
                            stable_mid,
                            book_tickers,
                        )
                        append_rows(data_path(output_root, session_id, at), rows)
                        counters.sample_row_count += len(rows)
                        last_sample_monotonic = now_monotonic

        except SequenceGap as exc:
            counters.sequence_gap_count += 1
            append_rows(
                output_root / "sessions" / session_id / "runtime_events.csv",
                [
                    {
                        "timestamp_utc": iso_utc(),
                        "event": "SEQUENCE_GAP",
                        "detail": str(exc),
                    }
                ],
            )
            await asyncio.sleep(1)
        except Exception as exc:
            append_rows(
                output_root / "sessions" / session_id / "runtime_events.csv",
                [
                    {
                        "timestamp_utc": iso_utc(),
                        "event": "RECONNECT",
                        "detail": repr(exc),
                    }
                ],
            )
            if time.monotonic() < deadline and not controller.requested:
                await asyncio.sleep(2)

    if controller.requested and stop_reason == "segment_complete":
        stop_reason = controller.reason or "stop_requested"

    ended_at = utc_now()
    manifest = {
        "capability_id": CAPABILITY_ID,
        "session_id": session_id,
        "status": (
            "RECONFIGURE"
            if stop_reason == "control_update_requested"
            else "STOPPED" if controller.requested else "SEGMENT_COMPLETE"
        ),
        "stop_reason": stop_reason,
        "mode": mode,
        "symbols": list(symbols),
        "sample_interval_seconds": sample_interval,
        "segment_requested_seconds": duration_seconds,
        "started_at_utc": iso_utc(started_at),
        "ended_at_utc": iso_utc(ended_at),
        "sample_row_count": counters.sample_row_count,
        "reconnect_count": counters.reconnect_count,
        "sequence_gap_count": counters.sequence_gap_count,
        "control_poll_error_count": counters.control_poll_error_count,
        "dependency": {"websockets": "17.2", "license": "BSD-3-Clause"},
        "interpretation_boundary": [
            "Public Binance Spot market-data collection only; no real orders.",
            "V1 stores normalized aggregate snapshots rather than every raw depth event.",
            "USDC-quoted values are normalized with the observed USDCUSDT book ticker.",
            "A market keeps its own statistical profile; this collector does not apply trading thresholds.",
            "Fixed-notional depth walks are virtual instantaneous costs versus the mid; fees and future market impact are excluded.",
        ],
    }
    write_json(output_root / "sessions" / session_id / "segment_manifest.json", manifest)
    return manifest


async def smoke(
    output_root: Path,
    symbols: tuple[str, ...],
    duration_seconds: int,
) -> dict[str, Any]:
    session_id = "smoke-" + utc_now().strftime("%Y%m%dT%H%M%SZ")
    result = await collect(
        output_root=output_root,
        session_id=session_id,
        symbols=symbols,
        mode="BURST",
        duration_seconds=duration_seconds,
        sample_interval_seconds=1,
        control_url=None,
    )
    result["pass"] = (
        result["sample_row_count"] >= len(symbols)
        and result["sequence_gap_count"] == 0
    )
    write_json(output_root / "smoke_summary.json", result)
    if not result["pass"]:
        raise RuntimeError("Live smoke did not satisfy acceptance criteria")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("collect", "smoke"))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--session-id", default=os.environ.get("SESSION_ID", "manual"))
    parser.add_argument("--symbols", required=True)
    parser.add_argument("--mode", default="LIGHT")
    parser.add_argument("--duration-seconds", type=int, default=DEFAULT_SEGMENT_SECONDS)
    parser.add_argument("--sample-interval-seconds", type=int)
    parser.add_argument("--control-url")
    parser.add_argument(
        "--control-poll-seconds",
        type=int,
        default=DEFAULT_CONTROL_POLL_SECONDS,
    )
    args = parser.parse_args(argv)

    symbols = normalize_symbols(args.symbols)
    if args.command == "collect":
        result = asyncio.run(
            collect(
                output_root=args.output_root,
                session_id=args.session_id,
                symbols=symbols,
                mode=args.mode,
                duration_seconds=args.duration_seconds,
                sample_interval_seconds=args.sample_interval_seconds,
                control_url=args.control_url,
                control_poll_seconds=args.control_poll_seconds,
            )
        )
    else:
        result = asyncio.run(
            smoke(args.output_root, symbols, args.duration_seconds)
        )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

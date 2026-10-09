"""Bounded, resumable public ten-market observation. No private strategy data."""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from market_data_worker import validate_session_id

EXPECTED_HOURS = 168
SEGMENT_SECONDS = 14400


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must have timezone")
    return result.astimezone(timezone.utc)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def session_root(data_root: Path, session_id: str) -> Path:
    return data_root / "data" / "sessions" / validate_session_id(session_id)


def completed_segments(root: Path) -> list[int]:
    completed = []
    for folder in (root / "segments").glob("*"):
        if not folder.is_dir() or not folder.name.isdecimal():
            continue
        manifest = folder / "segment_manifest.json"
        receipt = folder / "PERSISTED.json"
        if manifest.is_file() and receipt.is_file():
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            if payload.get("status") == "SEGMENT_COMPLETE":
                completed.append(int(folder.name))
    return sorted(completed)


def plan(root: Path, session_id: str, *, allow_start: bool = False,
         now: datetime | None = None) -> dict:
    now = now or utc_now()
    started = root / "STARTED.json"
    final = root / "COMPLETED.json"
    if final.exists():
        return {"action": "idle", "reason": "final_receipt_exists"}
    if not started.exists():
        if not allow_start:
            return {"action": "idle", "reason": "not_started"}
        write_json(started, {
            "session_id": validate_session_id(session_id),
            "status": "RUNNING", "started_at_utc": now.isoformat(),
            "target_hours": EXPECTED_HOURS, "segment_seconds": SEGMENT_SECONDS,
        })
    meta = json.loads(started.read_text(encoding="utf-8"))
    if meta["session_id"] != session_id or meta["target_hours"] != EXPECTED_HOURS:
        raise ValueError("Invalid stored observation contract")
    deadline = parse_utc(meta["started_at_utc"]) + timedelta(hours=EXPECTED_HOURS)
    if now >= deadline:
        return {"action": "finish", "reason": "observation_deadline"}
    completed = completed_segments(root)
    nxt = 1
    for index in completed:
        if index != nxt:
            break
        nxt += 1
    seconds_left = int((deadline - now).total_seconds())
    if seconds_left <= 0:
        return {"action": "finish", "reason": "observation_deadline"}
    return {"action": "collect", "segment": nxt,
            "duration_seconds": min(SEGMENT_SECONDS, seconds_left),
            "started_at_utc": meta["started_at_utc"]}


def stage(source: Path, target: Path, segment: int, run_id: str,
          *, now: datetime | None = None) -> dict:
    """Best-effort partial evidence. Never counted as a completed segment."""
    validate_session_id(run_id)
    attempt = target / "attempts" / str(segment) / run_id
    attempt.mkdir(parents=True, exist_ok=True)
    files = []
    for original in source.rglob("*"):
        if not original.is_file() or original.suffix not in (".csv", ".json"):
            continue
        rel = original.relative_to(source)
        dest = attempt / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        staging = dest.with_name(dest.name + ".tmp")
        shutil.copyfile(original, staging)
        staging.replace(dest)
        files.append(str(rel))
    receipt = {
        "partial_only": True, "segment": segment, "run_id": run_id,
        "checkpoint_utc": (now or utc_now()).isoformat(),
        "files": sorted(files),
    }
    write_json(attempt / "CHECKPOINT.json", receipt)
    return receipt


def finish_segment(source: Path, root: Path, segment: int, run_id: str) -> dict:
    manifest_path = source / "segment_manifest.json"
    if not manifest_path.exists():
        raise ValueError("Cannot complete a segment without collector manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "SEGMENT_COMPLETE":
        raise ValueError("Collector did not finish normally")
    if int(manifest.get("sequence_gap_count", -1)) != 0:
        raise ValueError("Unresolved depth sequence gap; retain partial evidence")
    if int(manifest.get("sample_row_count", 0)) <= 0:
        raise ValueError("Empty collector segment")
    dest = root / "segments" / str(segment)
    if (dest / "PERSISTED.json").exists():
        raise ValueError("Segment already committed; do not overwrite")
    if dest.exists():
        raise ValueError("Unrecognized existing segment; refuse overwrite")
    shutil.copytree(source, dest)
    receipt = {"segment": segment, "run_id": validate_session_id(run_id),
               "persisted_at_utc": utc_now().isoformat()}
    write_json(dest / "PERSISTED.json", receipt)
    return receipt


def audit(root: Path, expected_symbols: tuple[str, ...]) -> dict:
    started = json.loads((root / "STARTED.json").read_text(encoding="utf-8"))
    start = parse_utc(started["started_at_utc"])
    end = start + timedelta(hours=EXPECTED_HOURS)
    # Compare true UTC-minute coverage, not merely number of rows or timestamp span.
    first = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
    expected_minutes = [first + timedelta(minutes=i) for i in range(EXPECTED_HOURS * 60)]
    # The last bucket is outside the wall-clock observation deadline; remove it.
    expected = {int(t.timestamp() // 60) for t in expected_minutes if t < end}
    minute_sets = {symbol: set() for symbol in expected_symbols}
    seen_rows = Counter()
    sequence_gaps = 0
    manifests = []
    for index in completed_segments(root):
        segment_root = root / "segments" / str(index)
        manifest = json.loads((segment_root / "segment_manifest.json").read_text())
        manifests.append(index)
        sequence_gaps += int(manifest.get("sequence_gap_count", 0))
        for path in segment_root.glob("*/market_aggregates.csv"):
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    symbol = row.get("symbol", "")
                    if symbol not in minute_sets:
                        continue
                    seen_rows[symbol] += 1
                    minute = int(parse_utc(row["timestamp_utc"]).timestamp() // 60)
                    if minute in expected:
                        minute_sets[symbol].add(minute)
    per_market = {}
    for symbol, present in minute_sets.items():
        missing = sorted(expected - present)
        longest_gap = 0
        streak = 0
        previous = None
        for minute in missing:
            streak = streak + 1 if previous is not None and minute == previous + 1 else 1
            longest_gap = max(longest_gap, streak)
            previous = minute
        per_market[symbol] = {
            "rows": seen_rows[symbol], "unique_minutes": len(present),
            "expected_minutes": len(expected), "missing_minutes": len(missing),
            "coverage_pct": round(100 * len(present) / max(1, len(expected)), 4),
            "max_consecutive_missing_minutes": longest_gap,
        }
    gaps = any(item["missing_minutes"] for item in per_market.values())
    complete = bool(manifests) and not gaps and sequence_gaps == 0
    return {
        "status": "COMPLETED" if complete else "INCOMPLETE",
        "source": "PUBLIC_SPOT_ONLY", "target_hours": EXPECTED_HOURS,
        "completed_segments": manifests,
        "sequence_gap_count": sequence_gaps,
        "per_market": per_market,
        "note": "Missing public L2 observations cannot be reconstructed retroactively.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "stage", "complete", "finish"))
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--segment", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--allow-start", action="store_true")
    parser.add_argument("--symbols")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    root = session_root(args.data_root, args.session_id)
    if args.command == "plan":
        result = plan(root, args.session_id, allow_start=args.allow_start)
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as handle:
                for k in ("action", "segment", "duration_seconds"):
                    if k in result:
                        handle.write(f"{k}={result[k]}\n")
    elif args.command == "stage":
        result = stage(args.source, root, args.segment, args.run_id)
    elif args.command == "complete":
        result = finish_segment(args.source, root, args.segment, args.run_id)
    else:
        if not args.symbols:
            parser.error("--symbols required for finish")
        symbols = tuple(x.strip().upper() for x in args.symbols.split(","))
        result = audit(root, symbols)
        write_json(root / "COMPLETED.json", result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

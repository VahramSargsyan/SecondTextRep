from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_COMMANDS = {"START", "UPDATE", "STOP", "FINALIZE", "FAIL"}
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,96}$")
VALID_MODES = {"LIGHT", "WATCH", "BURST"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_symbols(value: str) -> list[str]:
    symbols = list(
        dict.fromkeys(
            part.strip().upper()
            for part in value.split(",")
            if part.strip()
        )
    )
    if not symbols:
        raise ValueError("symbols are required for START/UPDATE")
    for symbol in symbols:
        if not symbol.isalnum() or not symbol.endswith(("USDT", "USDC")):
            raise ValueError(f"unsupported symbol {symbol!r}")
    return symbols


def load_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def apply_command(
    path: Path,
    session_id: str,
    command: str,
    symbols: str = "",
    mode: str = "",
    segment_seconds: int = 900,
    detail: str = "",
) -> dict[str, Any]:
    command = command.strip().upper()
    if command not in VALID_COMMANDS:
        raise ValueError(f"Unsupported command {command!r}")
    if not SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("session_id must match [A-Za-z0-9._-] and be at most 96 characters")

    previous = load_state(path)
    timestamp = now_iso()

    if command in {"START", "UPDATE"}:
        normalized_symbols = normalize_symbols(symbols)
        normalized_mode = mode.strip().upper()
        if normalized_mode not in VALID_MODES:
            raise ValueError(f"Unsupported mode {mode!r}")
        if not 30 <= int(segment_seconds) <= 3600:
            raise ValueError("segment_seconds must be between 30 and 3600")
        if command == "UPDATE" and previous is None:
            raise ValueError("UPDATE requires an existing session")
        if previous is not None and str(previous.get("session_id")) != session_id:
            raise ValueError("session_id mismatch")

        payload = {
            "session_id": session_id,
            "desired_state": "RUNNING",
            "mode": normalized_mode,
            "symbols": normalized_symbols,
            "segment_seconds": int(segment_seconds),
            "revision": int((previous or {}).get("revision", 0)) + 1,
            "created_at_utc": (previous or {}).get("created_at_utc", timestamp),
            "updated_at_utc": timestamp,
            "last_command": command,
        }
        should_dispatch = previous is None or str(previous.get("desired_state")) != "RUNNING"

    elif command == "STOP":
        if previous is None:
            raise ValueError("STOP requires an existing session")
        payload = dict(previous)
        payload.update(
            {
                "desired_state": "STOP_REQUESTED",
                "revision": int(previous.get("revision", 0)) + 1,
                "updated_at_utc": timestamp,
                "last_command": "STOP",
            }
        )
        should_dispatch = False

    elif command == "FINALIZE":
        if previous is None:
            raise ValueError("FINALIZE requires an existing session")
        payload = dict(previous)
        payload.update(
            {
                "desired_state": "STOPPED",
                "revision": int(previous.get("revision", 0)) + 1,
                "updated_at_utc": timestamp,
                "last_command": "FINALIZE",
            }
        )
        should_dispatch = False

    else:  # FAIL
        if previous is None:
            raise ValueError("FAIL requires an existing session")
        payload = dict(previous)
        payload.update(
            {
                "desired_state": "FAILED",
                "revision": int(previous.get("revision", 0)) + 1,
                "updated_at_utc": timestamp,
                "last_command": "FAIL",
                "last_error": detail[:1000],
            }
        )
        should_dispatch = False

    write_state(path, payload)
    return {
        "state": payload,
        "should_dispatch": should_dispatch,
        "previous_state": previous,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--symbols", default="")
    parser.add_argument("--mode", default="")
    parser.add_argument("--segment-seconds", type=int, default=900)
    parser.add_argument("--result-file", type=Path)
    parser.add_argument("--detail", default="")
    args = parser.parse_args(argv)

    result = apply_command(
        path=args.state_file,
        session_id=args.session_id,
        command=args.command,
        symbols=args.symbols,
        mode=args.mode,
        segment_seconds=args.segment_seconds,
        detail=args.detail,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if args.result_file:
        args.result_file.parent.mkdir(parents=True, exist_ok=True)
        args.result_file.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

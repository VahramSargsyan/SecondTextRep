from __future__ import annotations

import argparse
import json
import os
import urllib.request


def dispatch(repository: str, token: str, event_type: str, payload: dict[str, object]) -> None:
    url = f"https://api.github.com/repos/{repository}/dispatches"
    body = json.dumps({"event_type": event_type, "client_payload": payload}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "SecondTextRep-MarketDataWorker/1.0",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status not in (200, 204):
            raise RuntimeError(f"Unexpected dispatch status {response.status}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--event-type", required=True)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not args.repository:
        raise SystemExit("repository is required")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    dispatch(
        args.repository,
        token,
        args.event_type,
        {"session_id": args.session_id},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

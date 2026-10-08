# Event-Driven Market Data Worker V1

This public worker intentionally knows very little.

```text
PRIVATE STRATEGY SYSTEM
        |
        | START / UPDATE / STOP
        | opaque session + public symbols + mode
        v
PUBLIC WORKER
        |
        | Binance public Spot data
        v
normalized session evidence
```

## Modes

| Mode | Default saved aggregate cadence | Intended use |
|---|---:|---|
| LIGHT | 60 s | cheap market baseline |
| WATCH | 10 s | candidate becoming relevant |
| BURST | 1 s | execution-near observation while consuming 100 ms depth events |

V1 does not keep every raw depth event. It rebuilds the book and stores compact aggregates.

## Control

Public command state is stored separately from source code on `runtime-control`.

Conceptual payload:

```json
{
  "command": "START",
  "session_id": "opaque-8f31c0",
  "symbols": "TWTUSDT,TWTUSDC,TRXUSDT,TRXUSDC",
  "mode": "WATCH",
  "segment_seconds": 900
}
```

`UPDATE` may change symbols/mode. The active collector notices the changed control state, exits its current segment cleanly, and the next segment restarts from the new configuration.

`STOP` sets `STOP_REQUESTED`. The collector polls control state, exits, persists its last bounded segment, and the workflow finalizes the session as `STOPPED`.

## Privacy boundary

Do not put the reason for the rotation in this repository. `session_id` should be opaque and must not contain names such as `TWT_TO_TRX_ROTATION_10PCT`.

The public symbol set is still observable. That residual leakage is accepted for V1 and can later be reduced by collecting a wider candidate set or continuous LIGHT background coverage.

## Retention

`market-data` is for bounded normalized evidence, not unlimited raw L2 history. Future retention/archival changes need a separate Build Packet.

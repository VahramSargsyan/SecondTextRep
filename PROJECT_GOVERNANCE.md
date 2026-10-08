# SecondTextRep — Public Market Data Worker Governance

GOVERNANCE_VERSION: **VAHRAM_APP_GOVERNANCE v1.1.0**  
CANONICAL_SOURCE: `VahramSargsyan/vbos-app/docs/governance/VAHRAM_APP_UNIVERSAL_GOVERNANCE_v1.1.0.md`  
LOCAL_PROFILE: **PUBLIC_MARKET_DATA_WORKER**  
STATUS: ACTIVE WHEN MERGED TO `main`

This repository is intentionally generic. Its job is to collect reproducible public exchange market data for other systems without learning or exposing private strategy logic.

## 1. Mandatory workflow mode

Every task selects one primary mode from the canonical v1.1.0 set. `FULL_REBUILD_ALLOWED` requires explicit current permission.

## 2. Source-of-truth boundary

This repository may own:

- generic public-data collectors;
- collection session state;
- normalized public-market aggregates;
- data-quality manifests;
- generic transport/control code;
- tests and public operational documentation.

This repository must not own:

- Relative Rotation internals;
- portfolio state or capital size;
- private asset-selection thresholds;
- private strategy interpretation;
- real-order credentials or authenticated trading logic;
- Telegram secrets or private user data.

The private strategy repository decides **why / where** to rotate. This worker only collects the requested public markets.

## 3. Runtime lanes

Preferred lanes:

- `main`: reviewed source code and documentation;
- `runtime-control`: small mutable session-intent records only;
- `market-data`: bounded normalized collection evidence only.

Runtime/data branches are derived operational state. They are not accepted strategy source code and should not be merged into `main` merely because data exists there.

## 4. Collection protocol

Allowed public commands:

- `START`;
- `UPDATE`;
- `STOP`.

Minimum command payload:

- opaque `session_id`;
- symbols;
- `LIGHT`, `WATCH`, or `BURST` mode;
- bounded segment duration.

A command must not explain the private strategy reason for collection.

## 5. Retention boundary

V1 stores normalized aggregate snapshots, manifests and runtime events. It does **not** persist every raw depth event.

Future raw retention requires a separate storage/retention decision. Do not turn ordinary Git history into an unlimited append-only raw order-book archive.

## 6. Safety

- public Binance market data only in V1;
- no authenticated exchange endpoints;
- no real-money orders;
- no secrets in source, logs, payloads, or committed data;
- validate public inputs before using them as paths or symbols;
- bounded segments must stop on explicit control state;
- sequence gaps are evidence, not silently ignored success;
- missing runtime evidence is `NOT_RUN`, not PASS.

## 7. Test levels

Use exact labels such as:

- `STATIC_ONLY`;
- `LOCAL_TESTED`;
- `GITHUB_CI_TESTED`;
- `LIVE_PUBLIC_MARKET_DATA_SMOKE`;
- `PAPER_LIVE_OBSERVED`.

No static or unit test may be described as live runtime verification.

## 8. Promotion boundary

A source PR may be merged only after its required technical checks. Merging this worker does not authorize:

- changing `CryptoSignals` visibility;
- creating private-to-public credentials;
- starting indefinite collection;
- production strategy changes;
- real trading.

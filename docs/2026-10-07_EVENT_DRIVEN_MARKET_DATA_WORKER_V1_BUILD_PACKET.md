# EVENT_DRIVEN_MARKET_DATA_WORKER_V1 — Build Packet

CAPABILITY_ID: `EVENT_DRIVEN_MARKET_DATA_WORKER_V1`

USER_RESULT: repurpose the unused public `VahramSargsyan/SecondTextRep` repository into a generic, low-information-leak market-data worker that can start, update and stop public Binance order-book observation for the assets selected by a private strategy system.

WORKFLOW_MODE: `BUILD_NEW_APP`

RISK_CLASS: `L2` — public data infrastructure with runtime automation and privacy-leak considerations; no real orders or private strategy state.

BASE_COMMIT: `1015837eb09b921d70e926fa8ac2e24137e9a027`

OWNER_BRANCH: `feature/event-driven-market-data-worker-v1`

TEST_TARGET:

- deterministic local unit tests;
- Python compile check;
- GitHub CI;
- short live public Binance smoke on `TWTUSDT,TRXUSDT`;
- no private-strategy integration in this block.

## Scope

- preserve historical `testMarcdown.md` untouched;
- adopt canonical governance v1.1.0 through local adapters;
- generic collector for USDT/USDC Binance Spot books;
- local L2 reconstruction from snapshot + diff depth stream;
- `aggTrade` and `bookTicker` observation;
- depth bands at 25/50/100/200 bps;
- additions/removals within ±1%;
- taker buy/sell quote flow;
- USDC values normalized through `USDCUSDT`;
- modes:
  - `LIGHT`: default 60-second aggregate sample;
  - `WATCH`: default 10-second aggregate sample;
  - `BURST`: default 1-second aggregate sample while consuming 100ms depth events;
- opaque session control: `START / UPDATE / STOP`;
- bounded collection segments, default 900 seconds;
- public control state on `runtime-control` branch;
- normalized evidence on `market-data` branch;
- collector polls control state and exits early on STOP or reconfiguration;
- self-chain the next bounded segment only while desired state remains `RUNNING`;
- partition stored evidence by session / segment / UTC date;
- fail closed: a fatal segment failure marks session `FAILED` and does not auto-chain.

## Out of scope / do not touch

- do not change `CryptoSignals` repository visibility;
- do not implement the private `CryptoSignals -> SecondTextRep` sender yet;
- do not copy private rotation thresholds, portfolio data or strategy reasons here;
- no real-money orders;
- no authenticated Binance endpoints;
- no Telegram behavior;
- no ML / alpha interpretation;
- no long-term raw depth-event archive in ordinary Git history;
- do not interrupt or modify the active TWT 72h experiment in `CryptoSignals`;
- do not delete or rewrite the old training file in this repository.

## Shared hotspots

- `.github/workflows/market-data-worker.yml` controls public runtime automation;
- `runtime-control` branch stores small desired-state files;
- `market-data` branch stores normalized evidence;
- public symbol selection itself may reveal which assets are being observed.

## Canonical / schema impact

Canonical strategy state: none in this repository.

New public data contract: aggregate CSV rows with session/mode/symbol, spread, mid, depth bands, depth-flow, trade-flow, update id and bookTicker fields plus per-segment manifest.

SCHEMA_IMPACT: new isolated dataset only; no migration of existing saved application data.

MIGRATION_PLAN: `NONE`.

## Dependencies

- Python standard library;
- `websockets==17.2`, BSD-3-Clause, already validated in the parent TWT public-data research path;
- GitHub-hosted standard public-repository Actions;
- `actions/checkout@v4` and `actions/setup-python@v5` as workflow dependencies.

No third-party strategy code is copied.

## Acceptance / required evidence

1. symbol/mode/session validation PASS;
2. depth update and gap detection deterministic test PASS;
3. START -> UPDATE -> STOP -> FINALIZE state test PASS;
4. path partition/control read deterministic test PASS;
5. Python compile PASS;
6. GitHub CI PASS on candidate SHA;
7. live public Binance smoke receives usable rows and reports zero sequence gaps for the smoke interval;
8. code and docs contain no private strategy reason/threshold/portfolio state;
9. active `CryptoSignals` 72h run remains untouched.

## Rollback

Before merge: close/revert feature PR.

After merge: revert the exact source commit and stop any active session through `STOP`; runtime/data branches may be retained as evidence or deleted only by a separately confirmed cleanup action.

## Promotion path

`CANDIDATE -> TECHNICALLY_VERIFIED -> AWAITING_USER_ACCEPTANCE`.

Cross-repository private sender and `CryptoSignals` visibility changes are separate future blocks.

AUTHORIZED_ACTIONS: current assistant may implement/test this bounded public worker and prepare a PR; no private-repository visibility change, external credential creation, real trading, or PROD strategy promotion is authorized.

EXECUTOR_PERMISSION: current ChatGPT assistant only.

PAID_API_BUDGET: `0`.

REPAIR_LIMIT: at most two focused evidence-producing repair cycles.

STOP_CONDITIONS: private strategy data would need to enter the public repo; paid/authenticated exchange data becomes required; real-order scope appears; live smoke still fails after two substantive repairs; an unapproved repository-visibility or credential decision becomes necessary.

AUTHORIZATION_END: block report after candidate + technical evidence are prepared.

UNRESOLVED_DECISIONS: `NONE` for this V1 block.

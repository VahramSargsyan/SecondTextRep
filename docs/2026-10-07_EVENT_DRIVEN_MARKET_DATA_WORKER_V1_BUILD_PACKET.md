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


## Follow-on observation — U10_EX_TWT_TRX_BASELINE_24H_V1

CAPABILITY_ID: `U10_EX_TWT_TRX_BASELINE_24H_V1`

USER_RESULT: collect the first 24 hours of LIGHT baseline order-book evidence for the eight currently discussed U10 markets not already covered by the separate TWT/TRX 72h experiment.

WORKFLOW_MODE: `PRODUCTION_OBSERVATION`

RISK_CLASS: `L2` — public market-data observation only; no private strategy state and no real orders.

BASE_COMMIT / OWNER_BRANCH / TEST_TARGET:
- worker candidate base: `fba4f999ec9d09f83599f6d7c64ae567e12413db`;
- owner branch: `feature/event-driven-market-data-worker-v1`;
- data branch: `market-data`;
- session id: `obs-20261007-01`;
- test target: all-market public Binance smoke before the 24h chain, then six sequential 4h collection segments.

SCOPE:
- symbols: `PEPEUSDT,BNBUSDT,AAVEUSDT,AVAXUSDT,FILUSDT,ALGOUSDT,XRPUSDT,HBARUSDT`;
- mode: `LIGHT`;
- saved aggregate cadence: 60 seconds;
- incoming public streams remain depth@100ms + aggTrade + bookTicker;
- six bounded 4-hour segments = 24 hours of requested collection time;
- persist normalized aggregate evidence and manifests on `market-data`;
- preserve TWT/TRX exclusion because those markets are already under the separate CryptoSignals observation.

OUT_OF_SCOPE / DO_NOT_TOUCH:
- no TWT/TRX collection in this session;
- no `CryptoSignals` code or visibility change;
- no private rotation trigger/reason/portfolio state;
- no START/STOP sender integration from the private repository;
- no authenticated Binance endpoints;
- no real-money orders;
- no indefinite collection;
- no raw event-by-event L2 archive.

SHARED_HOTSPOTS:
- GitHub-hosted runner capacity;
- public Binance market-data availability;
- `market-data` branch writes are serialized by the observation workflow.

CANONICAL / SCHEMA_IMPACT:
- new isolated observation session using the existing worker aggregate schema;
- no strategy/schema migration.

MIGRATION_PLAN: `NONE`.

ACCEPTANCE / REQUIRED_EVIDENCE:
1. preflight live smoke sees usable rows for all eight symbols with zero sequence gaps;
2. observation session claim is persisted before long-running segments start;
3. six sequential 4h segments complete;
4. each segment persists a manifest and aggregate CSV evidence;
5. final completion marker records the session as complete;
6. no TWT/TRX rows are present in this session;
7. no private strategy data appears in public payloads/logs/files.

ROLLBACK / STOP:
- if preflight smoke fails, do not start the 24h chain;
- if a segment fails, fail-fast stops later matrix segments;
- partial evidence remains labeled incomplete and may be inspected rather than silently promoted;
- no automatic restart after failure.

AUTHORIZED_ACTIONS: current assistant may add/start this bounded observation workflow and inspect its launch state. No extra executor, paid API, private-repository mutation, real trading, or PROD strategy change is authorized.

EXECUTOR_PERMISSION: current ChatGPT assistant only.

PAID_API_BUDGET: `0`.

REPAIR_LIMIT: at most two focused evidence-producing repair cycles.

STOP_CONDITIONS: smoke failure after two substantive repairs, authenticated/paid market data becomes required, private strategy data would need to be exposed, real-order scope appears, or GitHub runner/push permissions prevent safe persistence.

AUTHORIZATION_END: launch confirmation and block report; the GitHub workflow may continue independently for its bounded 24h observation.

UNRESOLVED_DECISIONS: `NONE`.


## Follow-on bounded observation — PUBLIC_10_MARKET_BASELINE_7D_V1

CAPABILITY_ID: `PUBLIC_10_MARKET_BASELINE_7D_V1`

USER_RESULT: collect seven successive days of public Spot order-book statistics for ten named USDT markets, measuring both replenishment and hypothetical fixed-notional sell/buy execution costs to inform later private research. The data worker receives only public symbols and an opaque session identifier, not any private strategy, allocation, trigger, account or threshold.

WORKFLOW_MODE: `IMPLEMENT_FEATURE` (the new finite observation workflow and additive research measurements), then bounded public-data observation only.

RISK_CLASS: `L3` (financial research conclusions, multi-day hosted workflow, and public disclosure of the observed tickers).

BASE_COMMIT: `9274e902e7e49bb5d851acfb36bb09c9d6d96dc2`; OWNER_BRANCH: `feature/event-driven-market-data-worker-v1`; PR: `#1` remains DRAFT, not merged to main. TEST_TARGET: PR GitHub Actions, market-data isolated lane, Python deterministic tests and public Binance smoke.

SCOPE:
- session id `obs-20261008-07d-01` contains no strategic reason;
- markets: `TWTUSDT,PEPEUSDT,BNBUSDT,TRXUSDT,AAVEUSDT,AVAXUSDT,FILUSDT,ALGOUSDT,XRPUSDT,HBARUSDT`;
- `LIGHT` aggregate cadence of 60 seconds, consuming 100ms depth updates, aggTrade and bookTicker;
- bounded 42 four-hour segments (requested collection 168 hours), max one concurrent segment; one preflight smoke for all ten; each segment persists independent evidence;
- new additive columns: static-book sell and buy mid-relative execution costs (bps) for 10k, 50k, 100k, 250k and 500k USD; empty means not fully fillable using stored visible L2; these exclude trading fees and future drift;
- persist metadata, per-symbol coverage and fail-closed final completeness checks on `market-data`, without rewriting the historical 24h baseline data;
- existing 72h TWT/TRX private-repository observation remains unchanged and may overlap in collection time.

OUT_OF_SCOPE / DO_NOT_TOUCH:
- no strategy algorithms, signal inputs, universe membership, portfolio data, holdings, reasons, Telegram, private repository visibility, authenticated Binance endpoints or real orders;
- no unbounded running, no raw depth-event archive in Git, no assertion that visible-book costs predict true execution;
- no automatic production promotion; the existing draft PR is not merged by this task.

SHARED_HOTSPOTS: branch feature PR CI, GitHub Actions runner concurrency, public Binance capacity, `market-data` write lane, concurrent 72h TWT/TRX observer.

SCHEMA_IMPACT: strictly additive columns for the *new* isolated 7d research output; old CSV schema and canonical private strategy untouched. MIGRATION_PLAN: none; rollback by cancelling the exact workflow run, no legacy deletion.

ACCEPTANCE:
1. deterministic depth-walk tests and original worker tests PASS;
2. preflight live smoke receives all ten symbols, nonempty depth and zero detected sequence gaps before claiming the session;
3. each of 42 four-hour segments persists a manifest and rows for all ten with at least 90% of theoretical minute count and zero sequence gaps;
4. final audit uses correct `segments/*/*/market_aggregates.csv` path and verifies 42 unique segments, per-symbol coverage, zero gaps, and observed span at least 167 hours;
5. final status is `COMPLETED` only when checks pass; otherwise `INCOMPLETE` with errors;
6. generated evidence contains no private strategy capital size, event rationale or trading signals. Notional test levels are generic public liquidity research parameters, not account holdings.

ROLLBACK: cancel the specific GitHub Actions workflow run and retire draft new workflow, retain bounded partial evidence labelled incomplete; existing 24h session and 72h project observer unchanged. No data migration.

AUTHORIZED_ACTIONS: user requested beginning a bounded seven-day observation. The current assistant may add generic public metrics, run safety checks, and start exactly one bounded seven-day workflow under the existing draft PR. No additional AI executor, authenticated API, paid API, or PROD changes.

EXECUTOR_PERMISSION: current assistant only for authoring; GitHub Actions may execute bounded standard collection CI as requested, not additional Codex/AI agents.

PAID_API_BUDGET: 0. REPAIR_LIMIT: at most two focused cycles. STOP_CONDITIONS: permission error; preflight fails; missing market; incomplete segment or sequence error; unauthorized public disclosure beyond public market symbols; repo/main promotion required; actual costs/capacity cannot be supported by available data.

AUTHORIZATION_END: launch receipt and exact technical block report. The platform-hosted collection may run according to its explicitly bounded duration; no continuing autonomous assistant work is promised.

## Follow-on bounded block — PUBLIC_10_MARKET_RESILIENT_7D_V2

CAPABILITY_ID: PUBLIC_10_MARKET_RESILIENT_7D_V2
USER_RESULT: Make future 7-day public observations restartable, preserve intermediate evidence, and report exact gaps; do not touch active V1.
WORKFLOW_MODE: PATCH_FIX (isolated reliability successor). RISK_CLASS: L3 (data-integrity/automation).
BASE_COMMIT: af4cdc34b56536270b3a4988ec946793911bcb49 (PR #1 candidate).
OWNER_BRANCH: feature/public-ten-7d-resilience-v2. TEST_TARGET: Python CI, GitHub PR tests, then gated TEST shutdown/restart.

SCOPE:
- Add separate public-ten-market-7d-resilient-v2.yml; original live V1 workflow/session remain untouched.
- Only an explicit workflow_dispatch creates STARTED; cron can resume but not independently start a session.
- Single concurrency group serializes START, repository_dispatch continuation and 15-minute scheduled recovery.
- Stage public-data partial checkpoints to market-data every 15 minutes; keep attempts separate from completed segment receipts.
- Persist immutable completed-segment receipt; retry interrupted attempt without claiming missing samples were observed.
- Validate per-market unique UTC minute coverage, longest missing streak and unresolved sequence gaps.
- Finalize at the 168-hour wall deadline; mark incomplete evidence INCOMPLETE, not PASS.

OUT_OF_SCOPE: CryptoSignals, V1 active run/session obs-20261008-7d-01, live strategy/trading, Telegram, credentials, paid API, source PR merge.
DEPENDENCIES: existing public Binance collector, Python stdlib, GitHub Actions, existing market-data branch, existing pinned websockets.
SCHEMA_IMPACT: additive isolated future session only; no legacy/strategy/schema changes. MIGRATION_PLAN: none.
ACCEPTANCE: deterministic tests covering explicit-only start, runner shutdown partial, segment retry protection, depth gap failure, and true UTC-minute coverage; GitHub CI; runtime TEST forced shutdown/recovery before adoption.
ROLLBACK: close/revert V2 PR; once adopted, disable/revert V2 workflow, retain evidence until separate cleanup approval.
PROMOTION: CANDIDATE -> TECHNICALLY_VERIFIED -> AWAITING_USER_ACCEPTANCE -> separate activation after the V1 run ends.
EXECUTOR_PERMISSION: current assistant only. PAID_API_BUDGET: 0. REPAIR_LIMIT: 2.
AUTHORIZED_ACTIONS: isolate feature, create draft PR against current candidate and perform safe tests. No merge, no concurrent new observation, no PROD.
STOP_CONDITIONS: active V1 endangered, failed required gate after bounded repairs, missing essential access or new external-data/permissions decision.
AUTHORIZATION_END: candidate PR and technical report.
RESIDUAL_RISK: GitHub scheduled events may be late or absent. A watchdog cannot reconstruct data never observed. Full GitHub crash/recovery acceptance: NOT_RUN until TEST.

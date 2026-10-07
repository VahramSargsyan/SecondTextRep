# Instructions for AI maintainers

GOVERNANCE_VERSION: **VAHRAM_APP_GOVERNANCE v1.1.0**  
CANONICAL_SOURCE: `VahramSargsyan/vbos-app/docs/governance/VAHRAM_APP_UNIVERSAL_GOVERNANCE_v1.1.0.md`  
BOUNDED_CONTRACT: `VahramSargsyan/vbos-app/docs/governance/BOUNDED_CHAT_WORK_CONTRACT_v1.1.0.md`  
LOCAL_PROFILE: **PUBLIC_MARKET_DATA_WORKER**

Read `PROJECT_GOVERNANCE.md` before implementation work. The canonical v1.1.0 rules are authority when accessible; this adapter may be stricter but may not weaken them.

Local P0 rules:

- this public repository is a generic public-market-data worker, not a strategy repository;
- never commit private rotation logic, portfolio state, capital size, private thresholds, Telegram credentials, exchange credentials, API tokens, or user-private data;
- no real-money order placement belongs here;
- collection commands expose only an opaque `session_id`, public market symbols, collection mode, and bounded runtime parameters;
- preserve the historical `testMarcdown.md` file unless a separate task explicitly retires it;
- `runtime-control` and `market-data` are runtime/data lanes and must not become strategy source-of-truth;
- Git should retain compact evidence and bounded aggregates, not unlimited raw L2 traffic;
- every runtime/data-contract change needs an updated Build Packet and exact test level;
- unknown third-party license means no copied code;
- do not change repository visibility or the private `CryptoSignals` repository without a separate explicit authorization.

# Local bounded-work adapter

Canonical contract: `VahramSargsyan/vbos-app/docs/governance/BOUNDED_CHAT_WORK_CONTRACT_v1.1.0.md`.

The canonical contract is normative when this adapter is merged. This file adds no new permission.

For normal/major work, use or extend a Build Packet with result, mode, base/head, scope, out-of-scope, risk, schema/migration impact, required evidence, rollback, budget, stop conditions and authorization boundary.

Current-assistant execution is allowed only by the actual user task. Additional executors and paid APIs require explicit authorization. Paid API budget defaults to `0`. Ordinary in-scope repairs are bounded to at most two focused evidence-producing cycles unless a stricter rule applies.

# ADR: Funding-History Refresh-Ahead Without Shortening Publication TTL

## Status

Accepted by the user for this LOW corrective stage.

## Decision

Funding history becomes refresh-due 300 seconds before its configured hard
publication expiry. The default thresholds are therefore 1500 seconds for
refresh and 1800 seconds for publication.

## Alternatives Rejected

### Change the global history TTL from 1800 to 1500

Rejected. That field also controls publication expiry and currently feeds the
borrow component due checks. It would move the visible gap earlier and increase
private refresh frequency.

### Change `_sweep_group_c` `component_ttl` to 1500

Rejected. That local value controls borrow-rate and max-borrowable checks; it
does not control the history cache guard.

### Fix coverage exit/re-entry in the same patch

Deferred by explicit user decision. Small-rate rows near `-0.00030000` are not
important opportunities for the current operator and do not justify expanding
this patch.

## Consequences

- Current approximately 94 candidates can receive early history refresh work
  during the approximately five-minute headroom without increasing the
  at-most-10-symbol tick boundary.
- Public history request cadence becomes approximately 25 minutes under the
  default setting; private borrow cadence remains approximately 30 minutes.
- Candidate sets exceeding the available five-minute sweep capacity are a
  future scaling concern, not part of this bounded correction.

本地北京时间: 2026-07-15 10:44:33 CST
下一步模型: claude_glm
下一步任务: 保持所有非历史组件不变，仅实现历史 refresh-ahead

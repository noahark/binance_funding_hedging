# Independent Main Baseline Amendment — Private TTL Example

## Human Direction

After local display-acceptance startup failed because the ignored `.env` still
contained `BINANCE_PRIVATE_CHANNEL_TTL_SECONDS=3600`, the human explicitly
directed the bookkeeper to update the tracked example directly and not rerun
review-1.

## Resolution

- Local ignored `.env`: changed from `3600` to `1800`; configuration parsing
  passed with `private_channel_ttl_seconds=1800`.
- Tracked `.env.example`: changed from `3600` to `1800` in an isolated direct
  `main` commit:
  `413aa94c3bc4d89088b77eca07d89f59d2285d4d`.
- The current stage branch did not modify `.env.example`; therefore the fixed
  reviewed implementation range and fingerprint remain unchanged.
- A later merge of the accepted stage branch into `main` must preserve commit
  `413aa94` and its `.env.example=1800` value.

This is a one-line operator-facing example correction, not delivery-code
authorship and not a claim that review-1 covered commit `413aa94`.

## Post-Review Bookkeeper Correction

Opus4.8 review-2 identified that the earlier full SHA
`413aa94c74e356d2a99595f11cc0b91b8448fece` was a transcription error. The
authoritative value from `git rev-parse main` is
`413aa94c3bc4d89088b77eca07d89f59d2285d4d`; the short prefix and one-line
`.env.example` content were always correct. The executed review prompts retain
the original string as immutable dispatch evidence, while this artifact and
`status.json` carry the corrected authoritative value.

Verification:

```text
git show main:.env.example | rg '^BINANCE_PRIVATE_CHANNEL_TTL_SECONDS='
=> BINANCE_PRIVATE_CHANNEL_TTL_SECONDS=1800

local .env parse
=> config_parse=PASS private_channel_ttl_seconds=1800
```

本地北京时间: 2026-07-15 09:06:19 CST
下一步模型: human → codex
下一步任务: review-2 同时核对固定 stage diff 与独立 main 基线修正 413aa94

# Design: Contract-First Public Market Discovery

## Design Summary

This stage separates market-field verification from UI implementation.

Claude-GLM first produces a backend-owned API contract. Kimi starts frontend work
only after the contract is frozen. This prevents the frontend from duplicating
Binance-specific assumptions and avoids repeating the Grok implementation drift.

## Data Flow

```text
Binance public docs + raw public samples
  -> Claude-GLM field matrix
  -> normalized public market snapshot contract
  -> JSON schema + normalized sample
  -> Kimi frontend adapter and Chinese workstation UI
```

## Backend Contract Work

Claude-GLM must:

1. Verify endpoint auth/security status.
2. Capture or reference raw JSON samples.
3. Map raw fields to normalized contract fields.
4. Explain ambiguous fields and unresolved questions.
5. Update `docs/api/public-market-contract.md`.
6. Update `schemas/api/public-market/snapshot.schema.json` if needed.
7. Provide one normalized sample for Kimi.

## Frontend Work

Kimi must:

1. Read only the frozen contract and sample JSON.
2. Keep the agreed Chinese workstation style.
3. Build the public market table, route labels, bStock labels, funding display,
   and manual-open ticket shell from contract fields.
4. Mark missing contract fields as blocked instead of inventing UI logic.

## Review Gates

- Contract review happens before frontend integration.
- Backend implementation review must use raw samples and schema validation.
- Frontend review must check Chinese copy, no Binance direct calls, and schema
  compatibility.

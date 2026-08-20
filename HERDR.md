# Herdr Window Routing

Read this file only for a task that inspects or uses Herdr. It defines stable
window labels for this computer and the local procedure that resolves a label
to the current Herdr pane. It is not a dispatch packet and never authorizes a
message send.

## Fixed Window Labels

| Window label |
|---|
| `codex` |
| `codex-review` |
| `grok` |
| `grok-review` |
| `claude-glm` |
| `claude-glm-review` |
| `claude` |
| `claude-review` |
| `kimi` |
| `kimi-review` |
| `agy` |
| `agy-review` |

These are delivery addresses, not model identities. Exact model, provider,
and role routing live only in `agents/roles.md`. Pane IDs, agent names,
session UUIDs, agent status, and terminal titles are transient and must never
be copied into this file as routing targets.

## Review Window Routing

When Human explicitly asks a model to perform a review, use that model's
corresponding `-review` label: for example, `grok` routes to `grok-review` and
`claude` routes to `claude-review`. If Human already names a `-review` label,
use that exact label. This rule applies only to review tasks; it does not route
other tasks to a review window. If the corresponding `-review` label is absent
from the table or cannot be resolved, stop and report it. Do not substitute a
base-model label or guess another target.

When sending an implement, fix, review-1, or review-2 task, choose `reply_to`
in this order and append the two lines below. Do not invent a label.

1. If Human already names a `reply_to` label, use that exact label.
2. Else if this is an implement, fix, review-1, or review-2 task on an active
   stage, use `status.json.bookkeeper_label`. If that field is missing, null,
   or cannot be resolved, omit `reply_to` and say so.
3. Else use this pane's label from `herdr pane current`. If this pane is not
   inside Herdr or has no label, omit `reply_to` and say so.

```text
reply_to: <label>
After emitting the normal console receipt, send that same receipt once to the
reply_to window per this file, then stop.
```

The named `reply_to` in a received prompt is the Human direction for exactly
one return send: the already-emitted console receipt, to that label, using
Resolve A Window and Send After Human Direction. Do not compose a second
receipt, wait, read, or poll. If `reply_to` is missing and this is an
implement, fix, review-1, or review-2 task on an active stage, send that same
receipt once to `status.json.bookkeeper_label`. Otherwise if `reply_to` is
missing, duplicated, or cannot be resolved, do not send; report it in this
window. The receipt already shown there still stands. This file does not
change where a staged task lands.

## Resolve A Window

1. Run `herdr pane list` on this local machine.
2. Find exactly one pane whose `label` exactly equals the Human-specified
   window label.
3. Use that pane's current `pane_id` with `herdr agent get <pane_id>` and
   confirm it still hosts a detected agent in the expected project directory.
4. If the label is absent, duplicated, or the pane is not a detected agent,
   stop and report the candidates or missing label. Never guess from position,
   model kind, terminal title, or a partial label.

## Send After Human Direction

Only after the Human explicitly directs a named window and the exact content to
send, use the pane ID resolved above:

```text
herdr agent prompt <pane_id> <content>
```

This is a local copy/paste-and-Enter operation. It does not create a model
session, does not record an approval, and does not authorize a later send or
any state transition. The only reply it authorizes is the one receipt return named in Review
Window Routing. Once Herdr returns `agent_prompted`,
report that the message was sent successfully and stop. Do not run `agent
wait`, `agent read`, polling, or `--wait` unless Human explicitly asks to
observe the target window. Those status checks do not prove that the newly
sent task completed: they may be satisfied by work that was already in
progress.

## Label Maintenance

Human owns the fixed labels. Do not rename, create, close, or rearrange Herdr
windows unless the Human explicitly asks. If Human changes the label scheme,
update this table before using the new labels.

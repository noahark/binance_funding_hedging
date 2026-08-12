# Herdr Window Routing

Read this file only for a task that inspects or uses Herdr. It defines stable
window labels for this computer and the local procedure that resolves a label
to the current Herdr pane. It is not a dispatch packet and never authorizes a
message send.

## Fixed Window Labels

| Window label | Intended model terminal |
|---|---|
| `codex` | Codex |
| `grok` | Grok |
| `claude-glm` | Claude Code using GLM |
| `claude` | Claude Code |
| `kimi` | Kimi |

These are expected labels, not a saved snapshot of live sessions. Pane IDs,
agent names, session UUIDs, agent status, and terminal titles are transient and
must never be copied into this file as routing targets.

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
session, does not record an approval, and does not authorize a reply, a later
send, or any state transition. Do not use `--wait` as proof that the newly sent
task completed: it observes a terminal state and may be satisfied by work that
was already in progress.

## Label Maintenance

Human owns the fixed labels. Do not rename, create, close, or rearrange Herdr
windows unless the Human explicitly asks. If Human changes the label scheme,
update this table before using the new labels.

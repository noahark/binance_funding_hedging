# Herdr Window Routing

Read this file only for a task that inspects or uses Herdr. It defines stable
window labels for this computer and the local procedure that resolves a label
to the current Herdr pane. It is not a dispatch packet and never authorizes a
message send.

## When Herdr Applies

A Human request to notify, prompt, or send an exact message to a named
terminal window is a request to read this file and, if needed, resolve the
window, even if the request does not name “Herdr”. It is not a send
authorization. A send still requires both a Human-specified label from the
table below and the exact content, as required by Send After Human Direction.
A name that is absent, partial, or not an exact table label is not a target;
stop under Resolve A Window. Do not compose, complete, or substitute message
text.

Herdr is the local `herdr` CLI, not an implicit model capability. Before any
inspection or send, verify that the current terminal is Herdr-managed:

```bash
test "${HERDR_ENV:-}" = 1
```

If the check fails, report that this terminal cannot safely inspect or control
Herdr and stop.

If it passes, the only allowed Herdr operations are the ones in this file. Do
not run bare `herdr` for discovery; it launches or attaches the interactive UI.
Do not run `herdr --skill` as a usage policy, and do not treat that skill or
`herdr --help` as permission to create layout, start or attach agents, read
another pane, wait, poll, or use `herdr notification`. The project send path is
`herdr agent prompt` below. If an allowed command in this file fails, run
`herdr --help` or that command’s `--help` only to recover installed flag names
for the same command.

## Fixed Window Labels

| Window label | Intended model terminal |
|---|---|
| `codex` | Codex |
| `codex-review` | Codex Review |
| `grok` | Grok |
| `grok-review` | Grok Review |
| `claude-glm` | Claude Code using GLM |
| `claude-glm-review` | Claude Code using GLM Review |
| `claude` | Claude Code |
| `claude-review` | Claude Code Review |
| `kimi` | Kimi |
| `kimi-review` | Kimi Review |
| `agy` | Antigravity (AGY), expected to run `gemini-3.1-pro` |
| `agy-review` | Antigravity (AGY) Review, expected to run `gemini-3.1-pro` |

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
send, or any state transition. Once Herdr returns `agent_prompted`, report that
the message was sent successfully and stop. Do not run `agent wait`, `agent
read`, polling, or `--wait` unless Human explicitly asks to observe the target
window. Those status checks do not prove that the newly sent task completed:
they may be satisfied by work that was already in progress.

## Label Maintenance

Human owns the fixed labels. Do not rename, create, close, or rearrange Herdr
windows unless the Human explicitly asks. If Human changes the label scheme,
update this table before using the new labels.

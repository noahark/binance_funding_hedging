# Follow-up: main 合入后文档卫生与语义冲突对照包

Status: **proposed plan for cross-model review** — not yet operator-approved as a
Harness delivery stage. No code/runtime contract is changed by this note alone.

> **执行状态 banner (2026-07-12)：本文件 §4 的 S1–S9 不再作为执行指令。**
> 以 Grok cross-review 的 Batch A1/A2/B/C 决议为准（S4 改走 STAGE_INDEX 索引标注、
> S6 取消、S7 跳过）。§1.2 的 Pass B 归档**目前仅完成文件系统操作，尚未形成 Git
> 提交**（`history/raw/*` 仍未跟踪）。**checkpoint 更正**：`433980d` 是原 T4 delivery
> checkpoint 的**正确**提交（snapshot 记录 `kind: combined_serial_v1_delivery_evidence`
> / `post_merge_pre_accept` / `passed`），当前工作树已**误将其改写**为 archive
> checkpoint。A2 必须从 snapshot **恢复**原 checkpoint 语义并**保留** `433980d`，
> 另在 `history_archive.post_accept_archive.content_commit` **单独绑定** A1 的真实归档
> SHA；`head_sha` / `diff_fingerprint` / handoff 的 T4 delivery head 继续为 `433980d`。
> **不得丢弃或重绑 `433980d`。** 正文以下保留 verbatim 作历史记录。

Recorded by: Grok bookkeeper session, 2026-07-12.<br>
Branch at authoring: `main` (local may be ahead of `origin/main`).<br>
Related stage: `2026-07-auto-review-pipeline-v1` (`status: accepted`, merged to
`main` by fast-forward).

Purpose: give another model a single, auditable packet covering:

1. history archive already done on the bootstrap stage;
2. remaining document scatter / cold-storage candidates;
3. multi-document semantic conflicts;
4. a proposed fix plan (priority-ordered, evidence-preserving).

---

## 0. Authority Order (do not invert)

> **更正 banner (2026-07-12)：本节以下列出的顺序并非 `AGENTS.md` 原文，请勿据此裁决。**
> 规范权威顺序的**唯一定义**是 `AGENTS.md` §Authority Order（第 52–66 行），共 10 级：
> 1 `AGENTS.md` · 2 `workflows/templates/*.yaml` · 3 `docs/parallel-development-mode.md` ·
> 4 `schemas/*.schema.json` · 5 `agents/registry.yaml` · 6 `docs/model-adapters.md` ·
> 7 `agents/skills/*.md` · 8 `agents/developer-discipline.md` ·
> 9 `reports/agent-runs/<stage>/` · 10 `docs/*.md`。
> 本节两处偏差：(a) 漏列 `agents/skills/*.md` 与 `agents/developer-discipline.md`；
> (b) 把 `docs/auto-review-pipeline.md` 提到第 7 —— 它其实停留在第 10 级 `docs/*.md`，
> 其规范力来自 `AGENTS.md` 正文引用，而非 authority order 里的独立层级。
> 下方原表保留作历史记录。

When resolving conflicts, use this order (from `AGENTS.md`):

1. `AGENTS.md`
2. `workflows/templates/*.yaml` (esp. `stage-delivery.yaml`)
3. `docs/parallel-development-mode.md` (when parallel mode applies)
4. `schemas/*.schema.json`
5. `agents/registry.yaml`
6. `docs/model-adapters.md`
7. `docs/auto-review-pipeline.md` (normative auto contract)
8. Active stage `status.json` / `70-handoff.md` / `current_inputs`
9. Other `docs/*.md`
10. Stage design shells (`10-design.md`, `11-adr.md`) and follow-up drafts

**Current model routing truth (registry, post convergence):**

| Adapter | Model |
|---|---|
| Codex default / schema review | `gpt-5.6-sol` |
| Grok dev + review (+ auto review-1 primary) | `grok-4.5` |
| Claude review primary | `claude-fable-5` |
| Claude review fallback | `opus4.8` (kept by operator; local CLI short-name may fail) |

**Auto v1 topology truth:** serial-only task units through review-1;
`parallel_mode` and `auto_review_pipeline` mutually exclusive; no total
runner-session wall-clock; per-adapter / command timeouts only.

---

## 1. History archive already performed

### 1.1 Pass A (earlier, stage slimming)

- ~67 root artifacts moved to
  `reports/agent-runs/2026-07-auto-review-pipeline-v1/history/raw/`
- Compatibility symlinks at former root paths
- Snapshots: `history/snapshots/status-before-slimming.json`,
  `70-handoff-before-slimming.md`

### 1.2 Pass B (2026-07-12 post-accept process archive)

Moved **20** closed process artifacts to `history/raw/` + symlinks
(`broken=0`). Root real files reduced to design authority + state:

**Archived (examples):** T4 prompts/verdicts, `20-implementation.md`,
`17`/`18` bookkeeper notes, `61`–`65` gate logs, short `30-review-1.md` /
`50-review-2.md` stubs, `task-serial-v1-slimming-*.prompt.md`.

**Kept as real files on stage root:**

```text
status.json
70-handoff.md
60-test-output.txt
00-task.md
10-design.md
11-adr.md
12-serial-v1-slimming-development-breakdown-codex.md
15-p8-wall-clock-withdrawal-design-amendment.md
16-serial-v1-slimming-design.md
19-model-routing-convergence-operator-decision.md
54-p8-wall-clock-withdrawal-operator-decision.md
```

Snapshots for pass B:

- `history/snapshots/status-before-post-accept-history-archive.json`
- `history/snapshots/70-handoff-before-post-accept-history-archive.md`

Index: `history/README.md` (updated for two passes).

**Non-goals of pass B:** no rewrite of historical evidence bytes; no runner
code change; no bulk rewrite of other stages; no push.

---

## 2. Remaining scatter / cold-storage candidates (not yet moved)

| Location | Issue | Proposed disposition |
|---|---|---|
| `reports/follow-ups/2026-07-auto-review-pipeline-design-note.md` | Pre-contract design | Mark historical in index; keep path or later move under design-review stage dir |
| `reports/follow-ups/2026-07-auto-review-pipeline-review-fable5.md` | Pre-contract review; stale models/wall-clock | Same; **do not rewrite body** |
| `reports/agent-runs/2026-07-auto-review-pipeline-design-review/` | Decision freeze evidence; no `status.json` | Index as historical-reference in `STAGE_INDEX.md` |
| `docs/phase2-direction-draft.md` | Draft sitting under `docs/` | Move to agent-runs direction evidence or archive path; or banner “duplicate of …” |
| `docs/private-account-v1-direction-draft.md` | Same | Same |
| `docs/planning/adapter-watchdog-runner.md` | Planning note, not DECISIONS | Leave or link from ROADMAP; not Harness runtime truth |
| Other product stage roots | Many prompts/raws | **Do not** bulk-archive; only clean when a stage explicitly slims |

---

## 3. Semantic conflict inventory

### P0 — Active navigation lies about current world state

| ID | Where | Says | Truth | Proposed fix |
|---|---|---|---|---|
| C1 | `reports/follow-ups/README.md` §auto-review | Design frozen; not yet delivery; next = open v1 stage | Stage **accepted + merged to main** | Rewrite section: **delivered**; link `docs/auto-review-pipeline.md` + stage path; design-note/review = historical |
| C2 | `reports/agent-runs/STAGE_INDEX.md` | Index date 2026-07-10; missing auto-review-v1 and funding-history; rollback narrative only | v1 accepted+merged; funding-history accepted+merged | Add rows; refresh date/note; optional design-review historical-reference row |
| C3 | `docs/README.md` | Harness docs list omits auto-review contract | `docs/auto-review-pipeline.md` exists on main | Add bullet under canonical paths |

### P1 — Follow-ups / process docs contradict registry (mislead agents)

| ID | Where | Says | Truth | Proposed fix |
|---|---|---|---|---|
| C4 | `reports/follow-ups/2026-07-harness-mechanical-gates.md` §4 | `codex.default_model` still `gpt-5.5` | Registry `gpt-5.6-sol` | **Do not rewrite fact body.** Banner or README: **§4 resolved by model-routing convergence**; keep §1–3, §5 open |
| C5 | `…/2026-07-auto-review-pipeline-review-fable5.md` | `grok-build`; wall-clock dual caps | `grok-4.5`; no session wall-clock | Index mark **superseded**; body stays verbatim |
| C6 | Stage `10-design.md` / `11-adr.md` | Residual `grok-build`, historical tip/parallel table rows | Serial-v1 + registry supersede | Keep root for lineage; **top banner: superseded by 16-serial + 19-model-routing + docs/auto-review-pipeline** |

### P2 — Wording residue in accepted stage status

| ID | Where | Says | Truth | Proposed fix |
|---|---|---|---|---|
| C7 | `status.json` → `auto_review_pipeline.reason` | cannot self-host **unaccepted** pipeline | Stage accepted; still correctly non-self-hosting | Optional one-line: bootstrap stage must not self-host even after acceptance |

### P3 — Known non-conflicts / leave alone

| ID | Item | Why leave |
|---|---|---|
| L1 | Historical stage prompts/verdicts with `gpt-5.5` / `grok-build` | Evidence of past dispatch; not registry truth |
| L2 | `docs/harness-design.md` “wall-clock time” in parallel mode prose | Means human wall-clock savings, not auto session budget |
| L3 | Claude `opus4.8` short name vs local CLI | Operator kept intentionally; separate optional fix stage |
| L4 | Pass B history paths via symlink | Intended; path identity preserved |

---

## 4. Proposed fix plan (for operator / other-model review)

### Principles

1. **Evidence stays verbatim** — no bulk edit of historical raw reviews/prompts.
2. **Navigation first** — fix indexes that agents read at startup.
3. **Banners over rewrites** — superseded design shells get headers, not rewrites.
4. **No runtime change** in this hygiene pass unless operator expands scope.
5. **Separate stage** if skill-injection / identity mechanical gates (mechanical-gates §1–3, §5) become implementation work.

### Priority sequence

| Step | Action | Files | Risk |
|---|---|---|---|
| **S1** | Fix follow-ups index for delivered auto-review + register this hygiene packet | `reports/follow-ups/README.md` | Low |
| **S2** | Update stage index | `reports/agent-runs/STAGE_INDEX.md` | Low |
| **S3** | Document map | `docs/README.md` | Low |
| **S4** | Supersede banners on stage `10-design.md` / `11-adr.md` | stage root only | Low |
| **S5** | Mechanical-gates §4 resolved note (header only) | follow-up file header or README only | Low |
| **S6** | Optional: relocate docs root `*-direction-draft.md` | `docs/` → agent-runs or archive | Med (path break if linked) |
| **S7** | Optional: `status.json` reason string | stage status | Low |
| **S8** | Out of band: Claude fallback ID if operator wants executable alias | registry + model-adapters | Med (policy) |
| **S9** | Out of band: mechanical gates §1–3, §5 as new small stage | new stage | Implementation |

### Explicitly out of this hygiene plan

- Auto parallel dual-dev / goal-orchestrator design
- Changing auto serial-only contract
- Rewriting `40-operator-decision-table.md` freeze evidence
- Pushing `main` to origin

---

## 5. Suggested review checklist for the other model

Please answer:

1. Is the authority order in §0 correct for this repo?
2. Is pass B history scope safe (any file that must remain a **real** root file)?
3. Any P0/P1 conflict missing?
4. Agree S1–S5 as the first commit-sized batch?
5. Should C7 (status reason string) be in S1–S5 or skipped?
6. Any objection to leaving L3 (`opus4.8`) unchanged until operator decides?

Output format preference for the reviewing model:

- ACCEPT plan as-is
- ACCEPT with amendments (list)
- REWORK (list blocking issues)

---

## 6. Related paths (quick index)

```text
docs/auto-review-pipeline.md
docs/model-adapters.md
docs/harness-design.md
docs/parallel-development-mode.md
agents/registry.yaml
workflows/templates/stage-delivery.yaml
AGENTS.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json
reports/agent-runs/2026-07-auto-review-pipeline-v1/70-handoff.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/history/README.md
reports/agent-runs/STAGE_INDEX.md
reports/follow-ups/README.md
reports/follow-ups/2026-07-harness-mechanical-gates.md
reports/follow-ups/2026-07-auto-review-pipeline-design-note.md
reports/follow-ups/2026-07-auto-review-pipeline-review-fable5.md
```

---

## 7. Footer

```text
本地北京时间: 2026-07-12 15:17:08 CST
下一步模型: 操作者指定的对照评审模型（Codex / Claude / 其他）
下一步任务: 对照本包 §3–§5 出 ACCEPT / ACCEPT-with-amendments / REWORK；
           操作者批准后再执行 S1–S5（或修订后的批次）
```

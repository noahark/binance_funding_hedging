# Fix Report — Review-2 REWORK（2026-07-docs-truth-sync-v1）

Fix author：`claude_glm`（本 stage 原实现者；允许当 fix 作者。Codex/Kimi 为审稿人，
不可自修）。
针对 Review-2 verdict `REWORK`，审核指纹
`c72987dc5cfe288e8df887cd14a965a48e93e3f3:bfd3106dd5a636868a66c56adfc7fdf94c00e57b251878633c9edc9d7265d812`
（原始 review + final verdict JSON：`50-review-2.md`）。
本次仅改文档文本/living-doc 时态，**未改任何代码、schema、契约行为、端点或产品范围**；
未 commit（bookkeeper 负责 stage 提交、重算指纹、重跑 validator、重新派发评审）。

## 发现→修复映射表

| # | 发现（severity） | 文件 : 行（before → after） | before 语义（缺陷） | after 语义（修复） |
|---|---|---|---|---|
| **F1** | funding-history `empty` 被描述为上游成功（P1） | `docs/api/public-market-contract.md:280-283` → `:280-294` + 披露 `:296-300` | 称 `funding_history` 为空“仅发生在上游抓取成功但窗口无记录” | 改为纯 PublishedState 投影：`empty` 仅表示已发布 row 无记录，**不证明**本次或先前上游成功；显式披露 `funding-history.schema.json:34` 描述更窄，延后 schema-alignment |
| **F2** | symbol-snapshot `partial`/`timeout` 语义窄于代码（P1） | `docs/api/public-market-contract.md:313-319` → `:324-340` + 披露 `:347-353` | `partial` 限定为 borrow 回退；`timeout` 限定为共享 deadline | 按代码三态：`ok`=无 warning 发布；`partial`=发布但 ≥1 source warning（premium/history/borrow/max_borrowable）；`timeout`=无新发布、投影 last-good（deadline/worker 未运行/assembly-validation 失败）；`warnings` 为细分原因；披露 `symbol-snapshot.schema.json:39` 描述过时 |
| **F3** | bookticker living-docs 仍含未来/当前态措辞（P1） | `status.json:518,653`；`70-handoff.md:63-66,129`；`20-implementation.md:79-82` → 全部改为过去时/历史快照 | 已 accepted/merged/pushed 的 stage 仍把视觉验收、证据提交、终审写成待办 | 转为完成过去时，保留全部 SHA/指纹/Session ID/verdict/用户授权/原始证据事实 |

> F3 明确覆盖 Review-1 的 P1-9 裁决（Review-1 曾判 bookticker `status.json` 不动；
> Review-2 终审判定其仍含未来/待办措辞需历史化）。以 Review-2 终审为准，本次允许并
> 要求编辑 bookticker `status.json`（仅改时态/时间锚定，不动任何审计事实）。

## F1 — funding-history empty 语义

**Before（缺陷，contract 旧 `:280-283`）：**

> `funding_history`: … Empty only when the upstream fetch **succeeded** but the
> window has no settled records (`history_status: empty`).

**代码真值（反驳 before）：**
- `backend/services/snapshot_service.py:259-302`（`get_funding_history`）/ `:304-315`
  （`_project_funding_history`）：live 路径是 **纯投影** —— `state = self._published_state`，
  `history = row.get("funding_history", [])`，`history_status = "available" if history else "empty"`。
  **零上游抓取、零缓存写。**
- `backend/tests/test_funding_history_endpoint.py:238-250`
  （`test_non_default_symbol_projects_when_present`）：未预热的 BBB（rate 未过阈值、未被
  selector 预热）仍以已发布 eligible row 投影返回 `200` / `history_status == "empty"`，且
  无任何按需抓取。即 `empty` 并不证明上游成功。

**After（contract 现 `:280-294`）：** `funding_history` 字段说明改为“**纯投影**”——端点对本
请求不发上游抓取，直接读已发布 state 的 `funding_history` 列表，列表为空即 `empty`；`empty`
**does not prove** 本次或先前上游成功（未预热的 symbol 或先前 history 抓取失败也会投影为
`empty`，无按需重试）。新增披露（contract 现 `:296-300`）：`funding-history.schema.json:34`
仍把空归因于“成功的上游抓取”，窄于现行纯投影语义；本 stage docs-only 不改 schema，对齐留给
后续受控 contract-amendment（列为已知 residual risk）。

## F2 — symbol-snapshot ok/partial/timeout 语义

**Before（缺陷，contract 旧 `:313-318`）：**

> - `ok`: all selected sources refreshed.
> - `partial`: public/history refreshed but borrow fell back to last-good …
> - `timeout`: the command reached its shared deadline before publication …

**代码真值（反驳 before）：**
- `snapshot_service.py:1527`：`cmd.refresh_status = "partial" if warnings else "ok"` ——
  任何非空 `warnings` 即 `partial`，不只 borrow。
- `:1424 / :1437 / :1455 / :1461`：warning token 分别为
  `premium_refresh_failed:<symbol>`、`funding_history_unavailable:<symbol>`、
  `borrow_rate_refresh_failed:<asset>`、`max_borrowable_refresh_failed:<asset>`。
- `:347-359`（`get_symbol_snapshot` 收尾）：`cmd is None`（worker 未运行）→ `timeout` +
  `worker_not_running`；deadline 未结算 → `timeout` + `refresh_deadline_exceeded`。
- `:1400-1402 / :1408-1411 / :1465-1470 / :1497-1502 / :1514-1519 / :1529-1533 / :1535-1538`：
  冷启动 base 未就绪、symbol 不 eligible、I/O 后超 deadline、assemble/validation 超 deadline
  或失败 → 一律 `timeout`，**不发布新版本**，投影 last-good。
- `backend/tests/test_symbol_snapshot_endpoint.py:252-270`：
  `test_history_failure_yields_partial_status` 断言 history 失败 → `partial` +
  `funding_history_unavailable`；`test_premium_failure_yields_partial_status` 断言 premium
  失败 → `partial` + `premium_refresh_failed`。

**After（contract 现 `:324-340`）：** 三态按代码重写——
- `ok`：一次新发布完成且无 per-source `warnings`。
- `partial`：新发布完成但存在 ≥1 source warning（列出现行 4 个真实 token）；并明确 **不意味着**
  public/history 数据新鲜，须读 `warnings` 看真正失败的源。
- `timeout`：**未产生新发布**，row 投影自先前已发布（last-good）state；触发含共享 deadline
  （`refresh_deadline_exceeded`）、worker 未运行（`worker_not_running`）、assembly/validation
  失败（`assemble_failed`、`validation_crossed_deadline` 等）；明确 **不证明** 仅 deadline 超时。
- `warnings`：source-specific reason 串数组——`partial` 的权威细分、非纯 deadline 的 `timeout`
  的诊断。

新增披露（contract 现 `:347-353`）：`symbol-snapshot.schema.json:39` 仍把 `partial` 限定为
borrow 回退、`timeout` 限定为共享 deadline，窄于现行行为；docs-only 不改 schema，对齐延后。

## F3 — bookticker living-docs 时态归一

四处全部由当前/未来态 → 完成过去时或带时间锚定的历史快照，**仅改时态/时间锚定**，所有
SHA / 指纹 / Session ID / verdict / 用户授权 / 原始证据数字（80 PASS、375 passed、merge
`9abad62f`、push `a3d541d`、review_2 ACCEPT 等）一字未动。

| 文件 : 行 | before（节选） | after（节选） |
|---|---|---|
| `status.json:518`（`independent_verification.note`） | …local evidence commit and the single fresh Codex final review **remain**. | …The local evidence commit and the single fresh Codex final review (review-2) **have since completed**: review-2 verdict is ACCEPT and the stage was merged and pushed (see `review_2` and `merge_result`). |
| `status.json:653`（`review_2` 路由 note） | Kimi **performs** … the user visually **accepts** it, then one fresh Codex final-review invocation **inspects** … Existing review-1 **remains** … no second new review-1 invocation **is requested**. …**cannot serve** as reviewer. | Kimi **performed** … the user visually **accepted** it, and one fresh Codex final-review invocation then **inspected** … (review-2, verdict ACCEPT). Existing review-1 **remained** … no second new review-1 invocation **was requested**. …**did not serve** as reviewer. |
| `70-handoff.md:63-66` | the user **performs** visual acceptance. …supersedes…invocation **is requested**; prior review-1 **remains**… Session **is forbidden** as reviewer. | the user **performed** visual acceptance (recorded as `accepted_merged_and_pushed`). …**superseded**…invocation **was requested and completed** `ACCEPT`; prior review-1 **remained**… Session **was forbidden** as reviewer. |
| `70-handoff.md:131`（原 :129，因上文 +1 行） | `20-implementation-task-b.md` (**must be amended by fix 2**) | `20-implementation-task-b.md` (**amended by fix 2**) |
| `20-implementation.md:79-83` | Task C **receives** no additional review-1… invocation **reviews** the updated full range… Session **cannot serve** as that reviewer. | Task C **received** no additional review-1… invocation **reviewed** the updated full range and Task C delta (review-2, verdict ACCEPT). Session **did not serve** as that reviewer. |

## 命令输出（调度包要求的 7 条，逐字）

```
########## CMD #1 ##########
$ python3 -m json.tool reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json >/dev/null
exit=0   (status.json 仍为合法 JSON)

########## CMD #2 ##########
$ rg -n 'pure projection|does not prove|premium_refresh_failed|funding_history_unavailable|worker_not_running|warnings' docs/api/public-market-contract.md
215:  "warnings": []
282:    … This payload is a **pure projection of the
287:    **does not prove** that this request (or any prior fetch) succeeded. …
298:  … narrower than the as-built pure projection above. …
326:    - `ok`: a fresh publication completed with no per-source `warnings`.
328:      `warnings` entry — e.g. `premium_refresh_failed:<symbol>`,
329:      `funding_history_unavailable:<symbol>`, `borrow_rate_refresh_failed:<asset>`,
331:      … read `warnings` for the actual failed
336:      (`worker_not_running`), or an assembly/validation failure that must not
339:  - `warnings`: array of source-specific reason strings — …
604:### `coverage` / warnings (§1.5)
621:`skipped` = borrowability-unprobed). When `skipped > 0`, a top-level `warnings`
exit=0   (命中：pure projection / does not prove / premium_refresh_failed /
        funding_history_unavailable / worker_not_running / warnings 均在；符合预期)

########## CMD #3 ##########
$ if rg -n 'Empty only when the upstream fetch succeeded|public/history refreshed but borrow fell back|the command reached its shared deadline before publication' docs/api/public-market-contract.md; then exit 1; fi
exit=0   (无任何违规短语残留在 contract)

########## CMD #4 ##########
$ if rg -n 'local evidence commit and the single fresh Codex final review remain|After deterministic verification, the user performs visual acceptance|fresh Codex final-review invocation is requested|must be amended by fix 2|Kimi performs one bounded frontend-only UI adjustment|the user visually accepts it|invocation inspects' \
    reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md \
    reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md \
    reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json; then exit 1; fi
exit=0   (7 个未来/待办短语全部从 bookticker living-docs 消除)

########## CMD #5 ##########
$ PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_funding_history.py backend/tests/test_funding_history_endpoint.py backend/tests/test_symbol_snapshot_endpoint.py -q -p no:cacheprovider
.......................................................................  [100%]
71 passed in 2.35s
exit=0   (71 项针对性测试全过；本 stage 未改代码，测试用作行为真值回归基线)

########## CMD #6 ##########
$ git diff --check
exit=0   (无尾空白 / 冲突标记)

########## CMD #7 ##########
$ git diff --name-only
docs/api/public-market-contract.md
reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md
reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md
reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json
exit-ok   (4 个改动路径全部 ∈ Allowed 交付集：contract + 3 个 bookticker living-doc；
          另含本新建报告 40-fix-report.md。无 backend/ / frontend/ / schemas/ / scripts/
          及 STAGE_INDEX / ROADMAP / harness-manifest / harness-design / AGENTS.md /
          stage-branch-mode / docs/README / docs/architecture/ADR 出现)
```

## 改动文件边界结果

| 路径 | 是否 Allowed | F# |
|---|---|---|
| `docs/api/public-market-contract.md` | ✅ Allowed（交付） | F1 + F2 |
| `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json` | ✅ Allowed（F3 覆盖 Review-1 P1-9，允许并要求） | F3 |
| `reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md` | ✅ Allowed | F3 |
| `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md` | ✅ Allowed | F3 |
| `reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md` | ✅ Allowed（新建报告） | 报告本身 |

Forbidden 集（`backend/`、`frontend/`、`schemas/`、`scripts/`、`STAGE_INDEX.md`、`ROADMAP.md`、
`harness-manifest.yaml`、`docs/harness-design.md`、`AGENTS.md`、`docs/planning/stage-branch-mode.md`、
`docs/README`、`docs/architecture/ADR/`、active-stage `status.json`/`70-handoff.md`/`60-test-output.txt`
即本 stage 的 bookkeeper-only 文件）—— **0 改动**。本 stage 的 active checkpoint/证据文件
（`reports/agent-runs/2026-07-docs-truth-sync-v1/status.json`、`70-handoff.md`、`60-test-output.txt`）
未触碰，留给 bookkeeper。

## 遗留 / 残余风险（与 Review-2 一致）

- `funding-history.schema.json:34` 与 `symbol-snapshot.schema.json:39` 的 prose description
  已与现行服务器/测试行为发生预存漂移；本 stage 禁改 schema，需另建有原始事实证据的
  contract-amendment stage 对齐（已在 contract 两处显式披露为 deferred 项）。
- `reports/agent-runs/ACTIVE.json` 的 phase 仍为 intake，而 status/handoff 为 review_2；属
  bookkeeper 在记录本次 REWORK 的强制 checkpoint 中同步的指针（不在实现者 Allowed 集）。
- 本次会话独立运行的 7 条命令全过（含 71 项针对性测试）；bookkeeper 提交后须基于新提交和新
  指纹重跑 `scripts/validate-stage.py 2026-07-docs-truth-sync-v1 --phase pre-review` 并保存证据，
  再重新派发 review-1/review-2。

---

当前 Session ID: unavailable (Claude Code 不向模型暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md
本地北京时间: 2026-07-16 19:32:15 CST
下一步模型: bookkeeper（独立 reconcile diff、更新 60-test-output.txt 与 active status.json/
            70-handoff.md/ACTIVE.json、提交于 stage 分支、重算标准指纹、重跑并保存
            pre-review validator、重新派发 review-1/review-2）
下一步任务: 以本修复为基线重入评审门

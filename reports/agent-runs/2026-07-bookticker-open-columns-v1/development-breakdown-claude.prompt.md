# Claude Development Breakdown And Design Review Prompt

你是本 stage 的 development breakdown author（开发细化作者）兼实现前设计审查者。用户要求你审查 Codex 写的初始文档，并为 `MEDIUM` stage 产出必需的开发细化。

## Identity And Mode

- Provider: Anthropic Claude
- Preferred model: `claude-fable-5`
- Fallback: 仅在 Fable5 明确 quota exhausted 后使用 `opus4.8`
- Skill: `task_planner`
- Mode: documentation write only
- 你属于 prior design involvement，不是本轮 formal review-1/review-2。

## Repository And Stage

- Repository: `/Users/ark/Desktop/ai code/funding_hedging`
- Stage: `2026-07-bookticker-open-columns-v1`
- Required branch: `stage/2026-07-bookticker-open-columns-v1`
- Base SHA: `fea9fdc3ecce7675b34b01fe0a4b9de08811f939`

先确认当前 branch。若不是 required branch，停止并报告 blocker；不得切 branch、rebase、merge 或 commit。

## Required Raw Read Set

必须亲自读取，不得只依赖本 prompt 的摘要：

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml` 的 `stage-design` 与 `development-breakdown` 段
3. `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-intake.md`
4. `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md`
5. `reports/agent-runs/2026-07-bookticker-open-columns-v1/10-design.md`
6. `reports/agent-runs/2026-07-bookticker-open-columns-v1/11-adr.md`
7. `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json`
8. `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/evidence-index.md`
9. `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/capture.md`
10. `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/normalized/bookticker-summary.json`
11. relevant raw BTC spot/futures responses and batch-probe response headers/bodies named by the evidence index
12. `docs/product/PRD.md`
13. `docs/architecture/ARCHITECTURE.md`
14. `docs/development/DEVELOPMENT_GUIDE.md`
15. `schemas/api/public-market/snapshot.schema.json`
16. `schemas/api/public-market/symbol-snapshot.schema.json`
17. `backend/adapters/binance_public.py`
18. `backend/domain/snapshot.py`
19. `backend/services/snapshot_service.py`
20. relevant tests under `backend/tests/`
21. `frontend/index.html`
22. `frontend/self-check.js`
23. `frontend/fixture/public-market-snapshot.json`

## Frozen User Requirements

不得自行改变：

- 正向开单：上合约买一、下现货卖一；`(futures bid - spot ask) / spot ask * 100`。
- 反向开单：上现货买一、下合约卖一；`(spot bid - futures ask) / futures ask * 100`。
- 两个方向正值都表示有利价差，显示两位小数。
- “净收益”改为“日净收益”；删除默认表“提示标记”列。
- 借贷状态在上、资产标签在下合并显示；底层字段不合并。
- bookTicker 是 always-on public Group A，默认 60 秒；两端完整成功才本地原子提交；两个刷新周期后不作为可用开单价。
- 后端 `Decimal` 计算，前端只展示；bStock 用 resolved `row.spot.symbol`。
- 不新增交易副作用、WebSocket、per-symbol HTTP、新环境变量或 scheduler abstraction。

如你认为冻结要求本身存在 P0/P1 矛盾，只能记录 finding 并要求 human decision，不能静默改写。

## Review Questions

先审查：

1. `book_ticker_pair` 的 atomic commit、failure retry 和 stale projection 是否能嵌入现有 worker，而不破坏 source 独立 timestamp？
2. `opening_quotes` 可选 row property、内部 required 字段和 percentage-point unit 是否足够明确且 backward compatible？
3. 120 秒 cutoff、cold unavailable、fresh/incomplete/stale/unavailable 状态是否有缺口？
4. selected-symbol click 与 legacy stub 是否会意外发额外 HTTP 或丢失 canonical row quote？
5. bStock/metal/no-spot/zero-price/invalid payload/negative-zero/round-half-up 是否有确定性 oracle？
6. 前端合并后 12 列、借贷额度迁移、旧后端降级是否完整？
7. 允许/禁止文件是否足以实现且没有越权？
8. 正式 review identity 路由是否符合 implementer provider isolation？

## Only Allowed Write

只允许创建或编辑：

`reports/agent-runs/2026-07-bookticker-open-columns-v1/12-development-breakdown.md`

禁止修改 `status.json`、`70-handoff.md`、`ACTIVE.json`、初始设计文档、API samples、产品代码、tests、schema、canonical docs、git state。不要 commit、push、merge、rebase 或执行模型 dispatch。

## Required Breakdown Content

`12-development-breakdown.md` 必须包含：

1. Breakdown author identity、provider、model、skill。
2. `## Design Review Verdict`：`READY` 或 `REVISE`。
3. `## Design Review Findings`：按 `P0/P1/P2` 列出；每项给出文件/行或原始证据、风险、可执行修订。没有 finding 时写 None。
4. 两个顺序任务：
   - Task A backend/API/schema/domain/tests owner `claude_glm`
   - Task B frontend/UI/fixture/self-check owner `kimi`，依赖 committed/frozen Task A contract
5. 每个任务的 exact allowed files、forbidden files、inputs、outputs、acceptance criteria、do-not-touch boundaries。
6. 完整 wire contract，逐字段确认 `opening_quotes` units/nullability/status/required/compatibility。
7. Cache lifecycle truth table：cold、fresh、one-side failure、retry、age `<120`、age `>=120`、recovery。
8. Formula vectors和 rounding/error vectors；明确 `incomplete` 行的两个方向独立计算，一个方向缺 operand 不得连带清空另一方向。
9. Exact test commands 与预期 evidence path `60-test-output.txt`。
10. Formal review focus 与 task-specific cross-review routing。
11. Grok advisory review 不替代 formal gate 的说明。
12. Prior involvement note：Claude provider 已参与 breakdown；未来 review-2 fallback 需 strong-reviewer disclosure override。
13. 文末 footer，时间必须通过本地 `date` 获取，并包含 provider-native session id（提供方原生会话 ID）与原始输出/写入路径。若当前 CLI/session 未暴露 ID，必须写 `unavailable (<reason>)`，不得猜测或编造。

不要开始实现。完成文件后，在最终响应中列出：verdict、findings 数量、写入文件、git status，并以以下导航 footer 结束：

```text
当前 Session ID: <provider-native id | unavailable (reason)>
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/12-development-breakdown.md
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: <model-or-human>
下一步任务: <specific next task>
```

Session ID 只是导航证据，不代表其他 provider 可以直接读取本会话；不得输出 token、cookie、credential、expanded environment 或任何认证材料。

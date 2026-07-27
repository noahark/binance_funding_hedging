# Review-2 R2 — Hedge Open Live Hardening v1

结论：`ACCEPT`（接受）。第 1 轮的 P2（S5 离线记录传输没有实际应用已加载交易对的数量过滤条件）已在固定范围内完整闭环。其修复复用既有的有效 MARKET 数量过滤语义，没有将离线校验器接入真实下单路径，也未改动冻结状态或 entries（条目）词表。

## 固定范围与核验

- 审查范围固定为 `6c5b17002cab189d752177b447ff576356998f58..c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8`。
- 独立重算二进制 diff 哈希为 `aad2351a429714f07e759304400087c2f0a5ccc33a0111b9532153bf86c50b23`，与固定指纹一致：`c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8:aad2351a429714f07e759304400087c2f0a5ccc33a0111b9532153bf86c50b23`。
- `scripts/validate-stage.py 2026-07-hedge-open-live-hardening-v1 --phase pre-review` 在本次审查前通过。
- 本会话实际复跑：返工相关后端测试 `176 passed`，`node frontend/self-check.js` 全部通过；阶段留存的合并态全量证据为 backend `983 passed`、frontend `122 PASS`、protocol `72 passed`。

## 第 1 轮 P2 闭环

接受修复报告对根因的补充：原记录快照本来只有 `spot_step` / `perp_step`，没有 min/max；因此单纯把参数接到校验调用并不能满足 S5。

`backend/hedge_open_tasks/domain.py:755-769` 现在只调用既有的 `effective_market_step` 与 `_qty_bounds`，以既有的 MARKET_LOT_SIZE → LOT_SIZE、逐约束回退语义计算两腿有效 step/min/max，并将四个 min/max 字段以 additive（新增兼容字段）方式放入 `snapshot_record`。`backend/hedge_open_tasks/executor.py:305-310,367-389` 仅消费该快照的每腿值，再传入 `validate_order_params`；没有复制第二套过滤选择规则。

新增行为测试不是校验器直调：`test_hedge_wire_constraints.py:252-312` 实际驱动 `RecordTransportExecutor`，断言非整步长/低于最小量和超过最大量均得到 `offline_constraint`、两腿零成交且不模拟 fill；也断言合法网格数量仍成功，并以 spot=0.001、perp=0.01 证明两腿过滤条件独立应用。S5 的 clientOrderId、字符集和科学计数法防线仍在；真实发送路径未导入或调用 `wire_constraints`，符合 ADR-H4。

## 其余范围复核

- S1：35 字符 `hg{attempt_id}s|p` 仍是 record/live 共用的唯一推导点；实盘验收已经证明它通过 Binance 格式校验。`fmt_decimal` 仍输出固定小数形式。
- S2：前端仅为 `running && worker_active === false` 放行启动，dry-run 的 `null` 与 live `tick()` no-op 均未改变。
- S3：确认字面量、CAS（比较并交换）、同事务审计、默认关闭与前端双向单次确认保持不变。
- S4：三态 symbol probe（交易对探测）只将成功读取后的明确 `False` 作为拦截条件；`None` 保持 fail-open（读取失败不误拒）。
- 冻结契约：任务状态、entries 的 `overall_result` / `next_action` 词表和既有 API 语义未改；新 snapshot 字段为持久 JSON 内的 additive 数据，不需迁移。
- F-1 至 F-4 仍是上一阶段遗留或外部 Binance 响应契约漂移，不属于本阶段五项；同意其另开 stage 的处理。

## 前端 Review-1 授权例外

我已逐字阅读 `21-user-authorized-frontend-fingerprint-exception.md`，并核对：

- `git diff 319d831..c91d2da -- frontend/` 为空，前端文件在该两点间字节未变；
- 例外文件已在阶段分支提交，SHA-256 为 `674ec82a18bca74e12c1a56f7e105503c0c94a92f885545e5928f7a1893349fb`，与 `status.json.authorized_exceptions[0]` 一致；
- 例外只豁免 `task:frontend` 的 `review_fingerprint_trails_status`，后端的新代码仍须独立复审，review-2 也已重跑。

该例外的机械依据成立。不过按 Harness（流程框架）规则，发布前仍必须由用户逐字确认该证据确实记录了用户本人决定；本审查无法替代这一人类确认。

当前 Session ID: unavailable（本 Codex 运行环境未暴露 provider-native Session ID）
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/51-review-2-r2.md
本地北京时间: 2026-07-28 07:01:21 CST
下一步模型: bookkeeper
下一步任务: 归档终审结果，运行 pre-accept 验证；随后阶段停在 stage_accepted_waiting_user，等待用户逐字确认前端例外并作出是否验收/合并的决定

{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-live-hardening-v1",
  "role": "final_reviewer",
  "model": "GPT-5 Codex",
  "verdict": "ACCEPT",
  "diff_fingerprint": "c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8:aad2351a429714f07e759304400087c2f0a5ccc33a0111b9532153bf86c50b23",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml (review-2)",
    "docs/parallel-development-mode.md (R7 / Review-2)",
    "schemas/review-verdict.schema.json",
    "docs/product/PRD.md",
    "docs/architecture/ARCHITECTURE.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/{00-intake.md,00-task.md,10-design.md,11-adr.md,12-development-breakdown.md,13-implementation-backend.dispatch.md,14-implementation-frontend.dispatch.md,16-r4-diff-reconciliation.md,17-pre-review-validation.txt,18-live-acceptance-findings.md,19-r4-diff-reconciliation-rework1.md,20-implementation-backend.md,20-implementation-frontend.md,21-user-authorized-frontend-fingerprint-exception.md,30-review-1-backend.md,30-review-1-frontend.md,40-fix-review-2-s5.md,50-review-2.md,60-fix-review-2-s5.dispatch.md,60-test-output.txt,status.json}",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/{11-adr.md,16-replacement-development-breakdown.md}",
    "git diff --binary 6c5b17002cab189d752177b447ff576356998f58..c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8",
    "backend/hedge_open_tasks/{domain.py,executor.py,wire_constraints.py,service.py,store.py}",
    "backend/services/hedge_preflight_provider.py",
    "backend/tests/{test_hedge_wire_constraints.py,test_hedge_executor.py,test_live_hedge_executor.py,test_hedge_service.py,test_hedge_api.py,test_hedge_store.py,test_hedge_preflight_provider.py}",
    "frontend/{index.html,self-check.js}"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "F-1 至 F-4（成交响应字段漂移、margin 正数错误码分类、错误消息未持久化、51169 根因未定）属于独立后续 stage，不由本次 ACCEPT 解决。",
    "发布前用户必须逐字核对并确认 21-user-authorized-frontend-fingerprint-exception.md 中记录的 class-1 例外确为本人决定；该例外会在任何指纹变化后自动失效。",
    "本轮未修的 P3 项仍为 api-samples 反斜杠措辞、confirm 负例容器覆盖、409 标题未冻结和弹窗正文 includes 断言；它们不影响本阶段的功能/安全验收。"
  ],
  "next_action": "stage_accepted_waiting_user"
}

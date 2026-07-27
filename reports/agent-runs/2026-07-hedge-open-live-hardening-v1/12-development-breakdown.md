# Development Breakdown — Hedge Open Live Hardening v1

作者角色：development-breakdown author（Claude Fable 5, anthropic）。设计-only。
输入：本 stage `10-design.md` / `11-adr.md`（决策权威）、`00-intake.md` /
`00-task.md`、`status.json`、`docs/parallel-development-mode.md`（v0.5 语义）、
`AGENTS.md`、上一 stage 冻结契约。所有文件边界与契约以 `10-design.md` §3/§4 为
准，此处只做任务化拆分，不重述设计理由。

## 1. 串行 vs 并行：建议并行（两任务）

**建议：启用 `docs/parallel-development-mode.md`，两个实现任务并行。**

- 任务边界两两不相交：后端任务只碰 `backend/**` + api-samples 新页；前端任务只
  碰 `frontend/index.html` + `frontend/self-check.js`。满足并行模式适用条件 1。
- 任务间接口契约可在设计期冻结且已冻结（`10-design.md` §4 的 5 条契约面：
  settings doc + version、start-gate POST 全形、task doc 两字段枚举、
  `missing_leg` 错误形、entries 投影零改动）。满足适用条件 2。前端全部用
  self-check mock 消费冻结契约，不依赖后端先落地。
- 默认路由与 intake 预置一致：后端 `claude_glm`（glm-5.2[1m]），前端 `kimi`
  （kimi-k3）。两 provider 互不相同，review-1 交叉池（GLM↔Kimi）成立。
- 依赖顺序：**无阻塞依赖**。唯一的顺序敏感点是共享契约本身，已由本拆分与
  10-design 冻结；两任务可同日并行开工。
- 若并行条件在执行中被破坏（任一实现者发现必须越界改对侧文件或契约字段），按
  R3 升级 bookkeeper，禁止本地修复——这是并行模式的既有硬规则。

嵌入预审（embedded review）：**不启用**（v0.5 默认 opt-out；本 stage 为 MEDIUM、
两侧 diff 都小、reviewer 池已恢复，正式 review-1 足够）。因此
`parallel_mode.embedded_review.enabled=false`，R10 checklist 不含 embedded 相关
字段。

bookkeeper 需把 `status.json.parallel_mode.enabled` 置 true 并联动
`r10_dispatch_tail_required=true`、`r4_diff_reconciliation_required=true`；进入
实现前必须过 `scripts/validate-stage.py 2026-07-hedge-open-live-hardening-v1
--phase dispatch-ready`。

## 2. 任务 A — 后端（owner: claude_glm / glm-5.2[1m]）

**范围**：S1、S3 后端、S4b、S5，及 settings doc 的 version 暴露。

**允许文件**（= 10-design §3 后端允许清单，逐字）：
`backend/hedge_open_tasks/{executor.py,service.py,store.py,domain.py}`（domain
仅错误码/文案最小增量）、`backend/hedge_open_tasks/wire_constraints.py`（新建）、
`backend/services/hedge_preflight_provider.py`、`backend/app/server.py`（仅路由
接线）、`backend/tests/test_hedge_*.py`、
`backend/tests/test_live_hedge_executor.py`、
`reports/api-samples/2026-07-hedge-open-live-hardening-v1/client-order-id-cap.md`
（新建）、原始报告
`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-backend.md`。

**禁止文件**：`frontend/**`、`backend/services/hedge_open_live_client.py`、
`backend/services/live_hedge_executor.py`、`backend/services/binance_signing.py`、
`backend/hedge_open_tasks/scheduler.py`、`backend/config.py`、
`backend/borrow_tasks/**`、`docs/**`、既有 `reports/**`、`status.json`、
`70-handoff.md`、env/凭据文件、任何网络配置。若认为必须触碰禁区（尤其
`live_hedge_executor.py`）→ R3 升级，停手等 bookkeeper。

**交付要求**（细节全部见 10-design 对应节，不得自行再设计）：

- A-1 (S1)：`_client_order_ids` → `hg{attempt_id}s|p`（ADR-H1）；核对全部
  `hgo-` 测试字面量（≈18 处：断言推导格式的更新，任意实参的不动）。
- A-2 (S5)：`wire_constraints.py` 校验器 + `RecordTransportExecutor` 接入 +
  `_FakeClient` 严格化 + pre-fix S1 离线失败回归 + api-samples 记录页 +
  `str(Decimal)` 科学计数法探测测试（10-design §8 未验证点，必须以测试证实或
  证伪；证实则在 params-build seam 收敛到 `fmt_decimal`）。
- A-3 (S3)：`set_start_gate_cas`（CAS + 同事务 audit 行）、`put_start_gate`
  service 方法、路由 + `_is_hedge_open_path`、`settings_to_doc` 加 `version`、
  默认关闭断言。错误码全形照 10-design §2.3，一字不改。
- A-4 (S4b)：provider 三态探针（含可辨认 -1121 的公共读取变体）+ `create_task`
  拦截 + `missing_leg` 中文文案照 10-design §2.4b 冻结文案。

**确定性自测命令**（R10 收尾段照抄）：

```text
.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check
```

**证据与报告**：原始报告 `20-implementation-backend.md`（含测试输出摘录与全量
计数）；不 commit、不碰 `status.json`；自测 PASS → 报告并停止等 bookkeeper；
FAIL → 仅 scope 内修复重跑；涉契约/共享面 → R3 升级。

**风险点/评审关注**：id 推导唯一来源不被复制第二份；CAS SQL 的
rowcount 判定与 audit 同事务原子性；`confirm` 字面量校验不可被 truthy 值绕过
（如 `1`、`"true"` 必须 400）；探针三态不得把 None 误判为 False；校验器
regex 与 api-samples 记录页一致；record transport 违规路径不得吞掉
`constraint_violations` 证据；纯度守卫（`test_hedge_purity.py`）对新模块生效。

## 3. 任务 B — 前端（owner: kimi / kimi-k3）

**范围**：S2、S3 前端（对称确认弹窗 + 控件）、S4a、S4b 错误展示确认。

**允许文件**：`frontend/index.html`、`frontend/self-check.js`、原始报告
`reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-frontend.md`。
**禁止**：其余一切。后端字段缺失/含义存疑 → 升级 bookkeeper，绝不发明字段。

**交付要求**：

- B-1 (S2)：`index.html:3685` 按钮条件照 10-design §2.2 的表达式逐字实现；
  dry-run（`worker_active===null`）行为必须逐字不变。
- B-2 (S3)：执行徽标行旁单一控件（label 随闸门状态）；两个方向各恰好一次确认弹
  窗（双按钮变体，无手输确认词）；弹窗中文文案照 10-design §2.3 冻结文案逐字；
  POST 携带 `state.hedgeSettings.version`；409 → 刷新 + 「设置已被其他会话修
  改，已刷新，请重试」；取消 → 零请求。
- B-3 (S4a)：任务卡新增
  `执行线程：<运行中|未运行|—> · 上次退出原因：<中文|—>` 行；退出原因中文映射
  照 10-design §2.4a 冻结映射；缺失字段按 `hedgeText` 约定降级「—」。
- B-4 (S4b)：确认建卡错误路径能展示 `missing_leg` 的中文 `detail`（复用既有
  hedgeApi 错误通道，如已天然支持则以 self-check 用例钉住）。
- B-5：`frontend/self-check.js` 扩展覆盖 10-design §6 前端各项（S2 四象限、S3
  弹窗/label/409、S4a 三态与映射、S4b detail 展示）；不允许 static-text-only。

**确定性自测命令**（R10 收尾段照抄）：

```text
node frontend/self-check.js
.venv/bin/python -m pytest backend/tests -q
git diff --check
```

**证据与报告**：原始报告 `20-implementation-frontend.md`；同样的停止纪律。

**风险点/评审关注**：S2 条件严格用 `=== false`（`null`/`undefined` 必须落
disabled 侧）；弹窗确认前不得发出任何请求；version 过期路径不得死循环弹窗；
文案与设计逐字一致（UI 中文优先）；不得顺手改动无关卡片渲染。

## 4. R10 checklist 输入项（bookkeeper 落 `status.json.r10_checklists`）

```json
{
  "backend": {
    "task_prompt_path": "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/13-implementation-backend.dispatch.md",
    "self_tests_command": "见 §2 自测命令块（两条 pytest 全列 + self-check + 协议套件 + git diff --check）",
    "artifact_paths": [
      "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-backend.md",
      "reports/api-samples/2026-07-hedge-open-live-hardening-v1/client-order-id-cap.md"
    ],
    "stop_instruction": "自测 PASS 报告并停止等 bookkeeper；FAIL 仅 scope 内修复；契约/共享面问题 R3 升级",
    "next_dispatch_executor": "human_operator"
  },
  "frontend": {
    "task_prompt_path": "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/14-implementation-frontend.dispatch.md",
    "self_tests_command": "node frontend/self-check.js && .venv/bin/python -m pytest backend/tests -q && git diff --check",
    "artifact_paths": [
      "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-frontend.md"
    ],
    "stop_instruction": "同上",
    "next_dispatch_executor": "human_operator"
  }
}
```

（嵌入预审未启用，`embedded_review_prompt_path` / `diff_patch_*` /
`cross_review_*` 字段按 v0.4 规则不填。）

## 5. 需要 human operator 执行的 dispatch / review packet 清单

以下 packet 由 bookkeeper 准备（本文件不写实现提示词本身），human operator 在
独立新会话逐个执行；全部 dispatch 必须以 `[HARNESS-EXECUTOR-CONTRACT v1]` 前言
开头，`dispatch_protocol: human-operator/v1`：

1. `13-implementation-backend.dispatch.md` — 任务 A，写权限 Claude-GLM 会话。
2. `14-implementation-frontend.dispatch.md` — 任务 B，写权限 Kimi 会话。
   （1、2 可并行执行。）
3. bookkeeper：R4 diff 对账 → 证据 commit → 指纹 →
   `validate-stage --phase pre-review`。
4. `30-review-1-backend.dispatch.md` — 后端 review-1，**kimi**（交叉池：GLM 实
   现 → Kimi 评审），只读新会话，审完整 `<base>..<head>` 范围。
5. `30-review-1-frontend.dispatch.md` — 前端 review-1，**claude_glm**（Kimi 实
   现 → GLM 评审），只读新会话。
   （4、5 可并行执行。）
6. `50-review-2.dispatch.md` — 最终门，**codex**（本 stage 设计/拆分走 Claude
   provider 正是为让 Codex 无先期涉入、无需 strong-reviewer 披露，见
   `status.json.designer.routing_reason`），只读新会话。
7. 各 REWORK 分支按 verdict 内 `fix_start_prompt` 由 bookkeeper 出 fix
   dispatch，仍由 human operator 执行；`max_rework=3`。

## 6. 实现顺序与集成测试计划

任务 A 内部顺序（串行，单会话）：S1 推导 → S5 校验器+严格假件+回归（此时 S1
测试面即刻受益）→ S3 后端 → S4b。任务 B 内部顺序：S2 → S4a → S3 UI →
B-4/B-5。A、B 之间并行。

集成（bookkeeper，两任务停止后）：R4 对账两份 diff 与允许清单逐文件核对 →
本地复跑全部 §2/§3 自测命令（全量 `backend/tests` + `node frontend/self-check.js`
+ 协议套件 + `git diff --check`）→ 证据 commit + 指纹 → pre-review 验证 →
按 §5 进入评审。集成断言重点：前端消费的三个契约面（settings.version、
start-gate POST、missing_leg）与后端实际 wire 形逐字段一致——这是上轮
「3 次跨 seam 漂移」教训的直接检查点。

## 7. 硬性测试与安全约束（两任务与所有评审共同遵守）

- 不发任何真实 POST；不访问凭据（读/打印/记录均禁止）；不发任何 Binance 私有
  请求；不启动 HTTP 服务；网络一律注入假件。
- 不开启 `APP_HEDGE_EXECUTOR=live`、不触碰 durable Start 闸门数据、不创建真实
  任务。intake 状态（服务已停、`start_gate=0`）在整个实现/评审期保持不变。
- 实现者不 commit、不改 `status.json`/`70-handoff.md`；单一写者是 bookkeeper。
- 任何冻结契约疑似需要改动 → 列「需用户批准的契约修订建议」，禁止直接写进
  实现。

当前 Session ID: 9c443dac-2917-4801-bd93-94db85d27de0
Session ID 来源: runtime_env (harness scratchpad path; navigation only)
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/12-development-breakdown.md
本地北京时间: 2026-07-27 17:59:40 CST
下一步模型: bookkeeper
下一步任务: 归档三份原始设计产物，不要实现代码

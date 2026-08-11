# Task Handoff: reverse-position-drift-implement

## Source Report (author-only; immutable after task end)
- task_id: `reverse-position-drift-implement`
- role: Implementer
- target model: Codex（provider: openai）
- stage_id: `2026-08-11-reverse-position-drift-v1`
- created_at: 2026-08-11 17:35:30 CST
- base_sha: `7194876e61c037d238d0e3d621a094d7dd3a6e43`
- delivery_sha: pending

### 任务背景与结论

按已通过跨 provider 计划评审的 `10-plan.md` 完成 reverse position drift 最小修复。统一账户快照现在把原始 `crossMarginLocked` 原样投影为 additive/optional `cross_margin_locked`；reverse 按解析后的账户资产聚合所有 active local reverse 行的 `spot_qty`，只消费一次账户 borrowed/free/locked，并以 `A=max(B-F-L,0)` 和既有 1% Decimal 容差回填组内统一 verdict。利息、普通现货余额及 `totalWalletBalance` 不参与 reverse 公式；坏值、账户不可读、缺资产行、closed/no_task 均 fail-closed 为 `drift=false`。forward 原有严格 held 比较及 positions API wire 字段集保持不变。

本任务只改变展示/校验含义，没有启动服务、调用本地或实盘 API，也没有触碰订单、借币、还款、划转、预检、闸门、凭据、部署、运行数据或服务控制。

### 实际修改范围

- `backend/domain/snapshot.py`
- `backend/hedge_open_tasks/domain.py`
- `schemas/api/public-market/snapshot.schema.json`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/test_positions_merge.py`
- `backend/tests/test_hedge_api.py`
- `docs/api/public-market-contract.md`
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-implement.handoff.md`（本交接，create-only）
- `reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json`（仅 `current_task.state: dispatched -> reported`）

未完成事项：无。实现者未做独立评审，也未填写实际 delivery SHA；Bookkeeper 须从单次交付提交解析实际 SHA。

### 命令与结果

```text
python3 -m pytest backend/tests/test_private_account_v1.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py -k 'cross_margin_locked or reverse_drift or forward_drift_ignores_reverse'
-> 39 passed, 185 deselected

python3 -m pytest backend/tests/test_private_account_v1.py backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py
-> 224 passed in 24.43s

git diff --check
-> exit 0

git diff --name-only（创建本交接与状态变更前）
-> 恰为 dispatch 指定的 7 个 delivery 文件
```

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-implement.handoff.md`、`reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json`、`reports/agent-runs/2026-08-11-reverse-position-drift-v1/reverse-position-drift-implement.dispatch.md`
- 执行：Bookkeeper（codex）核验同文件源区块 SHA-256、单次交付提交、实际 changed paths、224 项测试与唯一状态变更，解析实际 delivery SHA 并准备独立 review-1 packet
- 关卡：Bookkeeper 验证通过后，由 Human 启动独立 review-1；本实现回执不构成评审接受
- 不能假设的事实：`delivery_sha: pending` 必须由 Bookkeeper 从实际提交解析；`drift=false` 不是对账证明；本实现没有授权、执行或验证任何实盘、合并、push、部署、服务控制或账户动作

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: reverse-position-drift-implement
执行结果: completed（完成）
结果摘要: 完成 7 文件最小修复：统一账户投影新增 locked；reverse 按资产聚合本地数量并用 A=max(B-F-L,0) 与 1% Decimal 容差判 drift，坏值 fail-closed；forward 与 positions wire 不变。指定 224 项测试及 diff 检查通过。
产物: [backend/domain/snapshot.py; backend/hedge_open_tasks/domain.py; schemas/api/public-market/snapshot.schema.json; backend/tests/test_private_account_v1.py; backend/tests/test_positions_merge.py; backend/tests/test_hedge_api.py; docs/api/public-market-contract.md; reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-implement.handoff.md; reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json]
检查结果: [7 个 delivery 文件范围精确: pass; locked 投影、optional schema 与旧样本兼容: pass; reverse 资产级聚合及 A=max(B-F-L,0): pass; 缺失/空/文本/NaN/Infinity/负值 fail-closed: pass; 利息排除与 1% 严格边界: pass; forward 回归及 positions wire 键集不变: pass; 指定三文件全量 224 项: pass; git diff --check: pass]
阻塞项: [none]
本地北京时间: 2026-08-11 17:35:30 CST
下一步模型: codex（Bookkeeper，核验并封存本交接）
下一步任务: 读取：reports/agent-runs/2026-08-11-reverse-position-drift-v1/evidence/reverse-position-drift-implement.handoff.md、reports/agent-runs/2026-08-11-reverse-position-drift-v1/status.json、reports/agent-runs/2026-08-11-reverse-position-drift-v1/reverse-position-drift-implement.dispatch.md；执行：Bookkeeper 核验源区块、单次提交、实际范围与测试，解析 delivery SHA 并准备独立 review-1 packet；关卡：Bookkeeper 验证通过后由 Human 启动独立 review-1
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

## Errata (append-only)

（无。）

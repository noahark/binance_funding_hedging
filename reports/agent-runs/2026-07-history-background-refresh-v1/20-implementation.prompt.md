# Implementation Dispatch Prompt

你是本阶段唯一实现者 `claude_glm`（provider identity：`zhipu_glm`，模型
`glm-5.2`）。这是一个 backend-dominant bounded task（后端占主导的有界任务），前端
只有轻量集成。使用 `senior_developer`（高级开发者）skill，严格遵守
`agents/developer-discipline.md`；不要调用其他模型或 subagent（子代理）。

## 1. 启动读取顺序

先完整读取且以原始文件为准：

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml`
3. `reports/agent-runs/2026-07-history-background-refresh-v1/status.json`
4. `reports/agent-runs/2026-07-history-background-refresh-v1/70-handoff.md`
5. `reports/agent-runs/2026-07-history-background-refresh-v1/00-task.md`
6. `reports/agent-runs/2026-07-history-background-refresh-v1/10-design.md`
7. `reports/agent-runs/2026-07-history-background-refresh-v1/11-adr.md`
8. `reports/agent-runs/2026-07-history-background-refresh-v1/12-development-breakdown.md`
9. `agents/developer-discipline.md`
10. `agents/skills/senior-developer.md`

当前分支必须是 `stage/2026-07-history-background-refresh-v1`。工作区已有未提交的设计/
bookkeeper（台账员）文件，均属于用户和 bookkeeper；必须保留，不得覆盖、删除或整理。

## 2. 权限与身份边界

- 你是唯一 implementation author（实现作者），不是 bookkeeper、reviewer（审查者）或
  fix author（修复作者）。
- 不得修改 `status.json`、`70-handoff.md`、intake、task、design、ADR、breakdown、
  workflow、registry、Harness、canonical docs（正式项目文档）。
- 不得提交、推送、合并、rebase（变基）、启动其它模型，或宣称阶段通过审查。
- 不得写入凭证、签名、请求头、完整 signed query（签名查询）、余额、持仓、估值或展开
  的 `claude-glm` 环境。
- 只做只读 Binance GET；严禁下单、借币、还币、划转、平仓或任何交易执行。

## 3. 实现范围

严格按 `12-development-breakdown.md` 的 T1–T9 顺序和全部验收实现。允许修改：

- `backend/services/snapshot_service.py`
- `backend/services/private_client.py`
- `backend/adapters/binance_public.py`
- `backend/app/server.py`
- `backend/config.py`
- `backend/domain/snapshot.py`（仅确有必要的窄纯函数 helper／辅助函数）
- `schemas/api/public-market/symbol-snapshot.schema.json`
- `frontend/index.html`
- `backend/tests/`
- `frontend/self-check.js`
- `reports/api-samples/2026-07-history-background-refresh-v1/`
- `reports/agent-runs/2026-07-history-background-refresh-v1/20-implementation.md`
- `reports/agent-runs/2026-07-history-background-refresh-v1/60-test-output.txt`（只追加本次
  完整命令及原始结果，不覆盖已有 bookkeeper 记录）

其它文件一律禁止修改。若必须越界，停止并在 `20-implementation.md` 写明 BLOCKED，
不得自行扩大范围。

## 4. 四个不得误读的实现约束

1. `GET /api/public-market/snapshot` 在 live（在线）任何开关状态下都是零上游纯读。
   kill switch（紧急开关）关闭时：有 `PublishedState` 返回 last-good（最近成功状态），
   无状态返回 503；只有 `offline=True` 的冻结 fixture（夹具）测试分支允许同步 build。
2. `RefreshSymbolCommand.deadline_monotonic` 是共享 publication gate（发布闸门）。
   请求等待与 worker 提交均使用同一截止值；实现中到期判断写死为
   `time.monotonic() >= deadline_monotonic`。已过期命令若尚未开始，不启动新的上游 I/O；
   已开始的 I/O 可结束，但不得提交 history/domain cache（历史/领域缓存），不得替换
   `PublishedState`。传输层 `PrivateClient._cache` 被已发出的请求更新可以保留。
3. 点击实际利率使用 `fetch_cost_leg_chain([asset], force=True)`：只移除单资产 E2、E2b
   与 maxBorrowable 三个精确键；多资产 scheduled batch（定时批次）键及 classic、VIP、
   account info、crossMarginData 均保留。禁止 `_cache.clear()`。
4. v1 前端必须实现行点击后 1 秒不可点击和同 symbol in-flight（执行中）忽略再次激活；
   完成后的刻意再次点击仍创建新命令。不得实现 backend cooldown（后端冷却窗口）、
   watched set（关注集合）、interest TTL（关注时效）或优先级状态。

## 5. 最小改动与验证

- 复用现有组装、缓存、白名单、HMAC 单出口和前端状态结构；不要做无关重构。
- 新契约必须有 schema（模式）与 contract tests（契约测试）。
- raw public samples（原始公开样本）必须来自真实公开端点并原样保存。signed evidence
  （签名证据）只能保存脱敏 audit（审计）字段；没有操作者明确授权的安全 live 环境时，
  不得擅自发起签名实网调用，须在报告中明确证据待补，不能用合成 fixture 冒充事实证据。
- 不启动长期运行服务器，不使用后台 shell 进程。

至少运行并完整记录：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
node frontend/self-check.js
git diff --check
```

还要运行与新增 schema 相对应的 `jsonschema` 测试。不要运行 review gate（审查门）或
创建 fingerprint（差异指纹），这些由 bookkeeper 在提交后执行。

## 6. 交付报告

创建 `20-implementation.md`，包含：

- 实现者 provider/model/session ID 与 `senior_developer` skill；
- T1–T9 完成映射；
- 实际修改文件；
- 关键并发/失败语义说明；
- 所有测试命令、结果及 `60-test-output.txt` 路径；
- 公开样本与脱敏签名证据路径，或明确的未满足证据；
- 未完成项、风险、BLOCKED 与否；
- 明确声明未提交、未推送、未合并、未调用其它模型。

面向用户的报告如出现英文术语，紧随中文翻译或采用“英文（中文）”形式。报告末尾使用
本机 `date` 取得时间，并添加：

```text
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: Codex bookkeeper
下一步任务: 验收实现、测试与证据，创建本地 evidence commit 并准备 review-1
```

完成后回复只汇报：修改文件、实现摘要、测试结果、证据状态、BLOCKED、session ID。

本地北京时间: 2026-07-13 00:47:36 CST
下一步模型: claude_glm / GLM-5.2
下一步任务: 使用 senior_developer 实现本阶段 bounded task 并产出原始测试证据

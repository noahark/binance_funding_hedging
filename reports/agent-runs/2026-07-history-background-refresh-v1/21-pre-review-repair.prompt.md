# Pre-Review Repair Dispatch Prompt

你是本阶段原 implementation author（实现作者）`claude_glm` / GLM-5.2，继续在同一
阶段分支修复 bookkeeper（台账员）在正式 review-1（第一轮审查）前发现的两个 timeout
（超时）契约缺口。使用 `minimal_change_engineer`（最小改动工程师）skill；这不是正式
review 返回的 REWORK（返工），不改变 `rework_count`。不要调用其他模型或 subagent
（子代理）。

先读取：`AGENTS.md`、`workflows/templates/stage-delivery.yaml`、本 stage 的
`status.json`、`70-handoff.md`、`00-task.md`、`10-design.md`、`11-adr.md`、
`12-development-breakdown.md`、`20-implementation.md`，以及
`agents/skills/minimal-change-engineer.md`。保留当前工作区的所有既有改动。

## 发现（原始证据）

`backend/services/snapshot_service.py`：

1. `get_symbol_snapshot()` 在 `cmd.done.wait(timeout=remaining)` 到期、但 worker 尚未
   完成时，`cmd.refresh_status` 仍为 `None`，代码回退为 `"ok"` 并返回旧行。这把一次
   已超时的刷新错误标成成功，违反 `00-task.md` / breakdown §5、§9、§10：超时必须返回
   `refresh_status:"timeout"` 与上次已发布行。
2. `_handle_refresh_command()` 只在全部 premium/history/private I/O 之后检查 deadline。
   一条在队列中已过期的命令仍会启动新上游 I/O，违反 breakdown 的冻结规则：若命令在
   worker 开始处理前已经到期，不启动任何新的上游 I/O；已开始的 I/O 可以结束，但到期后
   不得提交 domain cache（领域缓存）或发布 `PublishedState`。
3. deadline 还必须在 `_assemble()` 完成后、写 history cache / `_last_private_inputs` /
   替换 `PublishedState` 之前再次检查；避免组装耗时跨过 deadline 后提交。
4. 若 live worker 未运行（例如 kill switch（紧急开关）关闭）但已有发布状态，
   symbol-snapshot 不得伪报 `ok`。返回该行的 `200` + `refresh_status:"timeout"` +
   可诊断 warning（警告），且零上游调用；无已发布状态仍是 `503`。
5. `fetchSymbolSnapshot` 当前把任何 HTTP 200 都当成功合并，未消费
   `refresh_status` / `warnings`。这违反 breakdown §9 的用户可见语义：timeout 必须明确
   呈现“刷新超时，显示上次数据”；partial（部分刷新）也必须显示非阻塞提示及后端
   warnings（警告），同时仍只补丁目标行/抽屉，绝不全表重渲染。
6. `_handle_refresh_command()` 的 `base_raw is None` 冷路径不得调用整宇宙
   `fetch_raw()`。即使这是正常 bootstrap（启动）后不应发生的防御路径，也必须直接完成
   `timeout` + warning，零上游 I/O、零发布；点击路径没有任何 `fetch_raw()` 例外。

## 允许修改（严格最小）

- `backend/services/snapshot_service.py`
- `backend/tests/test_symbol_snapshot_endpoint.py`
- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-history-background-refresh-v1/20-implementation.md`
- `reports/agent-runs/2026-07-history-background-refresh-v1/60-test-output.txt`（只追加）

不得修改任何其它文件；不得提交、推送、合并、rebase（变基）、更改 `status.json` /
`70-handoff.md`，或启动 model dispatch（模型分发）。

## 精确修复与测试要求

- deadline 判断统一为 `time.monotonic() >= cmd.deadline_monotonic`。
- worker 开始处理时若已过期：直接完成 command，`timeout`，不调用
  `fetch_raw`、`fetch_premium_index_for`、`fetch_funding_rate`、任何 PrivateClient
  fetcher（私有客户端读取器），不写 domain cache，不发布。
- I/O 在 deadline 内开始但完成或组装跨过 deadline：允许已启动 I/O 结束；但在任何
  domain-cache commit / `_publish()` 前再次检查，超时则保留旧状态。
- endpoint 等待到 deadline 但 command 未完成时：仅在请求局部构造 timeout 响应；请求
  线程不得修改 command、缓存或发布状态。若 command 在 deadline 前已完成且已发布，保留
  正常 `ok`/`partial` 语义。
- 增加确定性测试覆盖：(a) 已排队过期命令零上游 I/O；(b) endpoint 等待超时返回 timeout
  而非 ok；(c) 组装跨 deadline 不提交/不发布；(d) live kill-switch-disabled 有 last-good
  行返回 timeout 且零上游；(e) `base_raw is None` 时点击零 `fetch_raw()`；(f) 前端
  timeout/partial 文案显示、保留目标行/抽屉补丁、无 `renderTable()`。测试不得真实等待
  30 秒或访问网络。

运行并追加完整原始输出：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
python3 -m pytest backend/tests/test_symbol_snapshot_endpoint.py -v
node frontend/self-check.js
git diff --check
```

在 `20-implementation.md` 新增“Pre-review repair（审查前修复）”章节，逐项映射这六个
发现、文件修改、测试结果和剩余风险。继续保持所有英文术语带中文翻译。报告末尾通过本机
`date` 添加 Harness footer（页脚）；完成后只汇报修改文件、测试、BLOCKED、session ID。

本地北京时间: 2026-07-13 08:03:52 CST
下一步模型: claude_glm / GLM-5.2
下一步任务: 最小修复 symbol-snapshot 的超时响应、过期命令 I/O 与 deadline 提交闸门

# Task Handoff: 08-integration-p2

## Source Report (author-only; immutable after task end)

- task_id: 08-integration-p2
- role: Implementer
- target_model: grok-4.6 / provider xai
- stage_id: 2026-08-14-smooth-close-orders-v1
- created_at: 2026-08-14 23:07:20 CST
- base_sha: 6f6c7297c895a3bf56ae5e0abc7a542de891dff7
- delivery_sha: pending
- status_revision: 11
- parent_head_at_start: 28e2393b8d7aaf4cb60680481705a1502ae23d8b

### Scope

按 dispatch 做平滑平仓 V1 前后端串联（P2）。契约以 05 handoff「冻结的 API 契约」为准，07 仅补强 `smooth_close_start_failed` 的 409 detail 取当次落库中文。未启动服务、未创建任务、未下单。

### What changed

**`frontend/index.html`**

1. 平滑平仓按钮不再是样式预览：确认后 `POST /api/hedge-open-tasks`，body 为冻结键 `coin / direction / mode=smooth / single_amount / target_n / task_type=close / slippage_threshold_pct`。立即平仓仍走 `mode=immediate` 且不带阈值，既有 self-check 调用零回归。
2. 确认弹框回显币种、方向、单次量、次数、阈值，并写明比较当前方向**平仓率**。
3. 去掉五张静态样式卡与「样式预览、不执行」标注。
4. C13：smooth close 点启动期间该卡暂停/启动/删除/成交1次置灰，启动文案「备料中…」；失败走既有 `hedgeApi` detail（07 已保证不回显 awaiting_manual_start）。
5. C17：平仓卡只读后端 `close_preparation_state` 映射为 已备料 / 未备料 / 每轮实时校验，不另存、不推断。
6. 运行中平滑**平仓**卡盘口块：标题为正向/反向平仓率；forward close 高亮「现货买一+合约卖一」即 `reverse_spread_pct` 列；reverse close 高亮「合约买一+现货卖一」即 `forward_spread_pct` 列。开单卡两列标题与价格组零 diff。状态查询复用既有 `GET /api/hedge-open-tasks?status=all` 与 `GET /api/hedge-open-logs?task_id=`（2 秒刷新），成交1次仍带 `gate_seq`。

**`backend/app/server.py`**

P1 已把 smooth close 接到同一套 REST（create / list / start / fill-once / logs / positions / close-gate），本次只在路由表注明冻结键与「盘口读模型走 logs，没有浏览器 WebSocket」。未新增路径，未改 handler 行为。

### Checks

```text
node frontend/self-check.js
```

退出码 0，「全部自检通过」。立即平仓 POST 仍为 `mode=immediate`；平滑开单真卡、借币/还款/划转、闸门与同源白名单均绿。

### Not done

- 未启动应用、未做页面端到端、未实盘。
- 未改后端 service/store/domain（不在 Allowed Files）。
- 未新增浏览器 WebSocket（与既有开单卡同一读链）。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/08-integration-p2.handoff.md`；`reports/agent-runs/2026-08-14-smooth-close-orders-v1/status.json`；`frontend/index.html`；`backend/app/server.py`；`reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/05-backend-p1.handoff.md`
- 执行：Bookkeeper 核验本 handoff 与当前 stage 分支交付提交，解析 `delivery_sha`
- 关卡：核验通过后由 Human 本地启动应用做页面端到端；未授权模型启动服务或下单
- 不能假设的事实：服务当前未启动；建卡成功仍是 paused + 待手动启动；点启动才会同步备料并可能划转；Start gate 常开时备料成功会进入 running

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: 08-integration-p2
执行结果: completed（完成）
结果摘要: 平滑平仓已接真实建卡/列表/启动/成交1次：确认后 POST 冻结 body；启动中该卡全灰并显示备料中；平仓卡读备料状态并把盘口列改成平仓率且标出判定列。立即平仓与开单卡未改。server.py 沿用既有 REST，无新浏览器 WebSocket。
产物: [frontend/index.html, backend/app/server.py, reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/08-integration-p2.handoff.md]
检查结果: [pass 身份 revision 分支匹配；pass 只改 Allowed Files；pass node frontend/self-check.js 全部自检通过；pass 立即平仓 POST 仍为 immediate 且不带阈值；pass 开单卡盘口文案零 diff；pass 平滑平仓确认走独立 mode=smooth + slippage_threshold_pct；pass 无新定时器与浏览器 WebSocket；pass 未启动服务、未下单]
阻塞项: [none]
本地北京时间: 2026-08-14 23:07:20 CST
下一步模型: gemini-3.1-pro（Bookkeeper，核验本次实现回执）
下一步任务: 读取：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/08-integration-p2.handoff.md；reports/agent-runs/2026-08-14-smooth-close-orders-v1/status.json；frontend/index.html；backend/app/server.py；reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/05-backend-p1.handoff.md；执行：核验 handoff 与交付提交并解析 delivery_sha；关卡：核验通过后由 Human 本地启动应用做页面端到端，未授权模型启动服务或下单。
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
- source_sha256: bf95c909da58cd5e85ba384799c3604136b147dac611ad6b8bc3c03434908e4b
- 核验时间: 2026-08-14 23:45:00 CST
- 核对 status revision: 11
- 依据: Human 已确认通过前端验收；节点代码运行绿灯；已生成 P2 交付提交。交付 SHA 解析为 f95577fc892776e5fe268399a4331d86497c97f9。
- 后续状态: 验证通过（verified）。按 Human 决定，后续直接推进 Review-1（由 Bookkeeper 兼任执行完毕），并准备派发 Review-2。

## Errata (append-only)

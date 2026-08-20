# Task Handoff: 90-phase3-review1-kimi

## Source Report (author-only; immutable after task end)

- task_id: `90-phase3-review1-kimi`
- role: `Reviewer`
- target model: `kimi`（Moonshot，工作窗 `kimi-review`）
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- created_at: 2026-08-20 13:36:01 CST
- base_sha: `06c00c07e0181c596292c2f163890456abed3d8d`
- delivery_sha: `3bc6acaec6e3bd2b837239d7a925007a29729db6`

### 任务背景与只读评审范围

阶段三终章由 `claude_glm`（zhipu_glm）实现；本次 Review-1 由 `kimi`（moonshot）跨 provider 执行，审查交付区间 `06c00c07..3bc6acae` 内的代码与测试：

- `backend/hedge_open_tasks/store.py`：
  - `aggregate_positions` 只汇总 `task_type=open` 且有成交腿的冻结四列，经 `FF.usdt_fee_total` 折 U；本币均价用 `_leg_vwap`（quote/base），严禁 `avg_price`；不全时 `trading_fee_usdt`/`fee_bnb_qty` 为 None、`trading_fee_incomplete=True`。
  - `insert_close_log` 未显式传三个手续费键时，按周期 open+close 全部有成交腿现算聚合；完整写真实值 + `incomplete=0`，任一不全写 NULL/NULL/1；显式传参原样落库。
- `backend/hedge_open_tasks/fee_fetcher.py`：
  - 新增 `usdt_fee_total`、`_leg_vwap`、`resolve_leg_identity`、`build_realtime_transport`；
  - UM 零宽/倒置窗修正：由「返回 None 判失败」改为「向前扩 10 分钟回退窗」（inline 合约腿 dispatched==last_query 的必要处理）。
- `backend/hedge_open_tasks/service.py`：
  - `_realtime_fee_transport` / `_bnb_price_reader` 懒装配，D4 冻价复用预检 provider 现价读取器；
  - `_fetch_leg_fees_after_terminal` 终态提交后回写钩子；
  - 三处接线：inline 主终态、inline 暂停类终态、drain 查询终态。
- 测试：`test_hedge_store.py` +9、`test_hedge_service.py` +5、`test_backfill_leg_fees.py` 零宽窗修正；`test_hedge_purity.py` 仍绿。

### 评审结论

`ACCEPT`。

未发现阻塞交付的 in-range 缺陷。交付代码与 10-design §3/§4.1/§5/§7.1/§8 口径一致；验收命令全部通过（pytest 232 passed、`node frontend/self-check.js` 全绿）；评审过程中未执行任何带网络外发的 live 操作。

### 命令与结果

1. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py backend/tests/test_hedge_service.py backend/tests/test_backfill_leg_fees.py backend/tests/test_hedge_purity.py -q`
   → **232 passed**。
2. `node frontend/self-check.js`
   → **全部自检通过**。
3. `git diff --stat 06c00c07..3bc6acae`
   → 8 files changed, 882 insertions(+), 27 deletions(-)。

### 观察与建议（非阻塞）

- `_bnb_price_reader` 与 `_realtime_fee_transport` 采用私有属性 duck-typing（`getattr(self._preflight, "_read_est_price", None)` / `getattr(self._executor, "_client", None)`），已在 handoff 中说明为「不扩 Allowed Files 的务实选择」。后续若组合根接线，可再开一个小任务改为显式接口。
- `_cycle_trading_fee_total` 用 `CAST(cumulative_base_qty AS REAL) > 0` 过滤，仅作 >0 判断、不用于金额计算；量级极大的极端值可能有 SQLite REAL 精度风险，但对本业务数量级可忽略。
- 阶段二 Review-2 O1（脚本 dry-run 被拒绝时提示）仍记录为收口轮顺手修，未在本任务文件内。

### 未完成事项

- 阶段三 Review-2（§8：HIGH_RISK 双评审）。
- live 回补执行、服务重启加载新代码、UM orderId 支持性确认均须 Human 单独授权。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/90-phase3-review1-kimi.handoff.md`
  2. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
- 执行：Bookkeeper 核验 Review-1 结论与验收命令输出，按 §8 准备 Review-2（默认 `opus5`）。
- 关卡：Human 启动 Review-2 窗口；合并/重启/live 回补另需单独授权。
- 不能假设的事实：实时写入在生产进程未生效（须重启）；UM orderId 分支未经验证；D4 现价与回补 K 线收盘价是两条不同冻价路径。

## Human Brief / Console Receipt Source

[TASK_RESULT v2]
任务 ID: 90-phase3-review1-kimi
执行结果: completed（完成）
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
结果摘要: 阶段三终章 Review-1 通过。读聚合真实折 U（open 有成交腿、quote/base 均价、不全 None/None/True）、关仓现算 open+close 全腿（完整 0 / 不全 1）、三处终态 commit-first 实时写入、D4 现价复用预检链、UM 零宽窗向前扩 10 分钟均符合 10-design；验收 pytest 232 passed，self-check 全绿。
产物: [reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/90-phase3-review1-kimi.handoff.md]
检查结果: [验收1 持仓真实聚合（只 open 腿、quote/base 均价、不全返回 None/None/True）pass；验收2 关仓聚合开+平全腿（完整 0 / 不全 1 / 显式键优先）pass；验收3 三处终态 commit-first、失败不改终态留痕、每腿至多 1 次 GET pass；验收4 UM 零宽/倒置窗向前扩 10 分钟 pass；验收5 五文件 pytest 232 passed pass；验收6 node frontend/self-check.js 全部自检通过 pass]
阻塞项: [none]
本地北京时间: 2026-08-20 13:36:01 CST
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/90-phase3-review1-kimi.handoff.md；执行：核验 Review-1 结论与验收输出并按 §8 准备 Review-2；关卡：Human 启动 Review-2 窗口
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- **verification_time**: 2026-08-20 13:39:10 CST
- **source_sha256**: `4c9ed7c45093836daef1342e512cfd9aac7eef7e4b8844a769f6c645b27022c5`
- **status_revision**: 21 -> 22
- **verdict**: `ACCEPT`
- **rework_count**: 0
- **isolation_check**: pass（implementer=`zhipu_glm`, reviewer=`moonshot`, cross-provider isolation satisfied）
- **verification_status**: `verified`

## Errata (append-only)

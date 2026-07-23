[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。禁止调用/启动/转派任何其他模型会话或 adapter 命令；
禁止编造未执行的命令结果；只依据本 prompt 列出的 raw artifact 路径与你实际读取
的文件。

# Fix — hedge-be fix-2（stage 2026-07-hedge-open-live-v1）

你是 hedge-be 的 fix 实现者 Claude-GLM（zhipu_glm）。review-2（Codex 终审）
verdict=REWORK，一项 P1 必修。原始评审证据：
`reports/agent-runs/2026-07-hedge-open-live-v1/50-review-2.md`。固定审查范围 base
`6639b0025682f406f9a726104ef8d3b9e6f8fadd` head
`bd01eb52e9ec5464bb9f026f5ce666bc883db441`。

## 必修发现 F-007（P1）— leg_exposure 跨 FE/BE 契约漂移（安全关键）
冻结契约 `12-development-breakdown.md` §3.2：`leg_exposure: null|{leg,qty,price,ts}`。
- **后端违约**：`backend/hedge_open_tasks/domain.py:556-563` `build_leg_exposure`
  emit `{filled_leg, spot, perp, ts}`，而非 §3.2；`backend/tests/test_hedge_api.py:
  290-300` 用 `doc['leg_exposure']['filled_leg']` 把这个错误 shape 钉成断言。
- **前端已符合 §3.2**：`frontend/index.html:3600` 读 `task.leg_exposure.leg/qty/
  price`；`frontend/self-check.js:3664-3665` mock 也用 §3.2。
- **影响（安全关键）**：单腿敞口（尤其现货单成、合约失败）时，前端 `leg` 读不到
  （后端给的是 `filled_leg`）→ 走合约分支、显示 undefined 数量/价格，向操作员**错误
  展示已成交腿与数量**。任务暂停是对的，但人工决策所需的告警信息严重错误。这是本
  stage 第三次跨 seam 漂移（R4-001、F-001 之后），根因同类：各自 mock 掩盖。

## 必修（后端对齐 §3.2，前端不动）
1. `build_leg_exposure` emit **§3.2 shape `{leg,qty,price,ts}`**：现货单成 →
   `leg="spot"`、`qty`/`price` 取现货腿实际成交量/价；合约单成 → `leg="perp"`、
   `qty`/`price` 取合约腿。**完整的双腿原始细节仍按 ADR-4 保留在 fills/logs**（不要
   丢证据，只是 Task.leg_exposure 这个面向操作员的字段收敛到 §3.2）。
2. 改写 `test_hedge_api.py` 中锁错误 shape 的断言，改为断言 §3.2 shape；**新增 HTTP
   级回归**：fill-once 注入 **spot-only** 与 **perp-only** 两种单腿敞口，断言 Task
   响应的 `leg_exposure` 是 `{leg,qty,price,ts}` 且 `leg`/`qty`/`price` 正确。

## 非目标 / 边界
- **不改 §3.2 契约**。若"双腿都成交但数量不匹配"这类情形无法在 §3.2 无歧义表达 →
  输出 **ESCALATED** 交 bookkeeper/用户做契约处理，不要擅自扩展冻结 schema。
- **前端 `index.html` 已符合 §3.2，不改**（它是 Kimi 域）。`self-check.js` 的 mock
  也已用 §3.2；本 fix **不改前端**（若你判断 self-check 缺 spot-only/perp-only 覆盖，
  记录为 hedge-fe follow-up 交 bookkeeper，不要跨域改前端）。
- 不改 borrow、server.py 路由、docs、status.json、根配置；无新依赖；无真实网络。
- F-003~F-006 维持 live 轮 follow-up，不动。

## 文件边界（hard）
允许：`backend/hedge_open_tasks/**`、`backend/tests/test_hedge_*.py`。
禁止：其他一切（前端、borrow、server.py、docs、reports 除下方 R10 工件、AGENTS.md、
.env*、根配置）。

## 验收
1. 后端 `leg_exposure` emit §3.2 + 两方向 HTTP 回归测试落地。
2. `python -m pytest backend/tests -q` 全绿（基线 787，新增后总数增加），完整输出追加
   到 `60-test-output.txt` 新起 `===== hedge-be fix-2 … =====` 段（保留既有段）。
3. 修复说明写 `reports/agent-runs/2026-07-hedge-open-live-v1/40-fix-2-hedge-be.md`
   （根因、改动位置、测试结果、Output Footer 六行）。
4. R10：不 commit、不改 status.json、不转派；写完停，交 bookkeeper。

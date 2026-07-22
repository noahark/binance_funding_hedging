[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。禁止调用/启动/转派任何其他模型会话或 adapter 命令；
禁止编造未执行的命令结果；只依据本 prompt 列出的 raw artifact 路径与你实际读取
的文件。

# Fix — hedge-be fix-1（stage 2026-07-hedge-open-live-v1）

你是 hedge-be 的 fix 实现者 Claude-GLM（zhipu_glm）。review-1（Kimi）
verdict=REWORK，两项必修。原始评审证据：`reports/agent-runs/2026-07-hedge-open-
live-v1/30-review-1-hedge-be.md`（评审正文 + verdict）。固定审查范围 base
`6639b0025682f406f9a726104ef8d3b9e6f8fadd` head
`b773a470de62053207b85e58148bbf7c285026fd`。

## 必修发现（逐字自 review-1 verdict）

**F-001（P1）**：`GET /api/hedge-open-tasks?status=all` 不含 deleted，违反冻结契约
`12-development-breakdown.md` §3.1（'default excludes deleted unless
status=deleted|all'）。根因：`backend/hedge_open_tasks/domain.py`
`filter_status_for_list('all')` 返回 `None`，`backend/hedge_open_tasks/store.py`
`list_tasks(None)` 执行 `WHERE status != 'deleted'`，于是 `all` = 默认行为。前端
`frontend/index.html:3323-3327` 固定拉 `?status=all` 并依赖 deleted 在其中（已删除
筛选）。**必修**：让 `status=all` 包含 deleted（默认无 status 参数仍排除 deleted）；
改写 `backend/tests/test_hedge_domain.py` 中把错误行为钉住的
`test_filter_status_for_list_mapping`；在 `backend/tests/test_hedge_api.py` 新增
HTTP 级测试：创建→删除任务后，`?status=all` 含该任务、默认 list 不含、
`?status=deleted` 仅含该任务。

**F-002（P2）**：`mode="smooth"` 本轮被 BE 接受且会被 immediate 调度执行（实证：
创建返回 201 且出现在 `list_eligible_tasks()`）。契约 §3.1 冻结 `mode="immediate"`
本轮；FE 自检已要求「smooth 拒绝」。**必修**：`service.create_task` 对非 immediate
的 mode 抛 `invalid_field('mode', ...)`（400）；`smooth` 常量保留备用；新增
service/API 测试断言 `mode='smooth'` → 400 invalid_field。

## 非目标（不要顺手改）
F-003~F-006（`_qty_bounds` 回落、限频 enforcement、attempt persist-before-send
docstring、fill-all guard/start-gate 注记）本轮不修，bookkeeper 已记录为 live 轮
follow-up。不改 borrow 任何文件；不改 frontend；不引入新依赖；不发任何真实网络
请求。

## 文件边界（hard）
允许：`backend/hedge_open_tasks/**`、`backend/tests/test_hedge_*.py`。
禁止：其他一切（含 `backend/app/server.py`——本次修复不需要动路由）、frontend、
borrow、docs、reports（除下方 R10 工件）、AGENTS.md、.env*、根配置。

## 验收标准
1. 上述两个行为修正 + 三个测试改动/新增落地。
2. 自测命令（逐字）：`python -m pytest backend/tests -q` 全绿（当前基线 785
   passed；新增测试后总数增加），完整输出追加到
   `reports/agent-runs/2026-07-hedge-open-live-v1/60-test-output.txt`（新起
   `===== hedge-be fix-1 … =====` 段，保留既有段落）。
3. 修复说明写入
   `reports/agent-runs/2026-07-hedge-open-live-v1/40-fix-1-hedge-be.md`（含每条
   发现的根因、改动位置、测试结果、Output Footer 六行）。
4. R10 收尾：不 commit、不改 status.json、不启动/转派其他模型；写完报告即停，交
   bookkeeper 收证据、重算指纹、重进 review-1（Kimi）。

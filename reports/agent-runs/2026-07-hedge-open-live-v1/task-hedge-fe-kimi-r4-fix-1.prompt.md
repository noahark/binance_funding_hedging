[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的实现依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的
   文件。

# 任务 hedge-fe R4-fix-1：single_amount 类型对齐（decimal string）

bookkeeper R4 diff 核对发现一个**跨前后端接口不一致**（详见
`reports/agent-runs/2026-07-hedge-open-live-v1/r4-reconciliation.md` R4-001）：

- 你现在 `POST /api/hedge-open-tasks` 的 body 用
  `single_amount: Number(amountStr)`（JSON **number**）。
- 后端 `backend/hedge_open_tasks/domain.py:615-617` 的 `validate_single_amount`
  要求 **decimal string** `^[0-9]+(\.[0-9]+)?$`，收到 number 会返回
  `400 invalid_field`。金额用 decimal 字符串是正确做法（避免 float 精度误差），
  **后端不改，前端对齐**。契约已在 `12-development-breakdown.md` §3.1 补明
  `single_amount` 为 decimal string。

## 允许修改的文件（硬边界）
- `frontend/index.html`
- `frontend/self-check.js`

## 精确修复
1. `frontend/index.html`（约 3484 行的 POST body 构造）：把
   `single_amount: Number(amountStr)` 改为**送经前端校验后的原始十进制字符串**
   （满足 `^[0-9]+(\.[0-9]+)?$`，不要 `Number()`/`parseFloat` 往返，避免
   `0.01`→`"0.01"` 之外的精度或格式漂移，如 `.5` 应规范到 `0.5`、去除多余空白）。
   `target_n` 维持整数 number（后端要 int，一致，勿改）。
2. `frontend/self-check.js`：在创建任务的断言里，**断言 POST body 的
   `single_amount` 是 string 且匹配 `^[0-9]+(\.[0-9]+)?$`**（防止回归）。
3. 只改这一处类型对齐 + 对应断言；不要动其他已通过的逻辑。全部逻辑仍在第一个
   `<script>` 块内。

## 自测命令（必须真实运行并全绿）
```
node frontend/self-check.js
```
既有全部 `[PASS]` 保留 + 新增/更新的 single_amount string 断言通过，exit 0。

## R10 收尾（照做后停下）
1. 运行自测，把**完整输出**追加到
   `reports/agent-runs/2026-07-hedge-open-live-v1/60-test-output.txt`（保留
   已有 hedge-be/hedge-fe 段，新增 R4-fix 段带标题）。
2. 在
   `reports/agent-runs/2026-07-hedge-open-live-v1/20-implementation-hedge-fe.md`
   末尾追加「R4-fix-1」小节：改动点、single_amount 现送 string、自测结果、
   更新 Output Footer 时间戳（本地 `date`）。
3. **不要** commit、不要改 status.json、不要越边界、不要转派。完成后停下，交
   bookkeeper 重核 R4、串行证据 commit、算指纹、调度 review-1。

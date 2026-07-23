[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。禁止调用/启动/转派任何其他模型会话或 adapter 命令；
禁止编造未执行的命令结果；只依据本 prompt 列出的 raw artifact 路径与你实际读取
的文件。

# Fix — hedge-be fix-3（stage 2026-07-hedge-open-live-v1）

你是 hedge-be 的 fix 实现者 Claude-GLM（zhipu_glm）。这是**用户产品语义澄清**导致
的修正（非 review REWORK）。用户 2026-07-23 明确：**每次双腿成交暂时不做成交数量
校验**——因为正反向下单方式不同（现货市价买只能传总金额 quoteOrderQty，合约买卖
与现货卖传数量），双腿成交的基础币数量本就无法预先对齐（详见
`reports/agent-runs/2026-07-hedge-open-live-v1/design-inputs.md` DI-6）。

## 本轮唯一修改：去掉 classify_attempt 的成交数量校验
`backend/hedge_open_tasks/domain.py` `classify_attempt`：当前双腿都 FILLED 时还要
求 `spot_qty == perp_qty`，量不等就判 `single_leg_exposure`。**改为：双腿都 FILLED
→ `ATTEMPT_SUCCESS`（不再比较成交数量）**；恰好一腿 FILLED → `ATTEMPT_SINGLE_LEG_
EXPOSURE`（不变）；都没 FILLED → `ATTEMPT_FAILED`（不变）。同步更新 docstring
（去掉"qty 必须相等"的措辞，注明"暂不做成交数量校验，见 DI-6"）。

## 连带测试
- `backend/tests/test_hedge_*.py`：把"双腈 FILLED 且量相等才 success"「量不等→
  exposure」这类断言改为「双腈 FILLED（含量不等）→ success」；**新增/保留**一条
  "双腈 FILLED 但 filled_qty 不等 → success"的断言，锁住新语义。单腈失败 →
  exposure、累计 >3 → 暂停 这些断言**保持不变**。
- 注：`build_leg_exposure`（fix-2 的 §3.2 shape）不用改；classify 去校验后
  both-filled 走 success、不再建 leg_exposure，其 both→None 分支成为不可达防御，
  你可保留（无害）或顺带清理，二选一，不强制。

## 非目标（本轮不做，留真实 API 轮）
- **下单参数模型**（现货市价买用 `quoteOrderQty`、正反向下单方式差异、共同网格
  取整在正向不适用）——DI-6 记录为真实 API 轮重构，**本轮不改**。
- 不动共同网格取整现有逻辑（随下单模型一起在真实 API 轮改）、preflight、executor、
  scheduler、server.py、frontend、borrow、docs、status.json。无新依赖、无真实网络。

## 文件边界（hard）
允许：`backend/hedge_open_tasks/domain.py`、`backend/tests/test_hedge_*.py`。
禁止：其他一切（含同模块其他文件，除非 classify 改动确需，能不动则不动）。

## 验收
1. classify_attempt 去成交数量校验 + docstring 更新 + 测试改/加落地。
2. `python -m pytest backend/tests -q` 全绿（基线 790），完整输出追加到
   `60-test-output.txt` 新起 `===== hedge-be fix-3 … =====` 段（保留既有段）。
3. 修复说明写 `reports/agent-runs/2026-07-hedge-open-live-v1/40-fix-3-hedge-be.md`
   （根因=用户澄清、改动位置、测试结果、Output Footer 六行）。
4. R10：不 commit、不改 status.json、不转派；写完停，交 bookkeeper。

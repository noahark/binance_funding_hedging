# 00-intake — 2026-07-private-account-v1

## 目标

私有账户数据接入 v1（方向基线 = `docs/private-account-v1-direction-draft.md`
FROZEN @ 7168266，用户批准范围含 ADR-3 排序修订）：
①成本腿四级验证链 + 账户级利率；②负费率借币验证全覆盖（ADR-5 修订）；
③综合资产视图（统一账户 + 现货 + UM 敞口，防重复计算）；④净收益测算
（机会质量评分定位）+ sort_basis 排序切换。

复杂度：**MILESTONE**（白名单 4→12、账户数据首次入 UI、ADR-3 修订、
估值口径首次引入）。

## 三项流程首跑（本 stage 同时生效）

1. **stage 分支制**（DEC-2026-07-05-001）：本 stage 全部提交只落
   `stage/2026-07-private-account-v1`（designer 已建分支并记入
   status.json.stage_branch）；用户验收后才由 bookkeeper 合回 main。
2. **并行模式试运行 #2**：bookkeeper = 独立 fresh claude-glm 会话，
   **不兼任何实现任务**（v0.3 角色规则）。
3. **R10 收尾段**：双实现任务书末尾内嵌写死命令的预审派发段，实现
   终端必须机械执行，不得以「等待预审」结束。

## Bookkeeper

- Provider/model/session: claude_glm / glm-5.2 / **fresh 专职会话**
- Independent from implementers: **true**（Task A 用另一个 GLM 会话）
- 同模型不同会话的披露：bookkeeper 与 implementer-A 同为 claude_glm
  模型但强制不同会话；记账不产生代码作者身份；review-2 评估此披露。

## Parallel Mode

- Uses `docs/parallel-development-mode.md`: true
- R10 dispatch tail required: true
- R4 diff reconciliation required: true

## 冻结输入

| 输入 | 版本锚 |
|---|---|
| 方向基线 | `docs/private-account-v1-direction-draft.md`（FROZEN, 7168266） |
| 端点摸排 | `reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi.md`（1478ded） |
| 现行契约 | `docs/api/public-market-contract.md` v0.2 + snapshot.schema.json（wire v1） |
| 上游安全基线 | `docs/phase2-direction-draft.md`（FROZEN） |
| 遗留脚本架构参照 | `币安套费率策略，逐仓杠杆.js` L2706/2730/2824/3303（只读） |

## H_intake 硬门（bookkeeper 执行，全部通过才可派工）

- **G1 分支门**：当前分支必须 == `stage/2026-07-private-account-v1`。
- **G2 live discovery**：一次性脚本对 10-design §2 全部端点实抓（签名
  端点带 capture-time 脱敏 + URL 去 query）；**E3/E4/E6 任一失败 =
  BLOCKED 升级用户**（核心视图不可达）；E2/E2b/E5 失败 → 按四级链
  记录降级档位，不阻塞但必须落原始错误码。
- **G3 权重实测**：每次调用记录 `X-MBX-USED-WEIGHT-*` /
  `X-SAPI-USED-*-WEIGHT-*` 响应头，修订摸排预算表为**冻结版**（重点：
  papi 版 maxBorrowable 权重文档未见）。
- **G4 字段矩阵**：E3/E4/E6 实抓结构 → 10-design §2 附录冻结
  raw path → 契约字段映射与脱敏标记。
- **G5 禁令自查**：discovery 脚本白名单硬编码、无 POST/PUT/DELETE、
  key 零片段落档。

## 角色表

| 角色 | 承担者 | 边界 |
|---|---|---|
| designer / prompt author | Fable5 | 已建分支 + 本 packet；不写产品代码 |
| bookkeeper | claude_glm fresh 专职会话 | 单一写者；禁写业务代码；can_accept_final=false |
| implementer-A（后端） | claude_glm（独立实现会话） | backend/schemas/docs/api/tests；不 commit |
| implementer-B（前端） | kimi | frontend 两文件；不 commit |
| 嵌入预审 | 对侧模型 fresh 只读会话 | checkpoint 非门 |
| review-1 | A→fresh Kimi；B→fresh GLM | role=**first_reviewer** |
| review-2 | Codex/GPT（披露 direction_synthesis + 方向评审参与） | final gate |
| 外部复核 + 用户验收 | Fable5 → 用户 | 终态用户门，禁止 bookkeeper 代翻 |

## Evaluator

- Provider: 用户（最终验收）；Fable5（stage_accepted_waiting_user 后外部复核）

本地北京时间: 2026-07-06 00:20 CST（Fable5 起草）

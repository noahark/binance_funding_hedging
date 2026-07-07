# 12-development-breakdown

完整逐文件防漂移拆分见 `00-stage-plan.md §3`（本文件为其 stage-required 别名摘要）。owner=claude_glm 单一原子交付。

| 段 | 文件 | 改动要点 |
|---|---|---|
| 3.A | `backend/services/private_client.py` | next-hourly batch_size=15 分批合并（合并在 `_select_chain_tier` 前）；部分批失败仅跳过；修静默 except |
| 3.B | `backend/domain/snapshot.py` | `select_borrow_candidates` 拆三集合 + coverage 重定义；`resolve_cost_leg_rate` 不改 |
| 3.C | `backend/domain/snapshot.py` | `assemble_borrow_validation`：`borrowability_truncated`，截断保留利率、只清 portfolio、`borrowability_not_probed` |
| 3.D | `backend/services/snapshot_service.py` | 两集合分别驱动 cost_leg / maxBorrowable；利率解析解耦；warning 文案 |
| 3.F | `frontend/index.html` | 徽章第六态（在 `not_probed_this_round` 前） |
| 3.G | `docs/api/public-market-contract.md` | coverage/warnings 契约语义 |
| 4 | `backend/tests/`、`frontend/self-check.js` | 4 新增 + 3 修改（含 `test_borrow_validation_truncated_state`） |

**禁止**：文件边界外改动、整表缓存、float、擅自 commit / 碰 status.json。

owner split：单 owner claude_glm；allowed files 如上；forbidden：交易/借还/划转、WebSocket、bStock 规则、无关 UI。契约/数据面：`error` 新枚举 `borrowability_not_probed`。review focus：契约全下游闭合 + 60s 自愈 + 截断保留利率。

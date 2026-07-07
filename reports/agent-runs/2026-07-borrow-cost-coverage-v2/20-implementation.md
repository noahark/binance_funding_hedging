# 20-implementation

实现者：claude_glm。落盘：`11c3935`（base `5bdfc4b`）。详细改动清单与统计见 `H.impl-note.md`；diff 见 `H.diff.patch`。

## 改动文件（7）
`backend/domain/snapshot.py`、`backend/services/private_client.py`、`backend/services/snapshot_service.py`、`backend/tests/test_private_account_v1.py`、`docs/api/public-market-contract.md`、`frontend/index.html`、`frontend/self-check.js`。schema 未动（`error` 非枚举约束）。

## 测试
164 pytest passed + `node frontend/self-check.js` 全绿（含负费率六文案）。见 `60-test-output.txt`。新增 4：`test_borrowability_truncated_keeps_rate`、`test_next_hourly_subset_miss_no_fabrication`、`test_batch_merge_covers_all`、`test_partial_batch_failure_partial_merge`；修改 `test_borrow_validation_truncated_state` + coverage/warning 断言。

## 实盘 live smoke（验收项10，DONE）
见 `H.live-smoke.md`：`chain_hit_source=next_hourly`(tier1)，62/80 负费率行获利率，12 borrowability_not_probed，15 CRYPTO 子集缺失(defer/未伪造)，3 bStock。三修复目标命中，无回归。

## 审计
单一写者保持（实现者未 commit / 未碰 status.json）；R4 对账：`H.diff.patch==工作树代码 diff`，fingerprint 复算 == kimi 值。committed fingerprint `11c3935:2a73b681…`（bookkeeper + review-2 双复算一致）。

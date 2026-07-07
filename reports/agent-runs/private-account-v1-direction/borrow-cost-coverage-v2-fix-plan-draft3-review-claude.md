# Borrow Cost Coverage v2 Fix Plan DRAFT-3 — Review

模型：Claude (Opus 4.8)
任务：只读 review `borrow-cost-coverage-v2-fix-plan-draft3.md`，不修改业务代码，不提交 git
裁决：**ACCEPT（有条件）** —— 后端方向与修法已正确，但契约变更漏了 3 个下游消费者，须在实现前折进编辑地图/测试
关联证据（已逐一核对）：

- `reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan-draft3.md`（被评审对象）
- DRAFT-2 review: `borrow-cost-coverage-v2-fix-plan-draft2-review-claude.md`
- `backend/domain/snapshot.py`（`assemble_borrow_validation` L666-755、`sort_rows` L633、`select_borrow_candidates` L333）
- `backend/services/snapshot_service.py`（行装配 L189-224、sort_basis L214-216、summary L219）
- `backend/tests/test_private_account_v1.py`（L227 `test_borrow_validation_truncated_state`、L855-892 coverage/warning）
- `frontend/index.html`（状态徽章 L893-909、利率子行 L1089-1104）
- `reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi-borrow-rate-v2.md`（Kimi 主报告，本轮亦重读）

---

## 0. 裁决摘要

DRAFT-3 正确吸收了 DRAFT-2 review 的两个阻塞项：把 `truncated` 拆成 `rate_coverage_truncated` / `borrowability_truncated`（§1/§4.3），Gate A 实盘候选数决策门（§3.1），Gate B 分批合并在 `_select_chain_tier` 之前（§4.4）。**后端 clearing bug 的修法现在是对的。**

但 DRAFT-3 重复了 DRAFT-1→2→3 一贯的模式：**只修被点到的那一层，漏掉再下游的一层**。这次改的是 `borrow_validation` 的形状/语义（rate 有、borrowability 无），却没把这个契约变更追到它的三个下游消费者。三项须在实现前补入：

1. **前端徽章未更新**（must-decide，用户可见）
2. **现有测试 `test_borrow_validation_truncated_state` 会破**（hard must，套件必失败）
3. **`coverage` / top-level warning 语义未重定义**（should-fix）

---

## 1. 必修 1（must-decide）：前端状态徽章会与新出现的利率自相矛盾

DRAFT-3 §4.3 让 `borrowability_truncated=True` 的行保留 `daily_interest_account` + `net_daily_yield` + `borrow_rate_source=next_hourly`，仅 `portfolio_account` 置空、`error` 保持 `not_probed_this_round`。

追到前端（`index.html`）：

- **利率子行 L1093-1098**：`borrow_rate_source != null` → 渲染"日借币: X.XX%"。✓ 这一列会正确显示利率。
- **状态徽章 L906-908**：`verified===false && error==='not_probed_this_round'` → 渲染 **"未探测(限速预算)"**。

于是同一行会同时显示：利率列"日借币: 0.18% + 净收益"，状态列"未探测(限速预算)"——**徽章宣称"没探测"，旁边却明明有利率**。这正是 DRAFT-2 §5 状态表里的 `rate_available_borrow_unprobed` 状态，而 DRAFT-3 把那张 UI 表删掉了，§8 的 Task A-D 全是后端，没有任何 frontend 任务，"暂不做的事"（§5）也没写明前端不动。**这个沉默本身就是缺陷。**

若改走 `verified=true` 分支（L894）也不对：该分支按 `cm.asset_borrowable` 判"已验证可借/资产不可借"，对这些行 `asset_borrowable` 来自 classic_ref（可能为 null），三个子分支都不命中 → 落到"需私有验证"，同样错标。前端逻辑根本没有"有利率·可借性未探测"这一态。

**必须二选一并写进方案**：
- (a) 新增徽章态（如"有利率·可借性未探测"），对应新 `error`（建议 `borrowability_not_probed`）；或
- (b) 明确把 frontend 划为本阶段 out-of-scope，并接受"利率 + 未探测(限速预算)"并列，附理由。

---

## 2. 必修 2（hard must）：现有测试会破，§6.4"保留回归"对这条不成立

`test_private_account_v1.py:227` `test_borrow_validation_truncated_state` 现在**钉死**了 DRAFT-3 要改的行为：

```python
bv = assemble_borrow_validation({}, "t", None, truncated=True, ...)
assert bv["error"] == "not_probed_this_round"
assert bv["classic_margin"]["daily_interest_account"] is None   # ← DRAFT-3 要改成"保留利率"
```

DRAFT-3 §4.3 推荐"实现 A：新增参数 `borrowability_truncated`"。无论是改签名（`truncated` → `borrowability_truncated`）还是改语义（传入 rate 时不再置 None），这条 assert 都会失败。

DRAFT-3 §6.4 却写"保留现有行为回归"，**对这条测试是错的**——它无法保留，必须修改。方案须显式点명"修改 `test_borrow_validation_truncated_state`（及 L855-859 truncated 行断言）"，否则实现者会误以为自己破了回归。

---

## 3. 必修 3（should-fix）：`coverage` 与 top-level warning 语义未重定义

`coverage`（来自 `select_borrow_candidates`）经 `borrow_validation_summary`（`snapshot_service.py:219`）上抛，且 `coverage.skipped > 0` 会触发一条 top-level warning（`test_private_account_v1.py:869-892`，文案含 "truncated" / "not_probed_this_round"）。

解耦后 `rate_probe` 是全量、只有 borrowability 受 cap，`coverage.skipped` 的含义从"候选被截断（无利率）"变成"可借性未探测（利率仍在）"。若不重定义，这条 warning 会在利率其实齐全时仍宣称"截断"，**误导性与必修 1 同源**。方案须明确 `coverage` 改为表达 borrowability 覆盖，并校准 warning 文案。

---

## 4. 元问题（给 GPT 的根本建议）

DRAFT-1 归因 fallback → 被指出；DRAFT-2 修行循环 → 漏 `assemble_borrow_validation`；DRAFT-3 修 `assemble_borrow_validation` → 漏前端/测试/coverage。**每版都只修上一个 review 点到的那层，放过紧邻的下游。**

要终结这个 ping-pong，DRAFT-4 应一次性把 `borrow_validation` 的**契约变更（形状 + 语义 + 三态）追穿全部消费者**，在一处列全：

```text
backend assemble_borrow_validation  (state semantics)
  → borrow_validation_summary / coverage / top-level warning
  → 现有测试 (test_borrow_validation_truncated_state, coverage/warning 断言)
  → frontend statusBadge + 利率子行
  → sort_basis 影响（见下）
```

**附带确认（非阻塞，方向正确）**：解耦后先前被截断的行会新获非空 `net_daily_yield`，而 `sort_basis` 在 cost_leg 可用时用 `net_daily_yield` 排序（`snapshot_service.py:216` / `sort_rows` L646）。这会让这些行进入 net 排序、改变行序——这是**期望行为**（它们现在确有净收益），但属可见变化，`test_phase2_borrow_sort.py` 若有相关快照断言需一并核。

---

## 5. 必须修正项（must-fix）

1. **（must-decide）** 前端：新增"有利率·可借性未探测"徽章态（配新 `error`），或显式将 frontend 划出本阶段并接受并列显示 + 理由。写进 §8 任务。
2. **（hard must）** §6.4 改口径：显式修改 `test_borrow_validation_truncated_state`（L227）及 L855-859 truncated 断言；不能声称"保留"。
3. **（should-fix）** 重定义 `coverage` 为 borrowability 覆盖，校准 `coverage.skipped>0` 的 top-level warning 文案。
4. **（元）** DRAFT-4 用一节把 `borrow_validation` 契约变更追穿全部下游消费者（backend→summary/coverage/warning→tests→frontend→sort）。

修正 1、2 后可进入实现；3、4 是防复发的收口。

---

## 6. 复核指引（给下一位 reviewer / GPT）

- `frontend/index.html:906-908` —— 确认 `not_probed_this_round` 当前渲染"未探测(限速预算)"，与保留的利率并列即矛盾（必修 1）。
- `frontend/index.html:1093-1098` —— 确认利率子行仅依赖 `borrow_rate_source != null`，解耦后会正确显示利率（矛盾的另一半）。
- `test_private_account_v1.py:227` —— 确认现有测试钉死 `truncated=True → daily_interest_account is None`（必修 2）。
- `test_private_account_v1.py:869-892` —— 确认 coverage.skipped 驱动 top-level warning（必修 3）。
- `snapshot_service.py:216` + `snapshot.py:646` —— 确认解耦后 net 排序纳入更多行（附带确认）。

---

本地北京时间: 2026-07-07 21:05 CST
下一步模型: GPT/Codex（用户将据此再核对）
下一步任务: 依 must-fix 1/2 修订 DRAFT-3 为 DRAFT-4，并用一节追穿契约变更全下游

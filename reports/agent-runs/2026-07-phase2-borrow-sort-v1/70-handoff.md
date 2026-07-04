# Handoff — 2026-07-phase2-borrow-sort-v1

## 当前状态

- `status`：`review_1`（**round 2**；round-1 A=REWORK 已 fix，B=ACCEPT）
- 提交链：H_A `d8a1164` → H_B `cc25148`（round-1 fingerprint head）→ H_bind
  `59e0eab` → … → round-1 evidence `bd0159a` → **H_A2 `2a793a9`（E1 fix，
  round-2 fingerprint head）**
- `diff_fingerprint`：`2a793a9c35e8e5fe8cdebe8875cada9b85f335d0:9b92cc4595982f0e09ce33d179019fa54a370aa30aeeaa977772eca33fb433e9`
  （base = H_intake `4d47ad2`；shasum 复算一致；fingerprint head = H_A2 产品代码
  完成点，其后的 evidence/night-collection 不进入指纹）
- 测试：pytest **96 passed**（round-1 95 + E1 新测试 1）；node self-check 20 PASS
- `rework_count`：1（round-1 A=REWORK E1）

## review-1 round-1 结论

- **Task A（backend）← fresh Kimi**：**REWORK**，P1 = live fundingInfo 失败不
  降级（违反 design §2 E1「缺省全 8h + warning」）。bookkeeper 独立核实成立。
  verdict 见 `30-review-1-backend.md`（含 fix_start_prompt）。
- **Task B（frontend）← fresh Claude-GLM**：**ACCEPT**，2x P3 非阻塞
  （self-check 回归网收窄 F1 + role 模板 bug F2）。verdict 见
  `30-review-1-frontend.md`（从 GLM plan 文件 verbatim 提取）。
- 两 reviewer **独立**确认：模板 `role=second_reviewer` 不在 schema 枚举
  （模板 bug），均采合规 `first_reviewer`。

## E1 fix（H_A2 `2a793a9`，round-1 REWORK 响应）

- `backend/adapters/binance_public.py` `_fetch_live`：fundingInfo GET 包
  `try/except (URLError/HTTPError/OSError/ValueError)` → 空 dict + warning；
  `_fetch_offline` 加空 warnings。
- `backend/domain/snapshot.py` `assemble_snapshot`：加 `extra_warnings` 参数
  （additive；schema `warnings` 是开放 array，未改 schema/contract）。
- `backend/services/snapshot_service.py`：透传 `raw["warnings"]`。
- 新测试 `test_live_fundinginfo_failure_degrades_to_8h_with_warning`
  （monkeypatch urlopen，fundingInfo raise HTTPError，断言全 8h + warning 透传）。
- 未触碰耦合面三项 / classify / normalize / frontend。

## 下一步（review-1 round 2）

- 复审 Task A E1 fix（H_A2 `2a793a9`，fresh Kimi 只读）。
- dispatch：`review-1-round2-task-a-by-kimi.prompt.md`（base=`4d47ad2`,
  head=`2a793a9`）。
- Task B round-1 ACCEPT，backend-only fix 不影响 frontend，**B 不需 round 2**。
- round-2 ACCEPT → review-2（Codex，用户交，`direction_synthesis`）。

## 待 review/用户决策

- **ADR-5**：bounded portfolio 选样策略（live `portfolio_filled=0`，§3.4 结果非
  bug；是否调整策略留 design 决策）。
- night-collection-2026-07-05（用户夜间采集流程产物，非本 stage）已 commit
  独立 `48662df`（amounts redacted `<LIMIT>` + URL query stripped + .headers 无
  key），解除 worktree-clean 阻碍。

---

本地北京时间: 2026-07-05 00:10 CST
作者: bookkeeper (claude_glm)

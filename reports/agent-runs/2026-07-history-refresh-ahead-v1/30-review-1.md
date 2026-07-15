# Review 1 — Kimi Raw Output

## Dispatch Receipt

- Session: `session_c24f55dc-51b0-4f67-9cab-d43943935e1b`
- Provider/model: Kimi / `kimi-code/kimi-for-coding`
- Provider identity: `moonshot_kimi`
- Mode: fresh read-only review-1
- Retrieval: local `kimi export` of the exact user-supplied Session ID; the
  session was not resumed or continued
- Raw final response below preserves the complete substantive text and exact
  final JSON; Markdown trailing-space line breaks were mechanically removed to
  satisfy repository `git diff --check` hygiene.

---

## Review-1 评审结论

本次评审以只读方式核对阶段 `2026-07-history-refresh-ahead-v1` 的提交范围 `12b8e1c1ea5d86bf692bbba2183de08ee9429af4..2cb72fd870b1ef29cc4787e7dff102ab56bf8601`，并独立重新计算了 diff fingerprint，结果与权威指纹一致。

### 关键核对项

1. **刷新阈值一致**
   `backend/services/snapshot_service.py:853-862` 的 `_history_refresh_ttl()` 返回 `max(0, self.config.funding_history_cache_ttl_seconds - HISTORY_REFRESH_AHEAD_SECONDS)`，其中 `HISTORY_REFRESH_AHEAD_SECONDS = 300`（第 65 行）。
   `_history_is_fresh()`（第 864-869 行）与 `_fetch_history_for()` 的 cache-reuse guard（第 836 行）均使用同一阈值，符合 `max(0, publication_ttl - 300)` 的冻结公式。

2. **发布过期 TTL 未变**
   `_all_valid_history()`（第 809-823 行）仍使用完整的 `self.config.funding_history_cache_ttl_seconds` 作为发布过期判断，未受 refresh-ahead 影响。

3. **1500 秒边界行为正确**
   测试 `test_history_1499_reuses_cache_without_public_call` 与 `test_history_1500_performs_real_public_call` 证明：1499 秒复用缓存，1500 秒触发真实公开历史 I/O 并重新打时间戳。

4. **失败早期刷新不覆盖旧缓存**
   `_fetch_history_for()` 在异常时直接返回 `None`（第 848-849 行），不会写入缓存；`test_all_valid_history_publishes_old_entry_through_1799` 验证 1500-1799 秒旧成功条目仍被发布，1800 秒才过期。

5. **borrow 组件未提前到期**
   `_sweep_group_c()`（第 1163 行）的 `component_ttl` 仍为完整 TTL，并用于 `_borrow_rate_due()` / `_max_borrowable_due()`。`test_borrow_components_not_due_at_1500` 验证 1500 秒时 borrow-rate / max-borrowable 不产生额外私有调用。

6. **测试确定性且非重言式**
   新增 5 个测试覆盖 1499/1500、1800 发布边界、成功连续发布、私有调用隔离；`backend/tests/test_background_worker.py` 37 个测试全部通过，完整后端 335 个测试通过。

7. **TTL ≤ 300 的 clamp 行为**
   `_history_refresh_ttl()` 对 `ttl <= 300` 返回 0，意味着每次 cursor 访问都会刷新；这与冻结公式一致，配置默认值 1800 未变，未引入新的环境变量。

8. **无隐藏变更**
   diff 仅触及允许的三文件边界：`backend/services/snapshot_service.py`、`backend/tests/test_background_worker.py` 与 `20-implementation.md`。未修改 config、API/schema、前端、私有传输、coverage、cursor 大小或交易行为。

### 独立验证结果

- 重新计算 diff fingerprint：`a1406bde574ed193c12ee826f56102e99d6db029f6742d4412b44fea344b1ef3` ✅
- `python3 -m pytest backend/tests/test_background_worker.py -q` → 37 passed ✅
- `python3 -m pytest backend/tests -q` → 335 passed ✅
- `python3 -m py_compile backend/services/snapshot_service.py backend/tests/test_background_worker.py` ✅
- `git diff --check` ✅
- 未发现 P0/P1/P2/P3 级别问题。

本地北京时间: 2026-07-15 12:20:00 CST
下一步模型: claude
下一步任务: 执行 review-2 最终评审提示文件并输出 verdict JSON

{"schema_version":1,"stage_id":"2026-07-history-refresh-ahead-v1","role":"first_reviewer","model":"kimi-code/kimi-for-coding","verdict":"ACCEPT","diff_fingerprint":"2cb72fd870b1ef29cc4787e7dff102ab56bf8601:a1406bde574ed193c12ee826f56102e99d6db029f6742d4412b44fea344b1ef3","reviewer_prior_involvement":"none","reviewed_artifacts":["AGENTS.md","workflows/templates/stage-delivery.yaml","agents/skills/code-reviewer.md","schemas/review-verdict.schema.json","reports/agent-runs/2026-07-history-refresh-ahead-v1/00-intake.md","reports/agent-runs/2026-07-history-refresh-ahead-v1/00-task.md","reports/agent-runs/2026-07-history-refresh-ahead-v1/10-design.md","reports/agent-runs/2026-07-history-refresh-ahead-v1/11-adr.md","reports/agent-runs/2026-07-history-refresh-ahead-v1/20-implementation.md","reports/agent-runs/2026-07-history-refresh-ahead-v1/60-test-output.txt","backend/services/snapshot_service.py","backend/tests/test_background_worker.py","git diff 12b8e1c1ea5d86bf692bbba2183de08ee9429af4..2cb72fd870b1ef29cc4787e7dff102ab56bf8601"],"findings":[],"required_fixes":[],"next_action":"continue"}

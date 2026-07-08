# 70-handoff

## 当前状态

status=`review_1`。GLM serial implementation 已由 bookkeeper/codex 冻结并提交，准备派发 fresh Kimi review-1。

## 分支与提交

- current branch: `stage/2026-07-ui-filter-balance-metal-v1`
- stage_branch.name: `stage/2026-07-ui-filter-balance-metal-v1`
- base_sha: `3d3c66e64446d1285a96b4a0e0843e912e4c540e`
- frozen head_sha: `2e966904a6adb576adee8f979738ef664f80058c`
- current HEAD after implementation evidence commit: `2e966904a6adb576adee8f979738ef664f80058c`
- diff_fingerprint: `2e966904a6adb576adee8f979738ef664f80058c:83956ebe014a34fc8ee85cfb04bb701fac76e488e106fac746a1a542762222a1`

## 已完成

- GLM 实现报告已落档：`reports/agent-runs/2026-07-ui-filter-balance-metal-v1/20-implementation.md`。
- bookkeeper/codex 已复跑：
  - `python3 -m pytest backend/tests -q` => `173 passed`
  - `node frontend/self-check.js` => `全部自检通过`
  - `git diff --check` => PASS
  - 禁止项/旧格式 grep 审计 => 仅命中文档和测试中的缺失断言/说明
- 本地 evidence commit 已创建：
  - `2e966904a6adb576adee8f979738ef664f80058c bookkeeper(2026-07-ui-filter-balance-metal-v1): land GLM implementation evidence`
- `status.json` 已记录 committed fingerprint、测试通过、task `serial` landed、review-1 Kimi 路由。

## 冻结 diff 范围

Kimi review-1 必须使用 status-recorded range，不使用移动 HEAD：

```text
git diff --binary 3d3c66e64446d1285a96b4a0e0843e912e4c540e..2e966904a6adb576adee8f979738ef664f80058c -- . ':(exclude)reports/agent-runs/2026-07-ui-filter-balance-metal-v1/status.json'
```

该范围包含 stage 设计/证据与 GLM 产品实现。review focus 应重点检查 GLM 实现改动、契约同步、测试覆盖和红线约束。

## 代码改动文件

- `backend/domain/normalize.py`
- `backend/domain/snapshot.py`
- `backend/tests/test_normalize.py`
- `backend/tests/test_snapshot.py`
- `docs/api/public-market-contract.md`
- `frontend/fixture/public-market-snapshot.json`
- `frontend/index.html`
- `frontend/self-check.js`
- `schemas/api/public-market/snapshot.schema.json`

## 当前 git status

本 checkpoint 写入时还有待提交的 bookkeeper 状态文件：

```text
M reports/agent-runs/2026-07-ui-filter-balance-metal-v1/status.json
M reports/agent-runs/2026-07-ui-filter-balance-metal-v1/70-handoff.md
```

在正式 dispatch review-1 前，bookkeeper 必须提交这些状态文件、生成 review prompt、运行并保存 `scripts/validate-stage.py 2026-07-ui-filter-balance-metal-v1 --phase pre-review` 的 PASS 输出。

## 开放问题 / 阻塞

无产品阻塞。实现报告披露 `backend/services/snapshot_service.py` 中有两处 CRYPTO-only 注释漂移，但该文件不在实现边界内，当前行为由 `select_borrow_candidates()` 的 candidate set 控制；交给 review-1 判断是否要求修复。

## 下一步

1. 生成 `review-1-kimi.prompt.md`。
2. 提交 `status.json`、`70-handoff.md`、review prompt。
3. 运行 `scripts/validate-stage.py 2026-07-ui-filter-balance-metal-v1 --phase pre-review` 并保存 PASS evidence。
4. 派发 Kimi review-1，保存 raw output，校验最终 JSON verdict。

本地北京时间: 2026-07-08 10:56:41 CST
下一步模型: kimi
下一步任务: fresh read-only review-1：检查冻结 diff 与 raw artifacts，输出 schema-valid verdict JSON。

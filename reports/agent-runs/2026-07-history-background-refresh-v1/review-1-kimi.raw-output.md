## Review-1 审查叙述

我已按 `30-review-1.prompt.md` 对 stage `2026-07-history-background-refresh-v1` 的 committed diff 做了只读审查。

**身份与隔离**

- reviewer: Kimi (`kimi-code/kimi-for-coding`, provider `moonshot_kimi`)
- implementer: `claude_glm` / GLM-5.2 (provider `zhipu_glm`)
- 本人未参与本阶段设计、实现、修复或 bookkeeper 工作；provider 隔离符合 review-1 要求。

**审查范围**

- 原始证据：`AGENTS.md`、`workflows/templates/stage-delivery.yaml`、`00-task.md`、`10-design.md`、`11-adr.md`、`12-development-breakdown.md`、`20-implementation.md`、`60-test-output.txt`、`status.json`、已提交 diff（`0db66d2..6c9f8f2`）、相关源码与测试、公开样本。
- 绑定值校验：`diff_fingerprint` 与 `git diff --binary ... | sha256sum` 一致；工作区干净。

**关键实现核对**

1. **单 worker / 不可变发布**：`PublishedState` 为 frozen dataclass，`_publish_validated` 一次引用替换；HTTP 请求线程只读或提交命令，不碰 domain cache。
2. **默认视图选择器**：`default_view_history_symbols` 严格 `> 0.00030000`，null/invalid/`PERP_ONLY_EXCLUDED` 排除，与前端默认阈值一致。
3. **点击路径窄化**：`_handle_refresh_command` 使用 `fetch_premium_index_for` + `fetch_funding_rate`，不调用整宇宙 `fetch_raw()`；force-TTL 只 evict 3 个单资产精确键，测试证明多资产 batch 与共享引用保留。
4. **deadline 发布闸门**：入口 gate → I/O → post-I/O gate → `_assemble` → post-assemble gate → `_validate` → final gate → history-cache commit → `_publish_validated`，超时后状态/cache/inputs 全部保留旧值。
5. **legacy funding-history**：`get_funding_history` 纯 `PublishedState` 投影，零上游、零缓存写。
6. **symbol-snapshot 契约**：schema 定义 `public-market-symbol-snapshot/v1`，响应只含单行，无 `rows` 数组，测试验证同行与同版本全量行一致。
7. **前端**：`patchRow` 只替换目标 `<tr>`+抽屉，1s 防连点、`inflightSymbol` 忽略、按 `refresh_status` 分流 timeout/partial/ok。
8. **公开样本**：`reports/api-samples/.../raw/` 存在真实 `premiumIndex` 与 `fundingRate` 样本；signed 证据明确标注为 follow-up，未用 fixture 冒充事实。

**独立验证**

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider` → 289 passed
- `python3 -m pytest backend/tests/test_symbol_snapshot_endpoint.py -v` → 27 passed
- `node frontend/self-check.js` → 全部通过
- `python3 scripts/validate-stage.py 2026-07-history-background-refresh-v1 --phase pre-review` → PASS，指纹匹配

**结论**

未发现 P0/P1 阻塞问题。实现符合冻结设计、ADR、development breakdown 与验收标准。建议进入 review-2。

本地北京时间: 2026-07-13 10:03:00 CST
下一步模型: review-2 (Codex/Claude)
下一步任务: 对同一 committed diff 执行 final review 并输出 schema-valid verdict JSON

{"schema_version":1,"stage_id":"2026-07-history-background-refresh-v1","role":"first_reviewer","model":"kimi-code/kimi-for-coding","verdict":"ACCEPT","diff_fingerprint":"6c9f8f2f8a4e71dc59d1866b0f9acc616104ffbb:f81403b21f91b1c7b7a9fbf167f423d02061773920fdee9b51711fa97c3bad96","reviewer_prior_involvement":"none","reviewed_artifacts":["AGENTS.md","workflows/templates/stage-delivery.yaml","reports/agent-runs/2026-07-history-background-refresh-v1/00-task.md","reports/agent-runs/2026-07-history-background-refresh-v1/10-design.md","reports/agent-runs/2026-07-history-background-refresh-v1/11-adr.md","reports/agent-runs/2026-07-history-background-refresh-v1/12-development-breakdown.md","reports/agent-runs/2026-07-history-background-refresh-v1/20-implementation.md","reports/agent-runs/2026-07-history-background-refresh-v1/60-test-output.txt","reports/agent-runs/2026-07-history-background-refresh-v1/status.json","reports/api-samples/2026-07-history-background-refresh-v1/20260713T000000Z/capture.md","reports/api-samples/2026-07-history-background-refresh-v1/20260713T000000Z/raw/fapi-v1-premiumIndex-BTCUSDT.json","reports/api-samples/2026-07-history-background-refresh-v1/20260713T000000Z/raw/fapi-v1-fundingRate-BTCUSDT-limit1000.json","reports/api-samples/2026-07-history-background-refresh-v1/20260713T000000Z/signed-audit-template.json","backend/services/snapshot_service.py","backend/services/private_client.py","backend/adapters/binance_public.py","backend/app/server.py","backend/config.py","backend/domain/snapshot.py","frontend/index.html","frontend/self-check.js","backend/tests/test_background_worker.py","backend/tests/test_symbol_snapshot_endpoint.py","schemas/api/public-market/symbol-snapshot.schema.json","schemas/review-verdict.schema.json"],"findings":[],"required_fixes":[],"residual_risks":["真实 live signed capture（force-TTL 在生产 key 下的实网脱敏录制）仍为操作者授权后的 follow-up，未在本 bounded task 中完成；实现者已用脱敏 fake-key 单元测试验证行为级语义。"],"next_action":"continue"}

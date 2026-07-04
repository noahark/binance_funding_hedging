你是一个全新的只读 Kimi 会话，担任 stage `2026-07-phase2-borrow-sort-v1` Task A（后端）的嵌入交叉预审者。
这是并行开发模式的 checkpoint，不是评审门：只产出 blocker 清单或放行意见，不产生 review verdict JSON。

## 评审对象

- 当轮工作树 diff：`reports/agent-runs/2026-07-phase2-borrow-sort-v1/embedded-review-a-round1.diff.patch`（已生成，只包含 Task A 改动：`backend/**` + `schemas/api/public-market/snapshot.schema.json` + `docs/api/public-market-contract.md`；9 文件，不含 frontend）。
- 对照规格：同目录 `10-design.md` §1/§2/§3（含 §2.A discovery 字段冻结附录）、`00-task.md`、`status.json` 的 `hard_constraints` + `endpoint_whitelist`。
- 可读仓库任何文件；禁止写文件、改工作树；可运行 `python3 -m pytest backend/tests/ -q` 验证（只读运行）。

## 必查清单（逐项给 PASS/FAIL + 证据文件/行号）

1. **单一 HMAC 出口**：grep 产品代码，`hmac`/`hashlib`/`signature=` 仅出现在 `backend/services/private_client.py`（测试断言字符串除外）；无其他模块绕过签名通道直连 Binance。
2. **deny-by-default 白名单 + GET-only + 门控先于签名**：`WHITELIST` = `(method, exact-path)` 四项，与 `status.json` `endpoint_whitelist` 严格一致；非白名单 path 或非 GET method 在签名构造**之前** raise；无 POST/PUT/DELETE 代码路径。
3. **审计日志凭据清理**：日志条目仅 `{logical_endpoint, method, http_status, error, latency_ms}`，无 key/secret/signature/完整 query/headers。
4. **daily-rate Decimal 纪律**：`compute_daily_funding_rate` 用 `decimal.Decimal`，禁 float；§3.3 六向量正确（含负零归一化 `0.00000000`、缺失/空→`null`）；输出定点字符串无科学计数法。
5. **排序全序**：`sort_rows` 按 `abs(daily_funding_rate)` DESC、null 末尾、symbol 升序 tie-break，确定性；rows 有序性是后端职责（前端不重排）。
6. **borrow_validation 三态语义**：disabled（`verified=false` 全 null + `error`）/ verified-not-listed（`pair_listed=false` 数据 null）/ verified-listed（`pair_listed=true` + 数据）；`portfolio_account` 仅 bounded top-N `MARGIN_SPOT_CANDIDATE`+`CRYPTO`（bStock 排除）；并列输出块，不改 classify。
7. **raw→snake_case 映射**：E3 键 `assetName`、E4 键 `coin`（非 `asset`），VIP0 取档；raw camelCase 不泄露进 snapshot 输出。
8. **schema v0.2**：root `private_channel`（enum enabled/disabled）+ row `funding_interval_hours`/`daily_funding_rate`/`borrow_validation` 均为 optional（v0.1 frozen fixture 向后兼容）；`$defs/borrow_validation` 三态可空结构正确。
9. **降级**：env 缺失/offline → `private_channel=disabled` + 全行 `verified=false`；offline 模式不触网（`__init__` 强制 private disabled，不读 env）；公开快照仍正常产出。
10. **硬边界**：`classify.py`/`normalize.py`/`frontend/**` 零触碰（diff 核查）；枚举与优先级零改动；`route_class`/`negative_funding_status` 不受 borrow_validation 影响。
11. **越界检查**：diff 仅触碰允许文件；无 commit、无 `status.json` 改动。
12. **测试**：自跑 `python3 -m pytest backend/tests/ -q` 全绿（宣称 95 passed），既有零回归。

## 关于 bounded portfolio 的已知 live 观察（非必查缺陷，供参考）

实现报告 `20-implementation-backend.md` §3.1 已如实上报：live 下 bounded top-N（abs daily DESC 的 `MARGIN_SPOT_CANDIDATE`+`CRYPTO`）当前全为高费率小币，PM 不可借 → `portfolio_account` 全 null；可借大币（BTC/ETH）费率低不在 bounded。这是 §3.4 bounded 选样策略 + 市场现实的结果，**非实现 bug**。请判断实现是否严格遵循 §3.4（而非策略本身是否最优——后者属 design 决策，不在本预审范围）。

## 输出格式

逐项 PASS/FAIL 表 → blocker 清单（文件/行/缺陷/修法）→ 总结论 `PASS（可落盘）` 或 `BLOCKER（需修复后 round 2）`。末尾注明模型身份与当前本地北京时间。你的输出将被逐字落档到 `reports/agent-runs/2026-07-phase2-borrow-sort-v1/embedded-review-a-round1.raw-output.md`。

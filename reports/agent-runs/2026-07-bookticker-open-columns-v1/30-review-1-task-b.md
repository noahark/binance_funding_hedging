# Review-1 Narrative — Task B Frontend

**Reviewer**: `claude_glm` / `zhipu_glm` / `glm-5.2` · `first_reviewer` · fresh Claude-GLM Session(与 Task B implementer `moonshot_kimi` provider 隔离,亦非 Task A `aaba9bdc` session)
**Range**: `dff8b478..0a383f0`(单一 commit `feat(frontend): add opening quote columns`)
**Fingerprint 验证**: 亲自计算 `git diff --binary dff8b478..0a383f0 -- . ':(exclude).../status.json' | shasum -a 256` = `2fa0b749...4dce`,与 prompt 要求的 Task B fingerprint **逐字相等**。
**Provider isolation**: reviewer=zhipu_glm,implementer=moonshot_kimi,符合 cross-review pool(`implementer_provider_kimi → claude_glm`);session `04b6147e` 与 implementer session `session_727145b3` 不同源。`reviewer_prior_involvement=none`。

## 审查方法与证据来源

亲自读取 `AGENTS.md`、`stage-delivery.yaml` review-1/policy section、`code-reviewer.md`、`00-task.md`、`10-design.md`(D5/D6/D8/D9)、`11-adr.md`、`12-development-breakdown.md`(§5 列布局/§6 wire contract/§7 truth table)、`14-design-review-reconciliation.md`、Task B 实现/bookkeeper 报告、`60-test-output.txt`、`snapshot.schema.json#opening_quotes`、**实际 committed diff**(`frontend/index.html`+111/-...、`self-check.js`+303、`fixture`+84)、以及 `frontend/index.html` 的 `formatPrice`/`formatUsdt2`/`REQUIRED_ROW_FIELDS`。**未使用 bookkeeper summary 替代 raw diff**。

## 八项 Mandatory Focus 结论

1. **12 列契约** ✓ — 表头精确有序 `标的 / 借贷状态·资产 / 资金费率 / 结算时间 / 日费率 / 年化24h / 年化7D / 年化30D / 日净收益 / 标记价格·指数价格 / 正向开单 / 反向开单`;`提示标记` 与独立 `负费率状态` 列已删除;`REQUIRED_ROW_FIELDS` 仍含 `ui_flags`+`route_class`+`negative_funding_status`;empty-state `colspan=12`;data row 恰 12 `<td>`(self-check 33c 逐行计数断言)。
2. **借贷状态/资产合并** ✓ — `<td>${badgeForNegativeFundingStatus}${maxBorrowLine}<br/>${badgeForAssetTag}</td>` 状态在上、资产在下;`badgeForNegativeFundingStatus` 函数体未改(六文案语义保留);`maxBorrowableSubline` 仅依赖 `portfolio_account.max_borrowable != null`,**不再被 `borrow_rate_source` 门控**(F1 fix,case d DUSDT 验证);额度只在 index 1,net cell 不含 `可借:`;51061 零额度 `可借: 0` + `已借完` + `≈ 0.00 USDT`(case a 验证)。
3. **日净收益** ✓ — `${netText}${netSource}${borrowSubline}` 保留净值/source/日借币成本,可借额度子行已迁出;`sortBasisLabel('net_daily_yield')='日净收益优先'`。
4. **正/反向腿顺序** ✓ — forward 上「合约买一 `futures_bid_price`」/下「现货卖一 `spot_ask_price`」/右 `forward_spread_pct`;reverse 上「现货买一 `spot_bid_price`」/下「合约卖一 `futures_ask_price`」/右 `reverse_spread_pct`(self-check 33d 锁定标签+价格+百分比+颜色)。
5. **单位护栏** ✓ — `formatOpeningSpreadPct` 独立 formatter,直接展示后端字符串 + `%`,**不运算、不乘 100、不调用 `formatFundingRate`**(self-check 断言其函数体不含 `formatFundingRate(`);锁定 `-0.04→-0.04%`、`0.00→0.00%`;正 `+`/负原 `-`/零无号/null·invalid → `—`+`muted`。
6. **降级** ✓ — `!oq || stale || unavailable → —`;incomplete 保留单腿(`formatPrice(null)→—`)且两方向独立(forward 缺 spot_ask → forward spread `—`,reverse 仍 `+0.04%`,self-check 33e 锁定 ≥2 个 `—`);fixture `XAUUSDT.spot={symbol:null,exists:false}` → incomplete/spreads null(**不伪造 spot leg**,F2 fix);`TSLAUSDT` bStock `spot.symbol=TSLABUSDT` alias 正确。
7. **副作用面** ✓ — `setInterval`/`fetch(`/`addEventListener` 计数 base==head(3/2/13),`WebSocket`/`setTimeout`/`onclick` 均 0,**无新增 timer/fetch/WebSocket/按钮/交易副作用**;title 文案含「约 60 秒刷新…120 秒…非成交保证…stale/incomplete」;click handler/`data-symbol`/drawer/private/filters/refresh 逻辑未在 diff 中改动。
8. **self-check 有效性** ✓ — 严格有序 12 元素表头比较、逐行 td=12、empty colspan+1 td、status-before-asset、single-location(`可借:` 不在 net cell)、explicit dash(≥2)、formatter 三向量、各态降级;fixture 与冻结 contract 一致(BTC vector、incomplete、stale 保留 updated_at、unavailable null)。**独立运行 `node frontend/self-check.js` = 77 [PASS],全部通过**。

## 非阻塞观察(P3)

以下均为 P3,不影响 ACCEPT,不构成 `required_fixes`,记录供后续参考。

**P3-1** `formatOpeningSpreadPct` 正则 `^-?\d+\.\d{2}$` 隐式耦合后端"恒为两位小数量化字符串"。当前契约(D6/§6:ROUND_HALF_UP 两位 + 负零归一 `0.00`)下完全安全;仅在后端未来产出整数百分比(如 `5`)或非两位值时会静默降级为 `—`。非缺陷,建议后端 contract 文档固化"恒两位"约定即可。

**P3-2** `renderOpeningQuotesCell` 仅在 `status∈{stale,unavailable}` 整体降级;若后端违反冻结契约(`fresh` 但个别价格 null),前端会显示该价为 `—` 而 spread 照常渲染,产生局部不一致。此为后端契约违反场景,前端无责亦无需防御——`fresh 必四价齐全` 由后端 deterministic test 保证(Task A `test_snapshot.py`/`test_book_ticker.py`)。

## Verdict

**ACCEPT** — Task B frontend diff 与冻结产品语义、`10-design.md` D8/D9、`12-development-breakdown.md` §5 列布局逐项一致;`required_fixes=[]`;fingerprint 与 committed range 锚定;无 forbidden 文件、无交易副作用;独立 self-check 全绿。建议继续。

```text
当前 Session ID: 04b6147e-96ae-46c8-a147-2201aa4c590a
Session ID 来源: runtime_env (`CLAUDE_CODE_SESSION_ID`)
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/30-review-1-task-b.md
本地北京时间: 2026-07-15 21:41:28 CST
下一步模型: codex_bookkeeper
下一步任务: 校验 Task B review-1 JSON、Session/provider isolation 与 fingerprint，并与 Task A review-1 一并门禁
```

{"schema_version":1,"stage_id":"2026-07-bookticker-open-columns-v1","role":"first_reviewer","model":"glm-5.2","verdict":"ACCEPT","diff_fingerprint":"0a383f0f8528591898f12690c371108e7582a27e:2fa0b74988af0ae96a4a2f252f0aa67346c5b5fd3e89a218c78802bec4a48dce","reviewer_prior_involvement":"none","reviewed_artifacts":["AGENTS.md","workflows/templates/stage-delivery.yaml","agents/skills/code-reviewer.md","schemas/review-verdict.schema.json","schemas/api/public-market/snapshot.schema.json","reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md","reports/agent-runs/2026-07-bookticker-open-columns-v1/10-design.md","reports/agent-runs/2026-07-bookticker-open-columns-v1/11-adr.md","reports/agent-runs/2026-07-bookticker-open-columns-v1/12-development-breakdown.md","reports/agent-runs/2026-07-bookticker-open-columns-v1/14-design-review-reconciliation.md","reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-b.md","reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md","reports/agent-runs/2026-07-bookticker-open-columns-v1/21-bookkeeper-task-b-verification.md","reports/agent-runs/2026-07-bookticker-open-columns-v1/60-test-output.txt","frontend/index.html","frontend/self-check.js","frontend/fixture/public-market-snapshot.json","git diff dff8b4785f43cd9fb82b7fab6214bc8c7d98ac88..0a383f0f8528591898f12690c371108e7582a27e"],"findings":[{"severity":"P3","title":"formatOpeningSpreadPct 正则隐式耦合后端两位小数量化格式","file":"frontend/index.html","line":1011,"evidence":"formatOpeningSpreadPct 使用 if (!/^-?\\d+\\.\\d{2}$/.test(s)) return '—' 要求恰好两位小数。","impact":"当前后端契约(ROUND_HALF_UP 两位、负零归一 0.00)下完全安全;仅在后端未来产出整数百分比或非两位值时会静默降级为 —。属于防御性隐式耦合,非当前缺陷。","recommendation":"无需修改。建议 docs/api/public-market-contract.md 固化 *_spread_pct 恒为两位小数字符串的约定,降低未来误判风险。"},{"severity":"P3","title":"fresh 状态下个别价格 null 的契约违反场景前端无防御","file":"frontend/index.html","line":1042,"evidence":"renderOpeningQuotesCell 仅在 status==='stale'||'unavailable' 时整体降级 —;fresh/incomplete 时按字段渲染,若 status=fresh 但某价 null 会显示该价为 — 而 spread 照常渲染。","impact":"后端冻结契约保证 fresh 必四价齐全(由 Task A deterministic test 保证),故当前后端不会触发;前端无责亦无需防御后端契约违反,不影响任何现有正确路径。","recommendation":"非阻塞,不改。fresh 价格完整性依赖后端 test_snapshot.py/test_book_ticker.py 保证,前端不应承担该契约校验职责。"}],"required_fixes":[],"residual_risks":["formatOpeningSpreadPct 正则与后端两位小数量化格式存在隐式耦合,需 contract 文档固化(非阻塞)","fresh 行价格完整性依赖后端 deterministic test 保证,前端不重复校验(非阻塞)","fixture 预览文件与 self-check 内存注入各维护一套 opening_quotes 数据,字段变更需两处同步(设计要求 P2-3)"],"next_action":"continue"}

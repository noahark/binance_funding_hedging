<!-- ============ RECEIPT（审计元数据；非任务内容） ============
status: pending             # pending | running | done | escalated
stage_id: 2026-07-private-account-ui-polish-v1
stage_branch: stage/2026-07-private-account-ui-polish-v1
node: implementation (round-2 / v1.1-ui-polish-2)
target_model: kimi          # implementer
role: implementer
role_chain: designer=Codex → implementer=Kimi → review-1=Codex(设计者复核实现保真) → review-2=Claude/Fable5(独立终审)
design_source: 10-design.md#"v1.1-ui-polish-2 Design Addendum" + 11-adr.md#ADR-7/8/9 (Fable5 design_review_addendum=ACCEPT)
delivery_base_sha: 4549227e9f6528787fb8e69b72c0cd7c585611f4
adapter_cmd: 用户以「读此文件并执行 PROMPT BODY」一行指令发至 Kimi 终端
next_dispatch: 实现交回 → Fable5 独立校验(diff/fingerprint/测试)→ Codex review-1 → Fable5 review-2
======================================================================== -->

--- PROMPT BODY（不可变任务正文，自此行以下原样执行） ---

你是 stage `2026-07-private-account-ui-polish-v1` 的 **implementer（Kimi）**。本轮实现
**v1.1-ui-polish-2 增量(item 5–10)**,折入本未合并 stage(round-1 的 value_usdt + 前 4 项
已在分支上,勿回退)。**权威设计**:`10-design.md` 的 `## v1.1-ui-polish-2 Design Addendum`
与 `11-adr.md` 的 ADR-7/8/9。先完整读这两处,严格照其 HOW 实现。

## 红线(违反即 review 判 REWORK/BLOCKED)

1. **只排 private_account 余额数组**:item 6 排序仅作用 `assemble_private_account()` 输出的
   `balances_unified`/`balances_spot`。**绝不修改** `sort_rows()`、市场 `rows` 顺序、`sort_basis`、
   `docs/api/public-market-contract.md` 的 `Row order (frozen)`。若既有测试未显式守护 rows 顺序,
   补一条回归断言。
2. **无契约字段/枚举/`schema_version` 变更**:`value_usdt`、`valuation.priced_at`、`checked_at`、
   `price_source` 均已存在,不得增删字段或改枚举。schema 文件不动。契约文档**仅允许**在 v0.4
   amendment 追加一句 additive-only 的 balances 展示顺序说明(见 Addendum §Contract Change Gate)。
3. **后端时间字段不变**:item 9 是纯前端合并;`assemble_private_account()` 继续输出
   `valuation.priced_at = checked_at` 与顶层 `checked_at`,不改后端。
4. **只读不下单**:不新增/改动 order/borrow/repay/transfer/websocket 等任何写行为、私有通道
   鉴权/TTL/HMAC 白名单、部署。
5. **前端零排序**:前端只按 payload 顺序渲染余额,不在前端排序;不用余额数量×价格重算,
   不反推 `total_value_usdt`。

## 允许改动文件(超出即越界)

- `backend/domain/snapshot.py`（仅 `assemble_private_account()` 加排序）
- `backend/tests/test_private_account_v1.py`（排序断言）
- `backend/tests/test_snapshot.py`（仅在需要钉市场 rows 顺序回归时）
- `docs/api/public-market-contract.md`（仅 additive balance-order 说明句）
- `frontend/index.html`、`frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`（仅 self-check fixture 需要文本/值时）

## 逐项实现要点(细节以 Addendum 为准)

- **item 5 行内折算**:余额金额行内追加 `【: 123.45 USDT】`,2 位小数 **ROUND_HALF_UP**,
  用 decimal-string helper(勿 `Number(x).toFixed(2)`);`value_usdt` null/缺失/空 → `【: — USDT】`;
  合法零 `"0.00000000"` → `【: 0.00 USDT】`;隐私开关同时遮蔽金额与折算值。勿复用 `formatPrice`
  作 2 位 USDT 格式化器。
- **item 6 后端排序**:按 Addendum 伪码 `(null-flag, -value, asset, idx)` 对 `unified_out`/`spot_out`
  排序(值 DESC、null 末位、asset ASC、同 asset 稳定)。pytest 覆盖 unified 与 spot 的降序、
  null-last、同值 asset ASC,并断言市场 rows 顺序不受影响。
- **item 7 删估值来源卡**:移除面板「估值来源」overview 卡;payload 保留 `price_source`;
  如 `priceSource` 变量仅服务被删卡片则一并删除(勿留死代码)。self-check 断言不再出现可见
  「估值来源」且 payload `price_source` 仍在。
- **item 8 删矛盾运行约束**:删侧栏页脚「公开行情 · 只读展示 · 不连接 Binance」(建议删整个
  `.sidebar-footer` block),不加暗示「无 key/不连接」的替代文案。self-check 断言页面不含
  「不连接 Binance」。
- **item 9 时点合一**:纯前端。verified=true 面板副标题 `只读资产视图` → `资产更新时间 <时间>`
  (取 `pa.checked_at`,缺失回落 `pa.valuation.priced_at`,再缺 `资产更新时间 —`);删「估值时点」
  「检查时点」两张卡。self-check 断言副标题含「资产更新时间」且不再出现「估值时点/检查时点」。
- **item 10 审计文案校准**:按 Addendum §Item 10 的**精确替换表**改写侧栏/顶栏/数据说明/
  `WARNING_CHINESE[0]`/`marginPublicNote`/verified=false 降级态文案。**实现前先核对代码里的
  原文字符串是否与替换表「原文」列一致**;若现存措辞不同,按替换表「新文」的**意图**改写
  (保留「只读=不下单/不划转」、删除「不连接 Binance/无 key 阶段/账户是公开数据」)。中文优先。

## 验证(全绿方可交回)

```
python3 -m pytest backend/tests/test_private_account_v1.py -q
python3 -m pytest backend/tests/test_snapshot.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
python3 -c "import json,jsonschema;jsonschema.validate(json.load(open('frontend/fixture/public-market-snapshot.json')),json.load(open('schemas/api/public-market/snapshot.schema.json')))"
```

## 交回物

- 代码/测试/文案改动 + `frontend/fixture` 如有更新。
- `20-implementation.md`：追加 v1.1-ui-polish-2 实现说明(逐项 what/where、排序 tie-break、
  文案替换清单、红线遵循声明)。
- `60-test-output.txt`：追加本轮五条命令的真实输出。
- 提交后回报 `head_sha`;**不要**自行改 `status.json` 的 review 字段或 fingerprint(由 bookkeeper
  复算落定)。契约变更门无新字段,故不需要新的 raw api-sample。

（RECEIPT 由 bookkeeper 更新,你不改本 prompt 文件。）

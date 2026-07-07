# 摸排任务派单：next-hourly 单次 assets 上限 / 服务内失效 root-cause（Gate B）

派单模型：Claude (Opus 4.8)
执行模型：Kimi (`kimi-code/kimi-for-coding`)
类型：只读端点摸排（Gate B）
落档去向：**追加**到既有摸排报告，不新建独立报告

- 追加正文：`reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi-borrow-rate-v2.md` 末尾新增「§9 next-hourly 批量上限 / 服务内失效补测」
- 新增样本：沿用既有样本目录 `reports/api-samples/private-account-v1-direction/borrow-rate-endpoint-survey-20260707T120945Z/sanitized/`，本次样本文件名前缀统一 `next_hourly_batch_limit_*`
- 更新 `evidence-index.json`：追加本次样本条目

执行红线（与上次一致）：零下单、零借还、零划转、零业务代码修改、零 git 提交；样本脱敏（不落 API key / secret / 签名 / 完整余额 / 完整可借数量）。

---

## 1. 为什么要这次摸排（背景）

Gate A live check 确认根因 A（截断）成立，但同一份实盘快照暴露了更强的信号：

```text
borrow_validation.chain_hit_tier   = 2
borrow_validation.chain_hit_source = rate_history
```

按 `_select_chain_tier`（`private_client.py:424`），tier② 只有在 **next-hourly（tier①）完全为空**时才命中。即：**服务内 next-hourly 此刻没出数据，链路已降级到只覆盖 1 个资产的 rate_history。** 66 个负费率候选中约 49 个 `-` 由此产生（截断只解释 16 个）。

关键差异：你上次（v2 报告）用 probe-script 发 **9 个**资产成功，但服务 `fetch_cost_leg_chain` 一次发的是 **50 个** comma-joined 资产（`private_client.py:312`），失败后被 `except PrivateEndpointError: next_hourly = {}`（`:319`）**静默吞掉**。

**本次唯一目标：确定服务内 next-hourly 为何返回空，并给出可落地的分批参数。**

---

## 2. 待验证假设（按可能性排序）

- H1（最可能）：next-hourly 单次 `assets` 有**资产数量上限**（≤50），超过即 400。
- H2：单次有 **URL / query 长度上限**，与资产数无关而与字符串长度有关。
- H3：失败是 **429 / -1003 权重限频**，而非参数问题（服务高频调用耗尽权重）。
- H4：**参数形态**问题（如 `isIsolated` 缺失/取值、资产名大小写、含服务候选里某个非法 asset 导致整批 400）。

请用下面的探测把 H1–H4 逐一证实或排除。

---

## 3. 探测任务

候选资产全集（66 个，取自 Gate A live check `borrow-cost-coverage-v2-gate-a-live.md` §3）：

```text
BLUR,0G,ACH,AGLD,AIGENSYN,ALGO,ARB,ARKM,ARPA,ATOM,AXS,BANANA,BARD,BCH,BEL,CETUS,EPIC,FET,FLUX,GALA,GRAM,GRT,GTC,HBAR,HEI,HOME,ID,INJ,JOE,JST,JUP,LA,LAYER,LQTY,ME,MINA,MIRA,OGN,ONG,OPG,OP,PENGU,PLUME,PROVE,RESOLV,RE,RPL,SEI,SENT,SLP,SOL,SPELL,TLM,TRUMP,TST,TWT,USDC,VANRY,VTHO,WIF,WLD,XLM,XRP,XVS,YFI,ZK
```

### T1 — 阶梯放大，定位数量上限（证 H1）
对 `GET /sapi/v1/margin/next-hourly-interest-rate?assets=<前 N 个>&isIsolated=false`，N 依次取：

```text
9, 20, 30, 40, 45, 50, 55, 60, 66
```

每次记录 §4 全字段。找出**开始失败的最小 N**（若全部成功，直接给结论「无数量上限，服务失败另有原因」）。

### T2 — 复现服务失败（证根因①机制）
精确复刻服务当前调用：取候选按 abs daily rate DESC 排序后的**前 50 个**（服务 `probed_assets` 口径），`isIsolated=false`，comma-joined 单次调用。记录是否复现 400 / 空返回，抓**确切 Binance code 与 msg**。

### T3 — 区分数量上限 vs 长度上限（证/排 H2）
若 T1 在某 N 失败：另构造「资产**个数相同**但**名字更短/更长**」的两组（例如都取 N 个，一组全是 2–3 字母短名，一组混入长名），比较是否同一 N 下一成一败。若与字符串长度相关而非个数 → H2 成立。同时记录失败请求的 **query string 字节长度**。

### T4 — 权重 / 限频排查（证/排 H3）
连续发若干次 T2（50 资产）调用，记录每次 `X-SAPI-USED-IP-WEIGHT-1M` 走势；确认失败是稳定的 400（参数）还是间歇的 429/-1003（限频）。

### T5 — 非法资产排查（证/排 H4）
若 T2 失败但 T1 小 N 成功：用二分法把 50 个资产切两半分别请求，定位是否**某个特定 asset**（如新上币 / 已下架 / bStock 混入）导致整批 400。记录该 asset 与 code。

### T6 — 安全分批参数（产出实现输入）
基于 T1–T5 结论，给出：

```text
next_hourly_max_assets_per_call   = <实测安全上限>
recommended_batch_size            = <安全上限留余量后的建议值>
batches_to_cover_66               = <ceil(66 / batch_size)>
total_weight_per_snapshot         = <批数 × 单次权重>
```

---

## 4. 每次调用必录字段

```text
probe_id
request_asset_count
request_query_bytes           # assets 参数字节长度
returned_asset_count
missing_assets                # 请求有、响应无
http_status
binance_code / binance_msg
X-SAPI-USED-IP-WEIGHT-1M
isIsolated 取值
结论标签: SUCCESS | LIMIT_HIT | WEIGHT_LIMITED | PARAM_ERROR | ILLEGAL_ASSET
```

---

## 5. 落档要求

1. 在 `endpoint-recon-kimi-borrow-rate-v2.md` **末尾追加**「§9 next-hourly 批量上限 / 服务内失效补测」，包含：
   - T1–T6 结果矩阵
   - 明确回答：**服务内 next-hourly 返回空的确切原因是什么？**（H1/H2/H3/H4 哪个成立，附 code 证据）
   - §6 T6 的分批参数建议（供 Task A2 直接取用）
2. 样本落 `sanitized/next_hourly_batch_limit_*.json`（成功/失败各留代表样本，脱敏）。
3. `evidence-index.json` 追加本次条目。
4. 报告尾部更新「下一步模型 / 任务」为回交 Claude/GPT 做实现方案定稿。

---

## 6. 验收（这次摸排算完成的标准）

- 能一句话回答 Gate B：**服务内发 50 资产的 next-hourly 为何空**，且有 Binance code 级证据。
- 给出可直接写进代码的 `recommended_batch_size` 与覆盖 66 资产的批数、权重预算。
- 不改任何业务代码、不提交 git、样本已脱敏。

---

本地北京时间: 2026-07-07 21:40 CST
下一步模型: Kimi（执行本摸排）
下一步任务: 完成 §9 补测并回交 Claude/GPT 定稿 borrow-cost coverage v2 实现

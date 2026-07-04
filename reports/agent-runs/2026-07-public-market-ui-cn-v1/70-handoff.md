# Handoff — 2026-07-public-market-ui-cn-v1

## Stage status

`implementing` → 即将 `review_1`（Task A/B/C 全部实现并验证完毕；本提交 H_C 收尾）。
Controller **不**声明最终验收（`can_accept_final=false`）；终态目标 `stage_accepted_waiting_user`。

## Prerequisite (satisfied)

`2026-07-public-market-impl-v1` + `2026-07-public-market-bstock-alias-v1` 均已获用户最终验收
（commit `6d8c0c4`）。本阶段 base 锚定 H_intake = `b84a342`（intake/task/design/status +
live funding-semantics evidence）+ `d3d6e7c`（Fable5 预写 Task B 派工 prompt，intake/design 范畴）。

## Delivered tasks

| Task | Owner | Head | Scope | Key result |
|---|---|---|---|---|
| A — lastFundingRate warning semantic amendment | `claude_glm` | `dba4c12` | `snapshot.py` (CONTRACT_WARNINGS[1] string only) + contract doc + tests | 新实证文案；snapshot.py diff 仅 -1/+1；54 passed |
| B — frontend CN-first + column merge + flags de-noise | `kimi` | `0fd0d17` | `frontend/**` | 字符串移位格式化；列合并；数据说明区；self-check 14/14 |
| C — integration verification | `claude_glm` (controller, no product code) | H_C（本提交） | `20-implementation.md`/`60-test-output.txt`/`11-adr.md`/`70-handoff.md` | rows 与 548ae0d 逐字段一致；schema VALID；not BLOCKED |

## Evidence (intake, read-only during stage)

`reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/` — `evidence-index.md`
（sha256 of raw）+ `verify-funding-semantics.py`（offline replay, exit 0 = PASS）证明
`premiumIndex.lastFundingRate` 是本周期实时预估值（周期中段 ETHUSDT/SOLUSDT 预估值 ≠ 已结算记录；
15 分钟内漂移）。

## Hard constraints honored

- 无 live HTTP（intake 证据已抓齐；A/B/C 全程 offline）；无 key/签名/私有端点/order/borrow/
  repay/transfer/websocket。
- rows 结构与数值零变化（Task C 逐字段对比 548ae0d PASS）；API 载荷唯一变化是 `warnings[1]` 文本。
- `classify.py` / `normalize.py` / `snapshot_service.py` / `schemas/**` 零改动。
- 前端费率百分比格式化为纯字符串移位（`parseFloat`/`Number×100` 禁用；`formatFundingRate` 验证）。
- UI 中文优先（主表无英文枚举直出；USDT/bStock/API/symbol 等技术词保留）。
- `reports/api-samples/**` 全部只读。

## Review routing (per AGENTS.md + status.json)

- **review-1**（cross-review）：
  - Task A → **Kimi**（实现者 `claude_glm`，cross-review 选 Kimi）。
  - Task B → **全新只读 Claude-GLM 会话**（实现者 `kimi`；fresh session，禁止复用 controller/Task A transcript）。
- **review-2**（final gate）：**Codex/GPT `gpt-5.5`**（`codex exec -s read-only`），
  `reviewer_prior_involvement = direction_synthesis`（strong-reviewer disclosure override）。
  Anthropic/Fable5 本阶段为 designer/breakdown author（design involvement）→ 排除出 review-2 池；
  两实现方（`claude_glm`/`kimi`）hard-ban。Codex 无本阶段设计/拆分/代码参与（唯一先前参与是覆盖契约阶段的
  user-approved direction synthesis）。与前两阶段同径。

## Fingerprint protocol (single, unchanged)

`diff_fingerprint = head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/<stage-id>/status.json")`

- base_sha = `b84a342`（全程不变）。
- stage-level top-level fingerprint 在 H_C 后绑定（status.json.head_sha / diff_fingerprint）。
- status.json 排除在 hash 外。

## Known notes (transparent, non-blocking)

- H_intake 物理上是 `b84a342` + `d3d6e7c` 两个提交（`d3d6e7c` = Fable5 预写 Task B 派工 prompt，
  intake/design 范畴，无产品代码）。base_sha 按用户指令锚定 `b84a342`，故 `d3d6e7c` 的 intake 产物
  随 stage diff 携带（合法 intake/design 范畴，非产品代码；详见 `status.json.diff_fingerprint_note`）。
- 11-adr.md：`00-task.md` 称本阶段不设 ADR，但 `validate-stage.py` gate 要求该文件存在，故创建
  minimal ADR 记录「无新架构决策」+ 几条过程决策（见 `11-adr.md`）。

## Next step

`validate-stage.py --phase pre-review`（需 clean tree）→ status `review_1` → 派 review-1（A→Kimi，
B→fresh read-only Claude-GLM）→ review-2（Codex）→ `--phase pre-accept` → `stage_accepted_waiting_user`。
Controller 不声明最终验收，等用户外部 review。

本地北京时间: 2026-07-04 13:36 CST
下一步模型: review-1（cross-review）

---

## Rework round 1（2026-07-04,用户指示)

用户外部复核(Fable5)确认上轮全部硬性核验通过,但发现 P3 残留(资产标签列
CRYPTO/UNKNOWN 枚举直出;侧栏 Funding Hedge 英文),用户指示走一轮 P3,并
同时新增三项 UI 决策(见 status.json.user_decisions):

1. 状态枚举展示改「英文枚举(中文解释)」——路由/资产/负费率三列 + 筛选下拉,
   **取代上一轮"主表纯中文"规则**;
2. 删除「加载离线 fixture」按钮及代码路径(fixture 文件与 self-check 保留);
3. 前端 60s 自动刷新(对齐后端 TTL)+ 市场表旁倒计时;手动刷新保留并重置。

派工:`fix-start-prompt-ui-round1.md`(全部 frontend/**,Kimi)。上轮
review-1/review-2 ACCEPT(head 9b0e62c)原样保留;fix 后重审并绑定新 head。
status=fixing,rework_count=1/3。

本地北京时间: 2026-07-04 15:52 CST
下一步模型: Claude-GLM (controller) → Kimi (fix 实现)
下一步任务: controller 原样转发 fix-start-prompt-ui-round1.md 给 Kimi;完成后
H_fix → 指纹重算 → review-1(fresh GLM)→ review-2(Codex 重绑)→
stage_accepted_waiting_user。

---

## Rework round 2 + 最终验收（2026-07-04，stage closed）

轮一 fix（H_fix `7592b2c`）落地四项 UI 决策后，review-1 round-1（fresh GLM）
ACCEPT，但 review-2 round-1（Codex）REWORK，1× P2：手动刷新只重置了倒计时
显示（`nextRefreshAt`），未重置实际 60000ms 自动刷新计时器（全文无
`clearInterval`），显示与真实下次 fetch 不同步。

轮二 fix（H_fix2 `ee9296c`，Kimi）：`loadApi()` finally 在重置 `nextRefreshAt`
后 `clearInterval` 旧 timer 并重建 60000ms interval，倒计时与实际拉取共享同一
目标时刻；1s countdownTimer 保持独立；`startAutoRefresh()` 不变。self-check
新增 setInterval/clearInterval mock 断言。产品代码 diff 仅 6 行。

评审链：review-1 round-2 ACCEPT（`cbdaddf`）+ review-2 round-2 ACCEPT
（`a76dd23`），双双绑定指纹 `ee9296c:f4637f8a…`。

**最终验收**：用户于 2026-07-04 验收通过（commit `d91a6cf`，status=accepted）。
Fable5 外部复核：指纹独立复算一致；P2 修复逻辑原位确认；4 项 UI 决策逐项
grep 验证；保护函数（formatFundingRate/formatBeijing*）在 9b0e62c..ee9296c
全程零改动；`node frontend/self-check.js` 全 PASS；pre-accept gate PASSED。
P3 finding `asset_tag_enum_direct_display` 关闭（resolved，轮一已修）。
rework_count 终值 2/3。

## Carry-forward open items（验收后新增两条事实核查，均不阻塞）

沿承前阶段：bStock 与美股 1:1 等价性、现货交易时段 vs 永续 7×24、非 USDT
计价支持——排至开仓规划阶段。本阶段验收后用户问答补充落档：

1. **杠杆候选字段的验证边界（重要）**：`isMarginTradingAllowed` 是现货交易
   对级公开标志，不区分经典杠杆全仓/逐仓，更不覆盖统一账户（Portfolio
   Margin）的可借/质押规则。私有借币验证（`PRIVATE_BORROW_VALIDATION_REQUIRED`
   路径）届时必须按**用户实际账户类型**查对应私有接口（经典全仓
   `/sapi/v1/margin/allPairs` vs 统一账户接口族），不得拿经典杠杆清单套
   统一账户。
2. **TRADIFI 覆盖观察（2026-07-04 live）**：TRADIFI_PERPETUAL 合约共 118 个
   （全 TRADING、全 USDT 计价），仅 15 个有 B 后缀 bStock 现货腿（AMD/CRCL/
   EWY/INTC/LITE/META/MSFT/MSTR/MU/NVDA/PLTR/QQQ/SNDK/SPCX/TSLA，现货全部
   isMarginTradingAllowed=true）；其余 103 个（含 AAPL/GOOGL/SPY、商品类
   XAU/XAG 等）无现货腿 → PERP_ONLY_EXCLUDED。现货侧 baseAsset 以 B 结尾的
   USDT 对共 23 个，其中 8 个为普通加密货币假阳性（ARB/BNB/SHIB/TRB 等），
   印证别名规则必须由 TRADIFI 合约侧正向驱动。bStock 现货上架滞后于合约，
   后续补挂后快照会自动升级路由，无需改代码。

本地北京时间: 2026-07-04 18:14 CST
阶段终态: accepted（stage closed）
下一步: 用户与 Fable5 讨论下一轮开发目标;若为前后端双任务阶段,按
docs/parallel-development-mode.md（ADOPTED-TRIAL）由 Fable5 出全套
R9 dispatch packet。

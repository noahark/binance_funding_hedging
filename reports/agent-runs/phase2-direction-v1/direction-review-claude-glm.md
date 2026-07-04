# Phase 2 方向草案独立评审（落档）

- **评审对象**：`docs/phase2-direction-draft.md`（DRAFT-1.2, commit `f1297a5`）
- **评审者模型**：`claude_glm` = 智谱 **`glm-5.2[1m]`**（zhipu_glm，**非 Anthropic**；经本地 `claude-glm` 适配器调用）
- **角色**：独立只读需求评审者（未参与本草案的起草 / 设计 / 实现）
- **评审时刻**：2026-07-04 19:41:23 CST
- **约束遵守**：只读评审，未做任何签名 / 私有 API 调用；事实核查仅用匿名公开文档检索 + 仓库内既有证据（`reports/api-samples/**` 只读）。
- **Verdict**：**REWORK**（阻断项为 P1：§4 账户类型与端点族事实错配）

---

## 一、逐条回应（评审重点 1–7）

### 1. §3 安全红线修订——基线是否充分？
**结论：方向正确，但「白名单强制 + 单测断言 + 读通道自检 + 证据脱敏」四项不构成充分基线，缺最关键的「单一签名出口 + 出站审计」。**

在「保留全权限 key + IP 白名单已绑定」的前提下，IP 白名单只约束「key 被另一台机器滥用」，**不约束白名单机器上代码自身的行为**——草案 §3.3 自己已承认这点。那么主防线必须能证明「运行时没有任何代码路径绕过白名单直接发签名请求」。当前四项只能证明「白名单常量正确 + 白名单内调用 fail-fast」，**不能证明不存在第二个签名出口**。缺：

- **单一签名出口（架构约束）**：`private_client` 必须是全仓库唯一构造 HMAC-SHA256 签名的位置。配套单测：`grep -RniE 'hmac|HMACSHA256|signature' backend` 断言命中点仅 `private_client.py`。否则任何一处 `httpx.get(..., params=signed)` 都能在白名单之外发任意签名请求，单测白名单形同虚设。
- **白名单粒度 = (method, exact-path) 二元组**，不是 path 前缀。前缀白名单 `/sapi/v1/margin/` 会放行 `POST /sapi/v1/margin/loan`。单测三态：白名单内 `(GET,/sapi/v1/margin/allPairs)` 通过、白名单外任意 path raise、**白名单内 path 的非 GET method 也 raise**（method 维度）。
- **出站审计日志**：记录每一次签名请求的 `(method, path, timestamp, http_status)`（不含 key/sign/recvWindow）。这是「主防线」从静态常量升级到运行时可观测的最后一环。
- **降级路径单测**：key 缺失 → 优雅降级为 Phase 1，该分支也要有测试，防降级时抛异常阻塞快照。
- **脱敏时机**：账户级数据须「**抓取即脱敏**」，不落任何明文中间文件；脱敏规则入库 + 单测断言落档 JSON 不含已知账户标识字段名（`uid/email/asset/balance/free/locked/amount` 等）。

### 2. §8 Q1——统一账户下 `allPairs` 作为市场级可借信号是否失真？2a/2b 切分是否成立？
**结论：「市场级 vs 账户级」切分逻辑成立，`allPairs` 作为市场级候选信号不失真——但 §4 的端点族分叉前提存在事实错误（见 P1），必须先纠正才能定 2b 端点。**

- `GET /sapi/v1/margin/allPairs` 返回的是「哪些交易对开通了全仓杠杆」（市场级、与账户模式无关），其 base asset 即「该资产在经典全仓杠杆体系可借」的候选信号。统一账户（Unified Account, UA）仍沿用 `sapi` margin 体系，`allPairs` 语义不变。**作为「市场级可借候选」不失真。**
- 账户级失真（该资产在该账户下实际可借额度、是否触发统一账户的统一保证金约束）由 Phase 2b 的 `maxBorrowable` 回答——**这正是 2a/2b 切分的正当依据，切分成立。**
- **致命前提问题（P1）**：草案 §4 把「统一账户（非专业版）」对应到 `/papi` 端点族，是错的。Binance 体系里 `/papi` 是 **Portfolio Margin（组合保证金，专业版）专用**；**Unified Account（非专业版统一账户）仍走 `/sapi`**。`maxBorrowable` 在两族下都有，但语义/抵押范围不同（sapi 只看保证金账户余额，papi 看全组合）。用户自述「非专业版」→ 极可能是 UA → **2a 和 2b 都应走 `/sapi`，根本不存在 sapi/papi 分叉**。若用户实为 PM，则 PM 下**没有 `allPairs` 的干净市场级等价物**（PM 可借性由 `maxBorrowable`+`collateralRate` 直接给出），2a 的「市场级清单」概念本身要重设。**→ 这一项必须由用户澄清账户到底是 UA 还是 PM，是阻断性的。**

### 3. §8 Q7——借币利率端点选型
**结论：Phase 2a（市场级）正确候选是 `GET /sapi/v1/margin/crossMarginData`；但草案漏讲了「费率表 × VIP 等级」的语义陷阱，且字段名/取档规则须实抓后冻结。**

- `crossMarginData` 返回全仓杠杆各资产「按 VIP 等级分档的借币日利率 + 借款额度上限」表，对应 `binance.com/en/margin-fee` 页面，**是纯市场级、与账户无关**——正好匹配 §4 想要的「市场级利率」。首选。
- **语义陷阱（必须写进契约）**：`crossMarginData` 返回的是**整张费率表**（asset × vipLevel → rate），取出「用户实际适用利率」需叠加用户 VIP 等级（账户级信息）。所以 2a 落档的 `base_daily_interest` 只能是「市场基准档（如 VIP0 或当前公开显示档）」，**须在契约里写死取哪一档**；用户实际支付利率留 2b。草案目前没说取档规则 = 留了歧义。
- 候选优先级：`crossMarginData`（市场级表，2a 首选）＞ `/sapi/v1/margin/interestRateHistory`（带 `vipLevel` 的历史利率，更适合 2b 账户级）。
- 强制要求：**实抓 + 脱敏后落 raw 证据**（契合 Hard Gate「契约修订须附 raw 样本」；这里是 raw 私有签名样本，须脱敏）。注意有资料显示 2024-03 部分旧 `sapi` 接口被调整，`crossMarginData` 当前字段结构以实抓为准。

### 4. §5——枚举细化 vs 新增独立字段
**结论：新增独立字段代价更低。推荐结论——`negative_funding_status` 枚举零改动（或仅追加不重命名），可借性结论全部放 `margin_private` 块。**

- `negative_funding_status` 是**有序不可重排的优先级枚举**（`docs/api/public-market-contract.md` 明示）。把 `PRIVATE_BORROW_VALIDATION_REQUIRED` **重命名/拆分**为 `BORROW_LISTED_PENDING_ACCOUNT_CHECK` / `BORROW_NOT_LISTED` 是**破坏性契约变更**：既改了枚举集，又要重文档化优先级位次，且这两个新值与现有 `DISABLED_*` 不在同一抽象层（一个是「待验态」，一个是「已禁用原因」），混入会污染优先级语义一致性。代价最高。
- 更干净：枚举保留 `PRIVATE_BORROW_VALIDATION_REQUIRED`（待验态不变），可借性结论放草案已有的 `margin_private` 块（`verified`/`cross_pair_listed`/`base_daily_interest`/`checked_at`）。前端按 `margin_private` 渲染 badge，**`classify.py` 完全不动**——与草案 §5「分类层纯函数、不发请求」的意图更一致。
- 折中：若团队坚持让枚举自身表达「市场级已验不可借」终态，**只追加一个新值 `BORROW_NOT_LISTED`**（放 `PRIVATE_BORROW_VALIDATION_REQUIRED` 同层或之后，不动前几位优先级），**绝不重命名现有值**。

### 5. §6——比较器数值化是否接受？默认方向？
**结论：接受数值化可行，但更推荐「纯字符串十进制比较器」（零精度风险、与 display 同源）；默认排序接受「绝对值降序」。**

- fundingRate 8 位小数在 double 安全区，数值化比较技术上安全。
- 但既然 display 层已在 string-shift，**比较器用同源字符串十进制比较最省事**：逻辑统一、零精度假设、评审零争议。代价不大，倾向此项。
- 无论哪种，**必须加回归单测**：比较器对所有合规 fundingRate 字符串的排序结果 == 字符串十进制比较结果（负费率、0、最大正费率、前导零、不同小数位的边界集），防未来精度扩展导致分叉。
- 默认「绝对值降序」（机会导向）合理——**接受**。三态切换（升/降/默认无序）。注意刷新后行集合可能增删，排序键须对新行容错、按当前方向插入正确位置不报错。

### 6. §7——双任务并行（parallel-mode 首试）vs 拆两个串行阶段
**结论：耦合度可支撑并行，但并行首试的真正风险在「契约先冻结」的纪律执行，不在任务耦合。建议：采纳并行 + 利率字段后置冻结。**

- Task A（私有通道 + `margin_private` 块）与 Task B（排序 + 私有展示）的接口契约（块结构、字段可空性、利率字符串格式）**可在设计期冻结**，满足 `docs/parallel-development-mode.md §1` 适用条件 2。Task B 的「排序」部分**零依赖**，可完全并行先行。
- 关键耦合风险 = `margin_private` 字段在实现中漂移 → B 侧渲染错。这正是 parallel-mode **R3**（跨任务字段改动不得本地 fix）要守的。
- **强化为硬条件**：H_intake 的 `10-design` 必须冻结 `margin_private` schema 草案 + fixture 样例（草案 §7 已提，须从「建议」升为「硬门」）。
- **利率字段后置**：§8 Q7 利率端点未实抓，字段结构存疑 → `base_daily_interest` 先不冻结，B 侧利率列做「待 A 实抓后补」的后置项，避免并行期契约漂移。排序 + 私有验证展示仍可并行先行。
- 不必拆成两个串行阶段（排序耦合度低，同阶段并行即可）；但若对首试无信心，草案 §7 的「排序先行单任务阶段」是可接受的保守退路。

### 7. 其余缺陷/遗漏/过度设计
- **遗漏·限频与错误处理**：草案只说「请求失败 `verified:false` 降级」，未设计 Binance `sapi` 签名端点的 **weight 预算**（`crossMarginData` weight 较高）、`-1003`/429 限频退避、签名 timestamp 偏移窗口。须补。
- **遗漏·`checked_at` 语义**：是「请求成功时刻」还是「利率数据生效时刻」？`crossMarginData` 可能不带数据时间戳，`checked_at` 只能是请求时刻——须注明，防前端误展示为数据时刻。
- **不对称·缺 `source` 字段**：`margin_public` 有 `source:"unverified"`，`margin_private` 无对应 `source`。建议补 `source:"cross_margin_pair_list"`，便于前端/测试追溯来源端点，与 `margin_public` 对称。
- **过度设计·`papi base_url` 配置**：若账户确认为 UA，`papi` 用不上，先只配 `sapi`，避免无用配置项。
- **脱敏遗漏·query 整体剥离**：§3.4 说 key/sign/timestamp 不入档——好，但 `private_client` 落档时须**整体剥离 query string**（含 `recvWindow`），不只剥离三个参数。
- **赞同项**：§3.2「交易类操作永久禁止、脱离 phase」提升为跨阶段 invariant，正确；§5「分类层纯函数、私有结果作参数进入」正确（配合建议 4，`classify.py` 零改动）。

---

## 二、Findings

| 级别 | 标题 | 一句话缺陷 | 具体修法 |
|---|---|---|---|
| **P1** | §4 账户类型与端点族错配 | 「统一账户（非专业版）」被推导为走 `/papi`，但 `/papi` 是 Portfolio Margin（专业版）专用，UA 应走 `/sapi`，前提性事实错误，动摇 2b 端点选型与 2a 市场级清单概念。 | 先由用户澄清账户是 UA 还是 PM；UA → 2a/2b 全走 `/sapi`，删除 §4 的 sapi/papi 分叉论证；PM → 2a「市场级清单」概念重设。修订 §4 后再进入实现。 |
| **P2** | §3 主防线缺「单一签名出口 + 出站审计」 | 白名单常量 + 单测无法证明不存在绕过白名单的第二个签名出口，全权限 key 下这是主防线漏洞。 | 架构约束 `private_client` 为唯一 HMAC 出口 + grep 单测；白名单改 `(method, exact-path)` 二元组 + method 维度单测；增出站审计日志。 |
| **P2** | §5 枚举重命名属破坏性契约变更 | 把 `PRIVATE_BORROW_VALIDATION_REQUIRED` 拆/改名为两个值，改枚举集 + 扰动优先级语义，代价最高。 | 枚举零改（可借性放 `margin_private` 块）；若必须动，只追加 `BORROW_NOT_LISTED`，不重命名。 |
| **P2** | §8 Q7 利率取档规则缺失 | `crossMarginData` 返回 VIP 分档费率表，草案未规定 `base_daily_interest` 取哪档，留歧义。 | 契约写死取「市场基准档（VIP0/公开显示档）」并标注；用户实际利率留 2b；实抓后冻结字段。 |
| **P3** | §5 缺限频/weight/timestamp 错误处理 | `sapi` 签名端点 weight 预算、`-1003`/429 退避、签名时间窗口未设计。 | 补 weight 预算 + 限频降级策略 + timestamp 偏移处理。 |
| **P3** | `margin_private` 与 `margin_public` 不对称 | 缺 `source` 字段；`checked_at` 语义未注明。 | 补 `source` 字段；注明 `checked_at`=请求时刻。 |
| **P3** | 脱敏范围 + papi 配置过度 | 脱敏未含 `recvWindow` 等全部 query；`papi base_url` 在 UA 下无用。 | 落档整体剥离 query string；UA 下不配 papi。 |

---

## 三、总体 Verdict

**REWORK**

阻断项为 P1（账户类型/端点族事实错误）——它是 §4、评审重点 2/3 的共同前提，且与用户已确认的「非专业版」自相矛盾，必须先澄清事实、修正 §4，才能冻结 Phase 2b 端点选型与 2a 市场级清单语义。P2/P3 为同轮 required fixes，可在修订草案时一并吸收。

**Required fixes（进入实现前必须解决）：**
1. [P1] 用户澄清账户 = UA 还是 PM；据此修正 §4 端点族（UA→全 `/sapi`，删除 sapi/papi 分叉）。
2. [P2] §3 补「单一签名出口」架构约束 + grep 单测 + `(method, exact-path)` 白名单 + 出站审计。
3. [P2] §5 枚举不重命名；可借性结论放 `margin_private` 块。
4. [P2] §8 Q7 写死利率取档规则 + 实抓冻结。
5. [P3] 补限频/weight/timestamp 处理、`source` 字段、`checked_at` 语义、脱敏整体剥离 query、UA 下不配 papi。

---

## 四、给 Fable5 的修订启动文案（DRAFT-1.3）

> 修订目标：吸收独立评审 REWORK，产出 DRAFT-1.3。首要阻塞项是 §4 账户类型事实。
>
> 1. **先向用户求证一项事实**（不可由模型臆断）：账户是「统一账户 Unified Account（非专业版，走 `/sapi`）」还是「组合保证金 Portfolio Margin（专业版，走 `/papi`）」？用户原文「统一账户模式（非专业版）」最可能指 UA。求证后据实修正 §4：UA → 2a/2b 全部走 `/sapi`，删除「sapi vs papi 端点族分叉」论证，2b 账户级用 `/sapi/v1/margin/maxBorrowable`；PM → 重设 2a「市场级清单」概念（PM 无 allPairs 等价物，可借性由 maxBorrowable+collateralRate 直接给出）。
> 2. §3 主防线补三层：(a) `private_client` 为全仓库唯一 HMAC 出口 + `grep` 单测断言；(b) 端点白名单改为 `(method, exact-path)` 二元组 + 三态单测（白名单内 GET 通过 / 白名单外 raise / 白名单内 path 的非 GET 也 raise）；(c) 出站审计日志记录每次签名请求的 `(method,path,timestamp,http_status)`。
> 3. §5 契约演进改为「枚举零改动」：`negative_funding_status` 保留 `PRIVATE_BORROW_VALIDATION_REQUIRED`，可借性结论全部放 `margin_private` 块（`verified`/`cross_pair_listed`/`base_daily_interest`/`checked_at`/`source`），`classify.py` 不动。若团队坚持枚举表达「不可借」终态，仅追加 `BORROW_NOT_LISTED`，禁止重命名。
> 4. §8 Q7：2a 利率首选 `GET /sapi/v1/margin/crossMarginData`（市场级费率表）；契约写死 `base_daily_interest` 取「市场基准档」并标注取档规则，用户实际利率留 2b；**实抓脱敏后落 raw 证据再冻结字段**。
> 5. 补：§3 限频/weight/timestamp 处理；`margin_private` 加 `source` 字段对称 `margin_public`；注明 `checked_at`=请求时刻；脱敏整体剥离 query string（含 recvWindow）；UA 确认前不配 `papi base_url`。
> 6. §6 排序比较器优先实现纯字符串十进制比较（与 display 同源）+ 回归单测；默认绝对值降序，三态切换，刷新后对新行容错。
> 7. §7 并行采纳，但 H_intake `10-design` 冻结 `margin_private` schema+fixture 为硬门；利率字段后置冻结，排序+私有展示并行先行。

---

## 五、事实核查 Sources

匿名公开文档检索 + 仓库内既有证据：

- [Binance – Portfolio Margin API（PAPI endpoints，PM 不能用 sapi 做 margin order/loan）](https://www.binance.com/en/support/faq/detail/ccf04078d7774d479f11ae15c4f56081)
- [python-binance issue #1384（/um/order vs /order，sapi↔papi 结构差异）](https://github.com/sammchardy/python-binance/issues/1384)
- [Binance Margin Trading Change Log（2024-03 部分 sapi 接口调整）](https://developers.binance.com/docs/margin_trading/change-log)
- [Query Margin Interest Rate History（`/sapi/v1/margin/interestRateHistory`，带 vipLevel）](https://developers.binance.com/docs/margin_trading/borrow-and-repay/Query-Margin-Interest-Rate-History)
- 仓库内证据：`reports/api-samples/public-market-contract-v2/.../raw/sapi-v1-margin-allPairs-nokey.json`（`{"code":-2014,"msg":"API-key format invalid."}`，证实 Phase 1 未用 key）；`docs/api/public-market-contract.md`（现行冻结契约）；`backend/domain/classify.py`（优先级序列）。

---

本地北京时间: 2026-07-04 19:41:23 CST
评审模型: claude_glm = 智谱 `glm-5.2[1m]`（zhipu_glm，非 Anthropic；经本地 `claude-glm` 适配器）
下一步模型: human（用户）——P1（账户类型 UA vs PM）属人工事实澄清门；用户答复后回 Fable5 出 DRAFT-1.3
下一步任务: 用户确认账户为 Unified Account 还是 Portfolio Margin；据此 Fable5 修订 §4 端点族并吸收 P2/P3，产出 DRAFT-1.3 再评审

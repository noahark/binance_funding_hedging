# Phase 2 方向草案评审意见

**评审模型**：Kimi / moonshot_kimi / `kimi-2.7`  
**评审对象**：`docs/phase2-direction-draft.md`（DRAFT-1.2，commit f1297a5）  
**评审时间**：2026-07-04 19:17 CST  
**评审性质**：只读方向评审，不写代码、不调用签名 API、不修改契约产物。

---

## 总体结论

本方向草案 DRAFT-1.2 对 Phase 2 的目标、范围、安全红线有清晰框架，但在**统一账户（非专业版）下 `/sapi` 经典杠杆端点的实际可用性**、**全权限 API key 的纵深防御基线**、**借币利率端点与 VIP 行选择规则**三个关键点上证据不足，尚不能直接冻结为 stage intake。

**Verdict：REWORK**

评审人在本地用匿名公开 GET 验证了 `/sapi/v1/margin/allPairs`、`/sapi/v1/margin/isolated/allPairs`、`/sapi/v1/margin/crossMarginData`、`/sapi/v1/margin/interestRateHistory` 均返回 `{"code":-2014,"msg":"API-key format invalid."}`，确认这些端点确实需要签名，但统一账户下调用后返回什么结构、是否有效，必须用用户 key 实抓后才能决定设计。

---

## 逐条回应

### 1. §3 安全红线修订：是否充分？

**结论：不充分。** 在用户保留全权限 key 的前提下，仅靠代码层端点白名单 + 单测 + 读通道自检，纵深防御太薄。

必须补充：
- `private_client` 显式限制 `METHOD=GET`，任何非 GET 请求直接 raise；
- 单测覆盖白名单外路径、非 GET 方法、以及含交易语义的查询参数；
- 签名请求审计日志（只落档 endpoint/method/timestamp，**不含 key、secret、signature、timestamp 参数**）；
- 在 ADR 中写明残余风险：IP 白名单只能防外泄，不能防白名单机器上的代码 bug 或 prompt 注入。

### 2. §8 Q1：2a/2b 切分是否成立？

**结论：逻辑成立，但前提是 `/sapi` 端点在统一账户（非专业版）下能返回有效数据。**

`/sapi/v1/margin/allPairs` 给出的是“经典全仓杠杆对在列”，这是**必要而非充分**条件；统一账户的实际可借性由 `/papi` 账户级端点决定。因此 2a 的产出应命名为 `cross_pair_listed`（已在草案中），并明确不表示统一账户可借。

**风险**：如果统一账户禁用或清空 `/sapi` 经典杠杆响应，则 2a 设计不成立，必须直接走 `/papi` 账户级验证（即 2b）。需要在 H_intake 前用用户 key 实抓并脱敏落档。

### 3. §8 Q7：借币利率端点选型

**结论：优先使用 `GET /sapi/v1/margin/crossMarginData` 作为 `base_daily_interest` 来源；次选 `GET /sapi/v1/margin/interestRateHistory` 的最新点。**

验证方式：
1. 用用户 key 实抓 `/sapi/v1/margin/crossMarginData`；
2. 脱敏后落档 `reports/api-samples/2026-07-private-market-discovery-v1/...`；
3. 字段矩阵记录 raw JSON path、类型、单位、VIP 行结构；
4. 明确 VIP 行选择规则：默认取 VIP 0（保守），或取账户实际 VIP 等级（需额外账户级调用，属于 2b）。

若 crossMarginData 因账户权限不可行，再 fallback 到 interestRateHistory。

### 4. §5：negative_funding_status 枚举细化 vs 新增独立字段

**结论：枚举扩展代价更低。**

理由：
- 现有 `negative_funding_status` 已承载前端 badge 文案与优先级，新增独立字段需要前端同时消费两个字段并自行组合；
- 枚举扩展只需更新 schema、`classify.py`、frontend badge 映射，保持单一决策字段。

建议最终优先级序列（不可重排）：

```
1. PERP_ONLY_EXCLUDED        -> DISABLED_PERP_ONLY
2. asset_tag == BSTOCK       -> DISABLED_BSTOCK
3. SPOT_ONLY_CANDIDATE       -> DISABLED_SPOT_ONLY
4. MARGIN_SPOT_CANDIDATE + 不在 cross 清单 -> BORROW_NOT_LISTED
5. MARGIN_SPOT_CANDIDATE + 在 cross 清单   -> BORROW_LISTED_PENDING_ACCOUNT_CHECK
```

### 5. §6：排序比较器数值化是否接受？默认方向？

**结论：可接受，但建议使用纯字符串十进制比较器以避免浮点争议。**

`last_funding_rate` 为 8 位小数字符串，double 比较在精度上基本安全，但任何浮点比较都会成为后续 review 的争议点。字符串比较（先符号 → 整数位长度 → 小数位字典序）更稳。

默认排序方向：按绝对值降序可接受，但 UI 必须明确提示“按资金费率绝对值降序”，避免用户误以为只看正或只看负。

### 6. §7：双任务并行 vs 串行

**结论：不建议本阶段首次试运行并行模式。**

Task B 依赖 `margin_private` 块、新枚举、利率字段，而 Task A 的端点验证结果可能改变契约形状。若强行并行，一旦实抓发现 `/sapi` 不可用或字段结构不同，将触发 `parallel-development-mode.md` R3 “不得本地 fix 接口契约” 的升级，导致循环停摆。

建议拆为两个串行 stage：
- Stage `2026-07-private-market-discovery-v1`：Task A backend + 契约修订；
- Stage `2026-07-public-market-sort-v1`：Task B frontend 排序 + 私有验证结果展示。

这样每个 stage 都是单任务，风险低，也符合 `stage-delivery.yaml` 默认流程。

### 7. 其他设计缺陷 / 遗漏

- **阶段分类**：引入签名端点和 API key 属于安全/契约里程碑，应明确为 **MILESTONE**，触发 direction panel 与合成。
- **契约版本**：`docs/api/public-market-contract.md` 应从 v0.1 升级为 v0.2，并增加 Phase 2 amendment 变更记录。
- **`margin_private` null 语义**：需区分“未启用/失败”（`verified:false`，其余 `null`）与“已验证但不在列”（`verified:true, cross_pair_listed:false, base_daily_interest:null`）。
- **脱敏细节**：私有客户端的 request log 与 api-samples 落档前必须清洗 `signature`、`timestamp`、`recvWindow` 等签名参数，并提供可复核的脱敏脚本。

---

## Findings（按严重度排序）

### P1 - Unified Account 下 `/sapi` 经典杠杆端点适用性未经验证

- **文件**：`docs/phase2-direction-draft.md` §4、§5
- **缺陷**：草案假设 `/sapi/v1/margin/allPairs` 与 `/sapi/v1/margin/crossMarginData` 可作为 2a 市场级数据源，但未用用户 key 实抓验证统一账户（非专业版）下是否返回有效数据。
- **影响**：若统一账户禁用或清空这些端点，2a/2b 切分根基不成立，前端会基于错误契约开发。
- **修法**：H_intake 前必须实抓并脱敏落档；若返回空/错误，改走 `/papi` 账户级直接验证，取消 2a。

### P1 - 全权限 API key 下的安全基线不足

- **文件**：`docs/phase2-direction-draft.md` §3.3
- **缺陷**：白名单强制 + 单测 + 读自检对一把含交易/借币/划转权限的 key 来说纵深防御不够，缺少非 GET 方法硬拦截和签名请求审计日志。
- **影响**：代码 bug 或 prompt 注入可能在白名单机器上构造出越界签名请求（如 POST），而当前基线无法事后审计。
- **修法**：
  - `private_client` 只允许 GET，其他方法直接 raise；
  - 单测断言非白名单路径、非 GET 方法、含交易语义参数均失败；
  - 增加审计日志，记录 endpoint/method/timestamp，**禁止记录 signature/key/secret**；
  - ADR 中写明残余风险。

### P1 - 借币利率端点与 VIP 行选择规则未决

- **文件**：`docs/phase2-direction-draft.md` §5
- **缺陷**：`base_daily_interest` 只写了示例值，未说明取自哪个端点、哪个 VIP 等级行；`crossMarginData` 可能按 VIP 分级返回。
- **影响**：同一资产可能出现多条利率，契约字段语义模糊，前端无法正确展示成本。
- **修法**：明确主数据源为 `/sapi/v1/margin/crossMarginData`，取 VIP 0（或账户实际 VIP）的 `dailyInterest`；字段矩阵记录 raw path 与单位；不可行时 fallback 到 `/sapi/v1/margin/interestRateHistory` 最新点。

### P1 - 阶段分类未升级为 MILESTONE 且未触发方向 panel

- **文件**：`docs/phase2-direction-draft.md` 全文
- **缺陷**：草案未声明本阶段复杂度。引入签名端点、API key、安全红线修订、契约修订，符合 AGENTS.md 的 MILESTONE 标准。
- **影响**：若按 MEDIUM/LOW 直接 stage design，会跳过方向 panel 与合成，增加方向性错误风险。
- **修法**：在草案中明确本阶段为 MILESTONE；controller 运行 registered direction panel，Codex 合成 `06-direction-synthesis.md`，用户批准后再进入 stage design。

### P2 - `negative_funding_status` 枚举扩展结论未落档

- **文件**：`docs/phase2-direction-draft.md` §5、§8 Q4
- **缺陷**：提出细化为 `BORROW_LISTED_PENDING_ACCOUNT_CHECK` 与 `BORROW_NOT_LISTED`，但未给出最终优先级序列与 schema 更新策略。
- **影响**：实现时可能出现优先级歧义，导致分类器与前端 badge 不一致。
- **修法**：采用枚举扩展；优先级序列为 `DISABLED_PERP_ONLY → DISABLED_BSTOCK → DISABLED_SPOT_ONLY → BORROW_NOT_LISTED → BORROW_LISTED_PENDING_ACCOUNT_CHECK`；同步更新 schema、`classify.py`、frontend badge 映射。

### P2 - 排序比较器方案未拍板

- **文件**：`docs/phase2-direction-draft.md` §6、§8 Q5
- **缺陷**：草案提出“数值化可接受”，但未明确是 double 还是字符串十进制比较器，默认排序方向也未最终决定。
- **影响**：实现阶段可能因浮点精度引发 review 争议；UI 文案可能误导用户。
- **修法**：建议采用纯字符串十进制比较器；默认按绝对值降序，UI 表头明确标注“按资金费率绝对值降序”；若坚持 double，必须补充边界单测。

### P2 - 并行模式首次试运行耦合风险过高

- **文件**：`docs/phase2-direction-draft.md` §7、§8 Q6
- **缺陷**：Task B 依赖 Task A 的契约产出，而 Task A 的端点验证可能改变契约。
- **影响**：一旦实抓结果改变接口，将触发并行模式 R3 升级，造成循环停摆。
- **修法**：本阶段拆为两个串行 stage（2a backend 先走，2b frontend 随后）；或在 H_intake 中写入强 fallback：端点验证改变契约时立即升级 bookkeeper，禁止实现者本地修契约。

### P2 - `margin_private` null/false 语义与降级策略未细化

- **文件**：`docs/phase2-direction-draft.md` §5
- **缺陷**：`verified:false` 时“其余字段 null”不能区分“私有通道未启用”与“已验证但不在列”。
- **影响**：前端可能把“不在列”错误渲染为“未验证”。
- **修法**：失败/未启用：`verified:false, cross_pair_listed:null, base_daily_interest:null`；成功但不在列：`verified:true, cross_pair_listed:false, base_daily_interest:null`；成功且在列：`verified:true, cross_pair_listed:true, base_daily_interest:<str>`。

### P2 - 脱敏规则缺少 URL 签名参数排除机制

- **文件**：`docs/phase2-direction-draft.md` §3.4
- **缺陷**：只原则性说明“key、签名、时间戳参数不出现在落档 URL/头部中”，未说明 private_client request log 如何清洗。
- **影响**：脱敏执行口径不统一，可能意外落档 signature/timestamp。
- **修法**：在 `private_client` 中实现日志清洗函数，落档前删除 `signature`、`timestamp`、`recvWindow`；提供脱敏脚本与单测。

### P3 - 默认排序文案未说明“按绝对值”

- **文件**：`docs/phase2-direction-draft.md` §6
- **缺陷**：默认按绝对值降序的语义未在 UI 文案层体现。
- **影响**：用户可能误以为只看正费率或只看负费率。
- **修法**：UI 表头提示“资金费率（绝对值降序）”。

### P3 - 契约版本未 bump

- **文件**：`docs/api/public-market-contract.md`
- **缺陷**：Phase 2 将修改契约，但文档仍标记为 v0.1。
- **影响**：版本管理混乱，无法区分 Phase 1/Phase 2 契约。
- **修法**：升级为 contract v0.2，增加 Phase 2 amendment 变更记录。

### P3 - §8 待对齐问题仍以问号形式遗留

- **文件**：`docs/phase2-direction-draft.md` §8
- **缺陷**：Q1-Q7 多为“是否…”式提问，未给出结论。
- **影响**：草案读起来像开放问题清单，不像可冻结方向。
- **修法**：修订时给出每项结论，已决定事实写入正文，剩余风险写入“已知风险”小节。

---

## Required Fixes

1. 用用户 key 实抓 `/sapi/v1/margin/allPairs` 与 `/sapi/v1/margin/crossMarginData`，脱敏落档；若统一账户下无效则改走 `/papi` 账户级验证。
2. 补强 §3 安全基线：GET-only 强制、非白名单/非 GET 单测、签名请求审计日志（不含 secret）、ADR 残余风险披露。
3. 确定借币利率端点为 `/sapi/v1/margin/crossMarginData`，明确 VIP 行选择规则与 fallback。
4. 明确本阶段为 MILESTONE，触发 direction panel 与 `06-direction-synthesis.md`。
5. 给出 `negative_funding_status` 枚举扩展的最终优先级序列，并规划 schema/`classify.py`/frontend badge 同步更新。
6. 拍板排序比较器为字符串十进制比较器；默认按绝对值降序，UI 文案明示。
7. 将双任务并行改为两个串行 stage（2a backend → 2b frontend），或提供强 fallback。
8. 细化 `margin_private` null/false 语义与降级策略。
9. 明确 request log 与 api-samples 的签名参数清洗机制。
10. bump `docs/api/public-market-contract.md` 到 v0.2 并增加变更记录。

---

## Fix Start Prompt（给 Fable5）

你是 Fable5，负责本方向草案的修订（只改文档，不写代码，不创建 API key，不签名请求）。

**修订目标**：把 `docs/phase2-direction-draft.md` 从 DRAFT-1.2 推进到可冻结的 DRAFT-2.0，确保所有 P1/P2 findings 被解决。

**必须读取**：
- `docs/phase2-direction-draft.md`
- `AGENTS.md`（复杂度路由、MILESTONE 要求、方向 panel 规则）
- `docs/api/public-market-contract.md`
- `docs/parallel-development-mode.md`
- `backend/domain/classify.py`
- `reports/agent-runs/phase2-direction-v1/direction-review-kimi27.md`（本文件）

**修改边界**：
- 只能修改 `docs/phase2-direction-draft.md`。
- 禁止进入 `backend/**`、`frontend/**`、`schemas/**`、`reports/api-samples/**` 写文件。
- 若需要实抓 API 样本，在草案中写明“由 controller 用用户 key 抓取并脱敏落档”，不要自己调用签名端点。

**必须完成的内容**：

1. **安全红线 §3**：
   - 写明 `private_client` 强制 METHOD=GET；非 GET 直接 raise。
   - 写明单测覆盖：白名单外路径、非 GET 方法、含交易语义查询参数。
   - 增加“签名请求审计日志”小节：记录 endpoint/method/timestamp，禁止记录 signature/key/secret/timestamp 参数。
   - 增加 ADR 残余风险披露。

2. **统一账户 /sapi 验证 §4/§5**：
   - 写明在 H_intake 前必须实抓 `/sapi/v1/margin/allPairs` 与 `/sapi/v1/margin/crossMarginData`，脱敏落档路径 `reports/api-samples/2026-07-private-market-discovery-v1/`。
   - 给出结论：若统一账户返回有效数据，2a/2b 切分成立；若无效，直接取消 2a、改走 `/papi` 账户级验证。
   - 明确 `cross_pair_listed` 只是“经典全仓清单在列”，不表示统一账户可借。

3. **借币利率端点 §5**：
   - 选定 `/sapi/v1/margin/crossMarginData` 为主数据源。
   - 明确 VIP 行选择规则（建议默认 VIP 0，或匹配账户 VIP）。
   - 给出 fallback：`/sapi/v1/margin/interestRateHistory` 最新点。
   - 在字段矩阵占位中写明 raw JSON path、类型、单位。

4. **枚举扩展 §5**：
   - 给出最终优先级序列（见本评审 §4）。
   - 说明 schema、`classify.py`、frontend badge 映射的同步更新计划。

5. **排序 §6**：
   - 选择纯字符串十进制比较器（推荐）或 double + 边界单测。
   - 默认按绝对值降序，UI 表头文案为“资金费率（绝对值降序）”。

6. **流程 §7**：
   - 明确 Phase 2 拆为两个串行 stage：先 `2026-07-private-market-discovery-v1`（Task A），再 `2026-07-public-market-sort-v1`（Task B）。
   - 移除“双任务并行首次试运行”建议，改为后续阶段再试。

7. **其他**：
   - 明确 `margin_private` 的 null/false 语义。
   - 写明 request log / api-samples 脱敏清洗规则。
   - bump 契约版本到 v0.2。
   - 在文档开头声明本阶段为 MILESTONE。
   - 清理 §8，把问号改为结论或已知风险。

**验收标准**：
- 草案不再包含未决“是否”问题。
- 所有 P1 findings 在正文中有明确结论或执行计划。
- 任何需要实抓/签名/key 的工作都明确分配给 controller/用户，不落在 Fable5 自身。

---

本地北京时间: 2026-07-04 19:17:05 CST
下一步模型: Fable5 (Claude/anthropic) 修订方向草案；随后由 controller 运行 MILESTONE 方向 panel（Codex 合成 `06-direction-synthesis.md`）
下一步任务: 根据本评审修订 `docs/phase2-direction-draft.md`，解决 P1/P2 后重新进入方向评审

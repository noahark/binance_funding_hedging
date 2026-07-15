# Grok Round-2 Advisory Review — Raw Transcript Capture

The following review response is preserved from Grok Session
`019f6617-0199-7230-9d63-896434ea8b88`. It was requested directly by the user
as an additional review and is non-gating. The model did not write a stage file;
the bookkeeper captured the final response from the exact session transcript.

---

# 额外审核意见（不落档）

**阶段**: `2026-07-bookticker-open-columns-v1`  
**范围**: 产品交付 diff（Task A + Task B），对照 `00-task.md` / 冻结语义 / review-1  
**角色**: 额外一轮独立审核，**不是**正式 review-2 gate，**不写** stage 文件  
**披露**: 本 provider 曾做过本阶段 advisory design review；本次只审已提交实现与测试证据，不替代 Codex review-2。

---

## 结论

**建议：ACCEPT / 可进入正式 review-2**

未发现 P0 / P1 / P2 必改缺陷。与两份 formal review-1 的 `ACCEPT` 一致。  
独立复跑：

| 检查 | 结果 |
|------|------|
| focused backend (`test_book_ticker` + worker 等) | 67 passed |
| full `backend/tests` | **375 passed** |
| `node frontend/self-check.js` | **77 PASS** |
| full-stage fingerprint | 与 status 记录一致 |

---

## 交付摘要（是否对齐目标）

| 验收点 | 结论 |
|--------|------|
| 全量 spot + futures bookTicker，无 per-symbol HTTP | ✓ |
| 双端成功才写 pair cache；失败不推进时间戳 | ✓ |
| `Decimal` 公式 + 两位 `ROUND_HALF_UP` + 负零归一 | ✓ BTC 向量 `-0.04` / `0.04` |
| 120s 为 assembly 投影，非“再失败一次才 stale” | ✓ `119 fresh / 120 stale` |
| bStock 用已解析 `spot.symbol` 连接 | ✓ |
| 方向独立 incomplete | ✓ |
| 12 列：日净收益、合并借贷/资产、去掉提示标记、正/反向开单 | ✓ |
| 独立 `formatOpeningSpreadPct`，不走 `formatFundingRate` | ✓ |
| 无交易/借还/WS 副作用；click 不新增 bookTicker | ✓ |
| 文件边界 | ✓ Task A / B 仅允许文件 |

---

## 后端（Task A）要点

实现质量整体扎实：

1. **原子性**：adapter 任一侧失败 / 空 list / 空 map 即失败；service 仅在 `pair is not None` 写 cache。  
2. **类型护栏**：只接受 JSON string 价格，拒绝 number→`str()`。  
3. **可用性**：`usable = age < 2 * cache_ttl_seconds`，每次 assembly 重算。  
4. **公式**：`(bid - ask) / ask * 100`，只在最终结果 quantize。  
5. **兼容**：`opening_quotes` 可选；legacy stub 无 seam → `unavailable`，无 `AttributeError`。  
6. **测试**：truth table、原子失败、bStock、click 无额外 HTTP 覆盖充分。

---

## 前端（Task B）要点

1. **列契约**：12 列顺序与 empty `colspan=12` 正确；`ui_flags` 仍校验。  
2. **合并列**：借贷状态在上、资产在下；`可借` 只在合并列，日净收益只留成本。  
3. **开单列**：腿顺序与设计一致；stale/unavailable/缺字段 → `—`。  
4. **单位**：`-0.04 → -0.04%`，不会变成 `-4%`。  
5. **Fix 1/2**：max-borrowable 门控、XAU incomplete、BUSDT 断言等已收口。

---

## Findings（均为非阻塞）

### P3（与 review-1 一致）

1. **`formatOpeningSpreadPct` 与“恒两位”wire 耦合**  
   正则要求 `^-?\d+\.\d{2}$`。当前后端始终两位，安全；未来若产出 `5` 会静默变 `—`。  
   建议：后续可在 schema 收紧 `*_spread_pct` pattern（非本 stage 必改）。

2. **`fresh` 完整性依赖后端不变量**  
   前端不二次校验“fresh 必四价齐全”。后端测试已 lock，可接受。

### P3 / 观察（本轮补充）

3. **双 REST 非交易所时间原子**  
   spot/futures 顺序拉取，存在时刻差。产品已标注“约 60s / 非成交保证”。**残余产品风险**，非实现 bug。

4. **`incomplete` 且四价皆空时仍渲染双行结构**  
   全是 `—`，信息密度略噪，但符合 incomplete 投影规则；`unavailable`/`stale` 才整格 `—`。可接受。

5. **`formatPrice` 未 `escapeHtml`（既有模式）**  
   开单价格与 mark/index 一样直接插入 DOM。数据源为后端 decimal 校验后的公开行情，风险低；若以后要做通用 XSS 硬化，应统一处理所有价格渲染。

6. **schema 的 `decimal_string` 未强制两位**  
   pattern 允许 `5` / `5.1`；文档写了两位。与 P3-1 同源，文档已说明，schema 可后续收紧。

### 未发现

- 文件越界  
- 交易/私有写副作用  
- 公式方向反了  
- 百分比 ×100 二次放大  
- 部分提交 pair cache  
- review-1 指纹/隔离问题（本轮抽查 fingerprint 匹配）

---

## 对 formal review-1 的再确认

| Task | Reviewer | 结论 | 本轮 |
|------|----------|------|------|
| A | Kimi | ACCEPT，0 findings | 同意 |
| B | Claude-GLM | ACCEPT，2×P3 | 同意，并补充上列残余风险 |

Harness 上 review-2 需 strong-reviewer disclosure（Codex 设计/bookkeeper，Claude breakdown）——流程问题，不是产品代码缺陷。

---

## 建议

1. **产品侧**：可按现状推进正式 **review-2**。  
2. **不必为本轮 P3 再开 rework**。  
3. 后续（非本 stage）：  
   - schema 收紧 `*_spread_pct` 为两位；  
   - 文档继续强调 reference quote 非成交保证。

---

```text
当前 Session ID: unavailable (Grok CLI 本轮未见 provider-native session env)
Session ID 来源: unavailable
原始输出路径: unavailable（用户要求不落档；本回复即审核正文）
本地北京时间: 2026-07-15 22:05:44 CST
下一步模型: human → codex review-2（按 review-2-codex.prompt.md）
下一步任务: 执行正式 review-2；本额外审核仅供对照，不写入 50-review-2.md
```

---

## Same-Session Receipt Correction

The original footer above is preserved verbatim but was corrected later in the
same Grok Session after the user asked about the missing ID. The correction was
cross-checked against `~/.grok/active_sessions.json`, the encoded-cwd session
directory, live pid `67999`, and matching process cwd:

```text
当前 Session ID: 019f6617-0199-7230-9d63-896434ea8b88
Session ID 来源: active_session_registry
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/31-advisory-review-grok-round-2.md
本地北京时间: 2026-07-15 22:13:31 CST
下一步模型: human
下一步任务: 执行页面显示验收；之后由 bookkeeper 准备 Opus4.8 formal review-2
```

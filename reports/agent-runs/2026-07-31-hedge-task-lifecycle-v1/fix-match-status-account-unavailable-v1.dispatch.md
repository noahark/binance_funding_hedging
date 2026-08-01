# Dispatch —— fix-match-status-account-unavailable-v1（Task 1 修复轮 3/3 —— **最后一轮**）

```text
Identity:
  task_id:         fix-match-status-account-unavailable-v1
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 17
  required_skill:  agents/skills/minimal-change-engineer.md
```

## Goal

修复 review-1 r3（`grok`）的唯一 `in-range` 阻塞发现 **F4**：账户读不到时，`match_status` 谎称「交易所无仓」。

**完整评审正文见 `46-review-1-grok-task1-r3.md`（原文逐字留档于 §4），本 dispatch 不重述。**

- **`rework_count` 由 `2` 递增为 `3`，已达 `AGENTS.md` §8 的上限。这是最后一轮修复。**
  若此后仍出 `REWORK`，须由 Human 在「缩小范围 / 重新设计 / 接受为已知限制 / 停止」四项中选择，Bookkeeper 不得自行再派修复。**请把这一轮做到位。**
- 评审对本轮其余部分（G5 均价分母、G2 展示、G6/G7、D15、`merge_positions` 纯度、N2 表可见、精确键集、禁改区）**全部判 pass，不得回退**。
- 按 `minimal-change-engineer.md`：只改缺陷及其测试所必需之处。

## F4 是什么（Bookkeeper 已实测复验）

直接调用 `merge_positions` 的实测结果：

| 场景 | 输入 | 输出 `match_status` |
|---|---|---|
| 1 | `verified: false`，但 `private_account.um_positions` **确实含 BTCUSDT 空头 0.5** | **`no_um`** |
| 2 | `private_account` 为 `None`（快照未就绪） | **`no_um`** |
| 3（对照） | `verified: true`，`um_positions` 为空 —— 交易所确实没有 | `no_um` |

**三者输出完全一致。** 「查过、确实没有」与「**根本没查**」在契约上不可区分。场景 1 尤其严重：数据就在手上，只因 `verified=false` 被跳过，系统却对外宣称「交易所无仓」。

前端对 `no_um` 无条件渲染「交易所无仓」，`title` 写「可能已强平或手工平仓」—— **凭空断言的事实 + 误导性的强平推测**。而这正是上一轮 F1 特意打开的冷账户路径：用户会同时看到「账户数据未就绪」横幅和「交易所无仓 / 可能已强平」，**两条信息互相矛盾**，有据此误判仓位已被强平的实操风险。

**这和 F1、F2、F3、G5 是同一个根因**：展示层断言了它并不知道的事情。

## 要做的四项

### R1｜契约：只有真读到账户，才允许说「交易所无仓」

- `verified` 为假、或 `private_account` 缺失 → 本地行**不得**为 `no_um`。
- `verified` 为真且确无匹配 UM → 仍为 `no_um`（现有行为正确，勿回归）。
- `no_task` 仅在**存在真实 UM 行且无对应本地桶**时设置（现有行为正确，勿回归）。

**Bookkeeper 的取值建议**：新增一个中性值（如 `account_unavailable`）而非复用 `normal`。理由：`normal` 的含义是「两侧都有、对得上」，账户读不到时说 `normal` 同样是在断言一件不知道的事 —— 会重蹈同一根因。新增的是**枚举值不是新键**，`_POSITION_KEYS` 的键集不变，但前端必须同步处理该值。

若你有更好的方案，可以采用，但**必须满足**：从 `match_status` 能区分「查过没有」与「没查」。

### R2｜展示：N2 路径不得出现「交易所无仓」及强平推测

账户未就绪时，行上不得出现「交易所无仓」标签，也不得出现「可能已强平或手工平仓」的 `title`。可与「账户数据未就绪」横幅并存的，只能是中性标识或不标匹配态 —— 横幅本身已经解释了原因。

### R3｜测试（必须能失败）

- **merge 层**：`positions` 非空 + `verified=false` → `match_status != "no_um"`；`private_account=None` → 同上。
- **merge 层**：`verified=true` + 无 UM + 有本地桶 → **仍为** `no_um`（防止修过头）。
- **self-check**：`account.verified=false` 时，本地行的 HTML **不含**「交易所无仓」。

在实现报告中说明你如何确认这三条不是空断言（例如故意还原旧行为后断言变红）。**Bookkeeper 会独立复验。**

### R4｜同步文档

- `21-merged-positions-implementation.md` §11.2 穷举表的 `missing × 标记` 一格 —— 该格目前写的正是这个缺陷（详见下方「必读的一课」）。
- `10-design.md` §5 补一句：N2 与真 `no_um` 的区分方式。

## 必读的一课：你上一轮的穷举表把缺陷写进去了

上一轮按 §8 同根因刹车做了穷举扫描，`21-` §11.2 的「每列 × 六场景」表结构完整、与实现一致 —— **但 `missing × 标记` 那一格写的就是「交易所无仓」+ 横幅**。表格如实记录了实现，却把缺陷固化成了"预期行为"。

**穷举表只能抓住作者已经意识到"是错的"的东西。** 所以本轮更新该表时，请对每一格额外回答一个问题：

> **这一格断言了什么事实？我们真的知道它吗？**

只回答"这一格显示什么"是不够的 —— 那正是上一轮漏掉 F4 的原因。

## Allowed Files

沿用既有边界，不扩大：

- `backend/hedge_open_tasks/{domain.py, store.py, service.py}`、`backend/app/server.py`
- `backend/tests/{test_positions_merge.py, test_hedge_api.py, test_hedge_store.py, test_hedge_service.py, test_hedge_review2_regressions.py}`
- `frontend/index.html`、`frontend/self-check.js`

修改产物（就地更新，附日期说明）：`21-merged-positions-implementation.md`、`10-design.md`、`61-merged-positions-test-output.txt`（覆盖为本轮**原始**输出）。

**不得改动**：`private_client.py`、`hedge_preflight_provider.py` 白名单、`scheduler.py`、`domain.py` 的暂停原因集与 51169 文案区、`status.json` 的 `current_task.state` 以外任何字段。

**不得触碰**：Task 2 / Task 3 范围；**已接受限制 A / B**（`22-` §5）；Human 已裁定的两项（8 位有效数字、借款去重保留 —— `45-` §4）；Human 推后的建议项与历轮观察（`41-` §2、`42-` §2、`46-` §4 的观察 1-5）。

## Inputs

| 文件 | 读什么 |
|---|---|
| 本 dispatch | 全部 |
| `46-review-1-grok-task1-r3.md` | §1 Bookkeeper 实测复验、§2 穷举表的教训、§4 评审原文（F4 与修复要求） |
| `21-merged-positions-implementation.md` | §11.2 穷举表（须更新） |
| `22-` §5 / `45-` §4 / `42-` §2 | 范围外清单 |
| `agents/skills/minimal-change-engineer.md` / `agents/developer-discipline.md` | 全部 |

关键锚点：`domain.py` 的 `_merge_build_row`（`match_status` 赋值处）与 `merge_positions`（`verified` 为假时置空 UM 列表处）、`index.html` 的 `no_um` 渲染分支。

## Acceptance Checks

每项按 `AGENTS.md` §7 标注 `pass` / `fail` / `contested`；`检查结果` 最多八项，合并同类。

1. **R1 已修**：`verified=false` 与 `private_account=None` 两条路径均不再输出 `no_um`；`verified=true` 且确无 UM 时仍为 `no_um`；`no_task` 判定未回归。
2. **R2 已修**：N2 路径的行上无「交易所无仓」标签、无强平/手工平 `title`。
3. **R3 已补**：三条断言存在且**能失败**，报告说明确认方式。
4. **R4 已同步**：`21-` §11.2 的 `missing × 标记` 格已更正；`10-design.md` §5 已说明 N2 与真 `no_um` 的区分。
5. **穷举表已按新标准复核**：对每一格回答了「断言了什么事实 / 我们真的知道吗」，并列出因此发现的其它可疑格（若无则明确说明已逐格检查过）。
6. **未回退**：后端全套测试与 `node frontend/self-check.js` 全绿；G5 分母、G2 展示、G6/G7、D15、N2 表可见、精确键集形式、`merge_positions` 纯度、F1/F2、禁改区全部保持。
7. **未越界**：限制 A/B、Human 已裁定项、Task 2/3 范围、推后项与历轮观察均未触碰。
8. **原始测试输出**：`61-` 覆盖为本轮原始输出，不得改写为叙述。

## Stop

- 完成后按 `AGENTS.md` §7 输出 `[TASK_RESULT v2]`，把 `current_task.state` 由 `dispatched` 改为 `reported`（唯一授权改动的 `status.json` 字段），然后**停止**。
- 不得设置 `next`、不得自行判定验收、不得合并、不得推送。
- 不得接触凭证或实盘路径；不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- 若认为某条修复要求不成立：**不要沉默照改**，按 §7 标 `contested` 并给出被质疑项原文名称、质疑理由、替代证据。Bookkeeper 会显式裁定；质疑成立则按勘误更正，不消耗返工预算。
- **本轮修复仍触及 `match_status` 契约**，因此完成后按 §8 **再过一次 review-1（`grok`），通过后回 review-2（`codex`）**。评审轮次不消耗 `rework_count`。

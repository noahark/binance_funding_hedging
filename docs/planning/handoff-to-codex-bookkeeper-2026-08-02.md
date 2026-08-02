# 交接：Bookkeeper 由 opus5 移交 codex（2026-08-02）

写给接任的 `codex`。**你读不到上一个窗口，本文件是自包含的。** 需要细节按文中路径取，
**不要重新推导已核实的事实**。

- 移交人：`opus5`（provider `anthropic`）
- 接任人：`codex`（provider `openai`）—— Human 决定
- 第一件事：**开一个 stage 修 F4**。Human 明确要求由你来开，不是由我预开。

---

## 0. 一句话现状

**上一个 stage 已完整收口并推送，当前没有活跃 stage。** `ACTIVE.json` 是
`{"active": null}`，`main` = `60ef0ae`，与远端同步，工作区干净。

按 `AGENTS.md` §4 无 packet 启动：读 `AGENTS.md` → `ACTIVE.json` →
`PROJECT_STATE.md`，然后就是本文件。

---

## 1. 你要修的 F4 是什么

**账户读不到时，持仓表对每一行断言「交易所无仓」，并附强平提示——而它根本没查。**

已实测：`private_account` 块里**确实含有那个 UM 持仓**时，只因 `verified=false` 就被
跳过，然后系统对外宣称「交易所无仓」。触发路径有两条：

| 路径 | 何时 | 操作者会不会当真 |
|---|---|---|
| `SnapshotNotReady` | 仅首次发布前的启动窗口 | 不会（知道刚重启） |
| **`verified == false`** | **任何时刻**：API key 失效、IP 白名单变更、币安私有接口报错、网络抖动 | **会**——程序此前一直是对的 |

### 为什么它是最高优先（review-2 的核心发现）

**同一场交易所侧故障会同时触发两件事**：

1. 订单查询 inconclusive → 任务暂停，卡片提示「**请到交易所核对**」
2. 账户读取失败 → 持仓表对每一行谎报「**交易所无仓**」

**操作者被叫去核对的那一刻，恰是那张表最不可信的时刻。** 若信了「无仓」而重建任务，
交易所上原有的腿仍在 → **双重敞口**。

### 修法已被完整指定，不要重新设计

在归档分支里。stage 目录已从工作树移除，取法：

```bash
git show archive/2026-07-31-hedge-task-lifecycle-v1:reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/46-review-1-grok-task1-r3.md
```

看该文件 **§3.3**，四条要求（原文，勿改写）：

1. **契约**：仅在账户侧已成功读取时才允许 `match_status = "no_um"`；`verified` 为假或
   `private_account` 缺失时须用中性值（建议新增 `account_unavailable`，属枚举值不改键集）。
2. **展示**：N2 路径不得出现「交易所无仓」标签与强平/手工平 `title`。
3. **测试（须能失败）**：`verified=false` 与 `private_account=None` → `match_status != "no_um"`；
   `verified=true` + 无 UM + 有桶 → 仍为 `no_um`；self-check 断言 `verified=false` 时行
   HTML 不含「交易所无仓」。
4. 同步该 stage 的 `21-` §11.2 与 `10-design.md` §5（均在归档分支内）。

### 三个已知的坑（我出 packet 时踩过或预见到）

- **必须动 `frontend/`**：第 2、3 条要改 `index.html`（「交易所无仓」标签与图例）和
  `self-check.js`（**现有 G1 断言要求出现该标签，不改必红**），还要动
  `backend/tests/test_positions_merge.py`。**别把 `frontend/` 写进「不得改动」。**
- **`match_status` 是新增枚举值不是新增任务状态**：项目红线「不新增状态枚举」管的是
  `STATUS_*`（`running`/`done`/…）。给 `match_status` 加 `account_unavailable` 不违反它。
  packet 里写明，否则实现者会纠结或绕开。
- **前后端必须同版本上线**：`match_status` 是新 API 键。要求实现者交代前端遇到未知
  `match_status` 值时的兜底行为。

### 风险与路由

`HIGH_RISK`（资金可见性 / 操作误导），按 §8 需 review-1 + review-2。
`match_status` / `merge_positions` 在 `backend/hedge_open_tasks/domain.py`。

---

## 2. 评审人选的真实处境（你会立刻撞上）

| 模型 | provider | 状态 |
|---|---|---|
| `grok` | xai | **无额度** |
| `codex` / `gpt` | openai | **就是你**——你做 Bookkeeper 写 packet 后，同 provider 做评审属「设计参与」，须披露 |
| `deepseek` | deepseek | 上个 stage 做过计划评审、独立复核、并实现了一轮修复 |
| `fable5` | anthropic | 上个 stage 的 review-2，本 stage 零参与；**须 Human 显式启用其独立付费额度** |
| `claude_glm` | zhipu_glm | 后端实现默认人选 |
| `kimi` | moonshot | 前端实现默认人选；**`roles.md` 里 `claude_glm` 实现的 review-1 首选** |

**F4 是前后端混合任务**，实现者路由要 Human 定（`roles.md` 的规则是「混合但不可安全拆分
→ 按主要工作量选一个 owner」）。

`roles.md` 的 review-1 首选是 **Kimi**（对 `claude_glm` 实现），Grok 是 Human 批准的备选
但无额度。**上个 stage 全程没用过 Kimi，它是当前最干净的评审人选。**

---

## 3. 这个项目的根因，你必须知道

上一个 stage 抓到的缺陷里，**六个是同一个根因**：

> **展示层断言了它并不知道的事。**

F1（账户没就绪整张表不显示）→ F2（盈亏拿不到画 `0`）→ F3（错配行假成本显示 `0`）→
**F4（没查账户却宣称「交易所无仓」）** → G5（币安移除字段后未知被存成字面 `"0"`，均价砍半）
→ 以及最新一条：已删除任务的收口事件仍写「任务已暂停…请手动恢复」。

**你要修的 F4 正是这个家族里最严重的一个。** 修它的时候尤其容易在别处再犯一次——
比如给 `account_unavailable` 配的文案，如果写成「交易所可能无仓」，就是换个说法继续撒谎。

**判据**：任何一格显示，先回答两问——**这一格断言了什么事实？我们那一刻真的知道它吗？**
不知道就必须映射到中性值，**不得映射到零、空字符串或任何具体结论**。

---

## 4. 八条操作纪律（上个 stage 真栽过跟头换来的）

1. **派工前查 `docs/planning/DECISIONS.md`。** 我没查，结果 packet 要求实现者写了一个违反
   `DEC-2026-07-30-003` 的迁移——那条决策订立第三天就被破了，还导致实盘库被静默改写。
   三轮 review-1、review-2、我自己五次核验**全都没发现**，直到合并推送后才撞见。
2. **不要采信「我测过了」。** 破坏验证是唯一可信的。实现者两轮自称断言可失败，我破坏后
   才发现其中一条是空转。
3. **破坏验证要穷举同族站点后同时破坏。** 单点破坏会给假阴性——我曾据此误判「双保险」，
   被 review-1 纠正为覆盖缺口。
4. **用真实数据验，不要只信 fixture。** 迁移那次全部 1140 测试绿，因为测试一律建新库；
   复制实盘库一验才发现改动对既有库零效果。
5. **每次提交后回验分支归属**（`git branch --show-current && git log --oneline -1`）。
   这个 stage 出过派工单更正提交成游离提交、实现者读到旧版执行的事故。
6. **模型终端运行期间不要切换主工作区分支。** review-2 进行中工作区被切到 `main`，评审者
   grep 到旧代码、险些误判「交付被回退」。要在 `main` 上操作请用独立 worktree。
   本仓库有 **4 个 worktree**，派工前提醒 Human 确认位置。
7. **packet 里要删某个常量时，必须同步授权所有引用它的文件。** 我删了常量却把引用它的
   测试文件列进「不得改动」，把实现者逼到必须越界。
8. **`data/` 是活的实盘库，只读。** 任何验证先复制到临时目录。**禁止「构造 store 时指向
   真实路径」这种间接写入**——`PROJECT_STATE.md` 里有两条已生效的操作规则。

---

## 5. 上个 stage 的返工历史（供你校准期望）

`2026-07-31-hedge-task-lifecycle-v1` 的 Task 3（重查节奏）：

| 轮次 | 结果 |
|---|---|
| Bookkeeper 核验 | **拒收**（改动对既有库零效果） |
| review-1 r1（`codex`） | `REWORK`，五条 |
| review-1 r2（`gpt`） | `REWORK`，两条并发竞态；**触发 §8 同根因刹车** |
| review-1 r3（`gpt`） | `ACCEPT` |
| review-2（`fable5`） | `ACCEPT` |

`rework_count` 用到 **2/3**。**同根因刹车**（连续两轮同根因 → 禁止第三次点补丁，必须做
穷举扫描）在这个 stage 真的触发过一次，而那次穷举扫描找出了两个所有人都没看到的站点。
**它是有效的机制，不是形式。**

---

## 6. 当前状态与关键文件

```text
main            60ef0ae（与远端同步）
ACTIVE.json     {"active": null}
工作区          干净
实盘库 mtime    2026-08-01 23:45:48（今天所有操作均未触碰）
```

| 文件 | 内容 |
|---|---|
| `PROJECT_STATE.md` | 跨 stage 风险与后续项，**17 条 OPEN**。F4 在「Merged Position Table」段 |
| `docs/planning/DECISIONS.md` | 已批准决策，最新 `DEC-2026-08-02-001…003` |
| `docs/planning/ROADMAP.md` | 已同步至 2026-08-02，Current Focus 第一条就是 F4 |
| `docs/planning/deferred-hedge-task-lifecycle.md` | 被暂缓的生命周期改造，自包含 |
| `archive/2026-07-31-hedge-task-lifecycle-v1` | 上个 stage 全部证据，**70 个文件** |

### 与 F4 相邻、别一起改的三件

- **任务卡暂停原因 1/7 中文**（前端从不读 `pause_reason_zh`）——两行级改动，但**独立
  排期**，别混进 F4。
- **`exposure_alert` 是死状态**（后端无写入路径）——归 deferred 那份文档。
- **`49-` 只读冒烟清单从未执行**，现在是下次实盘启用的硬前置。F4 修完正是跑它的好时机
  （清单里「账户未就绪路径」一项就是 F4）。

---

## 7. 你的下一步

1. 按 `AGENTS.md` §4 无 packet 启动读三份文件 + 本文件；
2. 从归档取 `46-` §3.3 的原文修法；
3. 与 Human 确认：**实现者人选**（前后端混合）、**评审人选**（Kimi 最干净；Fable5 需显式
   付费额度）、以及 stage 命名；
4. 开 stage、写 packet、交 Human 启动终端。**不要自己启动任何模型终端**（§3 #2）。

`rework_count` 为新交付物从 0 起算。

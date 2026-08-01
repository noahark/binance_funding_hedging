# 26 —— 请求独立复核 Bookkeeper 的 Task 3 核验结论

**致复核者（`deepseek`）**：本文件请你复核 **Bookkeeper（`opus5`）自己的核验结论**，
不是复核实现者的代码。

## 0. 这不是什么

- **不是 `AGENTS.md` §8 的 review-1 或 review-2。** 那两道仍待走（review-1 `grok` →
  review-2 `codex`），本次复核不替代、不预判、不消耗任何评审轮次。
- **不产生 `ACCEPT` / `REWORK` verdict**，也不写 `status.json`。
- 你的产出是一份**对下列四个判断的独立意见**，供 Human 决定是否推翻 Bookkeeper。

## 1. 背景（最小集）

- 仓库：`funding_hedging`，分支 `stage/2026-07-31-hedge-task-lifecycle-v1`
- stage：`2026-07-31-hedge-task-lifecycle-v1`
- 任务：`hedge-leg-requery-cadence-v1`（把对冲任务的在途腿重查间隔 1s → 100ms，
  外加三道护栏：亚秒显示、读取处夹下限、worker 节流加抖动）
- 实现者：`claude_glm`；交付提交 `aac779d`，base `9faa716`
- 实现者自报：八项验收全 pass，`backend/tests/` **1140 passed**
- **Bookkeeper 裁定：拒收**（`current_task.state` 保持 `reported`，未写 `verified`）

设计权威：`11-adr.md` ADR-003（已过计划评审，`40-`，`deepseek` ACCEPT——即你自己
上一轮的结论，这与本次复核第 2 点直接相关）。

派工单：`hedge-leg-requery-cadence-v1.dispatch.md`
拒收记录：`24-bookkeeper-rejection-task3.md`
修复派工单（已备好，未投递）：`fix-cadence-existing-db-v1.dispatch.md`

## 2. 请你复核的四个判断

### 判断一（核心）：拒收依据 BK-T3-001 是否成立

**Bookkeeper 的主张**：`aac779d` 的默认值下调**对既有数据库完全无效**，交付目标在
真实部署上零效果。

**理由链**：

1. `DEFAULT_INTERVAL_US`（`domain.py:513-515`）只被**建库时的种子插入**引用
   （`store.py:337-350`），插入条件是
   `SELECT COUNT(*) FROM hedge_open_settings WHERE id = 1` 返回 `0`；
2. `_migrate()`（`store.py:351`）不触碰 `hedge_open_settings` 表；
3. `hedge_open_settings.interval_us` **没有任何运行时写入途径**——`store.py` 内除
   种子插入外无 `SET interval_us` / `set_interval*`；设置端点只有 start-gate 的 CAS
   更新（`service.py:1030-1045`）；
4. 因此既有库的 `interval_us` 永远停在建库当时写入的 `1_000_000`。

**Bookkeeper 的实测**（复制实盘库到临时目录，未写原库）：

```bash
cp data/hedge-open-tasks.sqlite3 /tmp/live-copy.sqlite3
sqlite3 /tmp/live-copy.sqlite3 \
  "SELECT id, interval_seconds, interval_us, version FROM hedge_open_settings;"
# 实测输出: 1|1|1000000|4
```

```python
from backend.hedge_open_tasks.store import HedgeOpenStore
from backend.hedge_open_tasks.service import settings_to_doc
import backend.hedge_open_tasks.domain as D
st = HedgeOpenStore("/tmp/live-copy.sqlite3", executor_mode_snapshot="disabled", now_us=0)
print(D.DEFAULT_INTERVAL_US, st.get_interval_us(),
      settings_to_doc(st.get_settings(), "live")["interval_seconds"])
```

| 库 | 代码常量 | `get_interval_us()` | 接口 `interval_seconds` |
|---|---|---|---|
| 实盘库副本 | `100_000` | **`1_000_000`** | **`1.0`** |
| 全新空库 | `100_000` | `100_000` | `0.1` |

**1140 个测试全绿，因为测试一律用 `tmp_path` 新建空库。**

**请你查**：

- 上述 1-4 步有没有事实错误？特别是第 3 步「无任何运行时写入途径」——请自己搜一遍，
  Bookkeeper 可能漏了某条路径（例如别的模块直连 sqlite、某个未被 grep 命中的写法、
  或运维脚本）。**只要存在任何一条合法途径能把该值改成 100ms，本拒收就不成立。**
- 「拒收」相对于「记为已接受限制并放行」是否过当？

### 判断二（最需要被挑战）：`rework_count` 不递增的裁定

**Bookkeeper 的裁定**：`rework_count` 保持 `0`，不因本次拒收递增。

**Bookkeeper 的理由**：依 `AGENTS.md` §8「缺陷在 packet 不在交付，不消耗返工预算」
的原则，本缺陷根在上游：

- ADR-003 Decision 第 2 条只写「把默认值从 1s 下调到 100ms」，未提迁移——**而该 ADR
  已过你（`deepseek`）的计划评审并获 ACCEPT**；
- `12-development-breakdown.md` Task 3 的文件边界与验收标准同样未涉及迁移；
- Bookkeeper 自己的 packet 照抄「下调默认值」，且把验收 2 写成了「用 `_pump_worker`
  或可控时钟确定性断言」——一个**在新建库上即可满足**的形式。

**利益冲突声明**：**这条裁定是 Bookkeeper 对「缺陷是不是自己造成的」所做的自我
判断，直接决定实现者是否被扣返工额度。请你带着敌意审视它。**

**请你查**：

- 「缺陷在 packet」的定性是否成立？还是说，一个称职的实现者本就应当知道
  「种子插入不会回溯更新既有行」，因而属于实现缺陷、应当计数？
- Bookkeeper 是否在用「packet 缺陷」豁免一个本应由交付承担的问题？
- 实现者在 `23-cadence-implementation.md:46-47` 写「种子插入引用常量，**自动生效**，
  无需改 `store.py` 种子」——把未验证的推断当作事实陈述。这一条本身够不够构成
  独立的交付缺陷（从而应当计数）？
- 注意你自己上一轮 ACCEPT 了 ADR-003。**这不该让你倾向于任何一方**：若你认为
  ADR-003 本就该覆盖迁移，请直说（那意味着计划评审也漏了）；若你认为迁移属于实现
  细节、不该由 ADR 承担，也请直说（那意味着责任更偏向交付）。

### 判断三：「七项通过」的结论是否被限定得足够

Bookkeeper 判定八项验收中七项 pass。但**所有测试都跑在新建空库上**，因此严格说
应为「在新库前提下通过」。

**请你查**：这个限定是否被充分说明？其中是否有哪一项，在真实库（`interval_us`
仍为 1 秒）下结论会不同、从而不该记为 pass？Bookkeeper 认为不会（显示逻辑对 1 秒
同样正确、下限与抖动同样工作，只是标称值不同），请独立判断。

### 判断四：抖动整件事——来源、有效性、是否应当移除

**（本条在 Human 质疑「抖动我没答应加，是谁加的」之后重写，请重点看。）**

**溯源（Bookkeeper 已核实）**：

| 文件 | 是否出现「抖动」 | 作者 |
|---|---|---|
| `01-intake-brief.md:74-83`（Human 对 ③ 的原始诉求） | **无**。Human 提的是「1 秒 → 100ms」；所附建议为「拆分两间隔、加下限、考虑 429 退避而非暂停」 | Human 诉求记录 |
| `02-` `03-` `04-`（Human 决策文件） | **无** | Human |
| `PROJECT_STATE.md`（历史 follow-up） | **无** | — |
| `10-design.md` P6 / `11-adr.md` ADR-003 | **首次出现** | `claude_glm`（D12） |
| `40-plan-review-deepseek-v2.md` | 计划评审 **ACCEPT**（含抖动） | `deepseek` |
| 本任务 packet 要点 4 / 验收 4 | 原样承接 | `opus5`（Bookkeeper） |

即：**抖动由方案作者 `claude_glm` 引入，经计划评审放行，Bookkeeper 未加质疑地写进
packet。Human 从未要求，也从未单独批准。** 同时，Human 自己提的三条建议中「拆分两
间隔」被 ADR-003 以事实 8 为据否决——**一条 Human 提的被砍，一条 Human 没提的被加。**

**Bookkeeper 现在的技术质疑（请你独立判断对错）**：

1. 抖动声称解决「10 个 worker 对齐成 100 req/s **脉冲**」。但币安限的是**权重总量**
   （ADR-003 自述 ~1200/min ≈ 20/s），而 10 任务 × 10 次/秒 = **100 次/秒的总量不因
   抖动而减少**——抖动只是把同样的总量摊平。**对「总量超限约 5 倍」这个真实风险，
   抖动基本无效。**
2. 实现取 `[0.75, 1.0]`，平均实际间隔 `87.5ms` < 标称 `100ms`，**总请求量反而比标称
   高约 14%**。方向选择源自 Bookkeeper packet 验收 4 的原文（要求抖动「不会……超过
   标称间隔」），实现者照做无误。
3. 真正对应该风险的手段是 429 退避（ADR-002），而它属 Task 2、**本轮明确不做**。

**请你查**：

- 上述技术质疑 1 是否成立？抖动对本场景是否确有 Bookkeeper 未看到的实际价值
  （例如避免瞬时突刺触发更严格的限流档位）？请给出你的判断而非折中表述。
- 按 `AGENTS.md` §1（「不要为假设场景添加防御性机制」），抖动属于**对已批准目标的
  正当技术手段**，还是属于**未经要求的范围扩张**？
- 建议 Human 选哪一项：**整个移除抖动** / **保留但改为保守方向（如 `[1.0, 1.25]`）**
  / **原样保留**？请给出理由与代价。
- 附带：`deepseek` 是上一轮计划评审的 ACCEPT 方（即你自己）。若你现在认为抖动本不
  该进方案，请直说；这属于计划评审的遗漏，如实记录即可。

## 3. 你可以核实的与只能采信的

- 若你能读取本仓库：上述所有行号、命令、测试结果均可自行复跑核实。**请优先自己
  验证，不要采信本文件的转述。** 全量回归命令：`python3 -m pytest backend/tests/ -q`。
- 若你读不到仓库：请明确区分你的结论中哪些基于本文件给出的事实（无法独立验证）、
  哪些基于逻辑一致性分析，并在结论中标注。

## 4. 请返回

1. 对上述四个判断逐条给出：**同意 / 不同意 / 证据不足**，并给理由；
2. 你发现的、本文件未提及的问题（尤其是 Bookkeeper 核验遗漏的检查项）；
3. 一句话总体意见：Bookkeeper 的拒收裁定应当**维持、推翻、还是修改**。

不要写 `status.json`，不要修改任何仓库文件，不要启动其他模型会话。

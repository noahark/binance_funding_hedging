# 25-review-1（fix-2 后重跑）：2026-07-31-hedge-task-inline-log-v1

> 本轮修复改了**实盘执行器的资金字段解析语义**，且是本 stage 首次触碰该文件，
> 按 `AGENTS.md` §8 重跑 review-1。本终端**只读**，锚定固定区间，不移动 `HEAD`。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1-review-1-fix2
- target_role: Reviewer（review-1，只读）
- target_model: `grok`
- provider: `xai`
- status_revision: 17
- required_skill: `agents/skills/code-reviewer.md`
- rework_count: 2（**上限 3，仅剩一次**；评审轮不递增）

### 隔离披露（须在结论中原样给出）

你（`grok` / xai）担任过本 stage 计划评审 r1-r3、首轮 review-1 与 review-1 重跑。
跨 provider 相对实现/修复作者成立（xai ≠ `claude_glm` / zhipu_glm，你不是实现或修复
作者）。请写明一行：「review-1（fix-2）与本 stage 计划评审 r1-r3、前两轮 review-1
同为 grok/xai」。

## 本轮背景

你在 review-1 重跑给出 `ACCEPT`。随后 review-2（`codex`）复审判 `REWORK`，阻塞项一条：

> **R2-Rerun-F1**：`_avg_price_decimal` 的判零条件是 `raw in (None, "", "0", 0)`，
> **只认字面 `"0"`**。而币安 USDⓈ-M「查询订单」对已受理未成交的订单返回
> `avgPrice="0.00000"` —— 该值会被解析、落库，并在日志表显示为均价 `0.00000`。
> 用户会读成「成交价是零」，事实是「还没成交」。违反本 stage「零不是价格」硬约束。

Bookkeeper 已在固定提交上独立复现确认。

**这个缺陷的责任在 Bookkeeper**：上一轮 packet 曾写死「不得改 `_avg_price_decimal`，
它已把 `"0"` 映射为 `None`」并配 AC8 要求该文件零改动 —— 那是只读代码字面、**未验证
币安实际返回格式**得出的结论，且主动堵死了实现者发现它的路。该禁令本轮已撤销。

## 本轮改了什么（两层）

1. **解析层**（`live_hedge_executor.py` 的 `_avg_price_decimal`）：判零由字面比对改为
   `Decimal(str(raw)) == 0` 数值比较，覆盖 `"0"` / `"0.00000"` / `"0.0"` / `0` /
   `"0E-8"` / `"-0"` 等全部零写法；非零值仍走 `_quote_decimal` 原样透传。
2. **展示层**（`service.py` 的 `_resolve_avg_price`）：取用库存值前做同样的数值判零，
   为零则退回本地计算 —— 护住可能已落库的脏数据与未来的其它写入路径。

## Goal

1. **零值归一是否完备且无副作用**：
   - 是否覆盖了所有零写法？有没有遗漏的表示（例如超长精度、正负号、空白字符）？
   - **非零值是否严格原样透传**？有没有引入补零、截断、科学计数法转换？
   - `Decimal(str(raw))` 对异常输入（`float('nan')`、`float('inf')`、超长字符串、
     非法类型）的行为是否安全？异常路径是否都归到 `None`？
2. **【最易错处】成交额的零语义是否被波及**：`_quote_decimal` 的 `"0"` 是**真实的零
   成交**（合法值），与均价的零含义相反。请独立验证 `cumulative_quote_amt` 的 T1 契约
   （`NULL` = 未知 / `"0"` = 真实零）**完好无损**，两者未被"顺手统一"。
3. **展示层防御是否恰当**：`_resolve_avg_price` 的零判断是纵深防御还是多余？它用了
   宽泛的 `except Exception: pass`，这个吞异常的写法在此处是否可接受？
4. **接缝**：`_avg_price_decimal` 是实盘执行器的共用函数，其行为变化对 POST 路径
   （`_post_figures`）、GET 路径（`_query_figures`）、inline confirm
   （`_confirm_um_figures`）三处调用方是否都安全？有没有依赖旧行为的地方？
5. **测试强度**：新增 4 个用例是否真的锁住了行为，还是只覆盖 happy path？
6. **是否超出 dispatch 边界**（`22-fix2.dispatch.md` 的 Allowed Files 与 Stop）。

## Allowed Files

只读。不修改任何文件、不提交、不建分支。结论以 `[TASK_RESULT v2]` 文本返回给 Human。

## Inputs

- **受审区间（唯一权威）**：
  `base_sha = 42de1aff364e7c979d2fbb5dc56f1dec65287cc7`
  `delivery_sha = e9ba135541959272d3f6c10d789af702a79f61a7`
  用 `git diff 42de1aff..e9ba1355` 审查。**不要**看工作树、不要移动 `HEAD`。
  区间含首轮交付 + fix-1 + fix-2 的全部改动。
- review-2 复审 verdict（含 R2-Rerun-F1 原文与修复要求）：同目录
  `21-review-2-rerun-verdict.md`（**必读**）。
- fix-2 packet：同目录 `22-fix2.dispatch.md`。
- 实现者自述：同目录 `23-fix2-result.md`。
- **Bookkeeper 独立核验**（含实测输出表）：同目录 `24-bookkeeper-verification-fix2.md`。
- 你上一轮的 `ACCEPT`：同目录 `19-review-1-rerun-verdict.md`。
- 授权文件：`AGENTS.md`、`agents/roles.md` Reviewer 段、`agents/skills/code-reviewer.md`。

### 已知且**不在**本次受审范围的事项

- O1（后续查询用 `None` 覆盖已知价）：review-2 已裁定当前不可达、**不阻塞合并**，
  保留为上游接口变化时的后续保护项。
- 订单重查间隔 1 秒 → 100ms：已按 Human 决定记为 follow-up。
- 「任务卡卡住」全套：已移出本 stage。
- 上述各项若被发现，按 §8 **范围三分类**标注，不要按 `in-range` 阻塞交付。

## Acceptance Checks

- 逐条回答 Goal 六项，每项给出明确判断与依据（引用 `文件:行号` 或 diff 位置）。
- 每条发现按 §8 标注**范围三分类**；`pre-existing-*` 须附引入提交引用。
- 返回 `[TASK_RESULT v2]`，含 `评审结论: ACCEPT | REWORK`、`问题记录`、`修复要求`。
- **`问题记录` / `修复要求` 不要写 `none`**：写 `inline-full-text` 并把发现清单与修复
  要求放在同一次输出的正文里。
- **注意 `rework_count` 已达 2/3。** 若你判 `REWORK`，请明确区分「必须现在修的
  in-range 阻塞项」与「可作为后续项记录的观察」——把可延后的东西计入阻塞会耗尽仅剩的
  一次返工额度。反之，真正影响资金判断的问题**不要**因为额度紧张而放过。

## Stop

- 只读：不改代码、不改 packet、不改 `status.json`、不提交、不移动 `HEAD`。
- 不做实现、不写修复代码、不启动其他终端。
- 不重评已移出本 stage 的工作，不把 follow-up 当作本次交付缺陷。
- 不替 Human 做合并、部署、实盘决策。`ACCEPT` 不等于合并授权。

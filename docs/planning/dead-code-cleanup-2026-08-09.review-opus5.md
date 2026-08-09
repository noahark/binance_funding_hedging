# Opus 5 单轮 Final Review：退役资产与生产零调用代码清理

## 任务身份

- 角色：独立最终 Reviewer。
- 目标模型：Opus 5（Anthropic provider），由 Human 启动独立终端。
- 实现作者：Codex / OpenAI；provider isolation 成立。
- 风险路由：`LOW_RISK` 单轮 final review。理由：交付应只删除退役文件、零调用函数、
  失效配置面及其专用测试，不改变 API、schema、资金含义、实盘闸门或运行行为。
- 唯一任务技能：`agents/skills/reality-checker.md`。
- 本轮不是新的 ponytail audit，不寻找更多可删内容，不修改受审交付。

## 固定评审范围

```text
base_sha:     3e2c4b79378bbe67da6efdaa5fe1c25492606482
delivery_sha: 95515f46f42ffcbe3369fc20c4ee37b02a545ae7
```

只以该固定范围为交付事实，不以移动的 `HEAD`、工作区或口头摘要代替。包含本文案的后续
提交不属于受审交付。

## 权限与启动条件

开始前按顺序读取：

1. `AGENTS.md`；
2. 本文件；
3. `reports/agent-runs/ACTIVE.json`（必须仍为 `{"active": null}`）；
4. `PROJECT_STATE.md`；
5. `agents/roles.md` 的 Reviewer 小节；
6. `agents/skills/reality-checker.md`；
7. `docs/planning/dead-code-cleanup-2026-08-09.codex-review-execute.md`；
8. 固定 diff 及其直接相关源码、测试、活文档和历史证据。

Reviewer 不得修改代码、既有文档、配置、状态、数据库或服务，不得提交、推送、合并、
部署或启动其他模型会话。唯一写权限是在完成评审后**新建**：

`docs/planning/dead-code-cleanup-2026-08-09.review-opus5-result.md`

启动时先执行：

```bash
test ! -e docs/planning/dead-code-cleanup-2026-08-09.review-opus5-result.md
git status --short --branch
git rev-parse 3e2c4b79378bbe67da6efdaa5fe1c25492606482
git rev-parse 95515f46f42ffcbe3369fc20c4ee37b02a545ae7
```

结果文件若已存在，返回阻塞，不得覆盖。测试产生的解释器缓存也应关闭。

## 评审目标

回答以下八项，结论必须来自仓库原始证据：

1. 固定 diff 是否只有执行包授权的 18 个路径，没有触碰明确禁止范围？
2. 四个整文件删除是否确实只移除退役原型、一次性脚本及其专用测试；是否仍有现役代码、
   CI、启动入口、运维入口或活文档依赖它们？
3. 删除 `scripts/backfill-cycles.py` 后，新数据库的周期 schema/migration 是否仍由现役
   store 负责；`test_migrate_creates_cycle_schema_idempotent` 是否从旧测试文件等价迁入
   `backend/tests/test_hedge_store.py`，保留字段、`cycle_id`、两个索引和重复打开断言？
4. 被删函数是否在基线中均无生产调用；删除模块级 `dispatch_to_outcome` 及其专属私有
   helper 后，生产使用的 `backend/hedge_open_tasks/service.py::_dispatch_to_outcome` 及其
   调用和测试是否完整保留？
5. `APP_TOP_N` / `FUNDING_HEDGING_TOP_N` / `Config.top_n` 在基线是否无生产消费者，交付后
   是否从配置解析、启动日志、示例、测试和活开发文档完整清除，没有留下半套合同？
6. `docs/api/public-market-contract.md` 的改动是否只把已删 discovery 脚本改成准确的历史
   Git/evidence 指针；历史样本和审计证据是否仍存在？
7. 后端全测与前端 self-check 是否在当前交付上真实通过；删除测试是否仅随死实现删除，
   没有移除仍生效的关键行为合同？
8. 实际效果是否仍符合 `LOW_RISK`：不改变 API、schema、资金/订单/借还/账务语义、实盘
   闸门、凭据、数据或服务状态，并且可以进入 Human 的推送决策？

不要因为删行数量大本身返工。任何 Reviewer 新提出的假设场景须满足 `AGENTS.md` §1
Scenario Admission；没有当前证据锚点的刁钻可能性不能扩大范围或导致 `REWORK`。

## 最小证据命令

至少执行并记录真实结果：

```bash
git diff --check \
  3e2c4b79378bbe67da6efdaa5fe1c25492606482..95515f46f42ffcbe3369fc20c4ee37b02a545ae7

git diff --name-status \
  3e2c4b79378bbe67da6efdaa5fe1c25492606482..95515f46f42ffcbe3369fc20c4ee37b02a545ae7

git diff --stat \
  3e2c4b79378bbe67da6efdaa5fe1c25492606482..95515f46f42ffcbe3369fc20c4ee37b02a545ae7

rg -n 'top_symbols_by_abs_rate|\bdispatch_to_outcome\b|_exchange_status_for_outcome|\bleg_is_filled\b|sort_interest_desc|sort_income_desc' \
  backend --glob '!backend/hedge_open_tasks/service.py'

rg -n 'APP_TOP_N|FUNDING_HEDGING_TOP_N|\.top_n\b' \
  backend frontend scripts .env.example docs/development \
  --glob '!docs/planning/**'

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
node frontend/self-check.js
```

两个 `rg` 命令应无输出。另须直接比较迁移前后的测试内容，并用 `git grep` / `rg` 核对
删除文件及函数的真实引用；不要只复述实现者的 `1593 passed` 摘要。

不得运行服务、访问实盘端点、修改数据库或凭据。若测试因环境而无法运行，缺失的必要
证据应导致 `REWORK`，不能猜测通过。

## Verdict 规则

- 八项均有充分证据且无 in-range 缺陷：`ACCEPT（接受）`。
- 存在由该固定 diff 引入或触碰的实际缺陷、范围越界或必要证据缺失：
  `REWORK（返工）`，每条 finding 按 `AGENTS.md` §8 标注范围分类，给出路径、证据、实际
  影响和最小可执行修复要求。
- 纯范围外问题按 §8 分类；全是范围外问题时不得机械返回 `REWORK`。
- 不得修改交付来“验证修复”，也不得提出与本次删除无关的重构。

## 结果文件与控制台回执

完成后新建
`docs/planning/dead-code-cleanup-2026-08-09.review-opus5-result.md`，至少包含：

- Reviewer/provider 与隔离披露；
- 固定 `base_sha..delivery_sha`；
- 八项逐项结论与证据；
- 测试命令和真实结果；
- findings、范围分类、剩余风险；
- 明确 `ACCEPT` 或 `REWORK`；
- 若 `REWORK`，完整最小修复要求。

控制台按仓库当前 `[TASK_RESULT v2]` 和 review closure 收口，`产物`列出上述结果文件，
`下一步模型`填 `Human（决策者）`。不得创建提交或推送；由 Human 决定后续动作。

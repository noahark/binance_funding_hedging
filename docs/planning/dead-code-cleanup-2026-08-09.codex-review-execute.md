# Codex 影响核验 + 条件执行：现役死代码清理

## 修订记录

- 2026-08-09：第一次影响核验返回 `IMPACT_STOP`。本版保留现役周期 schema / migration
  幂等测试，并明确把模块级 `dispatch_to_outcome` 的专属私有 helper 一并纳入删除范围；
  其余范围不变，须重新执行全部六项影响核验。

## 任务性质

- 执行者：另一个独立 Codex 终端，由 Human 启动。
- 方式：Human 直接驱动、无 stage；启动时 `reports/agent-runs/ACTIVE.json`
  必须仍为 `{"active": null}`。
- 先只读核验影响；只有结论为 `IMPACT_OK` 才继续删除、测试和提交。
- 这不是正式代码评审。执行者一旦修改交付物，就不能评审自己的交付；交付后如需正式
  review，应交给非 OpenAI provider 的独立只读模型。
- 风险口径：拟议范围只删除已证明无生产调用、无独立生命周期的资产，不改变 API、
  schema、资金含义、实盘闸门或运行行为，因此预期为 `LOW_RISK`。若核验发现任一行为或
  合同变化，立即停止，不得自行扩大或重新分类。
- 指定 skill：`ponytail:ponytail`（full）。

## Human 已授权的条件

Human 授权：先检查下列删除是否存在遗漏影响；若整份清单可安全成立，直接执行删除、
运行验收并提交；若任一项不成立，保持工作区不变并报告 `IMPACT_STOP`。

不得部分删除、不得顺手处理相邻问题、不得调用或启动下一正式工作流模型、不得推送。

## 启动读取

按顺序读取：

1. `AGENTS.md`；
2. 本文件；
3. `reports/agent-runs/ACTIVE.json`；
4. `PROJECT_STATE.md`；
5. `agents/roles.md` 的 Implementer 小节；
6. `agents/developer-discipline.md`；
7. `ponytail:ponytail` skill；
8. 仅限本文件列出的源码、测试、活文档和引用搜索结果。

开始前要求：工作区干净，记录 `base_sha = git rev-parse HEAD`。若存在其他终端未提交改动，
停止，不得覆盖。

## 第一阶段：只读影响核验

逐项回答并给出仓库内证据：

1. 下列整文件是否没有现役代码、CI、启动脚本、运维入口或活文档要求其继续存在？
2. 一次性采集与回填的原始证据是否已经保存在 `reports/api-samples/`、已完成 stage evidence
   或 Git 历史，删除脚本不会删除证据本身？
3. 下列函数是否只有定义和专用测试，没有生产调用？特别区分
   `live_hedge_executor.dispatch_to_outcome` 与仍在生产使用的
   `HedgeOpenTaskService._dispatch_to_outcome`。
4. `Config.top_n` / `APP_TOP_N` 是否只剩配置解析、启动日志、示例和文档，没有快照、历史
   拉取或其他生产消费者？
5. 删除专用测试是否只是随被删实现一起移除，不会删掉仍生效的行为合同覆盖？特别核对
   周期 schema / migration 幂等测试已迁入 `backend/tests/test_hedge_store.py`，且迁移前后
   断言等价。
6. 是否能在不触碰“禁止范围”的前提下完整完成？若必须增加未授权文件，返回
   `IMPACT_STOP` 并列出文件和原因。

只有六项全部成立才输出：

```text
影响核验: IMPACT_OK
依据: <按上述六项给出简短路径/引用证据>
```

否则输出并停止，禁止编辑：

```text
影响核验: IMPACT_STOP
阻塞项: <具体文件、调用方、合同或生命周期>
建议: <删除该项、缩小清单或另开高风险任务>
```

## 第二阶段：`IMPACT_OK` 后的唯一允许删除范围

### A. 删除完整文件

1. `prototypes/fake-ui/index.html`
   - 已被 `frontend/index.html` 取代，无现役引用。
2. `scripts/discovery-capture-phase2.py`
   - 绑定已完成的 `2026-07-phase2-borrow-sort-v1` 一次性取证。
3. `scripts/backfill-cycles.py`
   - 持仓周期存量回填已完成，审计证据已归档；新数据库走当前 schema/migration。
4. `backend/tests/test_hedge_cycle_backfill.py`
   - 先把 `test_migrate_creates_cycle_schema_idempotent` 迁入
     `backend/tests/test_hedge_store.py`，保留原有字段、`cycle_id`、两个索引以及重复打开
     数据库的全部断言；
   - 除该测试外，其余内容只覆盖一次性回填脚本，迁移完成后删除本文件；
   - 不得借迁移改写、扩充或抽象该测试。

报告声称“一次性脚本约 1973 行”，但上述三个脚本/测试实际约 1083 行；不要为了追求
删行数字额外寻找或删除其他 cleanup、backfill、discovery 脚本。

### B. 删除生产零调用函数及其专用测试

1. `backend/domain/snapshot.py`
   - 删除 `_abs_rate`；
   - 删除 `top_symbols_by_abs_rate`。
2. `backend/tests/test_snapshot.py`
   - 删除 `top_symbols_by_abs_rate` import；
   - 删除 `test_top_symbols_by_abs_rate_ranks_and_caps`。
3. `backend/services/live_hedge_executor.py`
   - 删除模块级 `dispatch_to_outcome`；
   - 同步删除只被它调用的私有函数 `_exchange_status_for_outcome`；
   - **严禁删除或修改**
     `backend/hedge_open_tasks/service.py::_dispatch_to_outcome`；它仍有生产调用。
4. `backend/tests/test_live_hedge_executor.py`
   - 删除上述模块级 helper 的 import；
   - 删除 `test_dispatch_to_outcome_accepted_pair_is_success`；
   - 删除 `test_dispatch_to_outcome_single_leg_is_exposure`。
5. `backend/hedge_open_tasks/domain.py`
   - 删除零调用的 `leg_is_filled`；保留 `leg_is_accepted` 及全部实际分类逻辑。
6. `backend/ledger_flow/domain.py`
   - 删除 `sort_interest_desc`；
   - 删除 `sort_income_desc`；
   - `OrderedDict` 仍被分组和去重函数使用，不得删除或替换。
7. `backend/tests/test_ledger_flow_domain.py`
   - 删除上述两个排序函数的专用测试。

只移除本清单明确列出的专属私有 helper 和删除直接造成的孤儿 import；不得重排、格式化
或重构相邻代码。

### C. 删除失效的 `APP_TOP_N` 配置面

1. `backend/config.py`
   - 删除 `Config.top_n`；
   - 删除 `from_env()` 中 `APP_TOP_N` / `FUNDING_HEDGING_TOP_N` 解析；
   - 修正文件头仍称“funding_history top-N = 20”的过时说明。
2. `backend/tests/test_config.py`
   - 删除测试输入中的 `APP_TOP_N`；
   - 删除 `cfg.top_n` 断言。
3. `backend/app/server.py`
   - 从启动日志删除 `top_n` 输出；不得改其他启动信息。
4. `.env.example`
   - 删除 `APP_TOP_N` 示例。
5. `docs/development/DEVELOPMENT_GUIDE.md`
   - 删除 `APP_TOP_N` / `FUNDING_HEDGING_TOP_N` 配置说明。

不得修改本地 `.env`；它属于运行环境，不是本次交付物。

### D. 活文档的最小同步

允许修改 `docs/api/public-market-contract.md`，但仅限把
`scripts/discovery-capture-phase2.py` 的现役文件引用改成明确的历史表述或 Git/evidence
指针。不得改写公共市场契约正文。

历史 `reports/`、已完成 stage evidence 和其他 `docs/planning/` 记录继续保留旧路径，
不得清洗历史引用。

## 明确禁止范围

不得修改或删除：

- `scripts/check_symbol_mismatch.py` 与 `scripts/check-spot-symbol-map.py`；两者职责不同；
- `hedge_open_fill` 表、聚合读取、`insert_fill`、`list_fills_for_task`、
  `repair_legacy_exposure_ts` 及其测试；它们等待单独的存量数据库核验；
- `smooth` / 平滑开单的按钮、枚举、服务拒绝分支、API 契约与测试；
- borrow/hedge/ledger scheduler；
- `borrowApi`、`hedgeApi`、`__appHelpers`；
- `OrderedDict`；
- `PROJECT_STATE.md`、`AGENTS.md`、`agents/`、schemas、数据文件、凭据、实盘服务；
- 任何 money/order/live gate/deployment 行为。

发现上述范围存在问题只能报告，不能顺手修。

## 验收检查

实施后至少执行：

```bash
git diff --check

test ! -e prototypes/fake-ui/index.html
test ! -e scripts/discovery-capture-phase2.py
test ! -e scripts/backfill-cycles.py
test ! -e backend/tests/test_hedge_cycle_backfill.py

rg -n 'top_symbols_by_abs_rate|\bdispatch_to_outcome\b|_exchange_status_for_outcome|\bleg_is_filled\b|sort_interest_desc|sort_income_desc' \
  backend --glob '!backend/hedge_open_tasks/service.py'

rg -n 'APP_TOP_N|FUNDING_HEDGING_TOP_N|\.top_n\b' \
  backend frontend scripts .env.example docs/development \
  --glob '!docs/planning/**'

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
node frontend/self-check.js
```

两个 `rg` 命令应无输出。测试必须以当前环境的真实结果为准，不得只引用历史基线。

再核对：

- `git diff --name-status` 只包含本文件授权的路径；
- 没有新增抽象、兼容层、配置项或测试框架；
- 没有修改本地数据库、服务进程、凭据和 `.env`；
- docs 活文档已检查，除上述两处配置/历史指针外无需更新产品、架构、路线图或 API
  契约。

## 提交与回执

全部检查通过后创建一个本地提交，commit message 清楚说明“删除已结束资产和生产零调用
代码”。不要 push。

最终回执必须列出：

- `base_sha`、`delivery_sha`；
- 删除和修改文件；
- 实际删行数；
- 六项影响核验结论；
- 后端全测和前端 self-check 结果；
- 未处理的禁止范围；
- 当前 `git status --short --branch`。

按仓库当前 `[TASK_RESULT v2]` 收口。`下一步模型` 填 Human，因为 Human 需要决定是否
启动独立 final review 和 push。

# Opus 5 单轮 Final Review 结果：退役资产与生产零调用代码清理

## 评审身份与隔离披露

- Reviewer：Claude Opus 5（模型 ID `claude-opus-5`），provider identity = `anthropic`
  （`agents/roles.md` → Reviewer → Provider Identity）。
- 会话：Human 启动的独立只读终端；本会话未参与本次交付的实现、修复或计划撰写。
- 实现作者：Codex / OpenAI（`openai` provider）。**Provider isolation 成立**
  （`anthropic` ≠ `openai`，满足 `AGENTS.md` §3.5 与 Reviewer → Isolation）。
- 风险路由：`LOW_RISK` 单轮 final review（依据记录在
  `docs/planning/dead-code-cleanup-2026-08-09.review-opus5.md`「任务身份」节）。
- 唯一任务技能：`agents/skills/reality-checker.md`。
- 写权限：仅新建本文件。本会话未修改任何代码、既有文档、配置、状态、数据库或服务，
  未提交、未推送、未合并、未启动任何其他模型会话。
- 本轮不是新的 ponytail audit：不寻找额外可删内容，不修改受审交付。

## 固定评审范围

```text
base_sha:     3e2c4b79378bbe67da6efdaa5fe1c25492606482
delivery_sha: 95515f46f42ffcbe3369fc20c4ee37b02a545ae7
```

- `git rev-parse` 两个 SHA 均解析成功且与文案一致。
- `git log --oneline base..delivery` = **单一提交** `95515f4 chore: remove retired
  assets and unused production code`（作者 noahark，2026-08-09 12:17:21 +0800）。
  区间内不含本阶段控制提交，故不存在 `AGENTS.md` §8「评审范围口径」的范围外提交。
- 当前 `HEAD` = `68d9ae0`（`docs(planning): prepare Opus final cleanup review`），
  `git merge-base --is-ancestor 95515f4 HEAD` = YES。该文案提交**不属于受审交付**，
  结论只以固定区间为准。

## 启动条件核验

| 检查 | 结果 |
|---|---|
| `test ! -e docs/planning/dead-code-cleanup-2026-08-09.review-opus5-result.md` | 通过（本文件在评审完成后新建，未覆盖任何已有文件） |
| `reports/agent-runs/ACTIVE.json` | `{"active": null}`，符合无 stage 要求 |
| `git status --short --branch` | `## main...origin/main [ahead 4]`，工作区干净、无未提交改动 |
| 未推送提交 | `68d9ae0` / `95515f4` / `3e2c4b7` / `88fd8fc` 共 4 个，尚未 push |
| 启动读取顺序 | `AGENTS.md` → 本轮评审文案 → `ACTIVE.json` → `PROJECT_STATE.md` → `agents/roles.md` Reviewer 节 → `agents/skills/reality-checker.md` → `docs/planning/dead-code-cleanup-2026-08-09.codex-review-execute.md` → 固定 diff 与源码/测试/活文档/历史证据 |

测试均以 `PYTHONDONTWRITEBYTECODE=1` + `-p no:cacheprovider` 执行，未产生解释器缓存。

---

## 八项逐项结论与证据

### 1. 固定 diff 是否只有执行包授权的 18 个路径，没有触碰明确禁止范围？

**结论：是。**

`git diff --name-status base..delivery` 共 **18 个路径**（4 个 `D` + 14 个 `M`），
与执行包 A/B/C/D 四节授权路径**逐一对应，无一多、无一少**：

| 执行包节 | 授权路径 | diff 状态 |
|---|---|---|
| A | `prototypes/fake-ui/index.html` | D |
| A | `scripts/discovery-capture-phase2.py` | D |
| A | `scripts/backfill-cycles.py` | D |
| A | `backend/tests/test_hedge_cycle_backfill.py` | D |
| A | `backend/tests/test_hedge_store.py`（迁入目标） | M |
| B | `backend/domain/snapshot.py` | M |
| B | `backend/tests/test_snapshot.py` | M |
| B | `backend/services/live_hedge_executor.py` | M |
| B | `backend/tests/test_live_hedge_executor.py` | M |
| B | `backend/hedge_open_tasks/domain.py` | M |
| B | `backend/ledger_flow/domain.py` | M |
| B | `backend/tests/test_ledger_flow_domain.py` | M |
| C | `backend/config.py` | M |
| C | `backend/tests/test_config.py` | M |
| C | `backend/app/server.py` | M |
| C | `.env.example` | M |
| C | `docs/development/DEVELOPMENT_GUIDE.md` | M |
| D | `docs/api/public-market-contract.md` | M |

禁止范围逐条核对，**全部未被触碰**：`scripts/check_symbol_mismatch.py`、
`scripts/check-spot-symbol-map.py`、`hedge_open_fill` 表 / `insert_fill` /
`list_fills_for_task` / `repair_legacy_exposure_ts`、`smooth` 相关按钮/枚举/拒绝分支/
契约/测试、borrow/hedge/ledger scheduler、`borrowApi` / `hedgeApi` / `__appHelpers`、
`OrderedDict`、`PROJECT_STATE.md`、`AGENTS.md`、`agents/`、`schemas/`、`data/`、
`.env`、实盘服务——均不在 18 个路径内。

`git diff --check base..delivery` 无输出、退出码 0（无空白错误、无冲突标记）。
`git diff --stat` = `18 files changed, 45 insertions(+), 2780 deletions(-)`。

被改动的两个含资金/下单逻辑的文件（`backend/hedge_open_tasks/domain.py`、
`backend/services/live_hedge_executor.py`）的实际 hunk 仅为函数整体删除，未触及
`hedge_open_fill`、`smooth`、scheduler、下单参数或闸门代码。

### 2. 四个整文件删除是否确实只移除退役原型、一次性脚本及其专用测试？是否仍有现役依赖？

**结论：是，且无现役依赖。**

- 现役引用扫描（排除 `reports/**`、`docs/planning/**`、`.git/**`）：
  `rg 'prototypes/fake-ui|discovery-capture-phase2|backfill-cycles|test_hedge_cycle_backfill'`
  在**整个仓库仅命中 1 处**：`scripts/clean-dryrun-fake-fills.py:20` 的中文注释
  「安全约束（沿用 backfill-cycles.py 风格）」——**是注释里的风格出处描述，不是
  import、不是 subprocess 调用、不构成运行期依赖**（详见「范围外观察 O-1」）。
- CI 依赖：仓库**没有 `.github/` 目录**，根目录 `workflows/` 为空目录，不存在引用这些
  文件的 CI 配置。
- 启动 / 运维入口：`deploy/`、`scripts/run-server.sh`、`backend/app/server.py` 均无引用
  （包含在上述全仓扫描内）。
- 活文档：`docs/` 下唯一引用 `scripts/discovery-capture-phase2.py` 的位置就是本次改动的
  `docs/api/public-market-contract.md`（见第 6 项）；其余 `docs/` 无引用。
- 前端取代关系：`frontend/index.html` 为现役页面，`prototypes/fake-ui/index.html`
  被删后 `git ls-files prototypes` **返回空**，前端 self-check 通过（见第 7 项）。
- 证据未被删除：
  - Phase-2 一次性取证的原始样本仍在
    `reports/api-samples/2026-07-phase2-borrow-sort-v1/20260704T133406Z/`（实测存在）；
  - `scripts/backfill-cycles.py` 与 `backend/tests/test_hedge_cycle_backfill.py` 的
    完整内容可从 Git 历史恢复（`git log --all -- scripts/backfill-cycles.py` 命中
    引入提交 `97ecb7f`，以及本次删除提交 `95515f4`；`git show 3e2c4b7:<path>` 可完整取回，
    本评审即以此方式读取了原文件用于比对）。

### 3. 删除 `scripts/backfill-cycles.py` 后，新库周期 schema/migration 是否仍由现役 store 负责；迁移测试是否等价迁入？

**结论：是；迁移测试逐字节等价。**

- 周期 schema 从来不由回填脚本负责：`hedge_open_cycle` 的 `CREATE TABLE IF NOT EXISTS`
  在 `backend/hedge_open_tasks/store.py:167`（模块级 `_SCHEMA`，见 `store.py:39`），
  由 `HedgeOpenStore.__init__` 于 `store.py:393` `executescript(_SCHEMA)` 执行，
  紧接 `store.py:395` 调用 `self._migrate(...)`（定义在 `store.py:413`）。
  回填脚本只做**存量数据**回填，与建表/迁移无关。
- 等价性验证（不复述实现者摘要，直接逐行比对）：
  取 `git show 3e2c4b7:backend/tests/test_hedge_cycle_backfill.py` 的第 107–136 行
  与 `git show 95515f4:backend/tests/test_hedge_store.py` 的第 644–673 行做 `diff`，
  **结果为空（完全一致）**，包含同名分节注释「建表 / 迁移幂等」。
  常量 `CYCLE_COLUMNS`（8 个字段：`id`/`symbol`/`direction`/`opened_at_us`/
  `closed_at_us`/`close_reason`/`first_task_id`/`last_task_id`）同样逐行一致，随测试
  迁入 `test_hedge_store.py:21-25`。
- 保留的断言（原样保留，未被改写、扩充或抽象）：
  1. `PRAGMA table_info(hedge_open_cycle)` 字段集 == `CYCLE_COLUMNS`；
  2. `hedge_open_attempt` 含 `cycle_id` 列；
  3. 索引 `idx_cycle_active` 存在于 `hedge_open_cycle`；
  4. 索引 `idx_attempt_cycle` 存在于 `hedge_open_attempt`；
  5. 重复打开同一数据库（`store2`）后：两表字段集不变、两个索引集不变、不报错。
- 定点执行：
  `pytest backend/tests/test_hedge_store.py::test_migrate_creates_cycle_schema_idempotent`
  → `1 passed in 0.14s`。

### 4. 被删函数在基线是否均无生产调用？生产用的 `service.py::_dispatch_to_outcome` 是否完整保留？

**结论：是；生产链路完整保留。**

在 **base_sha 树**上执行
`git grep -n 'top_symbols_by_abs_rate|dispatch_to_outcome|_exchange_status_for_outcome|leg_is_filled|sort_interest_desc|sort_income_desc' 3e2c4b7 -- backend frontend scripts deploy schemas`，
命中全集如下：

| 符号 | 基线命中 | 生产调用 |
|---|---|---|
| `top_symbols_by_abs_rate` | 定义 `snapshot.py:102` + `test_snapshot.py` 的 import/1 个测试 | **0** |
| `leg_is_filled` | 仅定义 `hedge_open_tasks/domain.py:1317` | **0**（连测试都没有） |
| 模块级 `dispatch_to_outcome` | 定义 `live_hedge_executor.py:504` + `test_live_hedge_executor.py` 的 import/2 个测试 | **0** |
| `_exchange_status_for_outcome` | 定义 `live_hedge_executor.py:544` + 仅被 `dispatch_to_outcome` 内部调用（517/524 两行） | **0**（专属私有 helper） |
| `sort_interest_desc` / `sort_income_desc` | 定义 `ledger_flow/domain.py:249/256` + `test_ledger_flow_domain.py` 的 2 个测试 | **0** |
| `service.py::_dispatch_to_outcome` | 定义 `service.py:3054` + 调用 `service.py:2888`、`service.py:2914` | **2 处生产调用** |

交付后复查：`_dispatch_to_outcome` 在 `backend/hedge_open_tasks/service.py` 的
**定义行 3054 与两处调用行 2888 / 2914 完全未变**（`rg -n '_dispatch_to_outcome'`
输出与基线一致）；`backend/tests/test_hedge_task_local.py:508` 引用
`service._dispatch_to_outcome` 的文档字符串也仍然指向存活对象，未成为悬空引用。

**动态引用与孤儿检查（防止「删了名字但别处仍取得到」或「留下孤儿 import」）：**

- 无 `__all__` 再导出：`git grep "__all__"` 在四个被改模块上只命中
  `hedge_open_tasks/domain.py:68` 的 `LIST_ALL = "__all__"`，那是一个**字符串常量**，
  不是模块导出列表。
- `AttemptOutcome` 的 import 已随模块级 `dispatch_to_outcome` 一并删除；
  `backend/services/live_hedge_executor.py` 内已无 `AttemptOutcome` 引用，
  其他模块也无人从该模块转导入它（现役 import 该模块的 6 处全部只取
  `LiveHedgeExecutor` / `LegDispatch` / 分类函数等仍存在的符号）。
- 其余符号未成孤儿：`LEG_REJECTED` 仍被 `live_hedge_executor.py:375/420/470/511`
  使用（其中 511 属于保留的 `leg_is_terminal_fill`）；`D.LEG_NEW` 仍用于 394/494；
  `LEG_FILLED` 仍是被 `service.py`、`store.py`、`live_hedge_executor.py`、
  `tests/fakes.py` 广泛引用的公共常量；`Decimal` / `InvalidOperation` / `List` /
  `Dict` 在 `snapshot.py` 仍有 96 / 35 / 31 / 14 处使用；`OrderedDict` 在
  `ledger_flow/domain.py` 仍被 228/238/281/309/341 五处分组去重函数使用（未被删除或替换）。
- 测试侧无孤儿：`test_live_hedge_executor.py` 中 `LEG_REJECTED` / `LEG_ACCEPTED`
  仍分别有 5 / 19 处使用；`test_snapshot.py` 的 `_eligible` helper 仍被第 44 行使用。

### 5. `APP_TOP_N` / `FUNDING_HEDGING_TOP_N` / `Config.top_n` 是否无生产消费者且被完整清除？

**结论：是；基线无消费者，交付后清除干净，未留半套合同。**

基线全集（`git grep` on 3e2c4b7，范围 `backend frontend scripts deploy .env.example`）
只有 4 处，**没有任何快照构建、历史拉取或其他生产消费者**：

1. `.env.example:20` 示例；
2. `backend/app/server.py:1501` 启动日志打印；
3. `backend/config.py:230` `from_env()` 解析；
4. `backend/tests/test_config.py:23/37` 测试输入与断言。

交付后：

- 必查命令
  `rg -n 'APP_TOP_N|FUNDING_HEDGING_TOP_N|\.top_n\b' backend frontend scripts .env.example docs/development --glob '!docs/planning/**'`
  → **无输出（退出码 1）**。
- 追加的**大小写不敏感全仓**复查（排除 `reports/**`、`docs/planning/**`、`.git/**`、
  `.venv/**`、`.pytest_cache/**`）：除 `Config.borrow_check_top_n`（另一个字段，
  见范围外观察 O-4）与 `..._stop_not_pause` 这一子串误命中外，**零残留**；
  `schemas/` 内亦零命中，故 API/JSON schema 不含该字段，无对外契约变化。
- 五个清除点逐一确认：`Config.top_n` 字段（`config.py`）、`from_env()` 解析行、
  `server.py` 启动日志、`.env.example` 示例、`DEVELOPMENT_GUIDE.md` 条目——全部删除；
  `config.py` 文件头「funding_history top-N = 20」的过时说明也已改正为
  「Defaults match the stage design: snapshot cache TTL = 60s, bind 127.0.0.1:8787.」。
- `Config` 是 dataclass，删字段会改构造签名：全仓无任何以 `top_n=` 关键字构造 `Config`
  的调用点（基线扫描已覆盖 `backend/frontend/scripts/deploy`），故无调用点破裂。
- 本地 `.env`（运行环境，执行包明令不得修改）**仍保留 1 行 `APP_TOP_N=`**。这是正确
  取舍：`backend/config.py` 只按名读取它认识的键，多余的环境变量被静默忽略，不会
  报错也不改变行为（见范围外观察 O-2）。

### 6. `docs/api/public-market-contract.md` 是否只改成准确的历史指针？历史样本与审计证据是否仍在？

**结论：是；改动最小且事实准确，契约正文未动。**

- 该文件在固定 diff 中**只有 1 个 hunk**（约第 1725 行起），位于「Frontend Integration
  Rules 的历史勘误」段落内部；公共市场契约正文（字段、枚举、schema、响应形状）
  **一行未改**。
- 新文本的两条事实均已实证：
  1. 「samples under `reports/api-samples/2026-07-phase2-borrow-sort-v1/`」——
     目录存在，内含取证批次 `20260704T133406Z`；
  2. 「`scripts/discovery-capture-private-v1.py` still attempts that path inside
     try/except with a fallback」——该脚本仍存在（未被本次删除），
     `FIXTURE_PATH` 定义在第 59 行，第 320–324 行确为
     `try: json.loads(FIXTURE_PATH.read_text(...)) / except Exception: return
     CANDIDATE_FALLBACK, "fixture unreadable; fallback ..."`，描述准确。
- 旧文本中「两个 discovery 脚本都读它」的表述在 phase2 脚本删除后已不成立，新表述把
  已删脚本降格为「retained in Git + 指向 evidence 目录」，属于文案要求的「准确的历史
  Git/evidence 指针」，未清洗历史。
- `reports/`、已完成 stage evidence、其他 `docs/planning/` 记录中的旧路径**均保持原样**
  （不在 18 个路径内），符合「不得清洗历史引用」。

### 7. 后端全测与前端 self-check 是否真实通过？删除测试是否只随死实现删除？

**结论：是，两项均在本会话真实执行通过；测试净减量完全对得上账。**

- 后端：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider`
  → **`1593 passed in 126.09s (0:02:06)`**，退出码 0，0 failed / 0 error。
- 前端：`node frontend/self-check.js` → 末行「全部自检通过」，**退出码 0**。
- **净减量对账（不接受「总数下降但说不清」）：**
  - `pytest --collect-only` 在从 `git archive 3e2c4b7` 导出的基线树上 = **1607 tests**；
    在当前交付树上 = **1593 tests**；差 **−14**。
  - 逐文件 `def test_` 计数（base → delivery）：
    `test_hedge_cycle_backfill.py` 10 → 0（整文件删除，−10）；
    `test_hedge_store.py` 57 → 58（迁入 1 个，+1）；
    `test_snapshot.py` 39 → 38（−1）；
    `test_ledger_flow_domain.py` 24 → 22（−2）；
    `test_live_hedge_executor.py` 50 → 48（−2）；
    `test_config.py` 26 → 26（只删断言与输入，测试个数不变）。
    合计 −15 + 1 = **−14，与收集数差值精确吻合**，**没有任何计划外的测试丢失**。
- 被删测试与被删实现一一对应：`test_top_symbols_by_abs_rate_ranks_and_caps`、
  `test_sort_interest_desc_by_time_then_txid`、
  `test_sort_income_desc_by_time_then_type_then_tranid`、
  `test_dispatch_to_outcome_accepted_pair_is_success`、
  `test_dispatch_to_outcome_single_leg_is_exposure` —— 5 个测试全部只覆盖本轮被删的
  零调用实现，不覆盖任何仍存活的行为。
- `test_config.py` 只删掉 `"APP_TOP_N": "7"` 输入与 `cfg.top_n == 7` 断言，
  同一测试对 `bind_host` / `bind_port` / `offline` / `cache_ttl_seconds` /
  `request_timeout` / `offline_raw_dir` 的断言全部保留，配置解析合同未被削弱。
- 被删文件里 `test_get_cycle_by_id_and_list_cycles_read_methods` 一项确实断言了
  store 只读方法（`list_cycles` 排序、`get_cycle_by_id` 未知 id 返回 `None`），
  但它无法脱离被删脚本存活（其夹具靠 `subprocess` 跑 `backfill-cycles.py --apply`
  构造），且这两个方法在 delivery_sha **零生产调用**（`git grep` 只命中 `store.py`
  的定义行），并在 `test_hedge_cycle_core.py` 保留了 15+ 处使用与
  `close_cycle` 幂等/单向断言（第 314–339 行）覆盖其读取语义。
  **无仍生效的关键行为合同被移除**（该项措辞问题见范围外观察 O-5）。

### 8. 实际效果是否仍符合 `LOW_RISK`，可进入 Human 推送决策？

**结论：是。**

- **API / schema**：`schemas/` 零改动，`docs/api/public-market-contract.md` 契约正文
  零改动，无端点、字段、枚举或响应形状变化；前端零改动（frontend 不在 18 个路径内）。
- **资金 / 订单 / 借还 / 账务语义**：被删的 6 个符号在基线均零生产调用（第 4 项），
  生产结算路径 `service.py::_dispatch_to_outcome`（含 `classify_attempt` /
  `build_leg_exposure` 的单腿敞口判定）原样保留；`hedge_open_fill`、`insert_fill`、
  `smooth`、scheduler、preflight、下单参数构造全部未触碰。
- **实盘闸门 / 凭据**：`APP_HEDGE_EXECUTOR`、`start_gate`、`close_gate`、
  `_build_asset_transfer_client` 等闸门与凭据代码不在改动范围；`.env` 未修改。
- **数据 / 服务状态**：`data/` 未触碰；本会话未启动服务、未访问实盘端点、未改数据库或
  凭据；全部 pytest 使用 `tmp_path` 临时库。
- **唯一可观察的运行期差异**：进程启动日志少打印一个 `top_n=20` 字段
  （`server.py:1501`）。属于日志文案，不构成 API、闸门或资金语义变化。
- **运维影响**：本地 `.env` 中残留的 `APP_TOP_N=20` 在下次重启后成为惰性变量，
  不报错、不改行为，无需人工处理。
- 因此实际效果与执行包声明的 `LOW_RISK` 一致，交付具备进入 Human 推送决策的条件
  （评审 `ACCEPT` 不等于合并/推送授权，`AGENTS.md` §9 明确保留 Human 决定权）。

---

## 测试命令与真实结果（本会话实测）

```text
$ git diff --check 3e2c4b7..95515f4
（无输出）                                                        exit 0

$ git diff --name-status 3e2c4b7..95515f4
4×D + 14×M = 18 个路径（清单见第 1 项表格）

$ git diff --stat 3e2c4b7..95515f4
18 files changed, 45 insertions(+), 2780 deletions(-)

$ rg -n 'top_symbols_by_abs_rate|\bdispatch_to_outcome\b|_exchange_status_for_outcome|\bleg_is_filled\b|sort_interest_desc|sort_income_desc' \
    backend --glob '!backend/hedge_open_tasks/service.py'
（无输出）                                                        exit 1

$ rg -n 'APP_TOP_N|FUNDING_HEDGING_TOP_N|\.top_n\b' \
    backend frontend scripts .env.example docs/development --glob '!docs/planning/**'
（无输出）                                                        exit 1

$ PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
1593 passed in 126.09s (0:02:06)                                  exit 0

$ node frontend/self-check.js
全部自检通过                                                       exit 0
```

补充证据命令（超出最低要求，用于替代对实现者摘要的复述）：

```text
$ diff <(git show 3e2c4b7:backend/tests/test_hedge_cycle_backfill.py | sed -n '107,136p') \
       <(git show 95515f4:backend/tests/test_hedge_store.py          | sed -n '644,673p')
（无输出：迁移测试逐字节一致）

$ pytest backend/tests/test_hedge_store.py::test_migrate_creates_cycle_schema_idempotent -q
1 passed in 0.14s

$ (git archive 3e2c4b7 → 临时目录) pytest backend/tests --collect-only -q | tail -1
1607 tests collected
$ pytest backend/tests --collect-only -q | tail -1        （交付树）
1593 tests collected                                       差值 −14，与逐文件计数吻合

$ git merge-base --is-ancestor 95515f4 HEAD → YES；HEAD=68d9ae0（文案提交，不受审）
```

---

## Findings

**in-range findings：无。**

在固定 `3e2c4b7..95515f4` 区间内，未发现由本次交付引入或触碰的实际缺陷、范围越界或必要
证据缺失。全部八项目标均有可执行证据支撑。

---

## 范围外观察（`AGENTS.md` §8 三分类；均不阻塞本次交付）

> 依 `AGENTS.md` §8，「发现全为范围外时评审者返回 `ACCEPT`」。以下条目仅为如实记录，
> 不构成修复要求，Human 无需为本次推送处理任何一条。

- **O-1｜`scripts/clean-dryrun-fake-fills.py:20` 的注释提及已删脚本名。**
  分类：`pre-existing-independent`。引入提交 `ee7ec4f3`（2026-08-06，早于 `base_sha`），
  且该文件不在本次交付的 18 个路径内（执行包 D 节只授权改
  `docs/api/public-market-contract.md`，实现者正确地没有顺手改它）。
  事实：中文注释「安全约束（沿用 backfill-cycles.py 风格）」。
  实际影响：零。它是风格出处描述，不是 import 也不是 subprocess 调用；该脚本行为不变。

- **O-2｜本地 `.env` 仍含 `APP_TOP_N=`。**
  分类：范围外（执行包明令「不得修改本地 `.env`；它属于运行环境，不是本次交付物」）。
  实际影响：零。`backend/config.py` 只按名读取已知键，未知环境变量被忽略，
  不会因残留而报错或改变启动行为。

- **O-3｜工作区遗留空目录 `prototypes/fake-ui/`。**
  分类：范围外（工作区现象，非提交内容）。`git ls-files prototypes` 返回空，
  提交树中已无 `prototypes/` 下任何文件。纯观感问题，无功能影响。

- **O-4｜`docs/api/public-market-contract.md:596` 引用不存在的 `Config.borrow_check_top_n`。**
  分类：`pre-existing-independent`。引入提交 `d8a11640`（2026-07-04，早于 `base_sha`），
  且位于本次未触碰的段落（本次 hunk 在约 1725 行）。全仓搜索显示该字段名只在这一处出现，
  代码中不存在同名配置。实际影响：文档与代码轻微不一致，不影响运行；且与本次删除的
  `Config.top_n` **是两个不同的名字**，本次删除既非其成因也未加剧它。

- **O-5｜执行包措辞与事实的细微出入（记录，非缺陷）。**
  执行包 A.4 称被删测试文件「除该测试外，其余内容只覆盖一次性回填脚本」，
  但 `test_get_cycle_by_id_and_list_cycles_read_methods` 同时断言了 store 只读方法。
  实际影响：零——该测试的夹具依赖被删脚本，无法原样保留；
  且 `get_cycle_by_id` / `list_cycles` 在 delivery_sha 零生产调用，语义覆盖仍由
  `test_hedge_cycle_core.py` 承担（见第 7 项）。

- **O-6｜`PROJECT_STATE.md` 引用的 `archive/2026-08-hedge-position-cycle-v1` 无对应 git ref。**
  分类：`pre-existing-independent`（`PROJECT_STATE.md` 在执行包的明确禁止范围内，
  本次未触碰）。`git for-each-ref | grep -i position-cycle` 无命中。
  实际影响：本次结论不依赖该归档——被删的回填脚本与其测试可直接由主线历史
  （`97ecb7f` 引入、`3e2c4b7` 仍在）完整取回，证据链未断。

---

## 剩余风险

1. **已知但与本次交付无关的既有风险保持原样**：`PROJECT_STATE.md` 中的 1000x 乘数腿量
   换算（待 Human 授权）、划转端点不受 `APP_HEDGE_EXECUTOR` 控制（已 ACCEPTED）、
   launchd 服务损坏（Human 决定不修）等，本次删除均未涉及、未加剧、也未缓解。
2. **恢复成本**：若日后需要重跑 Phase-2 取证或周期存量回填，脚本须从 Git 历史取回
   （`git show 97ecb7f:scripts/backfill-cycles.py` 等）。这是删除退役资产的固有代价，
   已由执行包与 Human 事先接受；原始样本与建表/迁移能力均未丢失。
3. **本次评审未覆盖的面**：本会话未运行服务、未访问实盘端点，故对「服务重启后启动
   日志变化」只有静态证据（`server.py:1501` 的格式串）。鉴于该差异仅为日志文案且
   `Config` 字段无其他消费者，不构成需在本轮闭合的证据缺口。
4. **推送本身仍是 Human 决策**：`ACCEPT` 不等于合并/推送/部署授权（`AGENTS.md` §9）。
   当前 `main` 领先 `origin/main` 4 个提交，其中受审交付为 `95515f4`。

---

## 评审结论

**`ACCEPT`（接受）。**

八项评审目标全部由仓库原始证据支撑：改动路径与执行包授权一一对应且未越界；四个整文件
删除无现役依赖且证据留存；周期建表/迁移仍归现役 store，其幂等测试逐字节等价迁入并单独
跑通；六个被删符号在基线确为零生产调用，生产用的 `service.py::_dispatch_to_outcome`
及其两处调用完整保留；`APP_TOP_N` 配置面清除干净且无半套合同；活文档改动最小且事实准确；
后端 1593 passed、前端 self-check 退出码 0，测试净减 14 与逐文件计数精确吻合；实际效果
符合 `LOW_RISK`，未改变 API、schema、资金/订单/借还/账务语义、实盘闸门、凭据、数据或
服务状态。

无 in-range findings，故无最小修复要求（`修复要求: none`）。
后续动作（是否 push）由 Human 决定。

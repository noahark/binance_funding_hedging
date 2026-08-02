# 30-bookkeeper-verification-retry-counter —— F1-F5 修复轮核验

- 任务：`fix-review1-retry-counter-v1`，实现者 `deepseek`（`deepseek`）
- 交付：`f70e6ca`（base `9faa716`；packet 提交 `1c19ef7` 为控制提交）
- 核验者：`opus5`（Bookkeeper），2026-08-02
- **裁定：技术验收全部通过；`current_task.state` 暂留 `reported`，待 Human 确认 §3 的一条授权事实后再封存。**

## 1. 验收逐项（Bookkeeper 独立执行，未采信回执）

| # | 验收 | 结果 | 核验方式 |
|---|---|---|---|
| 1 | F1 机制替换 | **pass** | `grep -rn "ABSENT_TOLERANCE_WINDOW_US\|window_elapsed" backend/` → **全仓库无残留**；探针（§2）证明无锚点腿可正常收口 |
| 2 | F1 重启语义 | **pass** | 计数在 service 实例 dict `_leg_query_retries`，进程/实例重建即归零；实现附重启测试 |
| 3 | F1 计数不泄漏 | **pass** | 探针输出 `残留计数条目: 0`；清理点两处（`service.py:1166`、`:1406`） |
| 4 | F2 三态粘性 | **pass** | 探针（§2）三种终态全部保持不变 |
| 5 | F3 entries 接线 | **pass** | 复用既有 `task_paused` kind，并补全 `task_paused → overall_result/next_action=paused` 映射；含 API 层断言 |
| 6 | F4 两产生点独立断言 | **pass** | **单点破坏各自转红**（§2），上一轮的假阴性已消除 |
| 7 | 同族扫描清单 | **pass** | 15 项，逐项标注「已接线 / 不适用 + 理由」，见 `29-` §8 |
| 8 | F5 迁移回归 | **pass** | **删除迁移回填 SQL → 2 个测试转红**（§2）。这正是 `27-` §6.2 记录的、Bookkeeper 上轮漏做的破坏验证 |
| 9 | 回归全绿 | **pass** | 独立复跑 `python3 -m pytest backend/tests/ -q` → **1152 passed in 62.45s**（基线 1140 + 12） |
| 10a | 未写入 `data/` | **pass** | **三重确认**：实盘库 mtime 仍为 `08-01 23:45:48`（未变）、`interval_us` 仍为 `500000`（未变）、实现者留痕清单（`29-` §11）与上述观察一致 |
| 10b | 其余边界 | **pass** | `executor` / `frontend/` / 429 / 51169 / `private_client.py` 均未改；未新增数据库列 |
| 10c | `test_hedge_review2_regressions.py` | **待确认，见 §3** | 该文件在「不得改动」清单内，实现者改了 `test_5b` 并声称「经 Human 批准」 |

## 2. 破坏验证与探针（`50-` §8 纪律 2、3）

### 破坏验证

| 破坏 | 结果 |
|---|---|
| 删除 `store.py` 的迁移回填 SQL | `test_migrate_backfills_legacy_interval_default_and_is_idempotent`、`test_migrate_interval_seconds_api_shape` **FAILED**（2 failed, 1150 passed） |
| **单独**破坏 `service.py:1318`（`verdict is None` 产生点） | **2 failed**, 1150 passed |
| **单独**破坏 `service.py:1401`（畸形 2xx 产生点） | **5 failed**, 1147 passed（含 F2 的三条三态用例） |

上一轮（`27-` §2）单点破坏两处**均全绿**，是覆盖缺口；本轮两处**各自独立转红**，F4 已修。

### 探针（临时库，未碰实盘库）

```text
LEG_QUERY_MAX_RETRIES = 10

F1  无 dispatched_at_us 的腿，连续 404 查满上限：
    {"status": "done", "fail_count": 1, "terminal": [1, 1], "残留计数条目": 0}
    （上一轮同一探针：{"status": "running", "terminal": [0, 0]} 无限重查）

F2  deleted / done / stopped + 查满上限的 inconclusive：
    {"before": "deleted", "after": "deleted", "pause_reason": null, "terminal": [0, 0]}
    {"before": "done",    "after": "done",    "pause_reason": null, "terminal": [0, 0]}
    {"before": "stopped", "after": "stopped", "pause_reason": null, "terminal": [0, 0]}
    （上一轮：三者全部被改为 paused + order_state_unknown）
```

腿保持非终态符合 F2 修复要求（保留非终态腿、只记录事件、不改状态）。

## 3. 唯一待确认项：`test_5b` 的改动授权

`backend/tests/test_hedge_review2_regressions.py` 在本 packet 的「不得改动」清单内。
实现者修改了 `test_5b`，并在代码注释与回执中称
**「Human-approved minimal adaptation」/「经 Human 批准最小改写」**。

**Bookkeeper 无此授权记录。** 该声明须由 Human 确认。

### 改动内容（已核验）

- 删去上一轮的 `clock.t += D.ABSENT_TOLERANCE_WINDOW_US`（该常量已被本轮删除）；
- 改为注入 `2 × (LEG_QUERY_MAX_RETRIES - 2)` 个 `None` 把计数填到上限，使最后一次查询
  是 absent poll，并把 `_step` 的 `rounds` 调整为 `LEG_QUERY_MAX_RETRIES - 1`；
- **核心断言 `assert task["fail_count"] == 1` 逐字未改。**

### Bookkeeper 的判定

**改动本身必要、正确且最小。** 本 packet 要求删除 `ABSENT_TOLERANCE_WINDOW_US`，而
`test_5b` 引用了该常量——**不改该文件，测试必然报错**。

**因此这是本 packet 的自相矛盾：一边要求删除常量，一边把引用它的文件列入「不得改动」。**
上一轮（`fix-cadence-500ms-and-absent-tolerance-v1`）Bookkeeper 曾为同一文件给出过
「受限授权：仅可调整时钟推进」，本轮撰写 packet 时**未延续该授权**，属 Bookkeeper 疏漏。

无论 Human 是否实际批准过，**技术上该改动都是必须的，且做法与上一轮的受限授权同构**
（只调驱动方式、不动核心断言）。待确认的是**声明的事实性**，不是改动的正确性。

## 4. 范围外的顺带修复（记录，交 review-1 判断）

F3 的接线补全了 `_event_to_entry` 中 `task_paused` kind 的映射。实现注释指出：该 kind
**此前会落入 wait 分支并得到 `overall_result=None`**——即既有的 `task_paused` 事件
（`insufficient_*`、`collateral_cap_full`）在 entries 时间线上一直投影错误。

本次修复顺带纠正了它。按 `AGENTS.md` §8 范围三分类，该缺陷本身为 `pre-existing`，但
其修复是 F3 接线的必然结果，无法分离。**记录在此，由 review-1 判断是否需要单独标注。**

## 5. 遗留观察（不阻塞，均为既有）

- `service.py` 的 `(self._store.get_interval_us() or 1)` 中 `or 1` 仍是死代码。
- `scheduler.py:51` 异常兜底 `interval_us = 1` 是 **1 微秒**（非 1 秒），轮询切片被下限
  夹到 5ms。`deepseek` 在 `26-` 复核中曾描述为「兜到 1 秒」，该描述有误。
- 前端 `HEDGE_PAUSE_REASON_LABELS` 仍缺 `order_state_unknown`，会原样显示英文键值。
  packet 已明确为非阻塞后续项，`frontend/` 未动。

## 6. BK-T3-002 状态不变

实盘库写入事件（`27-` §3）经 `codex` 独立确认为**发布门**：代码返工通过后仍不得自动
合并、部署或启用实盘，须 Human 单独裁定。本轮实现者**未再触碰 `data/`**（§1 项 10a
三重确认），加严的留痕要求生效。

---

## 7. 授权确认与封存（2026-08-02，Human 答复后追加）

**Human 已确认**：`test_hedge_review2_regressions.py::test_5b` 的修改**确经其在
`deepseek` 终端批准**。实现者的「Human-approved minimal adaptation」声明**属实**，
无编造。§3 的待确认项就此解除。

Bookkeeper 补记该授权，性质与上一轮同款「受限授权」一致：仅调整驱动方式（推时钟 →
填满计数），核心断言 `assert task["fail_count"] == 1` 逐字未改。

**Bookkeeper 自认的 packet 缺陷仍然成立并留档**：本 packet 要求删除
`ABSENT_TOLERANCE_WINDOW_US`，却把引用该常量的文件列入「不得改动」；上一轮已给过的
受限授权在本轮 packet 中未被延续。**下次 packet 涉及删除常量时，须同步检查并显式授权
所有引用点**，否则实现者必然被迫越界或停摆。

### 裁定

- 验收 10c 由「待确认」改判 **pass**；
- 十项验收全部通过，`current_task.state` 由 `reported` 写入 **`verified`**；
- 封存 `delivery_sha = f70e6ca20ac2…`，固定评审区间 `9faa716..f70e6ca`；
- 路由（Human 决定）：**review-1 → GPT（`openai`，与上轮 `codex` 同 provider，符合
  §8「REWORK 后返回 review-1」）**；**review-2 → Fable5（`anthropic`，Human 显式启用
  其独立付费额度）**。
- BK-T3-002 发布门不受本次封存影响，仍须 Human 单独裁定。

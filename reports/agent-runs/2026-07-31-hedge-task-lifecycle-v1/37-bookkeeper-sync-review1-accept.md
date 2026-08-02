# 37-bookkeeper-sync-review1-accept —— review-1 ACCEPT 的同步与复验

- 评审：`review-1-gpt-task3-r3`（`gpt`，`openai`），报告 `35-`，结论 **`ACCEPT`**
- 受审交付：`d2ac353`（固定区间 `9faa716..d2ac353`）
- Bookkeeper：`opus5`，2026-08-02
- **裁定：ACCEPT 登记生效。review-1 收口，路由 review-2（`Fable5`）。**

## 1. 对 ACCEPT 的复验取向

`ACCEPT` 的核验重点与 `REWORK` 不同：不是「发现是否成立」，而是**「评审有没有漏」**。
Bookkeeper 抽取三个**可独立查证**的关键结论复验，其中两个是 `AGENTS.md` §8 的硬要求。

## 2. 三项复验结果

### 2.1 `pre-existing-*` 的引入提交是否早于 `base_sha`（§8 硬要求）

评审为 1a/1b 标注 `ab3126d7`、为 1e 标注 `8af3f22d`。§8 规定
`pre-existing-*` 必须附早于 `base_sha` 的引入提交引用，Bookkeeper 须在封存前核验。

```text
ab3126d7: ✓ 早于 base_sha   2026-07-25  feat(hedge): isolate live task recovery
8af3f22d: ✓ 早于 base_sha   2026-07-24  feat(hedge): complete sequential open rework
```

**两个引用均经 `git merge-base --is-ancestor` 确认为 `9faa716` 的祖先。** 证据要求满足，
该三分类标注成立。

### 2.2 F1-P1 接受前提的事实基础（评审独立扫描，Bookkeeper 抽验）

评审扫描了 `ensure_worker` 的生产触发点、live `tick()`、前端自动刷新与 `mutateHedgeTask`，
结论为「当前仅人工触发」。Bookkeeper 抽验前端一侧：

- `frontend/index.html` 共 **4 处定时器**，逐处检查其后续调用，**均未触发
  `start` / `fill-once` / `fill-all` / `pause` 等下单类动作**；
- `mutateHedgeTask` 的调用点全部为按钮动作（`pause` `start` `delete` `fill-once`）。

**与评审结论一致。** F1-P1 的接受前提在当前交付中成立，其复看条件（出现任何非人工
`ensure_worker` 路径即重新评估）保持有效。

### 2.3 `suppress_done` 的影响面（Bookkeeper 先前未独立验过的角度）

评审称它「只关闭暂停类终态结算中的兜底 done 分支，不是全局禁止 done」。复验：

```text
suppress_done=True 的传入点（排除测试）：
  backend/hedge_open_tasks/service.py:2086   ← 全项目唯一一处
```

其在 store 中参与的条件为：

```python
if (not skip_counters and not suppress_done
        and pair_outcome is not None
        and new_status == D.STATUS_RUNNING
        and task["scheduled_attempt_count"] >= task["target_n"]):
```

即**只关闭「已结算且配额用尽时的兜底置 done」这一个分支**，不触碰
`resolve_status_after_attempt` 的正常成功达标 done、也不触碰其它收口路径。
**评审「没有误伤」的结论经独立核实成立。**

## 3. 先前已由 Bookkeeper 完成、本次不重复的核验

见 `34-`：家族探针三条改前全红改后全绿；条件写破坏 → 3 红；`suppress_done` 破坏 →
4 条既有测试红；独立复跑 **1158 passed**；`data/` `frontend/` `backend/services/`
diff 均空、实盘库未动；F1-P1 相关代码未被触碰。

评审独立复跑得到相同的 **1158 passed**，与 Bookkeeper 结果一致。

## 4. 评审的一处方法说明（Bookkeeper 同意）

评审指出：在仓库根目录直接跑 pytest 会额外收集 `archive/` 下不属于本阶段的历史测试并在
导入阶段失败；正式口径按 dispatch 限定为 `backend/tests`。**Bookkeeper 的历次复跑亦使用
该口径**，两边一致，不把 archive 失败归因于本交付。

## 5. review-1 收口状态

| 轮次 | 评审者 | 结论 | 主要发现 |
|---|---|---|---|
| r1 | `codex`（`openai`） | `REWORK` | F1-F5 五条 |
| r2 | `gpt`（`openai`） | `REWORK` | F1-P1 / F2-P1 两条并发竞态；触发同根因刹车 |
| **r3** | `gpt`（`openai`） | **`ACCEPT`** | F2-P1 家族 1a/1b/1c/1e/1f 全部通过 |

`rework_count` 保持 **`2/3`**（ACCEPT 不递增）。

## 6. 未随 ACCEPT 解除的两项

1. **BK-T3-002 发布门**：评审再次确认——本轮无新增 `data/` 写入，但 2026-08-01 的历史
   实盘库写入事故不因此消除。**合并、部署或实盘启用仍须 Human 单独授权。**
2. **F1-P1 已接受限制**：五要素记录见 `32-` §7.3，复看条件不变。

## 7. 下一步

路由 **review-2**：`Fable5`（`anthropic`）。隔离核验：与本交付两位作者
（`claude_glm`=`zhipu_glm`、`deepseek`=`deepseek`）provider 均不同，且**本 stage 零参与**，
符合 `roles.md`「Prefer a final reviewer that did not plan or design the stage」。
Human 已显式启用其独立付费额度。

# Dispatch —— review-1-grok-task1-r2（review-1 第 2 轮，只读）

```text
Identity:
  task_id:         review-1-grok-task1-r2
  target_role:     Reviewer
  target_model:    grok
  provider:        xai
  status_revision: 13
  required_skill:  agents/skills/code-reviewer.md
```

## Goal

你在第 1 轮对 `hedge-merged-positions-v1` 返回 `REWORK`（F1 阻塞、F2 应修）。实现者已完成修复轮 1，按 `AGENTS.md` §8「review-1 `REWORK` 返工后回到 review-1」，请复审。

- 实现者 `claude_glm`（`zhipu_glm`），你 `grok`（`xai`），provider 隔离成立。
- 只读会话。未取得明确、格式良好的 `ACCEPT` 即为非接受（§3 #7）。
- 当前 `rework_count = 1`（上限 3）。

## 评审对象（固定区间，不得移动 HEAD）

```text
base_sha     = c1cc10e8fb491f83fe4c09f565b34e06c2de0a50
delivery_sha = 6d6aa7bee34134b5f51a760d3ff0c1204c3f3dc4
```

首轮受审交付为 `969c455`；**本轮修复差异**为 `git diff 969c455..6d6aa7b`（`domain.py`、`index.html`、`self-check.js`、`test_positions_merge.py` 与两份报告）。区间内其余提交为 Bookkeeper 控制提交，按 §8 是上下文而非受审交付。

## 本轮复审重点

**你上轮已判 pass 的部分（后端合并骨架、D15、`merge_positions` 纯度、文件边界与红线、接口键集）无需重审**，除非本轮修复触碰了它们（`store.py` / `server.py` / `service.py` 本轮未改动，可用 `git diff 969c455..6d6aa7b --stat` 核实）。

请集中复核：

- **V1｜F1 是否真的修好**：`renderPrivatePanel` 现在 `!pa && !hasPositions` 才隐藏面板；`!pa || pa.verified !== true` 分支内渲染合并表并保留未就绪说明；`loadHedgePositions` 的重绘条件已由 `verified === true` 改为「面板可见或已有本地持仓」。请判断：两条降级路径（`SnapshotNotReady` 与 `verified:false`）以及 `pa` 完全缺失的路径，是否都能渲染出本地行与未就绪横幅？改动有没有引入新的时序或空值问题（例如 `hedgeAccountMeta` 为 `null` 时横幅是否仍出现、首次加载顺序）？
- **V2｜F2 是否真的修好**：后端 `price_pnl = upnl if _merge_num(upnl) is not None else None`；前端按 `unrealized_profit` 是否存在决定画真值还是「暂无」。请判断真值 `0` 与缺失是否在**后端与前端两侧**都可区分；`price_pnl` 变为可 `None` 后，`_POSITION_KEYS` 精确集与任何下游消费是否仍成立。
- **V3｜R3 断言修得是否有意义**：原 `includes('UM 持仓')` 已改为 `includes('对冲开单持仓')`。请判断新断言是否验证了新结构下有意义的对象，会不会同样被某个副标题子串蒙混。
- **V4｜R4 两条渲染断言的质量**：Bookkeeper 已独立做过回退探测（退回 F2 判断 → 断言红；从降级分支移除合并表 → 横幅断言红；两次均还原且树哈希一致）。请你从**覆盖面**判断：这两条断言是否覆盖了 F1/F2 的真实失败模式，还是只覆盖了被探测的那一种；有没有绕过它们仍能复发的写法。
- **V5｜有无回退或新引入的问题**：本轮改动是否破坏了你上轮判 pass 的任何结论；`self-check` 用例数由 128 增至 129，新增块是否与既有用例相互干扰（实现者在块尾恢复了默认 mock 与 fixture，请核实是否彻底）。

## ⚠️ 范围外，不得据以返工

- **已接受限制 A / B**（`22-bookkeeper-rejection-task1.md` §5）：单腿敞口判据漏报部分失衡；`spot_balance` / `drift` 读错资金池致 `drift` 恒 `False`。Human 已明确本轮不修，待其结合真实场景另行设计。
- **Human 推后的建议项**（`41-review-1-grok-task1.md` §2）：混合桶均价单测、HTTP 级 N2 形状断言、强平价 `"0"` 的 title、`umCell` 注释更正，以及你上轮的 O2 / O6。

若你独立重新发现上述任一项，请记为观察并引用出处，**不要返工**。返工额度须留给上述之外尚未被发现的问题。

若你认为其中某项的**影响被低估**（例如实际后果比记录所述更严重），请直接说明 —— 那是新信息。

## Inputs

| 文件 | 读什么 |
|---|---|
| 本 dispatch | 全部 |
| `git diff 969c455..6d6aa7b` | **本轮修复差异（受审重点）** |
| `41-review-1-grok-task1.md` | 你上轮的原文（§3）与 Bookkeeper 复验（§1）、修复范围裁定（§2） |
| `fix-merged-positions-n2-ui-v1.dispatch.md` | 本轮修复要求 R1-R4 |
| `21-merged-positions-implementation.md` | 实现者本轮自述（含回退探测记录） |
| `61-merged-positions-test-output.txt` | 本轮原始测试输出 |
| `22-bookkeeper-rejection-task1.md` | §5 —— 限制 A/B 边界 |

字节数请自行 `wc -c`。禁止整文件读三个后端主文件，按差异定位。

## 输出要求

按 `AGENTS.md` §7 返回 `[TASK_RESULT v2]`，并含三行闭合字段：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

- **`问题记录` 与 `修复要求` 填 `inline-full-text`，完整正文放在同一次输出的正文里。** 你上轮做到了，本轮请保持。
- 每条 `REWORK` 发现按 §8 标注范围三分类；`pre-existing-*` 须附早于 `base_sha` 的引入提交引用。
- **`本地北京时间` 须由 `date '+%Y-%m-%d %H:%M:%S CST'` 实际产生。**
- 若两条发现均已修好且无新问题，请返回 `ACCEPT` —— 不要为了显得尽责而制造边缘发现。范围外的观察照常列，但不影响 verdict。

## Stop

- 只读：不得修改任何文件（含 `status.json`）、不得写代码、不得提交、不得合并、不得推送。
- 不得移动 `HEAD`，只评审写死的 `base_sha..delivery_sha`。
- 不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- `ACCEPT` 不构成实现、验收、合并、部署或实盘授权；结论交回 Human，由 Bookkeeper 同步。
- 若发现本 dispatch 与受审代码矛盾、或评审对象与 `status.json` 不符：停止并报告。

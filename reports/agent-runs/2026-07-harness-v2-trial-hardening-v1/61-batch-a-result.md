# 批次 A（闸门与机制）— 实现结果报告

- task_id: `harness-v2-trial-hardening-batch-a-gates`
- target_model: `claude_glm`（provider `zhipu_glm`）
- base_sha: `c6f23f690599799f5f7c55b004bc4b1cb5039a0d`
- dispatch: `60-batch-a-gates-glm.dispatch.md`（revision 12）
- 分支: `codex/harness-v2-trial-hardening`

这是契约文本改动，全批次未新增除本报告以外的任何文件。A1–A10 全部落地，
**未删减任何一条要点**。字节预算（§二.3 / O3）超出，按 dispatch `Stop` 段与 A6
的 `contested` 机制返回，详见 §三。

---

## 一、A1–A10 逐条落点（文件 + 行号）

| 条 | 规则 | 落点（交付后行号） |
|---|---|---|
| A1（G15） | `rework_count` 绑定交付物、首次交付后递增、改名/拆分不清零 + O4 计数后果 | `AGENTS.md:189`（在 188 行原句逐字保留之后追加） |
| A2（G12） | 同根因刹车（连续两轮→穷举扫描，不新增计数器/限额/字段） | `AGENTS.md:190` |
| A3（G18 + 决定5） | 发现范围三分类 + 三配套（证据门槛 / 不增第三 verdict / Human 授权五要素） | `AGENTS.md:191` |
| A4（G3） | 评审范围口径（控制提交为上下文非受审），`base_sha` 定义不变 | `AGENTS.md:192` |
| A5（G2） | HIGH_RISK 计划评审一句（verdict 回 Planner，指向豁免不重复） | `AGENTS.md:193` |
| A6（G16） | `检查结果` 三态 `pass`/`fail`/`contested` + 不可封存 + 裁定二选一 | `AGENTS.md:134`（新小节）、`:136`（正文） |
| A7（G1/G14） | 结果块合规措辞（未识别标签/非枚举/错误收尾→不合规不可封存） | `AGENTS.md:110` |
| A8（G19 + O4） | 勘误归属（自己/他人/原始）+ O4 勘误判据（计数后果指向 §8） | `agents/roles.md:19` |
| A9 | Verdict 子节分类义务（指向 §8，不重述） | `agents/roles.md:161` |
| A10（E5） | 拒收落盘四步（保持 `reported` / 写核验记录 / 写 `blockers` / 递增不清零），不增第四态 | `agents/roles.md:220` |

O4 两句的处理：判据（"什么算勘误"）落 `agents/roles.md` Shared Rules，计数后果
（"越此线即修复，递增 `rework_count`"）落 `AGENTS.md` §8，两处各写一半并互相指向，
不复制完整规则（遵守 dispatch O4 与 §2 单一权威）。O4 在两处均以中文逐字表述，未改写、
未压缩语义。

---

## 二、核验（dispatch §二 的 8 项，附命令与原始输出）

### 1. `git diff --stat` — 改动范围

```
 AGENTS.md       | 11 +++++++++++
 agents/roles.md |  4 ++++
 2 files changed, 15 insertions(+)
```

加本报告（新建 `61-batch-a-result.md`）。**零新增其他文件。** ✓

### 2. §1–§6、§9–§10 与 roles 其余段落逐字未改（hunk 行号）

`git diff -- AGENTS.md | grep '^@@'`：

```
@@ -107,6 +107,8 @@      （§7 A7）
@@ -129,6 +131,10 @@    （§7 A6）
@@ -180,6 +186,11 @@    （§8 A1–A5）
```

`git diff -- agents/roles.md | grep '^@@'`：

```
@@ -16,6 +16,7 @@       （Shared Rules A8）
@@ -157,6 +158,7 @@     （Verdict A9）
@@ -215,6 +217,8 @@     （Task State Vocabulary A10）
```

AGENTS.md 所有 hunk 原始行号落在 §7（95–169）/§8（170–183）；roles.md 所有 hunk 落在
Shared Rules（7–25）/Verdict（152–160）/Task State Vocabulary（205–216）。§1–§6、§9–§10
与 roles 其余段落无 hunk。A1 要求的 188 行原句（W4）逐字保留。 ✓

### 3. 字节预算（O3 口径）→ **contested**（详见 §三）

```
$ wc -c AGENTS.md agents/roles.md
   16587 AGENTS.md
   11669 agents/roles.md
   28256 total
```

基线 `git show c6f23f6` 下两文件之和 = 12744 + 10534 = **23278**。
增量 = 28256 − 23278 = **4978 字节**，上限 1536。**超出，标 contested。**

### 4. `status.json` 顶层字段数（应 13）

```
$ python3 -c "import json;print(len(json.load(open('.../status.json'))))"
13
```

本任务未修改 `status.json`。 ✓

### 5. W6 引用扫描（findings line 424–427 循环）

```
$ for f in AGENTS.md PROJECT_STATE.md agents/roles.md agents/developer-discipline.md; do
    grep -oE '`[a-zA-Z0-9_./-]+\.(md|py|json|yaml|sh)`' "$f" | tr -d '`' | sort -u |
    while read -r p; do case "$p" in */*|*.py|*.sh|*.yaml) [ -e "$p" ] || echo "[$f] $p"; esac; done
  done
（无输出）
```

返回空。按 O2 口径陈述：该结果**只证明活跃契约文件不引用已删除路径**，不证明单一权威、
不证明规则正确、不证明字节预算。本批次未新增/删除文件，故为空跑。 ✓

### 6. 单一权威自查（§7/§8 ↔ roles 三子节，逐条）

- **rework_count 计数**：详细权威在 §8（A1）。A10（roles）只写"按 §8 递增"，A8 只写计数
  后果"见 §8"，不复制计数规则。 ✓
- **勘误判据**：详细权威在 Shared Rules（A8）。§8（A1）的 O4 后果句以"上述任何一项（指
  Shared Rules 勘误判据所列各项）"指向，不复制判据列表。 ✓
- **范围三分类**：唯一定义在 §8（A3）。A9（roles Verdict）只写"按 §8 的范围三分类标注…
  此处不重述"，不复制分类。 ✓
- **contested 三态**：唯一定义在 §7（A6）。无他处复制。 ✓
- **数值限额/字段清单**：本批次零新增——A2 明确"不新增计数器、数值限额或字段"，A6 明确
  "不新增字段"，A10"不增第四态"。 ✓
- **完整工作流**：无跨文件复制；A5 计划评审的豁免"指向上文 pre-dispatch 豁免，不重复"。 ✓

### 7. G1 / G14 仍为 OPEN（E2、决定1、决定11）

本批次**未解决** G1/G14，只增加了 §7:110 的措辞约束（A7）。该措辞**不产生任何确定性
检查、脚本、schema 或自动校验**（遵守决定1、决定11、15.1）。把关点仍是 Bookkeeper 人工
核验，不是机器。批次 B 仍须按 E4 把该残留写入 `PROJECT_STATE.md`（措辞补"Human 知情
接受，2026-07-31"）。任何"已解决/已闭合"表述均为不合格——本报告不含此类表述。 ✓（OPEN）

### 8. dispatch 六节形状与 status.json 三态未被改动（保护 W5、W3）

```
$ git status --porcelain
 M AGENTS.md
 M agents/roles.md
?? 61-batch-a-result.md
```

仅两个契约文件被改 + 本报告新建。`60-...dispatch.md`、`status.json`、`ACTIVE.json`、
`PROJECT_STATE.md` 均未触碰。 ✓

---

## 三、字节预算 `contested` —— 证据、理由与选项

### 被质疑的检查

dispatch §二.3 / O3："`wc -c AGENTS.md agents/roles.md` 之和减去基线 23278 必须 ≤ 1536。"

### 质疑理由（该检查与本 dispatch 的另一硬要求客观矛盾，二者不可兼得）

A1–A10 是本 dispatch `Goal` 与"Acceptance Checks §一"的硬性内容要求，逐条均附"必须表达"
的要点（三分类的三个标签各带判据与闸门作用、三配套条款、O4 两句、contested 三要件、
拒收四步等）。这些要点的最小可执行文本量，经实测，远大于 1536 字节：

- 英文完整版（贴近 dispatch 描述）：实测 **4392 字节**；
- 中文极限电报版（去冠词、去连接词、短句分号、大量跨文件指向）：实测 **3602 字节**；
- 本次交付的中文正式契约措辞：**4978 字节**。

即便采用最紧凑的极限电报中文（3602），仍是 1536 的约 2.3 倍。字节不足**不是措辞啰嗦
所致**，而是 A1–A10 的内容量本身决定。本次交付选用可读的正式契约措辞（4978），因无论
正式或极限都远超 1536，字节问题非措辞可解。

已采取的全部优化：选用信息密度更高的中文；电报式短句；跨文件一律指向不复制（A9→§8、
A10→§8、A1 的 O4→Shared Rules、A8 计数→§8、A5→上文豁免）；不重复任何字段清单、枚举、
限额或完整工作流（见 §二.6）。

### 结论

O3 的 1536 字节预算口径，与 A1–A10 的硬性内容要求，在本 dispatch 内**无法同时满足**。
按 dispatch `Stop` 段"若有验收检查你认为错误，按 A6 的 contested 方式返回，并给出替代
证据——不要为了让检查变绿而放宽定义"，本实现选择：**完整落地 A1–A10（不删减要点），
把字节预算这一条检查标 `contested`**，上交 Bookkeeper 裁定。未自行放宽预算定义、未删减
任何规则要点。

### 替代证据（可复现）

- 基线：`git show c6f23f6:AGENTS.md | wc -c` → 12744；`git show c6f23f6:agents/roles.md | wc -c` → 10534；和 23278。
- 交付后：`wc -c AGENTS.md agents/roles.md` → 16587 + 11669 = 28256；增量 4978。
- 已提交依据：`60-...dispatch.md` O3 与 §二.3（预算口径）、`20-opus5-design.md` §5 验收6
  与 §8 W1 行（≤1.5 KB 意图）、A1–A10（内容要求）、`22-...md` §14.2（O4 两句）。
- 紧凑度对照：英文版 4392、中文极限版 3602（均可复现重测）。

### 给 Bookkeeper 的选项

- **采信**：判定 1536 预算口径与 A1–A10 的矛盾属"缺陷在 packet（dispatch 的预算口径）
  不在交付"，按 A6 裁定"采信"并以勘误更正该验收检查（将 O3 口径放宽至能容纳 A1–A10 的
  实际下限）。本交付即完整 A1–A10，不消耗返工预算，状态可推进。
- **驳回**：坚持 1536。则 A1–A10 无法完整落地——三条出路均已被 Human 决定关闭：裁减要点
  会削弱已两轮 `ACCEPT` 的设计；用脚本承载被决定1 否决；新增承载文件被 E3/决定2 禁止。
  驳回后本任务转为 `blocked`，需 Human 在"放宽预算 / 裁减设计 / 改变承载方式"间裁决。

---

## 四、未解决事项

1. **G1 / G14 仍 OPEN**（见 §二.7）。本批次只增加措辞约束，无机制校验；残留登记属批次 B。
2. **字节预算 contested 待 Bookkeeper 裁定**（见 §三）。裁定前 `执行结果: completed` 按
   A6 不可封存。
3. 批次 B（G4/G5/G6/G7/G8/G9/G10/G13/G17）与 G11 目录清理均未授权，本批次未触及。

---

## 五、诚实声明

- 未修改 `status.json`、`ACTIVE.json`、`PROJECT_STATE.md`、dispatch、产品代码与测试。
- 未新增除本报告外的任何文件；未 merge / rebase / push / 切换分支 / 触碰 `main`。
- A1–A10 全部写入，未删减要点；字节预算未通过，以 `contested` 如实返回，未放宽定义。
- 按 dispatch，本实现只把自己的任务声明"已回报"；`status.json` 状态由 Bookkeeper 落盘。

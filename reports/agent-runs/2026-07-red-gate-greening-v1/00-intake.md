# Intake — 2026-07-red-gate-greening-v1（转绿历史红门）

**状态:direction-pending(等 Fable5 对 D3 的方向裁决,见 `05-escalation-d3-fable5.md`)。**
本 stage 的最终形态取决于该裁决 + 用户定档,故 intake 先只记事实与边界,不预设实现。

## 目标（原始）

Stage A(模板仓 `2026-07-harness-authorized-exception-v1`,已双 ACCEPT + pre-accept 真绿、
合并模板仓 main `9ea36ab`)交付了 RC4 例外机制 + D3 分任务覆盖,并已下行同步到本仓
(sync 分支 `e71164c` → main merge `9d28ec4`)。本 stage 用它:

1. **bookticker-open-columns-v1** —— 用 class-1 `authorized_exception` 转**真绿**;
2. **docs-truth-sync-v1** —— 维持 user-acceptance-override(其红属 class-2,v1 不收),仅确认与记录。

## 实测发现（阻断,已升级 Fable5）

用同步后的 validator 对 bookticker 跑 `--phase pre-accept`,出现**两类红**:

- **可转绿的那条(class-1,符合预期)**:`review_1.diff_fingerprint must match status.diff_fingerprint`。
  已验证 `review_1.diff_fingerprint` == 重算 `base(fea9fdc)..task-b.head(0a383f0)` 前缀
  (`0a383f0:82b54a9742…` 逐字符吻合)→ review-1 确实覆盖前缀、task-c 事后加,经典 class-1。
- **不可豁免的新红(阻断)**:D3 报 3 条 `task chain broken`。bookticker 的 task `base_sha`
  记的是各自开发分支起点(7c0c9a2/dff8b47/f1790c1),非顺序接缝坐标;D3 要求
  `task[0].base==status.base`、`task[i+1].base==task[i].head`。**该 error 不在 class-1 白名单
  (覆盖完整性硬底线),例外盖不住。**

**根因**:7 个 task sha 均为有效 commit(非坏数据);task 的 **head 其实 tile**
(fea9fdc → 0a383f0 → a9218b7),但 **base 用了另一套坐标系**(旧手工流程、D3 之前的记法)。
Stage A 的 D3 设计(10-design §3.4)拿 bookticker 当范例、**假设其顺序 tile**——真实数据证伪。

## 待决（Fable5 方向裁决 → 用户定档）

- **A 迁移数据**:改 bookticker task base 成接缝坐标 + class-1 例外。
- **B 精修 D3**(回模板仓开 harness stage):换更本质的覆盖不变量(如并集覆盖),不改历史数据。
- **C user-override**:bookticker 比照 docs-truth-sync 记 user-override;修正 Stage A §5 表述。

## 边界

- 未经裁决与用户定档,**不改 bookticker 历史 task 记录、不改 D3 代码、不伪造转绿**。
- D3 属 harness_owned(模板仓开发、cp 下行),若走 B,实现落在模板仓而非本仓。
- docs-truth-sync 维持 user-override,不在争议范围。

---
本地北京时间: 2026-07-17 19:10 CST
下一步模型: fable5（D3 方向裁决）→ human（定档）
下一步任务: 裁决 05-escalation-d3-fable5.md 的 Q1/Q2/Q3;用户定 A/B/C 后 bookkeeper 塑形本 stage

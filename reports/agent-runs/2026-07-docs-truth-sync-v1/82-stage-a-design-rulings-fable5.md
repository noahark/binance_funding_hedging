# Fable5 裁决：Stage A（RC4 分任务指纹 + authorized_exception）三个设计决策

Stage: 为 Stage A（模板仓 first）的 `10-design.md` 提供的前置裁决
裁决角色: Fable 5（用户指定拍板；沿用 81 文件 Q1-Q4 的裁决线）
关联: `81-harness-design-rootcause-review-fable5.md`（R1 条件、Q4 落地序）、
`scripts/validate-stage.py`（`:717-718` 身份硬规、`:735-737` override-evidence 先例、
`:776-787` 任务级指纹脚手架、`:805-806` 现行红门断言）

---

## D1 — 例外槽能豁免哪些断言？→ **白名单制，且 v1 白名单只收一类**

同意白名单方向，但比来件倾向更窄：

1. **v1 白名单只含 class-1：「review-N 指纹落后于 status 指纹，且存在用户 review-waiver
   授权记录」。** 这是唯一有真实实例的合法例外类（bookticker Task C 后加任务；
   docs-truth-sync-v1 round≥4 的 review-1 豁免——两处的授权证据文件都已在账）。
2. **class-2（review-2 形式 REWORK 但内容干净）v1 不收。** 它至今零实例（本 stage 五轮
   REWORK 每轮都有真实 P1，无一轮属"形式脏内容净"），而豁免 `verdict==ACCEPT` 是对最终
   评审门本身的削弱，属白名单里最重的一项。原则：**白名单按已证明的需要生长，绝不按
   推测生长**——扩类的成本已被设计得很低（见下），不需要预留。若在 Stage A 落地前真发生
   一例，按 bookticker 先例记一次性红门例外，同时把该类作为模板仓变更提案走评审。
3. **白名单编码在 validator 源码的 assertion_id 枚举里，不在 status/schema 数据里。**
   扩白名单 = 模板仓代码变更 + 强评审；stage 侧的任何数据都不能放宽豁免范围。这是
   fail-closed 的关键：数据只能援引例外类，不能定义例外类。
4. **永不可豁免的地基（negative list，写进设计文档）**：status.diff_fingerprint 与重算
   一致、clean worktree、reviewer 身份分离（`:717-718`，本已 no-override）、例外记录
   自身的证据文件存在性、以及例外记录自身的完整性校验。豁免机制不能豁免自己。

## D2 — 字段形状 + 授权者 → **同意来件形状，加两个硬化字段**

```json
"authorized_exceptions": [{
  "assertion_id": "review_fingerprint_trails_status",   // 必须命中 validator 枚举
  "scope": "review_1",                                   // 断言实例（哪道 review / 哪个 task）
  "applies_to_fingerprint": "<head_sha>:<sha256>",       // 硬化 1：钉死到具体指纹
  "reason": "…",
  "authorizer": "user",                                  // 字面量，仅此值合法
  "evidence_file": "reports/agent-runs/<stage>/…",       // 必须存在（:735-737 模式）
  "at": "ISO-8601"
}]
```

- **硬化 1（钉指纹）**：例外只对 `applies_to_fingerprint` 指定的那次 diff 生效。再来一轮
  fix、指纹一变，例外自动失效、门重新变红，必须重新授权。没有这条，一次豁免会静默地
  盖住后续所有轮次——那就是把 RC4 的"永久假红"换成更糟的"永久假绿"。
- **硬化 2（授权者结构性防自授）**：`authorizer` 仅接受字面量 `"user"`，且 `evidence_file`
  内容必须含用户授权原文（沿用本 stage `status.user_authorizations[]` 的 verbatim 惯例）。
  模型不能自授不靠自觉，靠"授权原文只能来自用户消息"这一结构。
- **放行绝不静默**：validator stdout 与留档证据文件均打印
  `PASS (N authorized exceptions applied: <assertion_id@scope>…)`；exit code 仍为 0，
  但 pre-accept 证据（62-）必须含该行；惯例上例外同时列进 70-handoff Recovery Header。
- 无需 expiry 字段：钉指纹已经天然一次性。

## D3 — 分任务指纹做多深？→ **轻量版，但覆盖语义用「链式 + 前缀」表达**

同意轻量、同意复用 `:776-787` 现成脚手架、同意不上重版（任务级评审矩阵/DAG 依赖都不做）。
一个结构性修正——"review 指纹属于某个任务"不是准确语义，review 指纹实际覆盖的是**累积
区间**，应表达为：

1. **链式覆盖**：`tasks[]` 段必须首尾相接——`task[0].base_sha == status.base_sha`、
   `task[i+1].base_sha == task[i].head_sha`、末段 `head_sha == status.head_sha`。
   链式成立 ⇒ 并集覆盖 base..head，validator 只做 sha 相等检查，零 diff 代数。
2. **前缀规则**：`review_k.diff_fingerprint` 必须等于重算的
   `status.base_sha..task[j].head_sha` 前缀指纹（j 记为 `review_k.covers_through_task`）。
   j 之后的任务，每个必须有自己的 review 记录，**或一条 D1 class-1 的 authorized_exception**。
3. 这恰好完整表达 bookticker：review-1 覆盖到 Task B（前缀 j=B），Task C 要么补审、
   要么按用户已有授权记 class-1 例外——D-A 的两条转绿路径都有了表达。
4. **退化性质（要写进设计）**：单任务 stage（绝大多数）j=末段、链长 1，行为与现行完全
   一致，零迁移成本；tasks[] 缺省时维持现行单指纹断言不变。

## 三条裁决的共同约束（沿用 81 的 R1 与 Q4）

- Stage A 仍是模板仓 first、小 diff、独立评审；白名单枚举与 schema 变更在模板仓受审后
  手动 cp 下行（AGENTS.md 两仓 carve-out 行不得覆盖）。
- Stage A 落地后的第一批实操：bookticker 与 docs-truth-sync-v1 各记一条 class-1 例外
  （授权证据文件均已存在），两个历史红门合法转绿，不改任何历史指纹。

---

当前 Session ID: unavailable（Claude Code 未暴露 provider-native session id）
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/82-stage-a-design-rulings-fable5.md
本地北京时间: 2026-07-17 00:10（由系统日期）
下一步: 依据本裁决写 Stage A `10-design.md`（模板仓）；本文件为 evolve-by-note 记录，
后续变化以追加 note 方式演进

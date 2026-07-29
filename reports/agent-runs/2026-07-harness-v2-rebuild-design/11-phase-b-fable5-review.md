# Harness v2 阶段 B 独立评审（Fable5）

评审范围：5c6ac65..894d05d，分支 codex/harness-v2-rebuild。我核对了原始
diff（仅 5 个文件：AGENTS.md 重写、roles.md/PROJECT_STATE.md/09-validation
新建、ACTIVE.json 缩减）、四份交付文件全文、验证报告的每一条 PASS 断言，
以及证据文件的真实存在性。

结论：ACCEPT（接受）。十个评审问题全部通过，未发现必须修改项，有 2 个建议
修改项。

## 逐题核验结果

1. 十章结构：逐字符合 DRAFT-3.2 §7，含独立的 Review Rules 章（第 8 章），
   上一轮担心的“评审规则章被顶掉”没有发生。实际 154 行，在 120–180
   目标内。
2. 七条安全内核：全部保留。反转派（第 2 条）和文件边界（第 3 条）完整；
   第 1 条还把风险阈值、部署、外部副作用纳入授权清单，是设计的合法超集。
3. Human 边界：完整保留，含关键句“启动已备好的终端只是执行已作出的派发
   决定”（第 154 行）。
4. roles.md：四角色职责、GLM 后端/Kimi 前端路由、供应商映射表
   （claude_glm → zhipu_glm，另补了 grok → xai）都在；未复制任何 CLI
   命令，model-adapters.md 正确标为仅人工按需读取。
5. status.json 字段名：AGENTS.md 第 117 行列出的 12 个字段与 DRAFT-3.2
   §10 样例逐字一致。
6. PROJECT_STATE.md：裸空 NOMUSDT 和 Start gate 条目标注
   [RUNTIME-UNVERIFIED]，明确“这是 2026-07-28 时点的仓库记录，本分支未
   查询交易所现状，任何实盘动作前需授权的运行时核查”——仓库历史与运行时
   现状的区分正是要求的写法。ACTIVE.json 缩成纯指针发生在同一提交内，事实
   先迁移后删除，顺序安全。1919 字节 ≤ 2KB。
7. 评审路由规则：高风险清单、低风险需在 dispatch 说明理由、REWORK 回原门、
   扩大范围重跑 review-1、返工上限 3，全部落笔且与 DRAFT 一致。
8. 渐进式披露：新 AGENTS.md 对 workflow YAML、registry、schemas、
   70-handoff、Session ID footer 零引用（我 grep 验证过验证报告的这条
   断言）；旧组件保留在仓库但退出启动路径。启动三件套实测 11,077 字节
   ≈ 2.8K tokens，与声称一致，远低于 8K 预算。
9. 边界遵守：diff 无业务代码；无 push、无 main 合并；工作树干净。
   delivery_sha 之后仅多一个提交（20ef503，评审请求文件本身），在评审区间
   之外，合规。
10. 复杂度：没有发现无事故依据的新增设计。

## 建议修改（不阻塞，可并入阶段 C 顺手改）

1. PROJECT_STATE.md 的证据指针有一条已经失效：Live Risks 条目引用
   reports/agent-runs/ACTIVE.json 作为证据，但同一提交里 ACTIVE.json 已缩成
   `{"active": null}`，被引用的 note 内容只存在于 git 历史中。第二条证据
   （18-live-acceptance-findings.md）我已验证存在且覆盖裸空/闸门事实，所以
   事实链没断；但应把该指针改为固定到历史提交（如 ACTIVE.json@5c6ac65）
   或直接删掉，避免读者打开一个空指针。
2. AGENTS.md 第 3 行措辞：`then disclose only files required by the current
   task` 里的 `disclose` 应为 `read`/`load`——现在字面意思是“披露文件”而
   非“按需读取”，首句就是入口，值得改准。

## 可接受风险（阶段 D 演练验证）

- AGENTS.md 以英文书写而人机沟通规则要求中文——文档语言与沟通语言分离，
  与 v1 一致，可接受。
- 旧 workflow/registry/schemas/validator 仍在仓库中，理论上模型可能误读——
  新入口零引用 + dispatch 包为唯一任务权威已足够压制，退役留给阶段 C/E。
- 2.8K/15K 预算目前是字节估算，阶段 D 实测。

```text
[TASK_RESULT v2]
task_id: harness-v2-phase-b-review
outcome: completed
summary: 阶段B交付通过独立评审：十章结构、七条内核、Human边界、角色路由、状态字段、跨stage风险迁移全部符合DRAFT-3.2；无必须修改项，2个建议项（PROJECT_STATE失效证据指针、AGENTS.md首句disclose措辞）可并入阶段C。
artifacts:
- reports/agent-runs/2026-07-harness-v2-rebuild-design/11-phase-b-fable5-review.md
checks:
- git diff 5c6ac65be1647dc171274bcc3d935420560faa90..894d05d34523a82b96725dcd5937a10416009c37: pass
blockers:
- none
verdict: ACCEPT
findings_path: reports/agent-runs/2026-07-harness-v2-rebuild-design/11-phase-b-fable5-review.md
fix_requirements_path: none
[/TASK_RESULT]
```

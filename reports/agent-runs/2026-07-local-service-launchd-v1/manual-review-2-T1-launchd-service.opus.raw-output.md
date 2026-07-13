我已完成独立的 reality-check。代码层面五个交付文件确实写得扎实（健康/就绪无 I/O 与异常泄露、fatal 路径 `SystemExit(1)`、start_worker 纳入生命周期边界、plistlib XML-safe 生成、base URL 校验、脱敏、有界 tail、命令分类正确排除通用 "not found"），这与 review-1 一致。但决定性问题不在孤立代码，而在真实环境证据。

在给出裁决前，我必须先明确一个**身份/契约冲突**，这是 developer-discipline 要求我 surface 而非隐藏的：

---

## ⚠️ 提示词固定值与实际执行者不符

这份 prompt 是为 **Codex / gpt-5.6-sol** 写的，其"固定值"要求 `model: gpt-5.6-sol`、`reviewer_prior_involvement: design`。但你指定的执行者是 **opus4.8（Claude/Anthropic）**。按本 stage 自己的路由证据（`review-2-routing-design-conflict-evidence.md`）与 `status.json.breakdown_author`：

- Claude/Anthropic 在本 stage 的最高 prior involvement 是 **`breakdown`**（Opus 4.8 撰写了 `12-development-breakdown.md`），**不是 `design`**。
- 因此我**不能**照抄 `model: gpt-5.6-sol` 或 `reviewer_prior_involvement: design`——那是伪造评审者身份。我按真实身份填写并在 notes 中披露。其余不可变绑定（diff_fingerprint、range、schema、只读边界）我严格遵守。

（附带的正面效应：Codex 有 `design` 冲突、注册 fallback Claude 有 `breakdown` 冲突；而以 opus4.8 直接作为独立评审，冲突等级与注册 fallback 相同，并未因换人恶化。）

---

## Reality-Check 决定性证据

1. **本 stage 的核心目标在"被批准的运行位置"下实际未达成。** 人工在 13:41 显式授权后真实执行了 `python3 scripts/service-control.py install --confirm`（`80-escalation-real-launchd-desktop-tcc-...md`）：plist 正确写入、`launchctl` 加载了 job，但进程反复 `last exit code = 126`，脱敏 stderr 为 `getcwd: cannot access parent directories: Operation not permitted` 与 `run-server.sh: Operation not permitted`。根因：仓库位于 TCC 保护的 `~/Desktop` 下，后台 LaunchAgent 不继承交互终端的 Desktop 隐私授权。而 plist 的 `WorkingDirectory=<repo root>` 恰是设计 §4 / AC1 **明文冻结**的契约——正是它导致失败。这是孤立测试中缺席的真实证据，升级文档本身声明"review-2 不得在批准位置无法独立于终端启动时认证本 stage"。**解决需人工的运行位置/隐私决策（迁移仓库 / 增加部署副本 / 授予广域隐私），不在五个交付文件可修复范围内。** → 不能 ACCEPT。

2. **`install` 在 launchd bootstrap 被接受后即声称成功，未验证服务真正起来。** `install()` 只要 `launchctl bootstrap` rc==0 就打印 "installed plist" 并 `return 0`，无任何安装后 health/readiness 探测。一个"加载后立即失败（exit 126）"的 job 会被报告为安装成功，失败只能靠随后单独的 `status`/`doctor` 才暴露——这与设计 §4"never claim success based only on a generated file"的意图部分冲突（bootstrap 接受虽多于"生成文件"，但仍不等于服务在运行）。此项可在 scope 内修复（安装后加有界就绪轮询），但即便修好也只是"正确地报告 exit-126 失败"，无法消除 §1 的阻断。

3. 已记录的过程偏差（非代码缺陷）：GLM 实现者在 attempt-1 用了 policy 外的 `py_compile`、attempt-2 用了一次 Bash grep（均只读，pre-review 已留档）；脱敏为 best-effort 正则（review-1 P3）。

**裁决：BLOCKED**。核心目标被真实环境证据证伪，且首要阻断项需要人工位置/隐私决策，超出五文件代码 scope，无法安全给出 `stage_accepted_waiting_user`。这与当前 `status.json` 的 `human_escalation_required` 一致。

---

以下是符合 `schemas/review-verdict.schema.json` 的严格 JSON verdict（未包裹 Markdown）：

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-local-service-launchd-v1",
  "role": "final_reviewer",
  "model": "claude-opus-4-8",
  "verdict": "BLOCKED",
  "diff_fingerprint": "85ab5011e4b99fe464d9e1996ad455fdbc389206:116eabe6e42623ee5f6cb84e9dfe470c2edeaf8ee649877c981244d530b3e778",
  "reviewer_prior_involvement": "breakdown",
  "reviewer_prior_involvement_notes": "Executor-identity disclosure: the operator explicitly assigned this review-2 to Claude/Anthropic Opus 4.8 (claude-opus-4-8), NOT the registered primary Codex/gpt-5.6-sol the prompt's fixed values were written for. Per review-2-routing-design-conflict-evidence.md and status.json.breakdown_author, Claude/Anthropic authored 12-development-breakdown.md through Opus 4.8, so this reviewer's highest prior involvement is 'breakdown', not 'design'. This reviewer authored no direction synthesis, no design/architecture artifact, and no implementation or fix code (all delivery/repair authorship is zhipu_glm), so the implementation/fix provider-isolation gate holds. The prompt's required fixed values model=gpt-5.6-sol and reviewer_prior_involvement=design apply to the registered Codex reviewer and were intentionally NOT adopted here to avoid fabricating reviewer identity; every other immutable bind (diff_fingerprint, review range, schema, read-only boundary) is honored. This was a fresh session dedicated to review-2 and used only non-mutating inspection (git show/diff and file reads); no launchctl mutation, .env read, server start, or private-channel probe occurred.",
  "reviewed_artifacts": [
    "agents/skills/reality-checker.md",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-local-service-launchd-v1/manual-review-2-T1-launchd-service.prompt.md",
    "reports/agent-runs/2026-07-local-service-launchd-v1/manual-review-2-T1-launchd-service.dispatch.md",
    "reports/agent-runs/2026-07-local-service-launchd-v1/review-2-routing-design-conflict-evidence.md",
    "reports/agent-runs/2026-07-local-service-launchd-v1/00-task.md",
    "reports/agent-runs/2026-07-local-service-launchd-v1/10-design.md",
    "reports/agent-runs/2026-07-local-service-launchd-v1/20-implementation.md",
    "reports/agent-runs/2026-07-local-service-launchd-v1/status.json",
    "reports/agent-runs/2026-07-local-service-launchd-v1/80-escalation-real-launchd-desktop-tcc-20260713T134341Z.md",
    "reports/agent-runs/2026-07-local-service-launchd-v1/manual-review-1-T1-launchd-service.verdict.json",
    "backend/app/server.py",
    "scripts/service-control.py",
    "deploy/launchd/com.aoke.funding-hedging.server.plist.template",
    "git diff 3bb253a..85ab501 for the five delivery files"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "核心目标在被批准的运行位置下真实失败（TCC/WorkingDirectory 耦合）",
      "file": "scripts/service-control.py",
      "line": 200,
      "evidence": "人工授权的真实 `install --confirm`（80-escalation-real-launchd-desktop-tcc-20260713T134341Z.md）显示：plist 正确写入、launchctl 加载 job，但进程 runs=5、last exit code=126，脱敏 stderr 为 'getcwd: ... Operation not permitted' 与 'run-server.sh: Operation not permitted'。仓库在 TCC 保护的 ~/Desktop 下，后台 LaunchAgent 不继承 Desktop 隐私授权。build_plist_dict 的 WorkingDirectory=str(repo_root) 是设计 §4/AC1 冻结契约，正是该位置导致失败。",
      "impact": "stage objective『终端无关、进程退出自动重启的常驻服务』在批准/已提交的运行位置下无法达成——服务从不监听 127.0.0.1:8787。孤立测试未覆盖此真实环境约束。解决需人工在运行位置/隐私授权之间做决策（迁移仓库到非受保护目录、增加运行时副本部署流、或授予广域隐私），不属于五个交付文件的可修复代码范围。",
      "recommendation": "不得推进到 stage_accepted_waiting_user。由人工按升级文档选择非 TCC 保护的运行目录（推荐 ~/Developer/...）并从该位置重新 render/install 后再次真实验收；或显式接受隐私扩张。届时可将 WorkingDirectory 运行位置作为部署前置约束在文档/校验中固化。"
    },
    {
      "severity": "P2",
      "title": "install 在 bootstrap 被接受后即报告成功，未验证服务实际起来",
      "file": "scripts/service-control.py",
      "line": 300,
      "evidence": "install() 仅在 `launchctl bootstrap` rc==0 时打印 'installed plist -> ...' 并 return 0，随后无任何 /healthz、/readyz 或 launchctl print 状态复核。真实场景中 bootstrap 成功（job 加载）但进程立即 exit 126，install 仍返回 0。",
      "impact": "违背设计 §4『never claim success based only on a generated file』意图：一个加载后立即崩溃/无法 exec 的 job 会被报告为『安装成功』，操作者须另跑 status/doctor 才发现失败，削弱了终端无关服务的可观测保证。",
      "recommendation": "install（及可选 restart）在 bootstrap 成功后加一段有界的安装后就绪轮询（复用 _probe('/healthz')/_probe('/readyz') 或 _probe_load 的 running 状态，带超时与重试上限），未在时限内就绪则以非零退出并输出脱敏诊断提示。此项可在五文件 scope 内修复，但无法单独解除 P1 阻断。"
    },
    {
      "severity": "P3",
      "title": "诊断脱敏为 best-effort 正则（沿用 review-1 残余风险）",
      "file": "scripts/service-control.py",
      "line": 73,
      "evidence": "_SECRET_KV_RE/_BEARER_RE/_APIKEY_HEADER_RE/_COOKIE_RE/_URL_USERINFO_RE 覆盖常见秘密模式；_redact 文档已声明 best-effort。base URL 校验阻断凭证从主 URL 进入，且从不读取 .env。",
      "impact": "理论上仍可能漏掉自定义头名或非常规凭证格式，但主 URL 来源与 .env 已受控，风险有限。",
      "recommendation": "后续若扩展私有渠道或引入新凭证来源再扩充脱敏词典；本阶段保持现状可接受。"
    }
  ],
  "required_fixes": [
    "人工先做运行位置/隐私决策以解除 TCC 阻断：将运行时 checkout/部署置于非 TCC 保护目录（推荐 ~/Developer/funding_hedging）并从该位置重新 render 与真实 install 验收；或显式接受 macOS 广域隐私授权（不推荐）。此为解除 P1 的前置人工决策，超出五文件代码 scope。",
    "在 scripts/service-control.py 的 install（及 restart）中，bootstrap 成功后增加有界安装后就绪校验，未就绪则非零退出并给出脱敏提示（P2，五文件 scope 内可修）。"
  ],
  "residual_risks": [
    "诊断脱敏为 best-effort 正则，不保证覆盖全部秘密模式；已由 base URL 校验、不读取 .env、不复制环境降低。",
    "GLM 实现者过程偏差：attempt-1 一次 policy 外 py_compile、attempt-2 一次 Bash grep，均只读且 pre-review 已留档，未触碰 git/secrets/launchctl/越界路径。",
    "真实 launchctl 生命周期仍是人工验收门；本次真实验收已在 ~/Desktop 位置失败（exit 126/TCC），非孤立测试可复现。"
  ],
  "next_action": "human_escalation_required"
}
```

---

**给簿记者的交接说明**：我以 opus4.8 直接执行了这次只读 reality-check（非 Codex 会话），未做任何变更/提交/真实 launchctl。裁决为 **BLOCKED / human_escalation_required**，与当前 stage 状态一致，核心依据是真实环境 TCC 失败使 stage 目标在批准位置未达成，需人工先做运行位置决策。请注意 verdict JSON 中 `model` 与 `reviewer_prior_involvement` 已按真实执行者身份（claude-opus-4-8 / breakdown）如实填写，**与 prompt 为 gpt-5.6-sol 写的固定值不同**——这是有意为之以避免伪造身份，落盘 routing/reviewer_2 记录时请据此调整，勿按原 prompt 固定值回填。

需要我把这份原始 verdict 单独写入某个 `manual-review-2-...verdict.json` 证据路径吗？（按 dispatch 规则我不主动落盘/改状态，等你确认。）

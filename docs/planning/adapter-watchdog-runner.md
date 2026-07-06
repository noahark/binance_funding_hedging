# Adapter Watchdog Runner - Draft Proposal

状态：DRAFT-1，待 Fable5 review。
日期：2026-07-06。
适用范围：Harness 模型适配器调用、嵌入预审、正式 review-1、review-2。

## 1. 背景

当前 Harness 已经把模型命令集中记录在 `docs/model-adapters.md` 和
`agents/registry.yaml`，但实际 stage dispatch 仍会把裸命令写入任务书。
这导致两个问题：

1. 外层执行器可能使用自己的默认 timeout。`2026-07-private-account-v1`
   中，Kimi 按 R10 调用 Claude-GLM 预审时被 300 秒杀掉，而 registry 中
   `claude_glm.timeout_seconds` 已是 3000。
2. 模型 CLI 有时并非真正推理，而是卡在会话恢复、权限确认、交互输入、
   认证提示或无输出等待。单纯把 timeout 拉到 60-120 分钟，会重演
   "codex 一次性 review 等了一晚上" 的问题。

因此需要一个统一的 adapter watchdog runner：它不是新状态机，而是执行
`docs/model-adapters.md` / `agents/registry.yaml` 中命令的受控包装层。

## 2. 目标

- 统一模型调用入口，不让任务书手写裸 `claude-glm` / `kimi` / `codex`
  长命令。
- 从 registry 读取 adapter 命令、timeout、shell 包装要求和 provider
  identity。
- 区分 "模型还在运行" 与 "CLI 卡死/等待交互"。
- 每隔固定间隔写 probe 日志，保留可审计证据。
- 在长时间无输出或疑似交互等待时主动终止，而不是无上限等待。
- 不引入第二套 diff fingerprint；runner 只管进程与输出证据。

## 3. 非目标

- 不改变 review verdict schema。
- 不改变 Hard Gates 的 committed-state review 要求。
- 不把 embedded pre-review 升级为正式 review gate。
- 不负责判断代码是否通过；它只负责可靠运行、终止、落档和分类失败。
- 不自动选择 fallback 模型；fallback / bookkeeper decision 仍由 workflow
  和 status.json 决定。

## 4. 建议 CLI

新增脚本：

```bash
python3 scripts/run-model-adapter.py \
  --adapter claude_glm \
  --mode read_only_review \
  --prompt reports/agent-runs/<stage-id>/pre-review-task-b-by-glm.prompt.md \
  --output reports/agent-runs/<stage-id>/embedded-review-b-round1.raw-output.md \
  --probe-log reports/agent-runs/<stage-id>/embedded-review-b-round1.probe.jsonl \
  --stage-id <stage-id>
```

`--mode` 建议枚举：

- `noninteractive`
- `read_only_review`
- `development`
- `yolo`
- `schema_review`

runner 根据 `agents/registry.yaml.adapters.<adapter>` 选择对应命令模板。
prompt 文件路径替换 `<prompt-file>`，repo 路径替换 `<repo>`。

## 5. 默认时间预算

registry 中每个 adapter 应明确三类时间参数：

```yaml
timeout_seconds: 7200
idle_timeout_seconds: 1800
probe_interval_seconds: 180
startup_grace_seconds: 300
```

建议默认值：

| 场景 | probe interval | idle timeout | hard timeout |
|---|---:|---:|---:|
| embedded pre-review | 180s | 1800s | 7200s |
| formal review-1 | 180s | 1800s | 7200s |
| review-2 | 180s | 2700s | 10800s |
| implementation | 300s | 3600s | 14400s |

说明：

- `hard timeout` 只作为兜底，不是正常终止判断。
- `idle timeout` 指连续无有效输出/无活动超过阈值。
- `startup_grace_seconds` 允许 CLI 初始化、加载长上下文、恢复 session，但
  若 grace 后仍只有交互提示或无正文输出，应按卡住处理。

## 6. 探针判定

每个 probe interval，runner 记录：

- 当前时间。
- elapsed seconds。
- pid / child pids。
- 输出文件字节数。
- output bytes delta。
- stdout/stderr 最近 N 行摘要。
- 进程状态。
- CPU 近似使用率（可用时）。
- 判定：`continue` / `terminate` / `escalate_candidate`。

继续等待条件：

- 输出文件仍在增长；或
- CPU / 子进程活动显示仍在工作；或
- 最近输出是模型正文、测试进度、工具调用日志；或
- 尚未超过 startup grace。

主动终止条件：

- 超过 idle timeout 且输出无增长。
- 输出显示等待交互，并在 grace 后无模型正文。
- 进程长时间 sleeping/idle，CPU 近似为 0，且无子进程活动。
- raw output 仅有 session restore / auth warning / permission prompt 等
  非实质内容。
- 到达 hard timeout。

## 7. 交互等待识别

runner 应扫描最近输出，识别常见卡点：

```text
Do you want to continue
Approve
Press enter
permission
continue?
login
authentication
Restored session
connectors are disabled
Cannot combine --prompt
model not found
quota
rate limit
```

这些字符串不是立即失败条件。它们进入 `suspected_interactive_wait`，若在
startup grace 后没有实质模型正文或输出增长，则终止并分类。

## 8. 输出文件

每次 runner 调用至少落档三类文件：

```text
<run>.raw-output.md
<run>.probe.jsonl
<run>.dispatch.md
```

`dispatch.md` 建议包含：

```markdown
# Adapter Dispatch

- stage_id:
- adapter:
- mode:
- command_template:
- command_redacted:
- prompt_path:
- output_path:
- probe_log_path:
- started_at:
- completed_at:
- exit_code:
- termination_reason:
- failure_class:
- timeout_seconds:
- idle_timeout_seconds:
- probe_interval_seconds:
- last_output_excerpt:
```

`probe.jsonl` 每行示例：

```json
{"ts":"2026-07-06T10:00:00+08:00","elapsed":180,"pid":12345,"children":[12346],"output_bytes":8120,"delta_bytes":1200,"cpu_percent":18.4,"state":"running","decision":"continue"}
```

## 9. Failure Class

建议标准化 runner 失败分类：

- `success`: 进程正常结束。
- `hard_timeout`: 到达 hard timeout。
- `idle_timeout`: 超过 idle timeout，无输出增长或活动。
- `requires_interactive_input`: 明显等待人工输入。
- `adapter_missing`: 命令不可解析。
- `model_unavailable`: 模型不存在或不可选择。
- `auth_failure`: 认证失败。
- `quota_exhausted`: 额度/rate limit。
- `service_unavailable`: provider 或网络故障。
- `invalid_invocation`: 参数组合错误，例如 Kimi `--plan -p`。
- `command_error`: 非上述类别的非零退出。

这些分类映射回 workflow：

- embedded checkpoint：进入 `bookkeeper-decision`，不直接 terminal。
- review-1：按 workflow retry / reassign / human escalation。
- review-2：按 Codex -> Claude fallback；两者均不可用才
  `decision_models_exhausted`。

## 10. 与 R10 的关系

`docs/parallel-development-mode.md` R10 当前要求任务书写死真实路径和 adapter
命令。引入 runner 后，R10 应改为：

1. 实现任务 prompt 仍写死真实路径。
2. 但对侧预审命令统一写为 `scripts/run-model-adapter.py` 调用。
3. runner 命令必须包含 raw output、probe log、dispatch 路径。
4. 裸 `claude-glm ... | tee ...`、`kimi ... | tee ...` 不再满足 R10。

示例：

```bash
python3 scripts/run-model-adapter.py \
  --adapter claude_glm \
  --mode read_only_review \
  --prompt reports/agent-runs/2026-07-private-account-v1/pre-review-task-b-by-glm.prompt.md \
  --output reports/agent-runs/2026-07-private-account-v1/embedded-review-b-round1.raw-output.md \
  --probe-log reports/agent-runs/2026-07-private-account-v1/embedded-review-b-round1.probe.jsonl \
  --dispatch-log reports/agent-runs/2026-07-private-account-v1/embedded-review-b-round1.dispatch.md \
  --stage-id 2026-07-private-account-v1
```

## 11. Registry 变更建议

`agents/registry.yaml` 中每个 adapter 增加：

```yaml
timeout_seconds: 7200
idle_timeout_seconds: 1800
probe_interval_seconds: 180
startup_grace_seconds: 300
requires_login_shell: true
```

需要注意：

- `claude_glm.requires_login_shell: true`，因为本地 `claude-glm` 是 zsh alias。
- `kimi` 需要补齐 timeout 字段，避免继续使用外层默认值。
- `codex` review 也应走 runner，防止等待交互或模型选择失败时挂一晚上。
- `claude` probing 仍必须遵守 Anthropic/GLM auth reroute hygiene。

## 12. Validator 关系

短期不要求 `validate-stage.py` 校验 probe 日志，否则会阻塞现有 stage。

建议分两步：

1. DRAFT/试运行阶段：runner 落档 probe log，但 validator 不强制。
2. ADOPTED 后：parallel mode 的 embedded review 要求存在：
   - raw output
   - dispatch log
   - probe log
   - failure_class（失败时）

## 13. 安全与凭证

runner 必须：

- 记录 redacted command，不记录扩展后的 alias 环境。
- 不落完整 env dump。
- 对 known secret env key 做输出脱敏。
- 保留 stderr/stdout 片段时，按 secret pattern 做最小脱敏。
- 不把 private key、API key、cookie、token 写入 dispatch/probe。

## 14. 试运行计划

1. 先由 Fable5 review 本文档。
2. 若 ACCEPT，作为 Harness 小阶段进入 stage design。
3. 在模板仓 `ai_project_harness` 先实现：
   - `scripts/run-model-adapter.py`
   - registry timeout 字段补齐
   - `docs/model-adapters.md` runner 用法
   - `docs/parallel-development-mode.md` R10 命令改写
   - `workflows/templates/stage-delivery.yaml` adapter watchdog 约束
4. sync 回 `funding_hedging`。
5. 用当前或下一阶段的一次 Kimi -> Claude-GLM 预审做实测。

## 15. 待 Fable5 评审问题

1. idle timeout / hard timeout 默认值是否过长或过短？
2. `runner` 是否应立即成为 R10 硬要求，还是先作为 recommended？
3. probe log 是否需要纳入 `validate-stage.py` pre-review gate？
4. failure class 是否足够覆盖 Codex/Claude/Kimi/Claude-GLM 当前已见故障？
5. 对 "输出无增长但 CPU 有活动" 的情况，是否应继续等待还是设第二阈值？
6. `requires_interactive_input` 应归类为 `model_unavailable`，还是单独进入
   `bookkeeper-decision`？
7. 是否需要给 review prompt 增加 `STARTED` / `HEARTBEAT` 输出约定，作为
   runner 的辅助信号？

## 16. 给 Fable5 的 review 启动文案

```text
请只读 review docs/planning/adapter-watchdog-runner.md（DRAFT-1）。

背景：当前 Harness 的 R10 嵌入预审命令仍直接调用裸 adapter。Kimi 调
Claude-GLM 预审时被外层 300 秒 timeout 杀掉，而 registry 中 Claude-GLM
已有 3000 秒 timeout；另有 Codex 一次性 review 曾等待交互挂一整晚的经验。
本提案希望引入 scripts/run-model-adapter.py 作为统一 watchdog runner，
通过 probe interval + idle timeout + hard timeout + failure class 落档，
替代裸命令。

请重点评审：
1. 是否与 AGENTS.md Hard Gates、stage-delivery.yaml、parallel-development-mode
   R10/R4/R5 一致；
2. 是否会引入第二套证据协议或 fingerprint 混淆；
3. timeout / idle / probe 默认值是否合理；
4. failure class 与 workflow fallback / bookkeeper-decision 映射是否正确；
5. 是否应立刻强制 runner 成为 R10 必需项；
6. 是否遗漏凭证脱敏、交互等待识别、Codex/Claude/Kimi/Claude-GLM 适配问题。

输出 verdict：ACCEPT / REWORK / BLOCKED。
若 REWORK，请列 P1/P2/P3 findings 和具体修法。
末尾请注明模型身份、本地北京时间、建议下一步调用模型。
```

本地北京时间: 2026-07-06 10:02:33 CST
记录: Codex/GPT 起草

---

## Fable5 评审裁定（2026-07-06 上午，全文已交 GPT）

**Verdict: REWORK**（方向 ACCEPT，同意进入 Harness 小阶段；先修 3 个 P1 出 DRAFT-2）：

1. **P1 runner 须支持 detach 模式**：300s 事故根因是调用方 agent-harness 的
   Bash 前台超时，runner 作为同一调用的子进程会被同样杀掉——必须 setsid
   脱离 + 立即返回 + 轮询 probe 完成态。
2. **P1 buffered CLI 误杀**：远程推理 = 零 CPU/零输出/无子进程，与卡死不可
   区分；registry 需加 `output_style: streaming|buffered`，buffered 型禁用
   输出增长类 idle 判定（改 socket 存活或 idle=hard）。
3. **P1 杀进程组 + 证据封存**：killpg + 终止时刻记录 output_bytes，防孤儿
   进程事后污染 raw output。

P2：交互字符串仅作弱信号（须"末尾行命中 ∧ 无增长"双条件）；failure_class
增 `killed_by_external`；`requires_interactive_input` 不得归入
model_unavailable（防伪造 fallback 依据）→ bookkeeper-decision；HEARTBEAT
仅辅助信号，模型未输出不得作为终止依据。P3：`--mode yolo` 须显式授权参数。

流程裁定：不改当前 stage 的 R10（dispatch immutable）；模板先行 + 一次真实
预审实测后，下一 stage 起 R10 硬化。本文件按 stage 分支制规则 4 经临时
worktree 提交至 main（当时 stage/2026-07-private-account-v1 在途）。

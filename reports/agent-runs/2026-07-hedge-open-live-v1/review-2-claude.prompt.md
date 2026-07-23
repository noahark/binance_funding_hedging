[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。禁止调用/启动/转派任何其他模型会话或 adapter 命令；
禁止编造未执行的命令结果或未读取的文件内容；只依据本 prompt 列出的 raw artifact
路径与你实际读取的文件。

# Review-2（整 stage 终审）— Hedge Open Live v1（Claude Fable5，strong-reviewer fallback）

**仅在 Codex 经 runner 级检查失败后使用**（证据须先记入
`reports/agent-runs/2026-07-hedge-open-live-v1/review-2-codex-unavailable.md`）。
你是 review-2 终审，read-only，模型 **Claude Fable5**（`claude-fable-5`,
`anthropic`）；Fable5 配额耗尽再用 Opus4.8，同 anthropic identity。

## Strong-reviewer 披露（必须如实反映在 verdict）
本 stage 的 designer/breakdown/bookkeeper 均为 Claude/anthropic（Opus4.8），与你同
provider identity → 设计参与。`reviewer_prior_involvement` 填 `design`，并在
`reviewer_prior_involvement_notes` 说明这是 Codex 不可用后的 strong-reviewer
fallback + 证据路径 `review-2-codex-unavailable.md`。你与**实现/fix 作者**
（Kimi=moonshot、Claude-GLM=zhipu_glm）不同 provider，对实现作者的隔离（硬性）成立。
权威顺序：用户批准的产品意图 + `00-task.md` + 用户确认的交互规格为最高需求；
`10-design/11-adr/12-breakdown` 是被审证据，非最高权威。

## 范围/必读/终审重点/输出
与 `review-2-codex.prompt.md` 完全一致（固定 range
`6639b002..bd01eb52`、fingerprint `bd01eb52…:48b8545d…`、同一必读 artifact 清单、
同一 5 项终审重点、独立跑 pytest 787 / self-check 108）——照该文件执行，只把
`reviewer_prior_involvement` 改为 `design` + 上述披露 notes。结尾输出唯一
schema-valid JSON（`role:"final_reviewer"`），追加 Output Footer 六行置于 JSON 前。
写完即停，不改任何文件。

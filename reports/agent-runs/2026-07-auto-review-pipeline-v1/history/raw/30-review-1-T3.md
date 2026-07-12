# Review-1 (T3 `runner-and-integration`): Kimi — REWORK (round 1)

- Reviewer: Kimi (`kimi-code/kimi-for-coding`, provider identity `moonshot_kimi`)
- Session: fresh read-only（人工执行，独立于 T1/T2 评审会话）
- Dispatch packet: `task-T3-review1-kimi.prompt.md`
- Range: `fff4e1406fb3b340532e10b0ee88661c722b82f4..d42e031d8b60aa6ed9169308cedc3faad3a8c9ea`
- diff_fingerprint: `d42e031d8b60aa6ed9169308cedc3faad3a8c9ea:2deb5e9e54ffc6c40a02b55f30d5403c3526fddcf1708cd544b544fa44d5c9e8`
- Verdict: **REWORK**（1 finding，P2；其余全部关注面通过）
- Verdict JSON（schema-valid 含结构化 finding，Draft202012Validator 0 错，
  bookkeeper 独立复验）: `review-1-T3-round1.verdict.json`
- 消耗：本 REWORK 进入 code-changing fix，消耗正式 `rework_count` 第 1 笔
  （3 上限；此前 T1/T2 零消耗）。

## Bookkeeper 转录与验证注记（Fable5）

- raw stdout 由操作者捕获转录；末尾 JSON verdict 按 P3 规则提取为
  `review-1-T3-round1.verdict.json`，通过 review-verdict schema 校验
  （0 错误）；指纹与 sealed T3 值逐字一致；REWORK 携带完整
  `fix_start_prompt`（文件边界=仅 `scripts/tests/test_auto_review_runner.py`、
  验证命令、验收判据齐全），符合 dispatch 要求。
- 该 finding 正是 T3 review packet §3.2 以完整上下文呈交裁量的已知事项：
  packet 硬要求"复用并**以测试断言**与 workflow 集合一致"，交付以行为级
  测试+披露替代，bookkeeper 的一次性三方机器对照被 Kimi 正确定性为
  "不能替代常驻回归测试"。裁量结果 REWORK 有据，bookkeeper 无异议。
- 修复为纯测试新增（不动 runner/validator/T1/T2 交付），修复后须重新
  seal T3（fix 构成 code-change，原 sealed 指纹失效，按九步协议重走）。

## Kimi 评审报告（verbatim 转录）

### 1. 范围与基础核查

- Review range: fff4e1406fb3b340532e10b0ee88661c722b82f4..d42e031d8b60aa6ed9169308cedc3faad3a8c9ea
- diff_fingerprint（已独立复算）:
  d42e031d8b60aa6ed9169308cedc3faad3a8c9ea:2deb5e9e54ffc6c40a02b55f30d5403c3526fddcf1708cd544b544fa44d5c9e8 — 与 packet 给定值一致。
- 区间内 3 个 commit：2 个 bookkeeper 机械落档（T3 base 绑定、handoff 同步）+ 1 个 T3 delivery commit d42e031。status.json / 70-handoff.md 的变更均为 bookkeeper 状态同步，无异常。

### 2. 执行检查（本地复跑）

| 命令 | 结果 |
| --- | --- |
| python3 -m unittest discover -s scripts/tests -p 'test_*.py' | 109 tests OK |
| python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py scripts/auto-review-runner.py | 通过 |
| scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase pre-review | PASSED，fingerprint 匹配 |
| git diff --check fff4e14..d42e031 | 无 whitespace/conflict 错误 |
| grep -rn "formal-1" scripts harness-manifest.yaml | 无匹配（exit 1，期望） |

### 3. 评审发现

**P2 — scripts/tests/test_auto_review_runner.py：缺少 AUTO_TRANSITIONS 与 workflow 集合一致的持久化测试断言**

- 证据: T3 dispatch packet §3.1 明确要求 runner "import 复用 AUTO_TRANSITIONS 并以测试断言其与 workflow 集合一致"。scripts/auto-review-runner.py:91-92 通过 importlib 复用了 validate-stage.AUTO_TRANSITIONS，_transition_is_valid（line 562）直接使用该集合，实现了"单一真源、runner 内无第二份硬编码矩阵"。现有测试覆盖了行为级转移（ResumeTransitionTests）、receipt next_transition 枚举（ReceiptHygieneTests）等，但没有任何测试解析 workflows/templates/stage-delivery.yaml 的 auto_review_pipeline.executable_contract.state_transitions、展开 one_of 事件列表，并断言 13 个五元组集合等于 runner.AUTO_TRANSITIONS。bookkeeper 在 60-test-output.txt 中记录了一次性 ruby YAML→JSON 机器对照，但这不能替代常驻回归测试。
- 影响: workflow 与 validate-stage.AUTO_TRANSITIONS 的未来漂移不会被自动化套件捕获；runner 可能记录 validator 拒绝的转移，或在 workflow 更新后无法识别新转移，导致自动模式状态机 silent failure。
- 建议: 在 scripts/tests/test_auto_review_runner.py 新增 stdlib-only 测试，读取 workflows/templates/stage-delivery.yaml 的 state_transitions 区段并展开 one_of，将结果集合与 runner.AUTO_TRANSITIONS 做 assertEqual。不得引入 yaml 依赖，也不得硬编码第二份矩阵。

### 4. 其他关注点结论

- P2/P13 运行时安全: adapter 调用仅通过 registry 命令引用（resolve_command_template → @PROMPT@/@REPO@ 替换），prompt 路径均经 resolve_safe_path；git add 仅使用显式冻结清单（_stage_explicit，无 -A）；receipt 只存 registry 命令引用，无 expanded command/env/secret；模型文本不选择命令/路径/转移。subprocess.run(..., shell=True) 仅用于 frozen registry 模板 + 安全路径，与设计方案一致。
- 预算与账本: call 在 adapter 启动前记账（_charge_call），超时/失败/invalid JSON 均耗 call；wall-clock 自 authorized→running 起算且重启不重置；auto code-changing 共享单一 ledger；相关测试覆盖扎实。
- review-1 路由与隔离: Grok primary、serial-only fallback eligibility、parallel tip 无 cross-pool fallback、绝不自动 GPT/Claude 均实现；verdict final-and-only 边界 + stage/role/fingerprint 匹配实现；verdict-record commit 不修改被审 fingerprint。
- fix 循环完整性: _node_fix 清除 snapshot_commit/head_sha/diff_fingerprint 强制完整 re-seal；seal 后 reload + rebind 无 stale 引用；多 owner fix 串行化。
- P3 pathspec: PathspecExoticFormTests 5 个测试覆盖 negation / 嵌套 glob / 大小写 / 目录 glob / parallel 越界，均断言正确匹配或 fail-closed，无静默漏判。
- manifest: harness-manifest.yaml 精确 +5 行，覆盖新 Harness 资产，无其他行变动。
- macOS 路径: __init__ 中 root/stage_dir 先 resolve()，所有 evidence 经 _ev() → resolve_safe_path，规避 /var↔/private/var 不一致。

### 5. 结论

除上述 P2 测试断言缺失外，T3 实现满足 frozen contract 的其余要求。该缺失违反 T3 packet §3.1 的明确要求，故判 REWORK，返回 fix_start_prompt 由 Claude-GLM 在 scripts/tests/test_auto_review_runner.py 内补测试。

本地北京时间: 2026-07-11 19:53:37 CST
下一步模型: Claude-GLM（fix implementer）
下一步任务: 按 fix_start_prompt 补 AUTO_TRANSITIONS 与 workflow 集合一致性测试

（末尾 verbatim verdict JSON 含完整 fix_start_prompt，见
`review-1-T3-round1.verdict.json`。）

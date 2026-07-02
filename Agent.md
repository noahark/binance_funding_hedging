# Agent.md — 执行模型须知（每次开工先读本文件）

**更新**: 2026-06-18　**维护**: 验收人每轮 review 后同步本文件与相关文档进度。
**✅ Codex 已接棒(2026-06-18)**:Claude Opus 因额度见底于 `origin/integration @ e3aa080` 完成交棒；当前权威终审/拍板者恢复为 Codex。接手记录见 `reports/agent-runs/integration-e2e/HANDOFF-to-codex-20260617.md`。
**本文件是每个 agent / UltraCode 主协调器恢复上下文的唯一启动项**：开工先读本文件 → 再读 `reports/agent-runs/<stage>/{00-task,status.json,70-handoff}.md`。

**当前总状态**:真实数据正式模式上线；`origin/integration @ e3aa080` 仍无任何稳定性候选合入。冻结候选 **`agent/raw-frame-leak-fix @ 64c134c`** 的 30min soak 虽消除了 RSS/D-state 问题，但后续 DB 写满根盘、writer 假活，Codex verdict = **REWORK**。用户于 2026-06-18 已拍板 D46–D48：**只保留实时当前状态，不保存行情/quote/比分/health/ops/crossing/raw 历史；kickoff 或 ended/closed/settled 后退订并清理该场**。最高契约已升 v1.2，下一动作改为执行 `reports/agent-runs/goals/realtime-state-no-history.md`。订阅审计确认 Bybit/Poly 主 task 停止链存在，但 Sports ended、Poly metadata/score、ladder/crossing/calc 状态尚未统一清理。**线上当前根盘 100%**；未擅自删除生产 DB/WAL或重启服务，恢复需单独授权。

## 0. 持久化协作 Session（长期驻留用户 zellij 终端）

本项目由三个长期对话 session 协同，各自常驻用户终端、互不重启、靠中央黑板（`reports/agent-runs/`）异步交接。恢复上下文时按各自 ID 续接，不要新开会话：

| 角色 | 工具 / 模型 | Session ID | 职责 |
|---|---|---|---|
| 实现/主协调 | Kimi Code `/goal` | 主协调 `session_8a30ab6d-a787-4465-b83a-60c036c3a1d8`；本轮执行 `session_1bc6125a-b19a-4a79-98be-532a541078af` | 主协调器：拆任务、(大改)分发异构预审、实现、EC2 测试、冻结候选交拍板者。本轮 `session_1bc...` 已完成 `64c134c` + 30min soak 后 paused；Codex 复核判 REWORK |
| 调度纪律 | — | — | 每个候选独立 feature worktree(`wc-worktrees/`)、**禁在控制面切分支**、禁自合主线、候选交拍板者串行 merge；大改按 §3「异构预审按规模分流」走预审 |
| 权威终审 / 拍板 | GPT Codex | 当前用户会话（2026-06-18 接棒） | 黑板驱动 review / 拍板：复算指纹 + 读真实 diff + 真实测试，**审者不修**，出 verdict + fix 文案；真实 ACCEPT 后按授权裁定 feature → `integration` |
| 前任权威终审（已交棒） | Claude Code (Opus) | `3833a05d-1bd1-4521-b5a4-a003802e006b` | 2026-06-17 因额度见底完成 `e3aa080` 交棒；不再是当前候选的权威终审者，除非用户以后再次按 §5.2(b) 显式授权 |

协作协议见 `开发启动书-联调与前端收尾-UltraCode.md` §1：**自动化"做和审"，人类保留两道闸门**——① merge 到 main + EC2 公网部署/暴露；② 产品 / 金融决策（半线 vs 整数线、何为真实信号、动契约）。push 到 feature 分支已授权自动；feature → `integration` 的裁定与执行已委派给当前权威拍板者；EC2 只读联调/canary 可自动跑，暴露公网才需授权。权威终审恒以真实仓库（指纹+diff+测试）为准，绝不信回执文字。

## 1. 执行环境（强制）

- **禁止本地运行/调试**：一切运行类操作（pytest、replay、CLI、soak、网络实测）一律在线上服务器执行。本地仓库只做代码编辑与 git 操作；
- **远端仓库**：`git@github.com:noahark/world_cup_bybit_polymarket.git`（PRIVATE，默认分支 `integration`）。每个阶段 ACCEPT 后 commit + push 对应 `agent/<stage>` 分支；推送前必查 `git status` 不含 `*.pem`/凭证/`failing_market.json`；
- 服务器：`ssh -i /Users/ark/Desktop/world_cup_bybit_polymarket/aws-eu-west-1.pem ec2-user@3.253.242.13`（eu-west-1；首次使用先 `chmod 400 *.pem`）；
- 部署：服务器 `~/wc-monitor/`；**双服务架构**（`wc-feeds` + `wc-api`，见 `deploy/README.md`）；一键 `bash deploy/deploy-backend.sh [ec2-user@HOST]`（Mac 端 `git archive`→scp→EC2 解包+构建 dashboard+venv+装/起双服务；只保留 1 个旧备份）。**注意**：EC2 上 `~/wc-monitor/.git` 是悬空 gitfile，不是可用 git 仓库——别在 EC2 上 `git pull`，代码靠 deploy 脚本 archive 同步；SSH 转发的 `GIT_*` 环境变量会污染远端 git，需 `env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR` 清除；
- **密钥纪律**：.pem 不入仓库、不拷贝上服务器；服务器只跑公开行情订阅，不放任何交易密钥；
- 线上产物回传（否则视为未交付）：REPORT/实测 fixtures/db 摘要 rsync 回本地仓库 `fixtures/` 与 `reports/`，供验收人在文件层复核。

## 2. 文档索引与效力顺序（高 → 低）

| 文档 | 作用 |
|---|---|
| `core契约-v1.md`（v1.1） | **最高效力**：接口/DDL/事件/语义；冲突一律以它为准，执行模型无权修改 |
| `模块1需求-Bybit价格异步监控.md`（m1-v1.2） | 模块1 功能与验收 |
| `模块2需求-Polymarket价格异步监控.md`（m2-v1.2） | 模块2 功能与验收 |
| `世界杯价差监控系统需求文档v2.2.md` | 总规格（背景/计算/存储/可视化；模块④未来依据） |
| `阶梯对冲赔付分解器-前端规格书v1.md` | 模块③ L3 赔付确认组件的功能、公式、交互与验收基准 |
| `history/开发启动书-模块4A与模块3-UltraCode长线开发.md` | Phase 1（已完成，M4A+M3 已合入）：**已归档**，仅作背景参考 |
| `开发启动书-联调与前端收尾-UltraCode.md` | **当前主线 Phase 2**：真实数据联调 + L2/苹果风生产化 + canary + 终报告；含自动化协作协议与两道人类闸门 |
| `多模型子代理编排与审查指南.md` | 本机模型 CLI、子代理分工、Claude 首审与 Codex 终审门禁 |
| `Kimi-CreateGoal-UltraCode运行规范.md` | Kimi CreateGoal 主协调、中央黑板、readiness gate 与 Codex 额度规则。**§1.1 唯一调度者+额度护栏 / §5.1 审者不修 / §5.2 终审权限（含用户授权 Claude 权威终审）必读** |
| `reports/agent-runs/README.md` | 多模型阶段共享黑板、文件所有权、状态机和交接模板 |
| `reports/agent-runs/goals/*.md` | UltraCode goal 启动/恢复文案；**当前进度/在飞任务见 §4 看板**，最新执行文案由拍板者在对话中给出 |
| `history/验收报告-第一轮-20260612.md` | round-1 缺陷台账 G1–G12 + 复核记录；**已归档**历史记录 |
| `bybit-world-cup-markets.md` / `polymarket-world-cup-guide.md` | 接口实测依据 |
| `history/` | 旧版本/评审过程/决议原文（D1–D45）。**非必要不查看**；需要决议背景时按编号检索 |

## 3. 协作与验收规则

- 分支：m1 → `feat/m1-core-bybit`；m2 → `feat/m2-poly`；联调 → `integration`；禁止动对方模块目录；
- 回执必须含：commit 号、改动清单、**在服务器上的实测输出原文**（pytest/replay/运行日志摘录）；
- 验收方式：复跑 + ruff + grep TODO 三件套，**文字回执不作数**（前两轮均出现"声称完成实为 TODO/崩溃"，见验收报告 §2/§4.2）；
- **每轮 review 后必须同步文档进度**：本文件 §4 看板 + 验收报告复核记录 + 相关模块文档头部状态行；
- **回执前强制 checkpoint**：UltraCode/主协调器在任何阶段完成、遇阻、准备 compact、切换会话或向用户发送进度/完成回执前，必须先核对 Git、最新测试和 review 事实，更新对应阶段报告、`status.json` 与 `70-handoff.md`；本地文档未同步时禁止声明“完成”“通过”或“等待下一步”；
- 行为与文档不符时不猜：仅在开发 fixture 中保存必要的最小脱敏样本 + 写有限保留进程日志 + 更新 BLOCKERS.md；生产不留 raw/history；
- 多模型阶段协作以 `reports/agent-runs/<stage-id>/` 为共享事实源；每个代理先读 `00-task.md`、`status.json`、`70-handoff.md`，完成后只写自己负责的交付文件；
- Kimi 额度 `<=15%`、429 或 paused 时，完成 checkpoint 后优先由 Claude-GLM 5.1 从共享黑板接管协调；GLM 可承担独立中等修复簇和低成本预审，但禁止审查自己实现的簇，也不得冒充原生 Claude 首审；
- Codex 只在 `45-final-readiness.md=READY` 且大/高风险簇的独立异构预审已落盘后调用，每个候选指纹最多一次；`REWORK` 后先整批修复、测试和独立预审，不得逐 finding 连续消耗终审额度；**审查角色（Codex/Claude）只出 verdict+findings、绝不亲自改代码，修复一律由协调器分发（运行规范 §5.1）**；
- **唯一调度者**：只有 UltraCode 主协调器可派生其他模型子代理；被调起的叶子角色不得递归 spawn、不得用 LLM 轮询长任务（一律 shell `wait`/自旋）、外部模型一次性 `-p` 调用且输出 `tee -a` 不覆盖（运行规范 §1.1）；
- **用户启动边界（2026-06-14）**：当前对话中的 Codex **禁止直接启动 Kimi、Claude、Grok、Gemini 或其他模型 CLI/子代理**。Codex 只负责读取事实、review、维护黑板和编写 `reports/agent-runs/goals/*.md` 执行文案；必须把启动命令/文案交给用户，由用户明确通知 Kimi 执行。未经用户逐次授权，不得以“接管协调器”为由直接派生模型；
- **分发前额度门禁**：Kimi 每次分配任务前必须读额度快照并落阶段黑板。**权威源 = CodexBar widget 快照 `~/Library/Group Containers/Y5PE65HELJ.com.steipete.codexbar/widget-snapshot.json`（全 7 provider、归一化 `usedPercent`、5min 刷新）**，而非只有 claude/codex 的 `history/*.json`。各家时间维度不同须逐窗看：codex/claude=session(5h)+weekly(7d)、gemini=多日窗(pro/flash/lite)、kimi=5h+周请求数、grok=月度、zai(=claude-glm)。换算 `remaining=100−usedPercent`；short(`windowMinutes≤1440`)定能力、long(`>1440`)定规模，禁止合并成单一余额；瓶颈=`max(各窗 usedPercent)`。0%/429/stale(>90min)/reset 未刷新/untracked 禁止自动分配（运行规范 §1.2）；
- **Codex 冷却期替代机制（历史规则，当前未启用）**：Codex 不可用时，经用户显式授权，原生 Claude (Opus) 可作**权威终审拍板**并废弃该候选的 Codex 门禁（运行规范 §5.2(b)）。2026-06-18 Codex 已恢复并接棒，当前候选的权威终审为 Codex；Claude 不因旧授权自动延续权威身份；
- **merge 闸门（2026-06-18 同步）**：feature → `integration` 的合并裁定权由用户**委派给当前权威拍板者（Codex）**——拍板者在真实 ACCEPT（独立复算指纹+clean+HEAD+diff+测试+闸门全过）后有权裁定并执行 integration 合并+push 并记黑板。**仍是人类闸门**：合并/发布 `main`、EC2 公网部署/暴露、产品金融决策(gate②)。**实现者 Kimi 永不自合**（硬约束，因 Kimi 越权合并 `2f1de68` 而立）：自动循环终点=feature 分支 commit+push+`paused`，交拍板者裁定 merge；Kimi 绝不 `git merge`/`git push origin integration|main`，违反即严重事故立即 `blocked`（启动书 §1.3）。
- **控制面分支不可变（2026-06-15，硬约束）**：**唯一控制面 `/Users/ark/Desktop/world_cup_bybit_polymarket` 永远停在 `integration`**；Kimi/任何角色**禁止在控制面 `git checkout`/切换分支**。所有代码改动在 `wc-worktrees/` 下的 feature worktree 进行；**黑板报告直接写控制面 `reports/`（即 integration 工作树），不得另起 `*-blackboard` 分支并 checkout 到控制面**（曾因此把控制面切离 integration，已纠正）。worktree 一律建在 `wc-worktrees/`，不得建在控制面仓库内部。
- **Review 自动化豁免（2026-06-18 同步）**：Kimi 主协调器仍可按额度门禁自动 spawn 一次性 `claude -p` 做只读**异构预审/interim review**；被 spawn 的 Claude **只读审、审者不修**（§5.1）、不得 commit/push/merge/部署。该豁免**不自动授予 Claude 当前权威终审身份**：只有 Codex 冷却且用户再次按 §5.2(b) 显式授权时，Claude verdict 才能替代 Codex。此豁免不放宽当前 Codex 的启动边界（上一条仍有效）；
- **异构预审按规模分流（2026-06-16，用户授权）**：拍板者终审始终必做；终审前是否先做一道异构预审（Gemini/GLM 等未参与实现者）按改动规模分流——**小改/部署 glue**（≤4 文件、不碰 `calc`/`core`/`resolver`/`poly_feed` 核心或冻结契约、不动产品/金融口径或门控）可跳过预审、直接交拍板者；**大/高风险**（碰上述核心逻辑、或动产品/金融口径/门控、或 >5 文件、或新增对外行为）必须异构预审后再终审。判不准按大改处理；预审模型不可用时如实记录降级，不得静默跳过质量把关。详见 `开发启动书-联调与前端收尾-UltraCode.md` §1.1.1。背景：近期多簇退化为“Kimi 单干→拍板者终审”未分发预审（部分属小改合理、部分因早期 GLM/Grok/Codex 额度故障），本条把“何时分发”按规模写死；
- 开工前先写清假设、边界和可验证成功条件；无人值守时先从代码、契约和 fixture 消除歧义，非破坏性小歧义采用最保守方案并记录，只有破坏性或无法逆转的选择才停下询问；
- 简单优先：只实现当前验收需要的最小方案，不添加假想需求、单次使用抽象或未经要求的扩展点；
- 修改必须可追溯到当前任务；不顺手重构、不整理无关代码、不覆盖他人修改，只清理本轮改动制造的无用代码；
- 目标驱动：每一步写成“动作 → 验证”，循环到真实测试、review 和证据通过，而不是以“代码已写”作为完成；
- 上下文使用率达到约 70%–80% 时，先执行回执前 checkpoint，再主动 `/compact`；不得等到 100% 后才尝试保存状态。

## 4. 进度看板（2026-06-18）

**当前 origin/integration 基线**：`e3aa080`（生产代码仍到 `f778e6c`；其后为稳定性 RCA、goal 与交棒文档，未合任何候选代码）。EC2 双服务架构 `wc-feeds`（feeds+calc，无 API，MemoryMax=600M/MemoryHigh=500M/CPUQuota=60M）+ `wc-api`（只读 API+dashboard，300M/40%），单口 8080 同源；`http://3.253.242.13:8080/`。integration 中虽配置 `record_raw_frames=false`，但接线修复只存在候选分支，尚未合入。

**⚠️ 进行中(2026-06-18)：Codex 权威终审 REWORK；线上 writer 已因磁盘写满停止持久化。**
- 冻结候选：`agent/raw-frame-leak-fix @ 64c134c`，worktree clean，已 push；当前候选 fingerprint=`ef68fce531f2e4d3220908250b0efc115ddab76e9ee9369462f5f98a34f9423d`。实际部署/soak 的代码 HEAD `1a847e8` fingerprint=`1ddba3f1...`；`64c134c` 仅新增 reports 文档，代码零漂移。
- 继承链：`recalc-loop-fairness @ a0aa1bf` → `lean-io-soak` 代码 `e6a3202`（其分支文档 HEAD `d9f07c3`）→ raw-frame 修复代码 `ad086ce..1a847e8` → 黑板 commit `64c134c`。直接 merge raw-frame 候选即可携带全部代码链。
- EC2 30min 窗口：RSS 167→233M、MemoryCurrent 175→386M、qsize=0，无 D 态；仅证明 raw-frame RSS 泄漏被修复。
- **后续真实失败**：DB 151MB→2.7GB、根盘 70%→100%；2026-06-17 20:57 UTC `writer_flush_failed`，之后 DB 不再推进。systemd `active/running`、API HTTP 200/status=ok，但双 feed STALE、DB age 约 13h。
- **Codex REWORK**：P0 高频表无限增长/无 retention 与磁盘闸门；P0 writer task 未监督/API 假活；P1 SQLite 单连接跨线程；P1 append 事件静默覆盖；P1 ingress API/先记录契约被改变。详见 `raw-frame-leak-fix/50-final-review.md`。
- **产品决策 D46–D48**：不再保留任何实时数据历史；高频表全部 latest-state UPSERT；比赛 kickoff/ended/closed/settled 后统一 retire。执行文案 `goals/realtime-state-no-history.md`。
- **退订审计**：Bybit kickoff 后最迟约 60s 停 probe/REST/WS 并删 mirror；Poly 会停止旧 shard task 并删 token mirror，但正常 kickoff 依赖 300s discovery，Sports ended 未接线，metadata/score/ladder/crossing/calc 未完全清理。
- Codex EC2 测试：pytest 210 passed；Ruff no-cache pass。独立异构预审仍缺，旧 fingerprint 已被 REWORK 判定失效。
- 下一动作：Kimi 按新 goal 整批修复后形成新指纹，跑 latest-state soak、retire_match/failure 注入和独立异构预审；READY 后再交 Codex。当前禁止 merge。

### 已完成并合入 integration
| 项 | 状态 |
|---|---|
| 需求/契约冻结、M0 数据链路、M1 bybit_feed、M2 poly_feed、双 feed 联调 | ✅ |
| 模块④A 组合定价 / 模块③ 只读 API+L1/L3 / module4a-3 真实 Poly 链路 | ✅ 合入（`c4229ba`） |
| Phase-2 integration-e2e 全部簇 | ✅ 全部 ACCEPT 合入：mapping、poly_freshness、health_summary、payoff fallback、**L3 前端(qty 缩放)**、deploy-dashboard、**backend-realmode(正式模式)**、prematch-lite(轻量+资源闸)、matches-query-fix(API 70s→<1s)、relax-gates(门控放宽)、l1-clickable、remove-demo、**api-decouple(API/feed 解耦)**、**poly-automatch(自动对盘)**、**l3-sizing(时间筛选+分腿成本+阈值70+磁盘清理)** |
| 自动对盘 | ✅ Gamma `active=true&closed=false` 发现 + 评分制匹配（阈值 `auto_match_min_score=70`，config 可调）；`manual_overrides` 仍最高优先 |
| **name-matching（队伍匹配全名→ISO）** | ✅ ACCEPT 合入（merge `01d5159`，黑板 `reports/agent-runs/integration-e2e/name-matching/`）：`resolve_poly` 改 Poly `teams[].name` 归一化（NFKD 去重音）→ ISO3 主匹配、abbr 仅兜底；`team_codes.toml` 48 队补 `poly_names`；**纠正 `cdr→COD`（原误配 CUW）、隔离 `kor→CUW`（不再撞 KOR）**；Gemini 预审 PASS + Opus 终审 + 控制面 EC2 实跑全绿 |
| **inplay-prematch-feed（开赛即退订，治 feed 卡死）** | ✅ ACCEPT 合入（merge `a1fc3ce` @ `c07324b`，黑板含 `90-final-verdict.md`）：BEL-EGY 开赛后 in-play 风暴（bybit seq_gap 洪流 + Poly 让球 token 404 重试）使 wc-feeds 内存涨满 systemd 限流→写库 stall→dashboard 冻结。修复：bybit/poly 双侧 kickoff+grace 即退订、CLOB 404→关闭停重试、mirror 内存释放、calc in-play 门控+平仓；配置 `drop_after_kickoff`/`inplay_grace_s`（默认开）。EC2 全量 190 passed(77s)+ruff 绿。**已部署 EC2 并复核**(cdr/kor 映射在真实数据正确)。**回执台账多处失实（计时/EC2 pytest/`_ready`/路径），代码本身无误**——已记 P3 反馈 Kimi |
| **24h 订阅窗口** | ✅ 合入(`f778e6c`)：`subscription_window_s` 72h→86400(24h)。小实例(1.8G/无 swap)容量所限,只实时监控未来 1 天开赛场,远期场进窗口后自动轮入。**注:仅缓解,非根治内存问题**(真因见上方 soak-stability) |
| 产品形态（线上可见） | ✅ L1 机会扫描(时间筛选 未来1/3/7天/全部,默认3天) + L3 阶梯赔付分解器(GD 滑块动态盈亏 + 本金1000 分腿成本=N×pₖ)；门控已放宽(`max_book_age_ms=3.6e6`、`require_executable_depth=false`，**有价即展示套利**，前端仍标"报价可能过期") |

### 在飞 / 待办
| 项 | 状态 |
|---|---|
| **realtime-lean-feed / soak-stability** | ❌ 候选 `agent/soak-stability @ 8c9f246` EC2 soak BLOCKED → 拍板者 **REJECT**(打错靶子)。修正 RCA 见 `86-`,详见上方进行中说明 |
| **recalc-loop-fairness(根治 v2)** | ✅ loop-fairness 已证有效(qsize=0、CPU 饿死消失)，branch-only `a0aa1bf`；已被 raw-frame 最终候选继承 |
| **lean-io-soak(根治 v3,合一)** | ✅ 降写量/I/O 修复已证生效，单簇 soak FAIL 仅用于暴露 raw-frame 泄漏；代码 `e6a3202` 已被最终候选继承，分支文档 HEAD `d9f07c3` |
| **raw-frame-leak-fix(根治 v4)** | ❌ `agent/raw-frame-leak-fix @ 64c134c` 30min 内存窗口通过，但约 7h 后 DB 写满根盘、writer 死亡且服务/API 假活；Codex **REWORK**，禁止 merge |
| **Poly 半线 vs 6腿整数线口径**(gate②) | ⬜ soak 过后转入的产品/金融决策:Poly 让球是半线(±1.5/2.5),6 腿阶梯是整数 GD 结算,口径差由用户拍板 |
| O1 contract_multiplier | ⬜ 人工未定 → net_edge 仍标"假设"；本金分腿暂为 Poly 现金口径，Bybit 保证金未计入 |
| L2 单场详情 | ⬜ 待补 |
| 模块④B 异步对冲下单 | ⬜ 后置；自动交易前另做长期稳定性与风控验收 |

## 5. 已知坑（新执行者必读）

- Bybit WC 合约发现只能 tickers 过滤 `WC_`；任何 snapshot 一律重置本地簿；delta 是绝对量替换；
- Polymarket spreads 的 outcomes 是队名、home/away 盘 line 同值；nominal_team 主源是 question/groupItemTitle；
- Polymarket spread/totals/BTTS 位于 h2h 的 `-more-markets` sibling event；基础 h2h 只有 moneyline。Bybit `SUI` 对应 Poly slug 可能使用 `CHE`，不得裸拼队码后把 404 当作无市场；
- Sports WS 心跳方向相反（服务端 ping→10s 内 pong），authority=informational；
- `operation:subscribe` 已观察到成功，但生产配置仍固定 reconnect；fixture flags、结论文字和 BLOCKERS 必须一致后才关闭 O4；
- 固定 24h soak 不再阻塞当前开发；线上仍须记录数据新鲜度、重连、队列、RSS、FD、SQLite 和磁盘指标，禁止静默数据错误；
- 只有自动交易启用前才重新设置严格长期稳定性与风控门禁；
- `.pem` 经扫描确认**从未进入 Git 历史**且被 `.gitignore`（`*.pem`）忽略，GitHub 私有仓已核对无私钥；但旧 EC2 key 尚未轮换、本地旧 PEM 尚未删除；
- 仓库在 mac 上：若 git 报 stale lock（index.lock），人工删除后重试；
- 服务器跑 Python **3.11+**（writer 的超时语义已兼容 3.10，但目标版本是 3.11）。
- 稳定性 soak 必须同时观察 DB 增长率、磁盘剩余量和 24h 外推；只看 RSS/D-state 的 30min PASS 不足以判定可上线。

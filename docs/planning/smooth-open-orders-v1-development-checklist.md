# 平滑开单 V1 开发清单（Opus 5 细拆输入）

状态：**Bookkeeper 粗清单，等待 Claude Opus 5 / Anthropic 细拆和跨 provider 正式计划评审。本文不授权实现、依赖安装、服务控制、部署或实盘。**

详细产品与资金语义的唯一权威是 `docs/planning/smooth-open-orders-v1.md`；本文只负责开发边界、并行候选和交付顺序，不复制完整 gate 契约。

## 1. 已取得的开发输入

- Human 已冻结：`bookTicker` 一档、严格 `spread > threshold`、两腿各 `>=80%`、每轮 5 分钟、`成交1次` 只放行当前 gate、两腿下单继续复用立即开单。
- P0 已验证 `ccxt==4.5.64` 的 Binance spot/USDⓈ-M `watchBidsAsks`、双 watcher cancel 隔离、普通合约单位和 raw/normalized 差异。
- 必须取 `info.b/B/a/A` 原始字符串；spot 无交易所时间戳；1000x 封禁不能靠 `contractSize` 解除。
- P0 未证明重连 generation、引用归零、close 无残留、多 symbol 共享；这些必须在 provider 交付中 fail-closed 验收。
- 前端 fake 只用于观察布局，不能当最终 API 或后端字段证据。

## 2. Human 指定的三模型并行候选

Human 希望由两个 `gpt-5.6-sol`（reasoning high）和一个 `claude-glm` 并行推进。以下只是粗分；Opus 5 必须依据真实调用链判断能否做到同基线、独立测试、零共享文件。若做不到，应明确改成“两项并行 + 一项依赖后置”，不能为了三路并行制造临时兼容层。

### 候选 A：Claude-GLM — 公共盘口 Provider

- 唯一运行时依赖清单与 `ccxt==4.5.64` 固定版本；不得安装进生产环境。
- `BestBidAskProvider`、CCXT adapter、两个独立 async watcher、共享 key/refcount、不可变 Decimal snapshot、同步读取桥、close/join。
- fake async source 覆盖延迟、异常、重连 generation、最后引用释放、多 symbol 共享和零悬挂。
- 不碰任务 store、gate 事务、worker、executor、前端。

### 候选 B：GPT-5.6-sol high ① — Gate 领域与持久化原子性

- threshold 规范化、gate seq/start/force、固定 deadline 派生、attempt pass reason。
- store 中自然/timeout/manual 三方竞争只生成一个 attempt；10/10 不出现第 11 次；崩溃缝和重启恢复符合冻结设计。
- fake clock 和数据库测试；不接 CCXT、不调用 executor、不启动服务。
- Opus 5 必须确认 `domain.py`、`store.py`、测试文件的唯一所有权，以及 `prepare_attempt` 是否应最小扩参或新增专用原子方法。

### 候选 C：GPT-5.6-sol high ② — Worker/API 集成与安全回归

- smooth 创建、读模型、`fill-once(gate_seq)` 分流、动态 `smooth_market` 读模型。
- Condition/wake_version 等待；市场/timeout/manual 候选只调用既有 dispatch；暂停、删除、Start gate 和 service stop 可立即唤醒并阻止旧 gate 发单。
- 使用 fake provider、fake clock、record executor 完成端到端回归，证明 immediate/close 不变且零真实订单。
- 不修改 live executor 的两腿提交/查单/结算实现。
- 该候选可能依赖 A/B 的冻结接口，Opus 5 必须判断能否真正并行；若不能，明确后置为单一集成任务。

## 3. 并行硬边界

- 三个实现各自使用独立 worktree、分支和任务状态；不得共享 Git index 或 `status.json`。
- 三个任务从同一个经正式计划评审通过的 committed base 开始，禁止各自发明接口。
- `service.py`、`scheduler.py` 和任何 executor 文件最多一个实现者拥有；其他任务只能通过冻结契约和 fake 使用它们。
- 同一个生产源文件、schema migration 或现有测试文件不得分给两个模型；需要共同验收时各写独立新测试文件，最后由单一集成者合并去重。
- 任一分支都不得启动服务、读取凭证、连接私有流或真实下单；公共 WS 连接也只在 dispatch 明确授权时允许。
- 不为并行临时增加兼容层、双实现、feature framework 或第二套 watcher/gate/executor。

## 4. 三路之后仍需要的单一集成交付

- 由一个模型在新的集成 worktree 按固定顺序合入三个已核验提交，解决接口接线和测试去重。
- 只有集成者可修改最终共享 wiring；不得顺手重构立即开单资金链。
- 前端真实接线在最终后端 API 冻结后单独完成：signed threshold、盘口块、当前 gate seq 的 `成交1次`、移除 smooth fill-all。
- 完整交付按 HIGH_RISK 路由：实现前跨 provider 计划评审；实现后 Review-1 + Review-2；Human 另行决定合并、依赖安装、服务重启和任何实盘。

## 5. Opus 5 必须产出的细拆结果

1. 判断三候选是“三路真并行”还是“两路并行 + 一路后置”，并用当前调用链/文件冲突说明原因。
2. 冻结最小接口：provider snapshot、订阅/释放/close、gate store 方法、worker 读取、API 字段；只保留实现必需字段。
3. 为两个 GPT-5.6-sol high 和一个 Claude-GLM 分别列出唯一文件所有权、禁止文件、输入提交、验收命令、失败停止条件和本地提交要求。
4. 给出 worktree/分支/stage 组织方式，使三个终端不会互改 `ACTIVE.json`、`status.json` 或 Git index。
5. 给出单一集成任务的合入顺序、冲突检查、回归矩阵和固定 `base_sha..delivery_sha` 方法。
6. 把 P0 未证事项变成可执行验收；不能用“CCXT 应该会自动重连/close”代替证据。
7. 明确唯一运行时依赖清单的文件名、维护者、安装/回滚边界；不得在规划阶段安装。
8. 产出三份 Human 可手动复制到不同终端的启动文稿草案，但标注“正式计划评审 ACCEPT 后由 Bookkeeper 填入最终 SHA/worktree 再启用”。
9. 产出正式跨 provider 计划评审请求，重点检查并发边界、单位/精度、gate 原子性、10/10 竞态和停机恢复。

## 6. 当前停止线

在 Opus 5 细拆和正式计划评审 ACCEPT 前，不创建后端实现 worktree，不安装 CCXT 到项目环境，不解除 `mode=smooth` 后端拒绝或前端 disabled，不接 worker/executor。

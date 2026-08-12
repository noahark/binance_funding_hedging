# 真实公网出口 IP 展示：开发计划

## 决定与范围

Human 已确认：将标题右侧的静态 preview 替换为**运行本机后端进程的公网出口 IP**。这个值只帮助 Human 核对 API 白名单，不参与开单、平仓、借币、还款、划转、风控或任何自动配置。

采用两个固定、无认证的 HTTPS IP 回显源：主源 `https://api.ipify.org?format=json`，备用 `https://checkip.amazonaws.com/`。币安的 API key 安全说明明确把 ipify 作为查询公网 IP 并填写 IP 白名单的示例。若本机到币安经由不同 VPN、代理或路由，该展示并不能证明币安实际观察到相同 IP；页面必须保留这个边界，且不得触发白名单变更。

### 非目标

- 不在浏览器直接请求外域，不新增 CORS 配置。
- 不读取 API 凭据，不访问币安，不改变任何 live gate 或资金路径。
- 不做 IP 白名单写入、告警、日志存储、后台线程、重试循环、配置项或第三方依赖。
- 不保证家庭宽带/VPN 的出口地址固定；展示的是一次受缓存约束的观察值。

## 交付设计

### 1. 后端：一个最小的只读缓存服务

新建 `backend/services/public_ip_service.py`。它只封装外部 HTTP、IP 校验和进程内缓存，接收可注入的 `urlopen` 与单调时钟以保持离线测试。使用 Python 标准库 `urllib.request`、`ipaddress`、`threading` 与 `time`；不读取环境变量。

- 每个缓存周期最多一次主源请求，主源失败或返回非 IP 值时才依序请求备用源；两次请求均使用 2 秒 timeout、GET、无请求体。
- 成功值必须经 `ipaddress.ip_address` 校验，IPv4/IPv6 都接受；主源读 JSON 的 `ip` 字段，备用源读去空白后的纯文本。
- 服务实例在进程内缓存 5 分钟；同一时刻缓存过期时由一个锁串行刷新，避免并发页面请求重复打外域。
- 两源均失败但曾有成功值时，返回旧值并标为 `stale`；从未成功时返回 `unavailable`。失败结果同样缓存 5 分钟，避免页面 60 秒刷新反复外呼。
- 不向浏览器暴露异常文本、URL、网络细节或请求头。

其唯一返回契约固定为：

```json
{
  "status": "ok | stale | unavailable",
  "public_ip": "string | null",
  "source": "api.ipify.org | checkip.amazonaws.com | null",
  "checked_at": "UTC ISO-8601 string | null"
}
```

`checked_at` 仅表示最后一次成功读取时间；`stale` 时保留该时间。服务不会猜测、合成或使用私网地址。

### 2. 同源 API：只暴露已规范化结果

在 `backend/app/server.py` 将 `GET /api/system/public-ip` 路由到该服务，并以 HTTP 200 返回上述三态 JSON、`Cache-Control: no-store`。这不是公共市场快照的一部分，也不修改既有快照或账户接口。

服务只在 `run()` 中创建并注入 `_Handler`；`build_server()` 增加一个可选、默认 `None` 的关键字注入参数并在每次建 server 时复位该 handler 属性，维持既有测试调用的参数形状且确保测试不会意外联网。若未注入，路由回答固定 `503 {"error":"public_ip_unavailable"}`，不尝试外呼。

### 3. 前端：复用标题 badge 与现有刷新节奏

修改 `frontend/index.html`，保留既有 `public-ip-badge` 与标题同行布局，将 preview 文案替换为三态真实展示：

- `ok`：`公网出口 IP <IP>`；
- `stale`：`公网出口 IP（上次成功） <IP>`，`title` 显示最后成功时间；
- `unavailable`、HTTP 错误或响应形状非法：`公网出口 IP 暂不可用`。

新增的 `loadPublicIp()` 只请求同源 `GET /api/system/public-ip`（浏览器缓存 bypass）。它从现有 `loadApi()` 触发，因此首屏、手动刷新与既有 60 秒市场刷新都会更新展示；不增设 timer、localStorage、外域 fetch 或重试。IP 请求失败不得让市场快照、持仓或右侧刷新控件进入失败态。

### 4. 测试与活文档

- 新建 `backend/tests/test_public_ip_api.py`：用注入 fake 覆盖主源成功和 5 分钟缓存、主源失败转备用、非法响应拒绝、两源失败的 `unavailable`、已有成功值后的 `stale`、`build_server` 未注入时 503，以及 HTTP 精确字段、`Cache-Control: no-store`。全程不进行真实网络请求。
- 更新 `frontend/self-check.js`：白名单加入且只加入 `/api/system/public-ip`；验证 `ok`/`stale`/`unavailable` 文案、该请求不创建新 timer 或 localStorage 键、失败不影响快照渲染；删除已不适用的静态 preview 地址断言。
- 更新 `docs/api/public-market-contract.md`，记录该同源只读端点、三态、缓存/外呼边界和“不是币安白名单权威”的限制；不改产品 PRD、架构或开发指南，因为功能不变更交易/产品边界或开发操作。

## 允许实现文件

- `backend/services/public_ip_service.py`
- `backend/app/server.py`
- `backend/tests/test_public_ip_api.py`
- `frontend/index.html`
- `frontend/self-check.js`
- `docs/api/public-market-contract.md`
- 本 stage 的实现 dispatch、状态、handoff 与测试原始输出

## 验收标准

1. 浏览器可访问 `GET /api/system/public-ip`，仅得到固定四字段的 `ok`、`stale` 或 `unavailable` JSON；未注入服务的隔离测试得到固定 503。
2. 主源失败、非法或非 IP 值时仅尝试一次备用源；两源失败时不伪造地址，也不把错误细节给浏览器。
3. 成功与失败缓存均为 5 分钟；缓存期内没有重复外呼；已有成功值刷新失败时只显示 `stale` 的上次值。
4. 页面标题右侧真实显示三态；未就绪或失败不影响市场快照、任务或任何交易相关控件。
5. 前端仅请求同源新接口，复用既有刷新，不新增 timer、localStorage、依赖或浏览器外域请求。
6. `python3 -m pytest -q backend/tests/test_public_ip_api.py`、`node frontend/self-check.js` 与 `git diff --check` 全部通过；无需真实 IP、币安请求、凭据、服务重启或部署。
7. 文档准确说明端点、两外部源、缓存和“仅供核对”的限制。

## 实施后关卡

本计划须先由 Claude 独立只读复审。复审接受后，才准备 Kimi（前端）与 Claude-GLM（后端）任务；两者共享的端点契约不能拆分为互相独立的实现提交。实现完成后按实际风险和固定 SHA 走正式评审；任何接受不授权重启、部署、交易所访问或白名单变更。

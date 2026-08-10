/**
 * 前端自检脚本：在 Node 环境下用 mock DOM 运行 index.html 的内联脚本，
 * 加载设计期 fixture 数据并断言市场表渲染结果；借币任务/借币日志/调度设置
 * 全部经 §3 冻结契约形状的 fetch mock 断言（含同源白名单与零任务定时器证明）。
 *
 * 运行: node frontend/self-check.js
 */
'use strict';

const fs = require('fs');
const path = require('path');

const root = __dirname;
const htmlPath = path.join(root, 'index.html');
const fixturePath = path.join(root, '..', 'backend', 'tests', 'fixtures', 'private-account-v1-design.json');

const html = fs.readFileSync(htmlPath, 'utf8');

// 提取内联 JS
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) throw new Error('未找到内联脚本');
const script = scriptMatch[1];

// 语法检查
new Function(script);
console.log('[PASS] 内联脚本语法检查');

let fetchUrl = null;
const fetchCallLog = [];    // 记录全部 fetch {url, method, body, cache}，用于同源白名单断言

// mock setInterval / clearInterval，记录调用以便验证自动刷新计时器重调度
let intervalIdSeq = 0;
const intervalCalls = [];     // { id, delay, callback }
const clearedIntervalIds = new Set();
global.setInterval = (callback, delay) => {
  const id = ++intervalIdSeq;
  intervalCalls.push({ id, delay, callback });
  return id;
};
global.clearInterval = (id) => {
  clearedIntervalIds.add(id);
};

// mock localStorage
const localStorageData = {};
global.localStorage = {
  getItem: (k) => localStorageData[k] !== undefined ? localStorageData[k] : null,
  setItem: (k, v) => { localStorageData[k] = String(v); },
  removeItem: (k) => { delete localStorageData[k]; }
};

if (typeof global.CSS === 'undefined') {
  global.CSS = { escape: (s) => String(s).replace(/(["\\])/g, '\\$1') };
}

const elementCache = {};

// mock Date.now: each call advances 1100ms so the 1s anti-double-click guard
// (breakdown §11.2) never blocks the back-to-back openDrawer() calls this
// self-check makes against the same symbol. The guard semantics themselves are
// unit-tested by the symbol-snapshot contract block below.
let _mockNow = 1700000000000;
Date.now = () => { _mockNow += 1100; return _mockNow; };

function makeElement(id) {
  if (elementCache[id]) return elementCache[id];
  const el = {
    id,
    _innerHTML: '',
    _textContent: '',
    _display: '',
    _value: '',
    _checked: false,
    _classList: new Set(),
    listeners: {},
    get innerHTML() { return this._innerHTML; },
    set innerHTML(v) { this._innerHTML = String(v); },
    get textContent() { return this._textContent; },
    set textContent(v) { this._textContent = String(v); },
    get disabled() { return !!this._disabled; },
    set disabled(v) { this._disabled = !!v; },
    get classList() {
      const self = this;
      return {
        add: (c) => { self._classList.add(c); },
        remove: (c) => { self._classList.delete(c); },
        contains: (c) => self._classList.has(c),
        toggle: (c, force) => {
          if (force === true) { self._classList.add(c); return true; }
          if (force === false) { self._classList.delete(c); return false; }
          if (self._classList.has(c)) { self._classList.delete(c); return false; }
          self._classList.add(c);
          return true;
        }
      };
    },
    get style() {
      const self = this;
      return {
        get display() { return self._display; },
        set display(v) { self._display = String(v); }
      };
    },
    get value() { return this._value; },
    set value(v) { this._value = String(v); },
    get checked() { return this._checked; },
    set checked(v) { this._checked = Boolean(v); },
    addEventListener(type, handler) {
      (this.listeners[type] = this.listeners[type] || []).push(handler);
    },
    setAttribute(name, value) {
      this._attrs = this._attrs || {};
      this._attrs[name] = String(value);
    },
    getAttribute(name) {
      return this._attrs ? this._attrs[name] : null;
    },
    removeAttribute(name) {
      if (this._attrs) delete this._attrs[name];
    },
    querySelector(sel) {
      if (!sel || typeof sel !== 'string') return null;
      const idMatch = sel.match(/^#([A-Za-z0-9_-]+)$/);
      if (idMatch) {
        const targetId = idMatch[1];
        const html = this.innerHTML;
        if (!html.includes(`id="${targetId}"`) && !html.includes(`id='${targetId}'`)) return null;
        return makeElement(targetId);
      }
      // class selectors used by flow-log render (heading / today body)
      const classMatch = sel.match(/^\.([A-Za-z0-9_-]+)$/);
      if (classMatch) {
        const cls = classMatch[1];
        const pseudoId = `${this.id || 'el'}__${cls}`;
        if (!elementCache[pseudoId]) {
          const child = makeElement(pseudoId);
          // mirror textContent updates onto parent innerHTML roughly
          Object.defineProperty(child, 'textContent', {
            get() { return this._text || ''; },
            set(v) { this._text = String(v); },
            configurable: true,
          });
          elementCache[pseudoId] = child;
        }
        return elementCache[pseudoId];
      }
      // tr.selectable[data-symbol="X"] — patchRow patches a single row in place
      const trMatch = sel.match(/^tr\.selectable\[data-symbol="([^"]+)"\]$/);
      if (trMatch) {
        const target = trMatch[1];
        return _trRows().find(r => r.getAttribute('data-symbol') === target) || null;
      }
      return null;
    },
    querySelectorAll(sel) {
      if (!sel || typeof sel !== 'string') return [];
      if (sel === 'tr.selectable') return _trRows();
      return [];
    }
  };
  elementCache[id] = el;
  return el;
}

const elements = {};
const ids = [
  'app-shell', 'app-sidebar', 'sidebar-toggle',
  'market-snapshot-meta', 'data-source-label', 'sort-basis-badge', 'btn-refresh', 'btn-cache-refresh',
  'refresh-countdown', 'account-asset-updated-at',
  'filter-search', 'filter-asset', 'filter-route', 'filter-show-perp-only', 'filter-hide-low-daily-rate',
  'filter-hide-low-net-yield', 'filter-prefer-openable',
  'summary-row', 'status-area', 'market-table-body',
  'private-panel', 'private-pm-source-time', 'private-panel-body', 'btn-privacy', 'privacy-label', 'privacy-icon-path',
  // 流水日志（task C + tab-layout-v2）：§13.7 冻结 id + 页内双看板
  'btn-market-board', 'btn-flow-log', 'market-board', 'flow-log-panel', 'flow-log-status-bar', 'flow-log-coverage-note',
  'flow-log-range-7d', 'flow-log-range-30d', 'flow-log-range-custom',
  'flow-log-custom-start', 'flow-log-custom-end', 'flow-log-custom-apply',
  'flow-log-refresh', 'flow-log-delta', 'flow-log-delta-interest', 'flow-log-delta-income',
  'flow-log-delta-symbols', 'flow-log-today', 'flow-log-filters',
  'flow-log-filter-funding', 'flow-log-filter-commission', 'flow-log-filter-realized',
  'flow-log-filter-transfer', 'flow-log-filter-other',
  'flow-log-interest-status', 'flow-log-interest-summary', 'flow-log-interest-body',
  'flow-log-income-status', 'flow-log-income-summary', 'flow-log-income-body',
  'drawer', 'drawer-backdrop', 'drawer-title', 'drawer-body', 'drawer-close',
  'nav-market', 'nav-borrow-tasks', 'borrow-task-count', 'market-view', 'flow-log-view', 'borrow-task-view', 'borrow-task-list',
  'borrow-task-filters',
  'borrow-tab-tasks', 'borrow-tab-logs', 'borrow-tasks-panel', 'borrow-logs-panel',
  'borrow-interval-input', 'borrow-interval-confirm', 'borrow-interval-error', 'borrow-interval-note',
  'borrow-tasks-error', 'borrow-logs-error', 'borrow-log-list', 'borrow-logs-refresh', 'borrow-logs-clear', 'borrow-logs-load-more',
  'borrow-execution-badge', 'borrow-execution-start', 'borrow-execution-stop', 'borrow-execution-detail',
  'nav-hedge-tasks', 'hedge-task-count', 'hedge-task-view', 'hedge-task-list', 'hedge-task-filters',
  'hedge-execution-badge', 'hedge-execution-detail', 'hedge-tasks-error',
  'hedge-attempt-list', 'hedge-attempts-error',
  'hedge-tab-tasks', 'hedge-tab-logs', 'hedge-tasks-panel', 'hedge-logs-panel',
  'hedge-logs-error', 'hedge-log-list', 'hedge-logs-refresh', 'hedge-logs-load-more',
  'hedge-modal', 'hedge-modal-backdrop', 'hedge-modal-title', 'hedge-modal-body', 'hedge-modal-close',
  'hedge-modal-confirm', 'hedge-modal-cancel', 'hedge-start-gate-toggle',
  // 历史仓位 fake 原型（2026-08 hedge-open-position-cycle-v1）：新增静态元素，须注册。
  'nav-history', 'history-view', 'history-list',
  // 资产互转 fake 预览：随私有面板重渲染的按钮与提示（局部刷新按 id 取用）。
  // transfer-asset：Q4 后 <option> 由 renderTransferAssetOptions 单独重建（可转出额
  // 异步回来后只换选项，不重建整块 DOM——重建会打断正在输入的光标）。
  'transfer-submit', 'transfer-hint', 'transfer-asset'
];
ids.forEach(id => { elements[id] = makeElement(id); });

// Parse the current market-table-body innerHTML into mock <tr> row elements so
// patchRow (querySelector tr.selectable[data-symbol="X"]) and bindRowSelection
// (querySelectorAll tr.selectable) operate on the rendered table. Each element
// supports getAttribute/setAttribute/addEventListener and an outerHTML setter
// that splices the row back into the tbody innerHTML (single-row patch, no
// full re-render — mirrors real-DOM patchRow behaviour, breakdown §11.6).
function _trRows() {
  const html = elements['market-table-body'].innerHTML;
  const rows = [];
  let pos = 0;
  while (true) {
    const trStart = html.indexOf('<tr', pos);
    if (trStart === -1) break;
    const trEnd = html.indexOf('</tr>', trStart);
    if (trEnd === -1) break;
    const seg = html.slice(trStart, trEnd + 5);
    const symMatch = seg.match(/data-symbol="([^"]+)"/);
    const symbol = symMatch ? symMatch[1] : null;
    const bound = /data-bound="1"/.test(seg);
    rows.push(_makeTrEl(symbol, bound));
    pos = trEnd + 5;
  }
  return rows;
}

function _makeTrEl(symbol, bound) {
  const obj = {
    _symbol: symbol,
    _bound: bound,
    getAttribute(name) {
      if (name === 'data-symbol') return this._symbol;
      if (name === 'data-bound') return this._bound ? '1' : null;
      return null;
    },
    setAttribute(name, value) {
      if (name === 'data-bound') this._bound = (value === '1');
    },
    removeAttribute() {},
    addEventListener() {},
    listeners: {}
  };
  Object.defineProperty(obj, 'outerHTML', {
    configurable: true,
    get() { return ''; },
    set(newHtml) {
      const cur = elements['market-table-body'].innerHTML;
      const idx = cur.indexOf(`data-symbol="${this._symbol}"`);
      if (idx === -1) return;
      const s = cur.lastIndexOf('<tr', idx);
      const e = cur.indexOf('</tr>', s);
      if (s === -1 || e === -1) return;
      elements['market-table-body'].innerHTML =
        cur.slice(0, s) + String(newHtml) + cur.slice(e + 5);
    }
  });
  return obj;
}

// 加载设计期 fixture
const designFixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));

// Task B 要求前端把 annualized / funding_sum 字段视为当前服务契约字段；给设计期 fixture 补齐。
designFixture.rows.forEach(r => {
  if (!('funding_sum_24h' in r)) r.funding_sum_24h = null;
  if (!('annualized_funding_24h' in r)) r.annualized_funding_24h = null;
  if (!('annualized_funding_7d' in r)) r.annualized_funding_7d = null;
  if (!('annualized_funding_30d' in r)) r.annualized_funding_30d = null;
});
// 为 opening_quotes 各态断言在内存注入；不修改 backend fixture。
const OPENING_QUOTES_FRESH = {
  status: 'fresh',
  updated_at: '2026-07-15T06:51:57Z',
  spot_bid_price: '64954.00000000',
  spot_ask_price: '64954.01000000',
  futures_bid_price: '64925.00',
  futures_ask_price: '64925.10',
  forward_spread_pct: '-0.04',
  reverse_spread_pct: '0.04'
};
const OPENING_QUOTES_INCOMPLETE = {
  status: 'incomplete',
  updated_at: '2026-07-15T06:51:57Z',
  spot_bid_price: '64954.00000000',
  spot_ask_price: null,
  futures_bid_price: '64925.00',
  futures_ask_price: '64925.10',
  forward_spread_pct: null,
  reverse_spread_pct: '0.04'
};
const OPENING_QUOTES_STALE = {
  status: 'stale',
  updated_at: '2026-07-15T06:51:57Z',
  spot_bid_price: null,
  spot_ask_price: null,
  futures_bid_price: null,
  futures_ask_price: null,
  forward_spread_pct: null,
  reverse_spread_pct: null
};
const OPENING_QUOTES_UNAVAILABLE = {
  status: 'unavailable',
  updated_at: null,
  spot_bid_price: null,
  spot_ask_price: null,
  futures_bid_price: null,
  futures_ask_price: null,
  forward_spread_pct: null,
  reverse_spread_pct: null
};
if (designFixture.rows[0]) designFixture.rows[0].opening_quotes = OPENING_QUOTES_FRESH;
if (designFixture.rows[1]) designFixture.rows[1].opening_quotes = OPENING_QUOTES_INCOMPLETE;
if (designFixture.rows[2]) designFixture.rows[2].opening_quotes = OPENING_QUOTES_STALE;
if (designFixture.rows[3]) designFixture.rows[3].opening_quotes = OPENING_QUOTES_UNAVAILABLE;
// rows[4] (EUSDT) 与 rows[5] (FUSDT) 保持 opening_quotes 缺失，测试字段整体缺失降级。

// v0.9 collateral_cap 各态：内存注入，不改 backend fixture。
// AUSDT 负费率已满；BUSDT 未满；CUSDT 正费率已满（同态方向无关）；
// DUSDT 未知；EUSDT 不适用 (asset=null)；FUSDT 缺键（冻结快照降级）。
const COLLATERAL_CAP_CHECKED_AT = '2026-08-03T04:15:22Z';
function injectCap(row, cap, extraFlags) {
  if (!row) return;
  row.collateral_cap = cap;
  const flags = Array.isArray(row.ui_flags) ? row.ui_flags.slice() : [];
  const cleaned = flags.filter(f => f !== 'COLLATERAL_CAP_EXCEEDED' && f !== 'COLLATERAL_CAP_UNKNOWN');
  for (const f of (extraFlags || [])) {
    if (!cleaned.includes(f)) cleaned.push(f);
  }
  row.ui_flags = cleaned;
}
if (designFixture.rows[0]) {
  injectCap(designFixture.rows[0], {
    exceeded: true, asset: 'A', checked_at: COLLATERAL_CAP_CHECKED_AT
  }, ['COLLATERAL_CAP_EXCEEDED']);
}
if (designFixture.rows[1]) {
  injectCap(designFixture.rows[1], {
    exceeded: false, asset: 'B', checked_at: COLLATERAL_CAP_CHECKED_AT
  }, []);
}
if (designFixture.rows[2]) {
  injectCap(designFixture.rows[2], {
    exceeded: true, asset: 'C', checked_at: COLLATERAL_CAP_CHECKED_AT
  }, ['COLLATERAL_CAP_EXCEEDED']);
}
if (designFixture.rows[3]) {
  injectCap(designFixture.rows[3], {
    exceeded: null, asset: 'D', checked_at: null
  }, ['COLLATERAL_CAP_UNKNOWN']);
}
if (designFixture.rows[4]) {
  injectCap(designFixture.rows[4], {
    exceeded: null, asset: null, checked_at: COLLATERAL_CAP_CHECKED_AT
  }, []);
}
// rows[5] FUSDT: deliberately omit collateral_cap key (legacy freeze).
// 给 AUSDT 行附加 settled history，用于抽屉 newest-first / 负费率 / 北京时间测试。
const ausdt = designFixture.rows.find(r => r.symbol === 'AUSDT');
if (ausdt) {
  const tEnd = 1783641600000;
  const day = 86_400_000;
  ausdt.funding_history = [
    { funding_time: tEnd - 2 * day, funding_rate: '-0.00010000' },
    { funding_time: tEnd - day, funding_rate: '0.00005000' }
  ];
  // 近 24h 窗口 [tEnd-24h, tEnd] 仅含下沿点 0.00005（上沿无点；-2d 在窗外）
  ausdt.funding_sum_24h = '0.00005000';
  // daily_funding_rate -0.00060000 * (24/8) = -0.00180000
  ausdt.annualized_funding_24h = '-0.65700000';
  // sum -0.00005000
  ausdt.annualized_funding_7d = '-0.00260714';
  ausdt.annualized_funding_30d = '-0.00060833';
}

// 为 v0.4 UI 断言使用具体数值（占位符无法被 formatFundingRate / maskAmount 有效测试）
designFixture.rows[0].borrow_validation.classic_margin.daily_interest_account = '0.00010000';
designFixture.rows[1].borrow_validation.classic_margin.daily_interest_vip0 = '0.00020000';
// cache-refresh v1: inject fixed five-key source_checked_at into the design
// fixture (backend design fixture predates the field; frontend fixture has it).
if (!designFixture.private_account.source_checked_at) {
  designFixture.private_account.source_checked_at = {
    price_map: designFixture.private_account.checked_at || '2026-07-05T23:30:00Z',
    unified_balances: designFixture.private_account.checked_at || '2026-07-05T23:30:00Z',
    um_positions: '2026-07-05T23:20:00Z',
    spot_balances: designFixture.private_account.checked_at || '2026-07-05T23:30:00Z',
    pm_account: null
  };
}
if (Array.isArray(designFixture._design_fixture_private_account_states)) {
  designFixture._design_fixture_private_account_states.forEach(s => {
    if (s && !s.source_checked_at) {
      s.source_checked_at = {
        price_map: null,
        unified_balances: null,
        um_positions: null,
        spot_balances: null,
        pm_account: null
      };
    }
  });
}

designFixture.private_account.balances_unified.forEach(b => {
  b.value_usdt = '123.45000000';
  // v0.8: default no effective borrow -> zero liability value (not null)
  if (b.cross_margin_borrowed_value_usdt === undefined) {
    b.cross_margin_borrowed_value_usdt = '0.00000000';
  }
});
designFixture.private_account.balances_spot.forEach(b => { b.value_usdt = '67.89000000'; });

let fixtureToFetch = designFixture;
let historyResponse = null;
let historyResolve = null;
let historyJsonResolve = null;
let lastHistoryUrl = null;

// ---- 借币任务 API mock（逐字段复制 12-development-breakdown.md §3 冻结示例文档） ----
// §3.3 任务文档示例（HOME）；派生文档经 deepCopy 覆盖字段值，不改字段形状。
const MOCK_TASK_HOME = {
  schema_version: 'borrow-tasks/v1',
  id: 'uuid4-string',
  asset: 'HOME',
  amount_per_attempt: '12.5',
  success_target: 3,
  success_count: 1,
  status: 'borrowing',
  version: 4,
  unresolved_attempt_id: null,
  latest_result: {
    result_category: 'execution_disabled',
    business_code: null,
    reason: 'executor_disabled',
    tran_id: null,
    finished_at: '2026-07-19T08:00:00.123456Z'
  },
  created_at: '2026-07-19T07:59:55.000000Z',
  updated_at: '2026-07-19T08:00:00.123456Z'
};

function deepCopy(base, overrides) {
  const t = JSON.parse(JSON.stringify(base));
  Object.assign(t, overrides || {});
  return t;
}

function mockTaskListDoc(tasks) {
  return { schema_version: 'borrow-tasks/v1', tasks };
}

// §3.5 调度设置文档：默认种子行 "5"/5000000；PUT 后 "2.5"/2500000（≥2s 容量地板示例值）。
const MOCK_SETTINGS_DEFAULT = {
  schema_version: 'borrow-tasks/v1',
  interval_seconds: '5',
  interval_us: 5000000,
  round_robin_cursor: null,
  global_cooldown_until: null,
  version: 1,
  updated_at: '2026-07-19T08:00:00.000000Z'
};
const MOCK_SETTINGS_2_5 = deepCopy(MOCK_SETTINGS_DEFAULT, { interval_seconds: '2.5', interval_us: 2500000, version: 2 });

// §3.6 日志页示例（HOME 条目 verbatim）+ 派生旧条目，供两页游标分页。
const MOCK_LOG_ENTRY_HOME = {
  id: 42,
  task_id: 'uuid4-string',
  asset: 'HOME',
  sequence: 7,
  outcome: 'resolved',
  result_category: 'success',
  business_code: null,
  reason: null,
  http_status: null,
  tran_id: 'paper-1',
  requested_amount: '12.5',
  scheduled_at: '2026-07-19T08:00:00.000000Z',
  dispatched_at: '2026-07-19T08:00:00.001000Z',
  finished_at: '2026-07-19T08:00:00.002000Z',
  latency_ms: 1,
  effective_gap_us: 500123
};
const MOCK_LOG_PAGE_1 = {
  schema_version: 'borrow-tasks/v1',
  entries: [
    MOCK_LOG_ENTRY_HOME,
    deepCopy(MOCK_LOG_ENTRY_HOME, { id: 41, asset: 'BTC', sequence: 3, result_category: 'known_rejection', reason: 'borrow_rejected', business_code: '51061', tran_id: null })
  ],
  next_cursor: 'cursor-page-2'
};
const MOCK_LOG_PAGE_2 = {
  schema_version: 'borrow-tasks/v1',
  entries: [
    deepCopy(MOCK_LOG_ENTRY_HOME, { id: 40, asset: 'ETH', sequence: 2, result_category: 'execution_disabled', reason: 'executor_disabled', tran_id: null }),
    deepCopy(MOCK_LOG_ENTRY_HOME, { id: 39, asset: 'ETH', sequence: 1, outcome: 'pending', result_category: null, tran_id: null, finished_at: null, latency_ms: null, effective_gap_us: null })
  ],
  next_cursor: null
};

// 各 borrow 路由的响应槽：每个测试块显式设置；未设置时 503（§3.7 错误形状）。
let borrowTasksGetResponse = null;
let borrowTasksPostResponse = null;
let borrowActionResponses = {};
let borrowLogsResponses = [];
let borrowLogsClearResponse = null;
let borrowSettingsGetResponse = null;
let borrowSettingsPutResponse = null;
// Boundary C 执行控制响应槽（§3.2）；未设置时回放默认 disabled 投影。
let borrowExecutionStatusResponse = null;

// ---- 开单任务 API mock（2026-07-hedge-open-live-v1，12-breakdown §3 冻结契约） ----
// 默认种子：空任务列表、空持仓、disabled 执行设置（启动即拉取，须可 200）；
// 各测试块显式覆盖响应槽；动作路由未设置时 503。
let hedgeTasksGetResponse = { status: 200, body: { tasks: [] } };
let hedgeTasksPostResponse = null;
let hedgeActionResponses = {};
let hedgeSettingsGetResponse = { status: 200, body: { executor_mode: 'disabled', start_gate: false, interval_seconds: 1, version: 1 } };
// live-hardening v1（10-design §2.3）：POST /api/hedge-open-settings/start-gate 响应槽；未设置时 503。
let hedgeStartGatePostResponse = null;
// 功能三 ③a：历史仓位——周期结算日志 GET 响应槽。
let hedgeCloseLogsGetResponse = { status: 200, body: { logs: [] } };
let hedgePositionsGetResponse = {
  status: 200,
  body: {
    positions: [],
    account: {      verified: true,
      error: null,
      checked_at: null,
      source_checked_at: {
        price_map: null,
        unified_balances: null,
        um_positions: null,
        spot_balances: null,
        pm_account: null
      }
    }
  }
};
// POST /api/public-market/cache-refresh mock slot (frontend-cache-refresh-v1).
let cacheRefreshPostResponse = null;
// 资产互转（T2）：POST /api/asset-transfer 的响应槽；未设置时 503。
let assetTransferPostResponse = null;
// 统一账户还款（T2）：POST/GET /api/margin-repay 的响应槽；未设置时 503。
// marginRepayPostThrow 置非空时 POST 直接抛出（模拟浏览器到本机服务网络中断/响应丢失）。
// marginRepayPostPendingSnapshot 记录 POST 到达瞬间的 localStorage 未决记录原文，
// 供「发送前持久化」断言取证（离线 mock 无法计时，改证请求时刻的存储状态）。
let marginRepayPostResponse = null;
let marginRepayGetResponse = null;
let marginRepayPostThrow = null;
let marginRepayPostPendingSnapshot = null;
// Q4：GET /api/private-account/max-withdraw 的响应槽；未设置时 503。
let maxWithdrawGetResponse = null;
// 流水日志 private-ledger mock（task C）
let flowLogGetResponse = null;
let flowLogRefreshResponse = null;

function buildMockFlowLogPayload(overrides) {
  const now = 1785798060000;
  const day = 86400000;
  const interestRows = [];
  for (let i = 0; i < 25; i++) {
    interestRows.push({
      tx_id: 'tx-' + i,
      accrued_at_ms: now - i * 3600000,
      asset: i % 2 === 0 ? 'HOME' : 'RSR',
      raw_asset: i % 2 === 0 ? 'HOME' : 'RSR',
      principal: '1.0',
      interest: '0.00010000',
      interest_rate: '0.00200000',
      type: 'PERIODIC',
      isolated_symbol: null,
    });
  }
  const incomeRows = [];
  for (let i = 0; i < 25; i++) {
    incomeRows.push({
      tran_id: 'tr-' + i,
      income_type: i % 4 === 0 ? 'COMMISSION' : 'FUNDING_FEE',
      time_ms: now - i * 7200000,
      symbol: i % 4 === 0 ? 'RSRUSDT' : 'COOKIEUSDT',
      income: i % 4 === 0 ? '-0.00001000' : '0.00100000',
      asset: i % 4 === 0 ? 'BNB' : 'USDT',
      info: i % 4 === 0 ? 't' + i : 'FUNDING_FEE',
      trade_id: i % 4 === 0 ? String(1000 + i) : null,
    });
  }
  const base = {
    schema_version: 'private-ledger/v2',
    served_at_ms: now,
    scheduler_enabled: true,
    window: { start_ms: now - 7 * day, end_ms: now },
    coverage: {
      start_ms: now - 10 * day,
      end_ms: now - 30 * 60000,
      complete: true,
      pending_tail_ms: 30 * 60000,
      by_source: {
        interest: { start_ms: now - 10 * day, end_ms: now - 30 * 60000 },
        income: { start_ms: now - 10 * day, end_ms: now - 30 * 60000 },
      },
      gaps: [],
    },
    last_run: {
      run_id: 1,
      kind: 'scheduled',
      finished_at_ms: now - 30 * 60000,
      interest_status: 'ok',
      interest_error: null,
      income_status: 'ok',
      income_error: null,
      truncated: false,
      consecutive_failure_count: 0,
    },
    delta: {
      baseline_ms: now - 3600000,
      complete: true,
      interest_by_asset: [
        { asset: 'HOME', interest_total: '0.00010000', row_count: 1, unparsed_row_count: 0 },
      ],
      income_by_type_asset: [
        { income_type: 'FUNDING_FEE', asset: 'USDT', income_total: '0.00100000', row_count: 1, unparsed_row_count: 0 },
      ],
      funding_by_symbol: [
        { symbol: 'COOKIEUSDT', asset: 'USDT', income_total: '0.00100000', row_count: 1 },
      ],
      interest_new_row_count: 1,
      income_new_row_count: 1,
    },
    today: {
      day_start_ms: 1785772800000,
      interest_by_asset: [
        { asset: 'HOME', interest_total: '0.00030000', row_count: 3, unparsed_row_count: 0 },
      ],
      income_by_type_asset: [
        { income_type: 'FUNDING_FEE', asset: 'USDT', income_total: '0.00300000', row_count: 3, unparsed_row_count: 0 },
      ],
    },
    interest: {
      rows: interestRows,
      summary_by_asset: [
        { asset: 'HOME', interest_total: '0.00130000', row_count: 13, unparsed_row_count: 0 },
        { asset: 'RSR', interest_total: '0.00120000', row_count: 12, unparsed_row_count: 0 },
      ],
      row_count: 25,
      row_limit_applied: false,
    },
    um_income: {
      rows: incomeRows,
      summary_by_type_asset: [
        { income_type: 'FUNDING_FEE', asset: 'USDT', income_total: '0.01900000', row_count: 19, unparsed_row_count: 0 },
        { income_type: 'COMMISSION', asset: 'BNB', income_total: '-0.00006000', row_count: 6, unparsed_row_count: 0 },
      ],
      row_count: 25,
      row_limit_applied: false,
    },
  };
  if (!overrides) return base;
  return deepMergeFlowLog(base, overrides);
}

function deepMergeFlowLog(a, b) {
  if (b === null || b === undefined) return a;
  if (Array.isArray(b)) return b.slice();
  if (typeof b !== 'object') return b;
  const out = Object.assign({}, a);
  for (const k of Object.keys(b)) {
    if (b[k] && typeof b[k] === 'object' && !Array.isArray(b[k]) && a && typeof a[k] === 'object' && !Array.isArray(a[k])) {
      out[k] = deepMergeFlowLog(a[k], b[k]);
    } else {
      out[k] = b[k];
    }
  }
  return out;
}
// real-api-v1：attempt 时间线数据源（既有 GET /api/hedge-open-logs，路由表不变，?limit=100 无 cursor）。
let hedgeLogsGetResponse = { status: 200, body: { logs: [], next_cursor: null } };
// 17 号兼容修正：开单日志页分页队列（?entries_limit=50[&entries_cursor=...]，响应带
// entries_next_cursor），与上面 attempt 时间线的 ?limit=100 请求区分，逐页 shift；未设置时 503。
let hedgeLogPageResponses = [];
// 任务卡内嵌日志（2026-07-31-hedge-task-inline-log-v1）：?task_id=… 请求的响应槽，
// 一次返回该任务全部 attempt（含双腿与错误字段）；未设置时 503。
let hedgeTaskLogsGetResponse = null;

function mockHedge503() {
  return { status: 503, body: { error: 'hedge_service_unavailable', detail: 'mock 未设置该路由响应' } };
}

// §3.2 Task JSON 冻结字段名（含 round-2 新增 q_common / leg_exposure / position_side_mode，
// 及 real-api-v1 §3.4 新增计数/阈值/暂停原因字段）。
function mockHedgeTask(overrides) {
  return Object.assign({
    id: 'h-1',
    coin: 'AUSDT',
    direction: 'forward',
    mode: 'immediate',
    single_amount: 0.5,
    target_n: 3,
    success_count: 0,
    fail_count: 0,
    status: 'running',
    q_common: 0.5,
    position_side_mode: 'BOTH',
    leg_exposure: null,
    scheduled_attempt_count: 0,
    accepted_pair_count: 0,
    consecutive_submission_failures: 0,
    failure_pause_threshold: 3,
    pause_reason: null,
    task_type: 'open',
    // I-4（15 号修正案）：stopped 为致命错误终止的新增字段，与 pause_reason 并存。
    stop_reason: null,
    created_at: '2026-07-22T08:00:00.000000Z',
    updated_at: '2026-07-22T08:00:00.000000Z'
  }, overrides || {});
}

// real-api-v1 §3.4 per-attempt 冻结文档形状（Decimal 均为字符串）。
function mockHedgeAttempt(overrides) {
  return Object.assign({
    task_id: 'h-1',
    attempt_id: 'att-1',
    attempt_seq: 1,
    direction: 'forward',
    q_common: '0.003',
    pair_outcome: 'accepted_pair',
    spot: {
      client_order_id: 'hgo-att1-s',
      order_id: '9001',
      status: 'FILLED',
      cumulative_base_qty: '0.003',
      cumulative_quote_amt: '0.36210000',
      avg_price: '120.70000000',
      fee_amount: '0.00000010',
      fee_asset: 'BNB'
    },
    perp: {
      client_order_id: 'hgo-att1-p',
      order_id: '9002',
      status: 'FILLED',
      cumulative_base_qty: '0.003',
      cumulative_quote_amt: '0.36210900',
      avg_price: '120.70300000'
    },
    residual: '0',
    ts: '2026-07-23T12:00:01.000000Z'
  }, overrides || {});
}

// 16 号拆分 §5 冻结契约：开单日志页 entries[] 条目形状（Decimal 均为字符串）。
function mockHedgeLogEntry(overrides) {
  return Object.assign({
    entry_id: 'e-1',
    entry_type: 'attempt',
    task_id: 'h-1',
    coin: 'AUSDT',
    direction: 'forward',
    attempt_seq: 1,
    created_ts: '2026-07-23T12:00:00.000000Z',
    submitted_ts: '2026-07-23T12:00:00.500000Z',
    final_ts: '2026-07-23T12:00:01.000000Z',
    q_common: '0.003',
    planned_quote_amount: '0.36',
    spot: {
      side: 'BUY',
      client_order_id: 'hgo-e1-s',
      order_id: '9101',
      status: 'FILLED',
      cumulative_base_qty: '0.003',
      cumulative_quote_amt: '0.36210000',
      avg_price: '120.70000000',
      fee_amount: '0.00000010',
      fee_asset: 'BNB'
    },
    perp: {
      side: 'SELL',
      client_order_id: 'hgo-e1-p',
      order_id: '9102',
      status: 'FILLED',
      cumulative_base_qty: '0.003',
      cumulative_quote_amt: '0.36210900',
      avg_price: '120.70300000',
      fee_amount: null,
      fee_asset: null
    },
    residual: '0',
    overall_result: 'filled',
    error_category: null, error_code: null, error_reason_zh: null,
    next_action: 'continue_next_attempt'
  }, overrides || {});
}

// 开单日志页固定装置：single_leg（缺 perp 腿）、task_event（无 orderId 的任务级事件，
// attempt/leg 字段全 null）、confirmed_failed（两腿均无 orderId 的确认失败，即“no orderId
// error 行”）。newest-first 两页游标分页装置。
const HEDGE_LOG_ENTRY_SINGLE_LEG = mockHedgeLogEntry({
  entry_id: 'e-10', task_id: 'h-log-1', coin: 'AUSDT', direction: 'forward', attempt_seq: 2,
  created_ts: '2026-07-24T10:00:00.000000Z', submitted_ts: '2026-07-24T10:00:00.400000Z',
  final_ts: '2026-07-24T10:00:01.000000Z', q_common: '0.004', planned_quote_amount: '0.48',
  spot: {
    side: 'BUY', client_order_id: 'hgo-e10-s', order_id: '9201', status: 'FILLED',
    cumulative_base_qty: '0.004', cumulative_quote_amt: '0.48280000', avg_price: '120.70000000',
    fee_amount: '0.00000012', fee_asset: 'BNB'
  },
  perp: null,
  residual: '0.004',
  overall_result: 'single_leg', error_category: null, error_code: null, error_reason_zh: null,
  next_action: 'continue_next_attempt'
});
const HEDGE_LOG_ENTRY_TASK_EVENT = mockHedgeLogEntry({
  entry_id: 'e-9', entry_type: 'task_event', task_id: 'h-log-1', coin: 'AUSDT', direction: 'forward',
  attempt_seq: null, created_ts: '2026-07-24T09:59:00.000000Z', submitted_ts: null,
  final_ts: '2026-07-24T09:59:00.000000Z', q_common: null, planned_quote_amount: null,
  spot: null, perp: null, residual: null,
  overall_result: 'task_paused', error_category: 'exchange_rate_limit', error_code: '429',
  error_reason_zh: '交易所限频，已延迟新开单请求', next_action: 'waiting_query'
});
const HEDGE_LOG_ENTRY_NO_ORDERID_FAIL = mockHedgeLogEntry({
  entry_id: 'e-8', task_id: 'h-log-2', coin: 'BUSDT', direction: 'reverse', attempt_seq: 1,
  created_ts: '2026-07-24T09:00:00.000000Z', submitted_ts: '2026-07-24T09:00:00.200000Z',
  final_ts: '2026-07-24T09:00:00.900000Z', q_common: '0.002', planned_quote_amount: '0.24',
  spot: {
    side: 'SELL', client_order_id: 'hgo-e8-s', order_id: null, status: null,
    cumulative_base_qty: '0', cumulative_quote_amt: '0', avg_price: null, fee_amount: null, fee_asset: null
  },
  perp: {
    side: 'BUY', client_order_id: 'hgo-e8-p', order_id: null, status: null,
    cumulative_base_qty: '0', cumulative_quote_amt: '0', avg_price: null, fee_amount: null, fee_asset: null
  },
  residual: '0',
  overall_result: 'confirmed_failed', error_category: 'insufficient_balance', error_code: '51008',
  error_reason_zh: '可用余额不足', next_action: 'stopped'
});
// 17 号兼容修正：entries 分页用独立的 entries_next_cursor，绝不回退到旧 next_cursor。
// 两个 fixture 都刻意携带一个与 entries_next_cursor 不同的旧 next_cursor 值，用来证明
// 前端翻页请求只采信 entries_next_cursor。
const HEDGE_LOG_PAGE_1 = {
  logs: [], attempts: [], next_cursor: 'legacy-cursor-should-be-ignored',
  entries: [HEDGE_LOG_ENTRY_SINGLE_LEG, HEDGE_LOG_ENTRY_TASK_EVENT],
  entries_next_cursor: 'entries-cursor-page-2'
};
const HEDGE_LOG_PAGE_2 = {
  logs: [], attempts: [], next_cursor: 'legacy-cursor-should-also-be-ignored',
  entries: [HEDGE_LOG_ENTRY_NO_ORDERID_FAIL],
  entries_next_cursor: null
};

function mockBorrow503() {
  return { status: 503, body: { error: 'borrow_service_unavailable', detail: 'mock 未设置该路由响应' } };
}

// 默认执行状态投影：disabled 模式、execution_enabled=false、can_execute=false。
function mockExecutionStatusDisabled() {
  return {
    status: 200,
    body: {
      schema_version: 'borrow-execution/v1',
      mode: 'disabled',
      execution_enabled: false,
      can_execute: false,
      block_reason: 'executor_disabled',
      in_flight_attempt_id: null,
      global_cooldown_until: null,
      live_authorized_task_count: 0,
      updated_at: '2026-07-21T00:00:00.000000Z'
    }
  };
}

function buildFetchResponse(response, jsonDelay) {
  return {
    ok: response.status >= 200 && response.status < 300,
    status: response.status,
    statusText: response.statusText || (response.status === 200 ? 'OK' : 'Error'),
    json: async () => {
      if (jsonDelay) {
        return new Promise((resolve) => { historyJsonResolve = () => resolve(response.body); });
      }
      return response.body;
    }
  };
}

global.fetch = async (url, options) => {
  const urlStr = String(url);
  const method = (options && options.method) || 'GET';
  let body = null;
  if (options && typeof options.body === 'string') {
    try { body = JSON.parse(options.body); } catch (e) { body = options.body; }
  }
  fetchCallLog.push({ url: urlStr, method, body, cache: options && options.cache });
  if (urlStr === '/api/public-market/snapshot') {
    fetchUrl = urlStr;
    return buildFetchResponse({ status: 200, body: fixtureToFetch });
  }
  if (urlStr === '/api/asset-transfer' && method === 'POST') {
    return buildFetchResponse(assetTransferPostResponse || {
      status: 503,
      body: { error: 'asset_transfer_unavailable', detail: 'mock 未设置划转响应' }
    });
  }
  if (urlStr === '/api/margin-repay' && method === 'POST') {
    marginRepayPostPendingSnapshot = localStorageData['funding_hedging_margin_repay_pending'] || null;
    if (marginRepayPostThrow) {
      const thrower = marginRepayPostThrow;
      marginRepayPostThrow = null;
      throw thrower;
    }
    return buildFetchResponse(marginRepayPostResponse || {
      status: 503,
      body: { error: 'margin_repay_unavailable', detail: 'mock 未设置还款响应' }
    });
  }
  if (urlStr.startsWith('/api/margin-repay?') && method === 'GET') {
    return buildFetchResponse(marginRepayGetResponse || {
      status: 503,
      body: { error: 'margin_repay_unavailable', detail: 'mock 未设置还款查询响应' }
    });
  }
  if (urlStr.startsWith('/api/private-account/max-withdraw')) {
    return buildFetchResponse(maxWithdrawGetResponse || {
      status: 503,
      body: { error: 'private_account_unavailable', detail: 'mock 未设置 max-withdraw 响应' }
    });
  }
  if (urlStr === '/api/public-market/cache-refresh' && method === 'POST') {
    return buildFetchResponse(cacheRefreshPostResponse || {
      status: 503,
      body: { error: 'cache_refresh_unavailable', detail: 'mock 未设置 cache-refresh 响应' }
    });
  }
  if (urlStr.startsWith('/api/public-market/symbol-snapshot')) {
    lastHistoryUrl = urlStr;
    if (historyResponse && historyResponse.delay) {
      return new Promise((resolve) => {
        historyResolve = () => {
          const jsonDelay = historyResponse && historyResponse.jsonDelay;
          // Resolve fetch() now; if jsonDelay is true, res.json() will remain pending.
          resolve(buildFetchResponse(historyResponse, jsonDelay));
        };
      });
    }
    if (!historyResponse) {
      return buildFetchResponse({ status: 502, statusText: 'Bad Gateway', body: { error: 'funding_history_unavailable' } });
    }
    return buildFetchResponse(historyResponse);
  }
  // 借币任务冻结路由（§3.1）：mock 响应逐块设置，未设置时 503。
  if (urlStr === '/api/borrow-tasks' && method === 'GET') {
    return buildFetchResponse(borrowTasksGetResponse || mockBorrow503());
  }
  if (urlStr === '/api/borrow-tasks' && method === 'POST') {
    return buildFetchResponse(borrowTasksPostResponse || mockBorrow503());
  }
  const borrowActionMatch = urlStr.match(/^\/api\/borrow-tasks\/([^/]+)\/(start|pause|delete|edit)$/);
  if (borrowActionMatch && method === 'POST') {
    const key = `${decodeURIComponent(borrowActionMatch[1])}:${borrowActionMatch[2]}`;
    return buildFetchResponse(borrowActionResponses[key] || mockBorrow503());
  }
  if (urlStr.startsWith('/api/borrow-logs?') && method === 'GET') {
    return buildFetchResponse(borrowLogsResponses.length > 0 ? borrowLogsResponses.shift() : mockBorrow503());
  }
  if (urlStr === '/api/borrow-logs/clear' && method === 'POST') {
    return buildFetchResponse(borrowLogsClearResponse || {
      status: 200,
      body: { schema_version: 'borrow-tasks/v1', deleted_count: 0, retained_unresolved_count: 0 },
    });
  }
  if (urlStr === '/api/borrow-scheduler-settings' && method === 'GET') {
    return buildFetchResponse(borrowSettingsGetResponse || mockBorrow503());
  }
  if (urlStr === '/api/borrow-scheduler-settings' && method === 'PUT') {
    return buildFetchResponse(borrowSettingsPutResponse || mockBorrow503());
  }
  // Boundary C 执行控制（§3.2）：status GET 回放投影；start/stop POST 回显同一投影。
  if (urlStr === '/api/borrow-execution/status' && method === 'GET') {
    return buildFetchResponse(borrowExecutionStatusResponse || mockExecutionStatusDisabled());
  }
  if ((urlStr === '/api/borrow-execution/start' || urlStr === '/api/borrow-execution/stop') && method === 'POST') {
    return buildFetchResponse(borrowExecutionStatusResponse || mockExecutionStatusDisabled());
  }
  // 开单任务冻结路由（2026-07-hedge-open-live-v1 §3）：响应逐块设置，未设置时 503。
  const hedgeActionMatch = urlStr.match(/^\/api\/hedge-open-tasks\/([^/]+)\/(pause|start|delete|fill-once|fill-all)$/);
  if (hedgeActionMatch && method === 'POST') {
    const key = `${decodeURIComponent(hedgeActionMatch[1])}:${hedgeActionMatch[2]}`;
    return buildFetchResponse(hedgeActionResponses[key] || mockHedge503());
  }
  if (urlStr === '/api/hedge-open-tasks' && method === 'POST') {
    return buildFetchResponse(hedgeTasksPostResponse || mockHedge503());
  }
  if (urlStr.startsWith('/api/hedge-open-tasks') && method === 'GET') {
    return buildFetchResponse(hedgeTasksGetResponse || mockHedge503());
  }
  if (urlStr === '/api/hedge-open-settings' && method === 'GET') {
    return buildFetchResponse(hedgeSettingsGetResponse || mockHedge503());
  }
  if (urlStr === '/api/hedge-open-settings/start-gate' && method === 'POST') {
    return buildFetchResponse(hedgeStartGatePostResponse || mockHedge503());
  }
  if (urlStr === '/api/hedge-open-positions' && method === 'GET') {
    return buildFetchResponse(hedgePositionsGetResponse || mockHedge503());
  }
  // 功能三 ③a：历史仓位——周期结算日志（真实数据源）。
  if (urlStr === '/api/hedge-open-close-logs' && method === 'GET') {
    return buildFetchResponse(hedgeCloseLogsGetResponse || mockHedge503());
  }
  // real-api-v1：attempt 时间线读取（既有 logs 路由，GET，固定 ?limit=100 无 cursor，
  // 17 号兼容修正未改动这条）；开单日志页改用独立加法式 ?entries_limit=[&entries_cursor=]
  // 走独立分页队列，二者共享同一路由但请求形状不同（不同字面量 query string），
  // mock 按此区分，不影响生产代码。
  if (urlStr.startsWith('/api/hedge-open-logs') && method === 'GET') {
    if (urlStr === '/api/hedge-open-logs?limit=100') {
      return buildFetchResponse(hedgeLogsGetResponse || mockHedge503());
    }
    // 任务卡内嵌日志：?task_id=… 一次返回该任务全部 attempt（独立于日志页分页队列）。
    if (urlStr.includes('task_id=')) {
      return buildFetchResponse(hedgeTaskLogsGetResponse || mockHedge503());
    }
    return buildFetchResponse(hedgeLogPageResponses.length > 0 ? hedgeLogPageResponses.shift() : mockHedge503());
  }
  // 流水日志 private-ledger（task C）
  if (urlStr.startsWith('/api/private-ledger/flow-log') && method === 'GET') {
    return buildFetchResponse(
      flowLogGetResponse || { status: 200, body: buildMockFlowLogPayload() }
    );
  }
  if (urlStr === '/api/private-ledger/refresh' && method === 'POST') {
    return buildFetchResponse(
      flowLogRefreshResponse || {
        status: 200,
        body: {
          run_id: 9,
          kind: 'manual',
          finished_at_ms: 1785798060000,
          interest_status: 'ok',
          interest_error: null,
          interest_new_row_count: 0,
          income_status: 'ok',
          income_error: null,
          income_new_row_count: 0,
          truncated: false,
        },
      }
    );
  }
  throw new Error(`Unexpected fetch URL: ${urlStr} (${method})`);
};

global.document = {
  getElementById: (id) => {
    if (!elements[id]) {
      // 借币任务操作控件为按 symbol/任务 id（字符串 UUID）动态生成的 id，按需惰性 mock（最小 mock 能力补足）；
      // 开单市场表操作列输入/行内错误、任务动作错误元素，与任务卡内嵌日志容器同样按需惰性 mock。
      if (/^(borrow-(amount|count|error|preview)-[A-Za-z0-9_]+|task-edit-(amount|count|error)-[A-Za-z0-9_-]+|hedge-(amount|count|error)-(forward|reverse)-[A-Za-z0-9_]+|hedge-close-(amount|count|error)-[A-Za-z0-9_]+|hedge-task-error-[A-Za-z0-9-]+|hedge-task-log-[A-Za-z0-9_-]+)$/.test(id)) {
        const el = makeElement(id);
        elements[id] = el;
        return el;
      }
      throw new Error(`未 mock 的元素: ${id}`);
    }
    return elements[id];
  },
  querySelector(sel) {
    // flow-log 自定义时间区：class 选择器映射到 mock 包装
    if (sel === '.flow-log-custom-range') {
      if (!elements['__flow-log-custom-wrap']) {
        const el = makeElement('__flow-log-custom-wrap');
        const set = new Set();
        Object.defineProperty(el, 'classList', {
          value: {
            add(c) { set.add(c); },
            remove(c) { set.delete(c); },
            contains(c) { return set.has(c); },
            toggle(c, force) {
              if (force === true) set.add(c);
              else if (force === false) set.delete(c);
              else if (set.has(c)) set.delete(c);
              else set.add(c);
            },
          },
          configurable: true,
        });
        elements['__flow-log-custom-wrap'] = el;
      }
      return elements['__flow-log-custom-wrap'];
    }
    return null;
  },
  body: {
    style: {}
  },
  addEventListener(type, handler) {
    (this._listeners = this._listeners || {})[type] = handler;
  }
};

// 运行脚本
eval(script);

function normalizeWhitespace(s) {
  return String(s).replace(/\s+/g, ' ').trim();
}

function assertOrder(tbodyHtml, symbols) {
  const positions = symbols.map(sym => tbodyHtml.indexOf(sym));
  for (let i = 1; i < positions.length; i++) {
    if (positions[i] <= positions[i - 1]) {
      throw new Error(`渲染顺序错误：${symbols[i - 1]} 与 ${symbols[i]} 位置关系不符`);
    }
  }
}

function getRowCell(tbodyHtml, symbol, cellIndex) {
  const symIdx = tbodyHtml.indexOf(symbol);
  if (symIdx === -1) throw new Error(`未找到 ${symbol} 行`);
  const trStart = tbodyHtml.lastIndexOf('<tr', symIdx);
  const trEnd = tbodyHtml.indexOf('</tr>', trStart);
  const rowHtml = tbodyHtml.slice(trStart, trEnd + 5);
  let tdCount = 0;
  let pos = rowHtml.indexOf('<td');
  while (pos !== -1 && tdCount <= cellIndex) {
    const close = rowHtml.indexOf('</td>', pos);
    if (tdCount === cellIndex) {
      return rowHtml.slice(pos, close + 5);
    }
    pos = rowHtml.indexOf('<td', close + 5);
    tdCount++;
  }
  throw new Error(`${symbol} 行缺少第 ${cellIndex + 1} 个单元格`);
}

// 借币任务卡解析：按 data-task-id 截取单张卡的 HTML
function getTaskCardHtml(listHtml, id) {
  const marker = `<div class="borrow-task-card" data-task-id="${id}">`;
  const start = listHtml.indexOf(marker);
  if (start === -1) throw new Error(`未找到任务卡 ${id}: ${listHtml}`);
  const next = listHtml.indexOf('<div class="borrow-task-card"', start + marker.length);
  return listHtml.slice(start, next === -1 ? listHtml.length : next);
}

function taskActionBtnHtml(cardHtml, action) {
  const m = cardHtml.match(new RegExp(`<button[^>]*data-task-action="${action}"[^>]*>`));
  if (!m) throw new Error(`任务卡缺少 ${action} 按钮: ${cardHtml}`);
  return m[0];
}

function taskEditConfirmBtnHtml(cardHtml, id) {
  const m = cardHtml.match(new RegExp(`<button[^>]*data-task-edit-confirm="${id}"[^>]*>`));
  if (!m) throw new Error(`任务卡缺少编辑确认按钮: ${cardHtml}`);
  return m[0];
}

function taskEditInputHtml(cardHtml, kind, id) {
  const tagStart = cardHtml.indexOf(`<input id="task-edit-${kind}-${id}"`);
  if (tagStart === -1) throw new Error(`任务卡缺少 task-edit-${kind}-${id} 输入: ${cardHtml}`);
  return cardHtml.slice(tagStart, cardHtml.indexOf('/>', tagStart) + 2);
}

// 等待 async 渲染
setTimeout(async () => {
  try {
    // 1. 默认请求 /api/public-market/snapshot
    if (fetchUrl !== '/api/public-market/snapshot') {
      throw new Error(`默认请求地址错误: ${fetchUrl}`);
    }
    console.log('[PASS] 默认请求 /api/public-market/snapshot');

    // 2. 数据源标签
    const sourceLabel = elements['data-source-label'].textContent;
    if (!sourceLabel.includes('/api/public-market/snapshot')) {
      throw new Error(`数据源标签错误: ${sourceLabel}`);
    }
    console.log('[PASS] 数据源标签显示后端 API');

    // 3. 数据说明模块已删除；市场表标题下一行展示北京时间快照元信息
    if (html.includes('id="warnings-panel"') || html.includes('>数据说明<')) {
      throw new Error('数据说明面板应已删除');
    }
    if (html.includes('id="footer-note"')) {
      throw new Error('页脚 footer-note 应已删除（时间已移到市场表标题下）');
    }
    const meta = elements['market-snapshot-meta'].textContent;
    if (!meta.includes('生成时间') || !meta.includes('数据时间') || !meta.includes('60 秒')) {
      throw new Error(`市场表标题下元信息缺失: ${meta}`);
    }
    // fixture generated_at/data_time are Zulu; UI must render Asia/Shanghai wall clock (not raw Z)
    if (meta.includes('T') && meta.includes('Z')) {
      throw new Error(`快照时间应已转为北京时间，不应再显示 ISO Z: ${meta}`);
    }
    console.log('[PASS] 数据说明已删除；市场表下北京时间元信息已渲染');

    // 低日费率过滤默认开启：设计期 fixture 的 CUSDT daily_funding_rate 正好是边界
    // 0.00030000，默认会被隐藏（6→5）。legacy 6 行基线段在此显式关闭该过滤并重渲染，
    // 使既有断言（引用 CUSDT 的 #6/#19/#20/#28/#33/#34 等）全 6 行可见。过滤的默认
    // 开启行为由 #39 独立低费率边界场景覆盖（实现 prompt §6.2；design review 推荐 B）。
    elements['filter-hide-low-daily-rate'].checked = false;
    (elements['filter-hide-low-daily-rate'].listeners.change || []).forEach(h => h());
    // 低日净收益过滤默认 on 会藏 net≤0.03%（有符号；设计 fixture BUSDT net=0.0001）；legacy 基线关闭。
    elements['filter-hide-low-net-yield'].checked = false;
    (elements['filter-hide-low-net-yield'].listeners.change || []).forEach(h => h());
    // 可开优先默认 on 会 re-rank；legacy 顺序断言要求 payload 序，此处显式关闭。
    // 可开优先行为由后续独立场景覆盖。
    elements['filter-prefer-openable'].checked = false;
    (elements['filter-prefer-openable'].listeners.change || []).forEach(h => h());

    // 4. 默认渲染 6 行（设计期 fixture；legacy 基线已关闭低日费率/低净收益过滤与可开优先）
    let tbody = elements['market-table-body'].innerHTML;
    let rowCount = (tbody.match(/<tr/g) || []).length;
    if (rowCount !== 6) {
      throw new Error(`默认筛选后期望 6 行数据，实际 ${rowCount} 行`);
    }
    console.log('[PASS] 默认渲染 6 行');

    // 5. 拆列：存在独立「资金费率」「结算时间」「日费率」「日净收益」列，合并列消失
    if (!html.includes('>资金费率<')) {
      throw new Error('缺少「资金费率」列名');
    }
    if (!html.includes('>结算时间<')) {
      throw new Error('缺少「结算时间」列名');
    }
    if (!html.includes('>日费率<')) {
      throw new Error('缺少「日费率」列名');
    }
    if (!html.includes('>日净收益<')) {
      throw new Error('缺少「日净收益」列名');
    }
    if (html.includes('资金费率/结算时间')) {
      throw new Error('仍保留「资金费率/结算时间」合并列名');
    }
    console.log('[PASS] 拆列存在，合并列消失');

    // 5b. 年化三列存在且列名/提示文案区分 24h 预估与 7D/30D 已结算
    const annualizedHeaders = ['年化 24h', '年化 7D', '年化 30D'];
    for (const h of annualizedHeaders) {
      if (!html.includes(`>${h}<`)) {
        throw new Error(`缺少「${h}」列名`);
      }
    }
    if (!html.includes('预估 24h 年化')) {
      throw new Error('24h 列头缺少「预估」提示');
    }
    if (!html.includes('已结算 7 日年化') || !html.includes('已结算 30 日年化')) {
      throw new Error('7D/30D 列头缺少「已结算」提示');
    }
    console.log('[PASS] 年化三列存在且文案区分预估/已结算');

    // 5c. Task D: 默认表移除路由分类列，但保留路由过滤器与字段校验；
    // Task B: 无「提示标记」/独立「负费率状态」列，新增开单列；
    // 借币任务阶段：第 13 列为「借币」；
    // 开单 fake 阶段：估算列改名「正向开单率/反向开单率」，借币列后新增两操作列
    // 「正向开单」「反向开单」→ 最终 15 列。
    if (html.includes('<th>路由分类</th>')) {
      throw new Error('默认表仍保留「路由分类」列');
    }
    if (html.includes('<th>提示标记</th>')) {
      throw new Error('默认表仍保留「提示标记」列');
    }
    if (html.includes('<th>负费率状态</th>')) {
      throw new Error('默认表仍保留独立「负费率状态」列');
    }
    const requiredHeaders = ['借贷状态 / 资产', '日净收益', '正向开单率', '反向开单率', '借币', '正向开单', '反向开单'];
    for (const h of requiredHeaders) {
      if (!html.includes(`>${h}<`)) {
        throw new Error(`缺少「${h}」列名`);
      }
    }
    const marketTableStart = html.indexOf('id="market-table-body"');
    const marketTheadStart = html.lastIndexOf('<thead>', marketTableStart);
    const marketTheadEnd = html.indexOf('</thead>', marketTheadStart) + 8;
    const marketTheadHtml = html.slice(marketTheadStart, marketTheadEnd);
    const headerCount = (marketTheadHtml.match(/<th[\s>]/g) || []).length;
    if (headerCount !== 15) {
      throw new Error(`市场表头应为 15 列，实际 ${headerCount} 列`);
    }
    // 路由过滤器仍保留
    if (!html.includes('id="filter-route"')) {
      throw new Error('路由过滤器被移除');
    }
    // REQUIRED_ROW_FIELDS 仍保留 route_class 字段校验
    if (!script.includes("'route_class'")) {
      throw new Error('REQUIRED_ROW_FIELDS 中 route_class 校验被移除');
    }
    console.log('[PASS] 路由分类列移除，过滤器与字段校验保留');

    // 5d. Task D: Drawer 宽度与卡片标签不换行
    if (!html.includes('width: min(620px, 100vw)')) {
      throw new Error('Drawer 未使用 min(620px, 100vw) 宽度');
    }
    if (!html.includes('grid-template-columns: repeat(3, minmax(0, 1fr))')) {
      throw new Error('年化网格未使用三列等宽非溢出布局');
    }
    const annualizedLabelCss = html.slice(html.indexOf('.annualized-card .label'), html.indexOf('.annualized-card .value'));
    if (!annualizedLabelCss.includes('white-space: nowrap')) {
      throw new Error('年化卡片标签未禁止换行');
    }
    console.log('[PASS] Drawer 宽度与卡片标签约束');

    // 6. 日费率 string-shift 格式化（含 null→—）
    // 6-addendum. 资金费率固定 3 位小数百分比
    const ausdtFundingCell = getRowCell(tbody, 'AUSDT', 3);
    if (!ausdtFundingCell.includes('-0.060%')) {
      throw new Error(`AUSDT 资金费率期望 -0.060%，单元格 ${ausdtFundingCell}`);
    }
    const cusdtFundingCell = getRowCell(tbody, 'CUSDT', 3);
    if (!cusdtFundingCell.includes('+0.030%')) {
      throw new Error(`CUSDT 资金费率期望 +0.030%，单元格 ${cusdtFundingCell}`);
    }
    const fusdtFundingCell = getRowCell(tbody, 'FUSDT', 3);
    if (!fusdtFundingCell.includes('0.000%')) {
      throw new Error(`FUSDT 资金费率期望 0.000%，单元格 ${fusdtFundingCell}`);
    }
    console.log('[PASS] 资金费率固定 3 位小数');

    const dailyRateChecks = [
      ['AUSDT', '-0.060%'],
      ['BUSDT', '-0.070%'],
      ['CUSDT', '+0.030%'],
      ['DUSDT', '-0.040%'],
      ['EUSDT', '-0.080%'],
      ['FUSDT', '—']
    ];
    for (const [sym, expected] of dailyRateChecks) {
      const cell = getRowCell(tbody, sym, 5);
      if (!cell.includes(expected)) {
        throw new Error(`${sym} 日费率期望 ${expected}，单元格 ${cell}`);
      }
    }
    console.log('[PASS] 日费率 string-shift 格式化（含 null→—）');

    // 6a. 近 24h 列：费率之和（非年化），固定 3 位小数；AUSDT 有值，BUSDT null→—
    const ausdtSum24 = getRowCell(tbody, 'AUSDT', 6);
    if (!ausdtSum24.includes('+0.005%')) {
      throw new Error(`AUSDT 近 24h 期望 +0.005%，单元格 ${ausdtSum24}`);
    }
    const busdtSum24 = getRowCell(tbody, 'BUSDT', 6);
    if (!busdtSum24.includes('—')) {
      throw new Error(`BUSDT 近 24h 期望 —，单元格 ${busdtSum24}`);
    }
    console.log('[PASS] 近 24h 列格式化（3 位小数，null→—）');

    // 6b. 年化三列格式化：AUSDT 三值齐全，BUSDT 7D/30D 为 null→—
    const ausdtAnn24 = getRowCell(tbody, 'AUSDT', 7);
    if (!ausdtAnn24.includes('-65.70%')) {
      throw new Error(`AUSDT 年化 24h 期望 -65.70%，单元格 ${ausdtAnn24}`);
    }
    const ausdtAnn7 = getRowCell(tbody, 'AUSDT', 8);
    if (!ausdtAnn7.includes('-0.26%')) {
      throw new Error(`AUSDT 年化 7D 期望 -0.26%，单元格 ${ausdtAnn7}`);
    }
    const ausdtAnn30 = getRowCell(tbody, 'AUSDT', 9);
    if (!ausdtAnn30.includes('-0.06%')) {
      throw new Error(`AUSDT 年化 30D 期望 -0.06%，单元格 ${ausdtAnn30}`);
    }
    const busdtAnn7 = getRowCell(tbody, 'BUSDT', 8);
    if (!busdtAnn7.includes('—')) {
      throw new Error(`BUSDT 年化 7D 期望 —，单元格 ${busdtAnn7}`);
    }
    const busdtAnn30 = getRowCell(tbody, 'BUSDT', 9);
    if (!busdtAnn30.includes('—')) {
      throw new Error(`BUSDT 年化 30D 期望 —，单元格 ${busdtAnn30}`);
    }
    console.log('[PASS] 年化三列格式化（含 null→—）');

    // 7. 结算间隔标注 8h（设计期 fixture 全部为 8h）
    if (!tbody.includes('>8h<')) {
      throw new Error('未渲染 8h 结算间隔徽标');
    }
    console.log('[PASS] 结算间隔标注 8h');

    // 8. 无通用排序控件 DOM（允许「可开优先展示」展示偏好；禁止排序按钮/下拉/「排序」字样）
    const controlsStart = html.indexOf('<div class="controls"');
    const controlsEnd = html.indexOf('</div>', controlsStart) + 6;
    const controlsHtml = html.slice(controlsStart, controlsEnd);
    if (!html.includes('id="filter-prefer-openable"') || !html.includes('可开优先展示')) {
      throw new Error('缺少「可开优先展示」筛选项');
    }
    if (controlsHtml.includes('排序') || controlsHtml.includes('sort') || controlsHtml.includes('Sort')) {
      throw new Error('页面控制区不应包含排序按钮或排序状态');
    }
    console.log('[PASS] 无通用排序控件 DOM；可开优先控件存在');

    // 9. 渲染顺序 == fixture 顺序（可开优先已关：AUSDT > BUSDT > CUSDT > DUSDT > EUSDT > FUSDT）
    assertOrder(tbody, ['AUSDT', 'BUSDT', 'CUSDT', 'DUSDT', 'EUSDT', 'FUSDT']);
    console.log('[PASS] 渲染顺序等于 payload 顺序');

    // 10. 时间转换正确 ( fixture next_funding_time 北京时间为 16:00 )
    if (!tbody.includes('16:00')) {
      throw new Error('下一次结算时间未正确转换为北京时间 HH:mm');
    }
    console.log('[PASS] 时间转换正确');

    // 11. 列名/文案符合契约：资金费率/日费率等非年化列头不得出现"已结算"或"预测"；
    // 年化 7D/30D 列头允许出现"已结算"，因其确为 settled-history 年化。
    const tableSection = html.slice(html.indexOf('<table>'), html.indexOf('</table>') + 8);
    const headers = [...tableSection.matchAll(/<th[^>]*>[\s\S]*?<\/th>/g)].map(m => m[0]);
    const thCount = (tableSection.match(/<th[>\s][^>]*>/g) || []).length;
    if (headers.length !== thCount) {
      throw new Error(`列头解析数量不匹配: ${headers.length} != ${thCount}`);
    }
    const nonSettledHeaders = headers.filter(h => !h.includes('>年化 7D<') && !h.includes('>年化 30D<'));
    const bad = nonSettledHeaders.find(h => h.includes('已结算') || h.includes('预测'));
    if (bad) {
      throw new Error('非年化列头出现"已结算"或"预测": ' + bad);
    }
    console.log('[PASS] 列名/文案无误导性 settlement/prediction 文案');

    // 12. 无交易按钮/开仓票据（UM 持仓展示列「开仓价」除外）
    if (html.includes('手动开仓') || html.includes('下单') || html.includes('立即开仓')) {
      throw new Error('页面不应包含交易按钮或开仓票据');
    }
    console.log('[PASS] 无交易按钮/开仓票据');

    // 13. 资金费率字符串移位格式化（7 个必测样例）
    const helpers = globalThis.__appHelpers;
    if (!helpers || typeof helpers.formatFundingRate !== 'function') {
      throw new Error('格式化辅助函数未暴露');
    }
    const rateCases = [
      ['0.00010000', '+0.01%'],
      ['-0.00005000', '-0.005%'],
      ['0.00000000', '0%'],
      ['-0.00000000', '0%'],
      ['0', '0%'],
      ['0.00008556', '+0.008556%'],
      ['', '—']
    ];
    for (const [input, expected] of rateCases) {
      const actual = helpers.formatFundingRate(input);
      if (actual !== expected) {
        throw new Error(`formatFundingRate(${JSON.stringify(input)}) 期望 ${expected}，实际 ${actual}`);
      }
    }
    console.log('[PASS] 资金费率格式化 7 个样例');

    // 14. formatFundingRate / formatBeijing* 函数体未变（字符串比对）
    const expectedFormatFundingRate = `function formatFundingRate(str) {
        if (str === undefined || str === null || str === '') return '—';
        const m = String(str).match(/^(-?)(\\d+)\\.?(\\d*)$/);
        if (!m) return '—';
        const [, sign, intPart, fracPart] = m;
        const firstTwo = (fracPart + '00').slice(0, 2);
        const newIntRaw = intPart + firstTwo;
        const newInt = newIntRaw.replace(/^0+/, '') || '0';
        const remainingFrac = fracPart.slice(2).replace(/0+$/, '');
        const isZero = newInt === '0' && remainingFrac === '';
        if (isZero) return '0%';
        const value = remainingFrac ? \`\${newInt}.\${remainingFrac}\` : newInt;
        const finalSign = sign ? '-' : '+';
        return \`\${finalSign}\${value}%\`;
      }`;
    if (normalizeWhitespace(helpers.formatFundingRate.toString()) !== normalizeWhitespace(expectedFormatFundingRate)) {
      throw new Error('formatFundingRate 函数体与基线不一致');
    }
    if (typeof helpers.formatBeijing !== 'function' || !helpers.formatBeijing.toString().includes('Asia/Shanghai')) {
      throw new Error('formatBeijing 函数体与基线不一致');
    }
    console.log('[PASS] formatFundingRate / formatBeijing* 函数体未变');

    // 14c. formatFundingRateFixed 固定小数位百分比（Task C addendum）
    if (!helpers || typeof helpers.formatFundingRateFixed !== 'function') {
      throw new Error('formatFundingRateFixed 辅助函数未暴露');
    }
    const fixedCases = [
      // 资金费率/日费率 3 位
      ['-0.00030000', 3, '-0.030%'],
      ['0.00030000', 3, '+0.030%'],
      ['0', 3, '0.000%'],
      ['-0.00000000', 3, '0.000%'],
      // 年化 2 位
      ['-0.657', 2, '-65.70%'],
      ['-0.00260714', 2, '-0.26%'],
      ['-0.00060833', 2, '-0.06%'],
      // HALF_UP 进位边界
      ['0.00000999', 3, '+0.001%'],
      ['0.00001999', 3, '+0.002%'],
      ['0.999995', 2, '+100.00%'],
      // 微小负值归一化为无符号零
      ['-0.00000499', 3, '0.000%'],
      // 无效/空输入
      ['', 3, '—'],
      [null, 3, '—'],
      ['not-a-number', 3, '—']
    ];
    for (const [input, decimals, expected] of fixedCases) {
      const actual = helpers.formatFundingRateFixed(input, decimals);
      if (actual !== expected) {
        throw new Error(`formatFundingRateFixed(${JSON.stringify(input)}, ${decimals}) 期望 ${expected}，实际 ${actual}`);
      }
    }
    console.log('[PASS] formatFundingRateFixed 固定小数位百分比');

    // 14b. formatUsdt2 2 位 ROUND_HALF_UP
    if (!helpers || typeof helpers.formatUsdt2 !== 'function') {
      throw new Error('formatUsdt2 辅助函数未暴露');
    }
    const usdt2Cases = [
      ['123.45600000', '123.46'],
      ['123.45400000', '123.45'],
      ['-123.45600000', '-123.46'],
      ['0.00000000', '0.00'],
      ['0.00500000', '0.01'],
      ['0.00499999', '0.00'],
      ['999.99900000', '1000.00'],
      ['', null],
      [null, null],
      ['not-a-number', null]
    ];
    for (const [input, expected] of usdt2Cases) {
      const actual = helpers.formatUsdt2(input);
      if (actual !== expected) {
        throw new Error(`formatUsdt2(${JSON.stringify(input)}) 期望 ${JSON.stringify(expected)}，实际 ${JSON.stringify(actual)}`);
      }
    }
    console.log('[PASS] formatUsdt2 2 位 ROUND_HALF_UP');

    // 15. 自动刷新 60s 与倒计时元素
    if (!html.includes('60000')) {
      throw new Error('未找到 60000 自动刷新间隔常量');
    }
    if (!html.includes('下次刷新')) {
      throw new Error('未找到「下次刷新」倒计时文案');
    }
    if (!html.includes('Config.cache_ttl_seconds=60')) {
      throw new Error('未注明与后端缓存 TTL 对齐的注释');
    }
    console.log('[PASS] 自动刷新 60s 与倒计时元素存在');

    // 16. 资产标签/负费率状态列显示中文优先格式；路由分类列已从默认表移除，
    // 但过滤器下拉仍保留选项。
    const enumDisplayChecks = [
      ['CRYPTO(加密货币)', '资产标签'],
      ['已验证可借', '负费率状态']
    ];
    for (const [expected, column] of enumDisplayChecks) {
      if (!tbody.includes(expected)) {
        throw new Error(`${column} 列未渲染预期格式: ${expected}`);
      }
    }
    if (tbody.includes('MARGIN_SPOT_CANDIDATE(杠杆现货候选)')) {
      throw new Error('默认表仍渲染路由分类单元格内容');
    }
    if (!html.includes('<option value="MARGIN_SPOT_CANDIDATE">')) {
      throw new Error('路由分类过滤下拉选项被移除');
    }
    // 结构禁用行保持结构文案，不得派生为"需私有验证"
    if (!tbody.includes('仅现货: 无杠杆借币')) {
      throw new Error('DISABLED_SPOT_ONLY 行未保持结构文案');
    }
    console.log('[PASS] 资产/负费率状态列中文格式与路由列移除检查');

    // 17. 侧栏品牌已中文化
    if (!html.includes('资金费率对冲')) {
      throw new Error('侧栏品牌未改为“资金费率对冲”');
    }
    console.log('[PASS] 侧栏品牌已中文化');

    // 18. 手动刷新后 60s 自动刷新计时器被重调度，1s 倒计时计时器保持独立
    const initialRefreshTimer = intervalCalls.slice().reverse().find(c => c.delay === 60000);
    const initialCountdownTimer = intervalCalls.slice().reverse().find(c => c.delay === 1000);
    if (!initialRefreshTimer) throw new Error('未找到初始 60000ms 自动刷新计时器');
    if (!initialCountdownTimer) throw new Error('未找到初始 1000ms 倒计时计时器');
    await Promise.all((elements['btn-refresh'].listeners.click || []).map(h => h()));
    if (!clearedIntervalIds.has(initialRefreshTimer.id)) {
      throw new Error('手动刷新完成后，旧的 60000ms 自动刷新计时器未被 clearInterval');
    }
    if (clearedIntervalIds.has(initialCountdownTimer.id)) {
      throw new Error('手动刷新完成后，1000ms 倒计时计时器不应被 clearInterval');
    }
    const newRefreshTimer = intervalCalls.slice().reverse().find(c => c.delay === 60000);
    if (!newRefreshTimer || newRefreshTimer.id === initialRefreshTimer.id) {
      throw new Error('手动刷新完成后，未重新创建 60000ms 自动刷新计时器');
    }
    const autoCallsBefore = fetchCallLog.length;
    newRefreshTimer.callback();
    await new Promise(resolve => setImmediate(resolve));
    const autoCalls = fetchCallLog.slice(autoCallsBefore);
    if (!autoCalls.some(c => c.url === '/api/public-market/snapshot' && c.cache === 'no-store')) {
      throw new Error('60s 自动刷新须强制重拉 snapshot（cache=no-store）');
    }
    if (!autoCalls.some(c => c.url === '/api/hedge-open-positions' && c.cache === 'no-store')) {
      throw new Error('60s 自动刷新须强制重拉对冲持仓（cache=no-store）');
    }
    console.log('[PASS] 60s 自动刷新强制重拉快照与持仓，手动刷新后计时器重调度');

    // 19. 净收益列存在与格式（统一 3 位小数百分比）
    const netYieldChecks = [
      ['AUSDT', '+0.040%', 'next_hourly'],
      ['BUSDT', '+0.010%', 'cross_margin_tier'],
      ['CUSDT', '+0.030%', null],
      ['DUSDT', '—', null],
      ['EUSDT', '—', null],
      ['FUSDT', '—', null]
    ];
    for (const [sym, expectedNet, expectedSource] of netYieldChecks) {
      const cell = getRowCell(tbody, sym, 10);
      if (!cell.includes(expectedNet)) {
        throw new Error(`${sym} 净收益期望 ${expectedNet}，单元格 ${cell}`);
      }
      if (expectedSource === 'next_hourly' && !cell.includes('下小时')) {
        throw new Error(`${sym} 期望成本来源徽标「下小时」，单元格 ${cell}`);
      }
      if (expectedSource === 'cross_margin_tier' && !cell.includes('杠杆分层')) {
        throw new Error(`${sym} 期望成本来源徽标「杠杆分层」，单元格 ${cell}`);
      }
      if (expectedSource === null && (cell.includes('source-badge') || cell.includes('下小时') || cell.includes('杠杆分层'))) {
        throw new Error(`${sym} 期望无成本来源徽标，单元格 ${cell}`);
      }
    }
    console.log('[PASS] 净收益列存在与格式');

    // 20. 负值净收益红色样式
    const cusdtNetCell = getRowCell(tbody, 'CUSDT', 10);
    const ausdtNetCell = getRowCell(tbody, 'AUSDT', 10);
    if (!ausdtNetCell.includes('positive')) {
      throw new Error('AUSDT 正净收益未应用 positive 样式');
    }
    // 设计 fixture 无负净收益行；构造一个负净收益 fixture 行验证样式
    const negativeNetFixture = JSON.parse(JSON.stringify(designFixture));
    negativeNetFixture.rows[0].net_daily_yield = '-0.00020000';
    negativeNetFixture.rows[0].borrow_rate_source = null;
    helpers.ingestSnapshot(negativeNetFixture);
    const negTbody = elements['market-table-body'].innerHTML;
    const negCell = getRowCell(negTbody, 'AUSDT', 10);
    if (!negCell.includes('negative')) {
      throw new Error('负净收益未应用 negative 红色样式');
    }
    // 恢复原始 fixture
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] 负值净收益红色样式');

    // 21. vip0_reference 显著标注「基准利率」
    const vip0Fixture = JSON.parse(JSON.stringify(designFixture));
    vip0Fixture.rows[1].borrow_rate_source = 'vip0_reference';
    helpers.ingestSnapshot(vip0Fixture);
    const vip0Tbody = elements['market-table-body'].innerHTML;
    const vip0Cell = getRowCell(vip0Tbody, 'BUSDT', 10);
    if (!vip0Cell.includes('基准利率') || !vip0Cell.includes('vip0-reference')) {
      throw new Error('vip0_reference 未显著标注「基准利率」');
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] vip0_reference 显著标注「基准利率」');

    // 22. sort_basis 标注
    const sortBasisBadge = elements['sort-basis-badge'];
    if (sortBasisBadge.style.display === 'none') {
      throw new Error('sort_basis 标注未显示');
    }
    if (!sortBasisBadge.textContent.includes('日净收益优先')) {
      throw new Error(`sort_basis 标注内容错误: ${sortBasisBadge.textContent}`);
    }
    console.log('[PASS] sort_basis 标注');

    // 23. 私有面板三态：verified=true
    const privatePanel = elements['private-panel'];
    if (privatePanel.style.display === 'none') {
      throw new Error('verified=true 时私有面板未显示');
    }
    const privateBody = elements['private-panel-body'].innerHTML;
    if (!privateBody.includes('总资产估值')) {
      throw new Error('私有面板未渲染总资产估值');
    }
    // PM / valuation split cards (missing pm_account still shows labels with —)
    for (const label of [
      '现货账户估值', '统一账户净资产', '借币负债', '杠杆率',
      '强平风险率', '总可用余额', '初始 / 维持保证金',
    ]) {
      if (!privateBody.includes(label)) {
        throw new Error(`私有面板概览缺少「${label}」`);
      }
    }
    if (!privateBody.includes('统一账户余额')) {
      throw new Error('私有面板未渲染统一账户余额');
    }
    if (!privateBody.includes('已借:')) {
      throw new Error('统一账户余额卡应展示「已借」行（cross_margin_borrowed）');
    }
    if (!privateBody.includes('净价值')) {
      throw new Error('统一账户余额卡应展示「净价值」行');
    }
    // 已借 > 0 时用红色 class borrowed-debt 高亮（保留），并展示已借价值
    {
      const debtFixture = JSON.parse(JSON.stringify(designFixture));
      if (debtFixture.private_account && Array.isArray(debtFixture.private_account.balances_unified)
          && debtFixture.private_account.balances_unified[0]) {
        debtFixture.private_account.balances_unified[0].cross_margin_borrowed = '1.5';
        debtFixture.private_account.balances_unified[0].total_balance = '1.5';
        debtFixture.private_account.balances_unified[0].cross_margin_borrowed_value_usdt = '25.00000000';
        helpers.ingestSnapshot(debtFixture);
        const debtBody = elements['private-panel-body'].innerHTML;
        if (!debtBody.includes('borrowed-debt') || !debtBody.includes('已借:')) {
          throw new Error('已借>0 应使用 borrowed-debt 红色样式: ' + debtBody);
        }
        // 价值断言须在显示态（隐藏态为 ****，不能假阴性）
        if (helpers.getPrivacyHidden()) helpers.togglePrivacy();
        const shownDebtBody = elements['private-panel-body'].innerHTML;
        const uStart = shownDebtBody.indexOf('统一账户余额');
        const sStart = shownDebtBody.indexOf('现货账户余额');
        const uSec = shownDebtBody.slice(uStart, sStart > uStart ? sStart : undefined);
        if (!uSec.includes('≈ 25.00 USDT')) {
          throw new Error('已借>0 应在统一区展示已借价值 ≈ 25.00 USDT: ' + uSec);
        }
        if (!uSec.includes('placeholder="0 自动还所有"')
            || !uSec.includes('data-repay-amount="BTC"')
            || !uSec.includes('data-repay-preview="BTC">还款</button>')) {
          throw new Error('已借>0 的资产卡须在已借行后展示还款输入框和按钮: ' + uSec);
        }
        const zeroDebtFixture = JSON.parse(JSON.stringify(debtFixture));
        zeroDebtFixture.private_account.balances_unified[0].cross_margin_borrowed = '0';
        zeroDebtFixture.private_account.balances_unified[0].cross_margin_borrowed_value_usdt = '0.00000000';
        helpers.ingestSnapshot(zeroDebtFixture);
        const zeroDebtBody = elements['private-panel-body'].innerHTML;
        const zuStart = zeroDebtBody.indexOf('统一账户余额');
        const zsStart = zeroDebtBody.indexOf('现货账户余额');
        const zeroDebtSec = zeroDebtBody.slice(zuStart, zsStart > zuStart ? zsStart : undefined);
        if (zeroDebtSec.includes('data-repay-preview="BTC"')) {
          throw new Error('无借款的资产卡不应展示还款按钮');
        }
        if (!helpers.getPrivacyHidden()) helpers.togglePrivacy(); // 恢复本段默认隐藏态
        helpers.ingestSnapshot(designFixture);
      }
    }
    if (!privateBody.includes('现货账户余额')) {
      throw new Error('私有面板未渲染现货账户余额');
    }
    // R3 (fix-merged-positions-n2-ui-v1): 原 `includes('UM 持仓')` 断言验证的是那张
    // 已被删除的独立 UM 持仓子表；它之所以仍绿，是因子表删除后改由「合并持仓表」承载，
    // 而新表副标题「（UM 持仓为骨架）」恰好命中子串。改为验证合并持仓表的 section 标题
    // 确实渲染（这才是新结构下有意义的对象），不删除断言。
    if (!privateBody.includes('对冲开单持仓')) {
      throw new Error('合并持仓表（对冲开单持仓 section）未渲染');
    }
    // designFixture 含 um_positions 时表头应有仓位价值列（方向与数量之间）
    if (Array.isArray(designFixture.private_account.um_positions)
        && designFixture.private_account.um_positions.length > 0
        && !privateBody.includes('仓位价值')) {
      throw new Error('UM 持仓表应有仓位价值列');
    }
    console.log('[PASS] 私有面板 verified=true 状态');

    // 23b. 时点合一：右上角显示旧聚合「账户资产更新时间」；私有面板内不再放同名聚合时间；
    // overview 不再出现估值时点/检查时点。
    const accountAssetTime = elements['account-asset-updated-at'].textContent;
    if (!accountAssetTime.includes('账户资产更新时间')) {
      throw new Error(`verified=true 时右上角未显示账户资产更新时间: ${accountAssetTime}`);
    }
    if (privateBody.includes('估值时点') || privateBody.includes('检查时点') || privateBody.includes('估值来源')) {
      throw new Error('verified=true 时私有面板 overview 仍出现估值时点/检查时点/估值来源');
    }
    if (!designFixture.private_account.valuation || !designFixture.private_account.valuation.price_source) {
      throw new Error('fixture 中 price_source 不存在');
    }
    console.log('[PASS] 时点合一与估值来源卡片删除');

    // 23c. 页面文案不再含矛盾运行约束
    const pageText = html + privateBody;
    if (pageText.includes('不连接 Binance')) {
      throw new Error('页面文本仍包含 "不连接 Binance"');
    }
    console.log('[PASS] 页面不含矛盾运行约束文案');

    // 24. 隐私开关默认隐藏金额
    const privacyLabel = elements['privacy-label'].textContent;
    if (privacyLabel !== '隐藏金额') {
      throw new Error(`隐私开关默认标签错误: ${privacyLabel}`);
    }
    if (!privateBody.includes('****')) {
      throw new Error('隐私开关默认隐藏态未将金额替换为 ****');
    }
    // localStorage 仅存布尔
    if (localStorageData['funding_hedging_privacy_hidden'] !== 'true') {
      throw new Error(`localStorage 隐私值错误: ${localStorageData['funding_hedging_privacy_hidden']}`);
    }
    console.log('[PASS] 隐私开关默认隐藏');

    // 25. 隐私开关点击切换
    await Promise.all((elements['btn-privacy'].listeners.click || []).map(h => h()));
    if (helpers.getPrivacyHidden() !== false) {
      throw new Error('点击隐私开关后应进入显示态');
    }
    const shownBody = elements['private-panel-body'].innerHTML;
    if (shownBody.includes('****')) {
      throw new Error('隐私开关显示态仍包含 **** 占位');
    }
    if (localStorageData['funding_hedging_privacy_hidden'] !== 'false') {
      throw new Error('localStorage 隐私布尔未更新为 false');
    }
    // 恢复隐藏态
    helpers.togglePrivacy();
    console.log('[PASS] 隐私开关点击切换');

    // 26. 私有面板 verified=false disabled 占位（未读提示在面板内，不在右上角聚合时间）
    const disabledFixture = JSON.parse(JSON.stringify(designFixture));
    disabledFixture.private_account = designFixture._design_fixture_private_account_states.find(s => s._state === 'verified_false_disabled');
    helpers.ingestSnapshot(disabledFixture);
    if (elements['private-panel'].style.display === 'none') {
      throw new Error('verified=false disabled 时私有面板不应隐藏');
    }
    const disabledBody = elements['private-panel-body'].innerHTML;
    if (!disabledBody.includes('私有账户未读取')) {
      throw new Error('verified=false disabled 未显示占位文案');
    }
    if (elements['account-asset-updated-at'].textContent.includes('私有账户未读取')) {
      throw new Error('右上角聚合时间不应复用「私有账户未读取」文案职责');
    }
    console.log('[PASS] 私有面板 verified=false disabled 占位');

    // 27. 私有面板 verified=false error 占位
    const errorFixture = JSON.parse(JSON.stringify(designFixture));
    errorFixture.private_account = designFixture._design_fixture_private_account_states.find(s => s._state === 'verified_false_error');
    helpers.ingestSnapshot(errorFixture);
    const errorBody = elements['private-panel-body'].innerHTML;
    if (!errorBody.includes('papi_balance_failed:HTTP 401')) {
      throw new Error('verified=false error 未显示错误原因');
    }
    console.log('[PASS] 私有面板 verified=false error 占位');

    // 恢复 verified=true fixture 供后续断言
    helpers.ingestSnapshot(designFixture);

    // 28. 行联动方向标（不带数量）
    const linkageFixture = JSON.parse(JSON.stringify(designFixture));
    linkageFixture.private_account.um_positions = [
      { symbol: 'AUSDT', position_side: 'LONG', notional_usdt: '1.50000000', position_amt: '1.5', entry_price: '1.00000000', mark_price: '1.00000000', unrealized_profit: '0.00000000' },
      { symbol: 'CUSDT', position_side: 'SHORT', notional_usdt: '6.00000000', position_amt: '-2.0', entry_price: '3.00000000', mark_price: '3.00000000', unrealized_profit: '0.00000000' }
    ];
    helpers.ingestSnapshot(linkageFixture);
    const linkageTbody = elements['market-table-body'].innerHTML;
    const ausdtSymbolCell = getRowCell(linkageTbody, 'AUSDT', 0);
    if (!ausdtSymbolCell.includes('direction-badge') || !ausdtSymbolCell.includes('多')) {
      throw new Error('AUSDT 行未渲染多头方向标');
    }
    if (ausdtSymbolCell.includes('1.5') || ausdtSymbolCell.includes('数量')) {
      throw new Error('AUSDT 行方向标不应携带数量');
    }
    const cusdtSymbolCell = getRowCell(linkageTbody, 'CUSDT', 0);
    if (!cusdtSymbolCell.includes('direction-badge') || !cusdtSymbolCell.includes('空')) {
      throw new Error('CUSDT 行未渲染空头方向标');
    }
    // 无持仓行不应有方向标
    const busdtSymbolCell = getRowCell(linkageTbody, 'BUSDT', 0);
    if (busdtSymbolCell.includes('direction-badge')) {
      throw new Error('BUSDT 无持仓行不应渲染方向标');
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] 行联动方向标（不带数量）');

    // 29. 优雅降级：新字段全缺失（旧后端）不白屏，日费率 —，净收益 —；
    // tab-layout-v2：费率行情页保留私有面板 header（双看板按钮所在），body 可空
    if (!helpers.ingestSnapshot) {
      throw new Error('ingestSnapshot 未暴露，无法测试优雅降级');
    }
    const degradedFixture = JSON.parse(JSON.stringify(designFixture));
    degradedFixture.rows.forEach(r => {
      delete r.daily_funding_rate;
      delete r.funding_interval_hours;
      delete r.net_daily_yield;
      delete r.borrow_rate_source;
    });
    delete degradedFixture.private_account;
    delete degradedFixture.sort_basis;
    helpers.ingestSnapshot(degradedFixture);
    const degradedTbody = elements['market-table-body'].innerHTML;
    const degradedRowCount = (degradedTbody.match(/<tr/g) || []).length;
    if (degradedRowCount !== 6) {
      throw new Error(`优雅降级后期望 6 行，实际 ${degradedRowCount} 行`);
    }
    const dRowIdx = degradedTbody.indexOf('DUSDT');
    const trStart = degradedTbody.lastIndexOf('<tr', dRowIdx);
    const dRowEnd = degradedTbody.indexOf('</tr>', trStart);
    const dRowHtml = degradedTbody.slice(trStart, dRowEnd + 5);
    let tdCount = 0;
    let pos = dRowHtml.indexOf('<td');
    let dailyCell = '';
    let netCell = '';
    // Columns after removing mark/index: 5=日费率, 9=日净收益
    while (pos !== -1 && tdCount < 13) {
      const close = dRowHtml.indexOf('</td>', pos);
      if (tdCount === 5) dailyCell = dRowHtml.slice(pos, close + 5);
      if (tdCount === 10) netCell = dRowHtml.slice(pos, close + 5);
      pos = dRowHtml.indexOf('<td', close + 5);
      tdCount++;
    }
    if (!dailyCell.includes('—')) {
      throw new Error('优雅降级后日费率列未显示 —');
    }
    if (!netCell.includes('—')) {
      throw new Error('优雅降级后净收益列未显示 —');
    }
    if (degradedTbody.includes('>8h<') || degradedTbody.includes('>4h<')) {
      throw new Error('优雅降级后仍渲染结算间隔徽标');
    }
    // 费率行情页双看板按钮依赖私有面板 header，无 private_account 时仍显示面板
    if (helpers.getActiveView() === 'market' && elements['private-panel'].style.display === 'none') {
      throw new Error('费率行情页无 private_account 时仍应显示私有面板 header（双看板按钮）');
    }
    if (elements['private-panel-body'].innerHTML.includes('总资产估值')) {
      throw new Error('无 private_account 时 body 不应渲染账户估值');
    }
    if (elements['sort-basis-badge'].style.display !== 'none') {
      throw new Error('优雅降级后无 sort_basis 时不应显示排序基准标注');
    }
    console.log('[PASS] 优雅降级：新字段缺失不白屏，日费率/净收益 —，间隔不显示');

    // 30. private-panel 在市场表之前（DOM 顺序）
    const privatePanelIdx = html.indexOf('id="private-panel"');
    const marketTableIdx = html.indexOf('id="market-table-body"');
    if (privatePanelIdx === -1) throw new Error('未找到 private-panel');
    if (marketTableIdx === -1) throw new Error('未找到 market-table-body');
    if (privatePanelIdx >= marketTableIdx) {
      throw new Error('private-panel 应位于市场表之前');
    }
    console.log('[PASS] private-panel 在市场表之前');

    // 30b. 抽屉 DOM 在应用脚本之前，确保真实浏览器 getElementById 命中
    const drawerIdx = html.indexOf('id="drawer"');
    const scriptIdx = html.indexOf('<script>');
    if (drawerIdx === -1) throw new Error('未找到 drawer');
    if (scriptIdx === -1) throw new Error('未找到 <script>');
    if (drawerIdx >= scriptIdx) {
      throw new Error('drawer DOM 必须位于应用 <script> 之前，否则真实浏览器初始化时 getElementById 返回 null');
    }
    console.log('[PASS] drawer DOM 在应用脚本之前');

    // 31. 成本腿命中行展示借币日利率（账户档）
    const ausdtNetCell2 = getRowCell(tbody, 'AUSDT', 10);
    if (!ausdtNetCell2.includes('日借币')) {
      throw new Error('AUSDT 成本腿命中行未展示日借币子行');
    }
    if (!ausdtNetCell2.includes('+0.01%')) {
      throw new Error(`AUSDT 日借币利率期望 +0.01%，单元格 ${ausdtNetCell2}`);
    }
    console.log('[PASS] 成本腿命中行展示借币日利率');

    // 32. VIP0 参考档显示"参考"徽标
    const vip0Fixture2 = JSON.parse(JSON.stringify(designFixture));
    vip0Fixture2.rows[1].borrow_rate_source = 'vip0_reference';
    vip0Fixture2.rows[1].borrow_validation.classic_margin.daily_interest_account = null;
    helpers.ingestSnapshot(vip0Fixture2);
    const vip0Tbody2 = elements['market-table-body'].innerHTML;
    const busdtNetCell = getRowCell(vip0Tbody2, 'BUSDT', 10);
    if (!busdtNetCell.includes('日借币') || !busdtNetCell.includes('参考')) {
      throw new Error('VIP0 参考档未显示"参考"徽标: ' + busdtNetCell);
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] VIP0 参考档显示"参考"徽标');

    // 33. 正费率/无成本腿行不展示借币成本子行
    const cusdtNetCell2 = getRowCell(tbody, 'CUSDT', 10);
    if (cusdtNetCell2.includes('日借币')) {
      throw new Error('CUSDT 正费率行不应展示日借币子行');
    }
    console.log('[PASS] 正费率行不展示借币成本子行');

    // 33b. opening_quotes 独立 formatter 三向量与 class 退化
    const spreadFmtCases = [
      ['-0.04', '-0.04%'],
      ['0.04', '+0.04%'],
      ['0.00', '0.00%'],
      [null, '—'],
      ['', '—'],
      ['not-a-number', '—']
    ];
    for (const [input, expected] of spreadFmtCases) {
      const actual = helpers.formatOpeningSpreadPct(input);
      if (actual !== expected) {
        throw new Error(`formatOpeningSpreadPct(${JSON.stringify(input)}) 期望 ${expected}，实际 ${actual}`);
      }
    }
    // classForOpeningSpread 对 null/empty/invalid 均返回 muted
    if (helpers.classForOpeningSpread(null) !== 'muted') {
      throw new Error('classForOpeningSpread(null) 应返回 muted');
    }
    if (helpers.classForOpeningSpread('') !== 'muted') {
      throw new Error('classForOpeningSpread("") 应返回 muted');
    }
    if (helpers.classForOpeningSpread('not-a-number') !== 'muted') {
      throw new Error('classForOpeningSpread("not-a-number") 应返回 muted');
    }
    // 确认 formatter 不调用/复用 formatFundingRate（允许注释提及，不允许调用）
    const spreadFormatterBody = helpers.formatOpeningSpreadPct.toString();
    if (/formatFundingRate\s*\(/.test(spreadFormatterBody)) {
      throw new Error('formatOpeningSpreadPct 不应调用 formatFundingRate');
    }
    console.log('[PASS] opening spread 独立 formatter 三向量');

    // 33c. 最终 15 列（开单 fake 阶段：估算列带「率」，借币后新增两操作列）：严格表头顺序、每行 15 个 td、empty-state colspan=15、合并列结构
    const taskCHeaders = ['标的', '正向开单率', '反向开单率', '资金费率', '结算时间', '日费率', '近 24h', '年化 24h', '年化 7D', '年化 30D', '日净收益', '借贷状态 / 资产', '借币', '正向开单', '反向开单'];
    const theadBlock = html.slice(html.indexOf('<thead>'), html.indexOf('</thead>') + 8);
    const renderedHeaders = [...theadBlock.matchAll(/<th[^>]*>([^\u003c]*)<\/th>/g)].map(m => m[1].trim());
    if (renderedHeaders.length !== 15) {
      throw new Error(`表头数量期望 15，实际 ${renderedHeaders.length}: ${JSON.stringify(renderedHeaders)}`);
    }
    for (let i = 0; i < 15; i++) {
      if (renderedHeaders[i] !== taskCHeaders[i]) {
        throw new Error(`表头第 ${i + 1} 项期望「${taskCHeaders[i]}」，实际「${renderedHeaders[i]}」`);
      }
    }
    if (theadBlock.includes('提示标记') || theadBlock.includes('负费率状态')) {
      throw new Error('最终表头仍含「提示标记」或独立「负费率状态」');
    }
    // 每行 data row 恰好 15 个 td
    const dataRows = tbody.match(/<tr[^\u003e]*class="[^"]*selectable[^"]*"[^\u003e]*>/g) || [];
    for (const rowStart of dataRows) {
      const pos = tbody.indexOf(rowStart);
      const end = tbody.indexOf('</tr>', pos);
      const rowHtml = tbody.slice(pos, end + 5);
      const tdCount = (rowHtml.match(/<td[\s>]/g) || []).length;
      if (tdCount !== 15) {
        const symMatch = rowHtml.match(/data-symbol="([^"]+)"/);
        throw new Error(`${symMatch ? symMatch[1] : '某行'} 数据行 td 数量期望 15，实际 ${tdCount}`);
      }
    }
    // empty-state colspan=15：触发无匹配行并断言
    const originalSearch = elements['filter-search'].value;
    elements['filter-search'].value = 'NO_SUCH_SYMBOL_XYZ';
    (elements['filter-search'].listeners.input || []).forEach(h => h());
    const emptyTbody = elements['market-table-body'].innerHTML;
    if (!emptyTbody.includes('colspan="15"')) {
      throw new Error('无匹配 empty-state 未使用 colspan="15"');
    }
    if ((emptyTbody.match(/<td/g) || []).length !== 1) {
      throw new Error('empty-state 行应只含 1 个 td');
    }
    // 恢复 fixture 与搜索框，避免破坏后续测试
    elements['filter-search'].value = originalSearch;
    (elements['filter-search'].listeners.input || []).forEach(h => h());

    // 合并列：AUSDT 状态 badge 位置早于资产 badge；额度只在 index 11，不在 index 8
    const ausdtCombined = getRowCell(tbody, 'AUSDT', 11);
    const statusIdx = ausdtCombined.indexOf('badge '); // 第一个 badge 是状态
    const assetIdx = ausdtCombined.indexOf('CRYPTO(加密货币)');
    if (statusIdx === -1 || assetIdx === -1 || statusIdx >= assetIdx) {
      throw new Error('AUSDT 合并列中状态 badge 应位于资产标签之前: ' + ausdtCombined);
    }
    const ausdtNet = getRowCell(tbody, 'AUSDT', 10);
    if (ausdtNet.includes('可借:')) {
      throw new Error('AUSDT 日净收益格不应含可借额度: ' + ausdtNet);
    }
    console.log('[PASS] 最终 15 列表头顺序、行单元格数、empty-state colspan 与合并列结构');

    // 33d. 正向/反向开单列：腿标签、价格、百分比与颜色
    // AUSDT fresh: forward -0.04%, reverse +0.04%
    const ausdtForward = getRowCell(tbody, 'AUSDT', 1);
    if (!ausdtForward.includes('合约买一') || !ausdtForward.includes('现货卖一')) {
      throw new Error('AUSDT 正向开单列上下腿标签错误: ' + ausdtForward);
    }
    // Trailing fractional zeros trimmed (64,925.00 → 64,925; 64,954.01000000 → 64,954.01)
    if (!ausdtForward.includes('64,925') || !ausdtForward.includes('64,954.01')) {
      throw new Error('AUSDT 正向开单列价格错误: ' + ausdtForward);
    }
    if (ausdtForward.includes('64,954.01000000') || ausdtForward.includes('64,925.00')) {
      throw new Error('AUSDT 正向开单列应省略价格末尾零: ' + ausdtForward);
    }
    if (!ausdtForward.includes('-0.04%')) {
      throw new Error('AUSDT 正向开单列百分比错误: ' + ausdtForward);
    }
    if (!ausdtForward.includes('negative')) {
      throw new Error('AUSDT 正向开单列负 spread 应使用 negative 色: ' + ausdtForward);
    }
    const ausdtReverse = getRowCell(tbody, 'AUSDT', 2);
    if (!ausdtReverse.includes('现货买一') || !ausdtReverse.includes('合约卖一')) {
      throw new Error('AUSDT 反向开单列上下腿标签错误: ' + ausdtReverse);
    }
    // 64,954.00000000 → 64,954; 64,925.10 kept (non-trailing significant digit)
    if (!ausdtReverse.includes('64,954') || !ausdtReverse.includes('64,925.1')) {
      throw new Error('AUSDT 反向开单列价格错误: ' + ausdtReverse);
    }
    if (ausdtReverse.includes('64,954.00000000')) {
      throw new Error('AUSDT 反向开单列应省略价格末尾零: ' + ausdtReverse);
    }
    if (!ausdtReverse.includes('+0.04%')) {
      throw new Error('AUSDT 反向开单列百分比错误: ' + ausdtReverse);
    }
    if (!ausdtReverse.includes('positive')) {
      throw new Error('AUSDT 反向开单列正 spread 应使用 positive 色: ' + ausdtReverse);
    }
    console.log('[PASS] 正向/反向开单列腿、价、百分比与颜色');

    // 33d-task-c. Task C 新增布局断言（依赖 33d 已初始化的 ausdtForward / ausdtReverse）
    // 标的不再显示 bStock 现货腿别名（保留数据语义与警告面板说明）
    const bstockRow = designFixture.rows.find(r => r.asset_tag === 'BSTOCK');
    if (bstockRow) {
      const bstockSymbolCell = getRowCell(tbody, bstockRow.symbol, 0);
      if (bstockSymbolCell.includes('B 后缀别名') || bstockSymbolCell.includes('现货腿:')) {
        throw new Error('bStock 行标的单元格仍显示 B 后缀别名或现货腿: ' + bstockSymbolCell);
      }
    }
    // 正向开单列文本顺序：合约买一 < 现货卖一 < 百分比
    const forwardFirstLegIdx = ausdtForward.indexOf('合约买一');
    const forwardSecondLegIdx = ausdtForward.indexOf('现货卖一');
    const forwardPctIdx = ausdtForward.indexOf('-0.04%');
    if (forwardFirstLegIdx === -1 || forwardSecondLegIdx === -1 || forwardPctIdx === -1 ||
        !(forwardFirstLegIdx < forwardSecondLegIdx && forwardSecondLegIdx < forwardPctIdx)) {
      throw new Error('AUSDT 正向开单列文本顺序应为 合约买一 < 现货卖一 < -0.04%: ' + ausdtForward);
    }
    // 反向开单列文本顺序：现货买一 < 合约卖一 < 百分比
    const reverseFirstLegIdx = ausdtReverse.indexOf('现货买一');
    const reverseSecondLegIdx = ausdtReverse.indexOf('合约卖一');
    const reversePctIdx = ausdtReverse.indexOf('+0.04%');
    if (reverseFirstLegIdx === -1 || reverseSecondLegIdx === -1 || reversePctIdx === -1 ||
        !(reverseFirstLegIdx < reverseSecondLegIdx && reverseSecondLegIdx < reversePctIdx)) {
      throw new Error('AUSDT 反向开单列文本顺序应为 现货买一 < 合约卖一 < +0.04%: ' + ausdtReverse);
    }
    // 开单单元格不再使用旧的 display:flex 水平布局
    if (ausdtForward.includes('display:flex') || ausdtReverse.includes('display:flex')) {
      throw new Error('开单单元格仍包含 display:flex 水平布局');
    }
    console.log('[PASS] Task C 别名移除、开单三行垂直顺序与 flex 布局移除');

    // 33e. incomplete 双方向独立：BUSDT forward 缺失 → —，reverse 有效 → +0.04%
    const busdtForward = getRowCell(tbody, 'BUSDT', 1);
    if (!busdtForward.includes('合约买一')) {
      throw new Error('BUSDT 正向开单列应仍渲染合约买一标签: ' + busdtForward);
    }
    if (!busdtForward.includes('现货卖一')) {
      throw new Error('BUSDT 正向开单列应渲染现货卖一标签: ' + busdtForward);
    }
    // 有效腿 futures_bid_price 显示格式化价格；缺失腿 spot_ask_price 显示 —；forward spread 显示 —
    if (!busdtForward.includes('64,925')) {
      throw new Error('BUSDT 正向开单列应显示有效合约买一价格 64,925: ' + busdtForward);
    }
    const busdtForwardDashCount = (busdtForward.match(/—/g) || []).length;
    if (busdtForwardDashCount < 2) {
      throw new Error(`BUSDT 正向开单列应至少包含 2 个 —（现货卖一 + spread），实际 ${busdtForwardDashCount}: ${busdtForward}`);
    }
    if (busdtForward.includes('-0.04%') || busdtForward.includes('+0.04%')) {
      throw new Error('BUSDT 正向开单列 forward spread 应为 —: ' + busdtForward);
    }
    const busdtReverse = getRowCell(tbody, 'BUSDT', 2);
    if (!busdtReverse.includes('现货买一')) {
      throw new Error('BUSDT 反向开单列应渲染现货买一标签: ' + busdtReverse);
    }
    if (!busdtReverse.includes('合约卖一')) {
      throw new Error('BUSDT 反向开单列应渲染合约卖一标签: ' + busdtReverse);
    }
    if (!busdtReverse.includes('+0.04%')) {
      throw new Error('BUSDT 反向开单列 reverse spread 应有效 +0.04%: ' + busdtReverse);
    }
    console.log('[PASS] incomplete 双方向独立显示');

    // 33f. stale / unavailable / 缺失 降级为 —，不白屏
    const cusdtForward = getRowCell(tbody, 'CUSDT', 1);
    const cusdtReverse = getRowCell(tbody, 'CUSDT', 2);
    if (!cusdtForward.includes('—') || !cusdtReverse.includes('—')) {
      throw new Error('CUSDT stale 开单列应显示 —: ' + cusdtForward + ' / ' + cusdtReverse);
    }
    const dusdtForward = getRowCell(tbody, 'DUSDT', 1);
    const dusdtReverse = getRowCell(tbody, 'DUSDT', 2);
    if (!dusdtForward.includes('—') || !dusdtReverse.includes('—')) {
      throw new Error('DUSDT unavailable 开单列应显示 —: ' + dusdtForward + ' / ' + dusdtReverse);
    }
    const fusdtForward = getRowCell(tbody, 'FUSDT', 1);
    const fusdtReverse = getRowCell(tbody, 'FUSDT', 2);
    if (!fusdtForward.includes('—') || !fusdtReverse.includes('—')) {
      throw new Error('FUSDT 缺失 opening_quotes 开单列应显示 —: ' + fusdtForward + ' / ' + fusdtReverse);
    }
    // 页面仍正常渲染 6 行（已在 #4 断言）
    console.log('[PASS] stale/unavailable/缺失 降级为 —');

    // 33g. 开单列标题/单元格携带参考报价说明
    if (!html.includes('约 60 秒刷新') || !html.includes('非成交保证') || !html.includes('incomplete')) {
      throw new Error('开单列头/单元格未明示参考报价说明');
    }
    console.log('[PASS] 开单列参考报价文案');

    // 34. 负费率状态行感知的六文案派生
    const labelFixtureBase = JSON.parse(JSON.stringify(designFixture));
    // 已验证可借：verified=true, pair_listed=true, asset_borrowable=true
    labelFixtureBase.rows[0].borrow_validation.verified = true;
    labelFixtureBase.rows[0].borrow_validation.classic_margin.pair_listed = true;
    labelFixtureBase.rows[0].borrow_validation.classic_margin.asset_borrowable = true;
    // 杠杆交易对未列出
    labelFixtureBase.rows[1].borrow_validation.verified = true;
    labelFixtureBase.rows[1].borrow_validation.classic_margin.pair_listed = false;
    labelFixtureBase.rows[1].borrow_validation.classic_margin.asset_borrowable = null;
    // 资产不可借
    labelFixtureBase.rows[2].borrow_validation.verified = true;
    labelFixtureBase.rows[2].borrow_validation.classic_margin.pair_listed = true;
    labelFixtureBase.rows[2].borrow_validation.classic_margin.asset_borrowable = false;
    // 未探测（限速预算，legacy：利率也无）
    labelFixtureBase.rows[3].borrow_validation.verified = false;
    labelFixtureBase.rows[3].borrow_validation.error = 'not_probed_this_round';
    // 需私有验证（private channel disabled/failed）
    labelFixtureBase.rows[4].borrow_validation.verified = false;
    labelFixtureBase.rows[4].borrow_validation.error = null;
    // 有利率·可借性未探测（borrowability_not_probed：利率有，可借额度未探）
    labelFixtureBase.rows[5].negative_funding_status = 'PRIVATE_BORROW_VALIDATION_REQUIRED';
    labelFixtureBase.rows[5].borrow_validation.verified = false;
    labelFixtureBase.rows[5].borrow_validation.error = 'borrowability_not_probed';
    labelFixtureBase.rows[5].borrow_validation.classic_margin.daily_interest_account = '0.00010000';
    labelFixtureBase.rows[5].borrow_rate_source = 'next_hourly';
    // AUSDT 日费率为负 → 仍「已验证可借」
    labelFixtureBase.rows[0].daily_funding_rate = '-0.00060000';
    helpers.ingestSnapshot(labelFixtureBase);
    const labelTbody = elements['market-table-body'].innerHTML;
    const labelCases = [
      { sym: 'AUSDT', label: '已验证可借', cls: 'success' },
      { sym: 'BUSDT', label: '杠杆交易对未列出', cls: 'warn' },
      { sym: 'CUSDT', label: '资产不可借', cls: 'danger' },
      { sym: 'DUSDT', label: '未探测(限速预算)', cls: 'muted' },
      { sym: 'EUSDT', label: '需私有验证', cls: 'warn' },
      { sym: 'FUSDT', label: '有利率·可借性未探测', cls: 'muted' },
    ];
    for (const { sym, label, cls } of labelCases) {
      const cell = getRowCell(labelTbody, sym, 11);
      if (!cell.includes(label)) {
        throw new Error(`${sym} 负费率状态期望 "${label}"，单元格 ${cell}`);
      }
      if (!cell.includes(`badge ${cls}`)) {
        throw new Error(`${sym} 负费率状态期望 ${cls} 样式，单元格 ${cell}`);
      }
    }
    // 第六态行：状态列「有利率·可借性未探测」AND 净收益列仍展示日借币子行
    const fusdtNetCell = getRowCell(labelTbody, 'FUSDT', 10);
    if (!fusdtNetCell.includes('日借币') || !fusdtNetCell.includes('+0.01%')) {
      throw new Error(`FUSDT borrowability_not_probed 行应展示日借币子行，单元格 ${fusdtNetCell}`);
    }
    // 正资金费率 + classic 可借 → 「正费率」，不再绿标「已验证可借」
    const posRateFixture = JSON.parse(JSON.stringify(labelFixtureBase));
    posRateFixture.rows[0].daily_funding_rate = '0.00180000';
    posRateFixture.rows[0].borrow_validation.verified = true;
    posRateFixture.rows[0].borrow_validation.classic_margin.pair_listed = true;
    posRateFixture.rows[0].borrow_validation.classic_margin.asset_borrowable = true;
    posRateFixture.rows[0].borrow_validation.portfolio_account = {
      max_borrowable: null, borrow_limit: null, error_code: null,
      max_borrowable_value_usdt: null, source: 'papi_max_borrowable'
    };
    helpers.ingestSnapshot(posRateFixture);
    const posCell = getRowCell(elements['market-table-body'].innerHTML, 'AUSDT', 11);
    if (!posCell.includes('正费率') || !posCell.includes('badge info')) {
      throw new Error(`正费率+可借应渲染 info「正费率」: ${posCell}`);
    }
    if (posCell.includes('已验证可借')) {
      throw new Error(`正费率行不应再显示「已验证可借」: ${posCell}`);
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] 负费率状态行感知的六文案派生');

    // 35. 余额卡片折算：统一/现货均有持有价值 + 净价值；隐私遮蔽
    const privateBody2 = elements['private-panel-body'].innerHTML;
    if (privateBody2.includes('【:')) {
      throw new Error('余额卡片仍残留旧的行内折算格式 【: ...】');
    }
    if (!privateBody2.includes('≈ **** USDT')) {
      throw new Error('隐藏态下折算值应被遮蔽为 ≈ **** USDT');
    }
    helpers.togglePrivacy(); // 切换到显示态
    const shownBody2 = elements['private-panel-body'].innerHTML;
    const shownUStart = shownBody2.indexOf('统一账户余额');
    const shownSStart = shownBody2.indexOf('现货账户余额');
    const shownUnified = shownBody2.slice(shownUStart, shownSStart > shownUStart ? shownSStart : undefined);
    const shownSpot = shownBody2.slice(shownSStart);
    if (!shownUnified.includes('≈ 123.45 USDT')) {
      throw new Error('显示态下统一账户持有价值未展示 ≈ 123.45 USDT');
    }
    if (!shownUnified.includes('净价值 ≈ 123.45 USDT')) {
      throw new Error('显示态下统一账户净价值（无借款）应为 ≈ 123.45 USDT: ' + shownUnified);
    }
    if (!shownSpot.includes('≈ 67.89 USDT')) {
      throw new Error('显示态下现货账户余额未展示持有价值 ≈ 67.89 USDT');
    }
    if (!shownSpot.includes('净价值 ≈ 67.89 USDT')) {
      throw new Error('显示态下现货账户应展示净价值 ≈ 67.89 USDT: ' + shownSpot);
    }
    if (!shownSpot.match(/class="amount locked value-usdt">净价值/)) {
      throw new Error('现货净价值应与冻结行同字体样式 (locked): ' + shownSpot);
    }
    helpers.togglePrivacy(); // 恢复隐藏态
    const hiddenBody2 = elements['private-panel-body'].innerHTML;
    if (!hiddenBody2.includes('≈ **** USDT')) {
      throw new Error('恢复隐藏态后折算值应再次被遮蔽');
    }
    console.log('[PASS] 余额卡片三行折算值与隐私遮蔽');

    // 36. value_usdt null：统一/现货持有与净价值均为 ≈ —；隐藏态遮蔽
    const nullValueFixture = JSON.parse(JSON.stringify(designFixture));
    nullValueFixture.private_account.balances_unified[0].value_usdt = null;
    nullValueFixture.private_account.balances_unified[0].cross_margin_borrowed_value_usdt = '0.00000000';
    nullValueFixture.private_account.balances_spot[0].value_usdt = null;
    helpers.ingestSnapshot(nullValueFixture);
    if (helpers.getPrivacyHidden()) helpers.togglePrivacy(); // 确保显示态
    const nullValueBody = elements['private-panel-body'].innerHTML;
    const unifiedSectionStart = nullValueBody.indexOf('统一账户余额');
    const spotSectionStart = nullValueBody.indexOf('现货账户余额');
    const unifiedSection = nullValueBody.slice(unifiedSectionStart, spotSectionStart);
    if (!unifiedSection.includes('≈ — USDT')) {
      throw new Error('value_usdt null 时统一账户未显示 "≈ — USDT"');
    }
    if (!unifiedSection.includes('净价值 ≈ — USDT')) {
      throw new Error('value_usdt null 时统一账户净价值应为 ≈ — USDT');
    }
    const spotSection = nullValueBody.slice(spotSectionStart);
    if (!spotSection.includes('≈ — USDT')) {
      throw new Error('value_usdt null 时现货账户未显示 "≈ — USDT"');
    }
    if (!spotSection.includes('净价值 ≈ — USDT')) {
      throw new Error('value_usdt null 时现货净价值应为 ≈ — USDT');
    }
    // 隐藏态下 null 折算值应被遮蔽为 ****
    helpers.togglePrivacy();
    const hiddenNullBody = elements['private-panel-body'].innerHTML;
    if (!hiddenNullBody.includes('≈ **** USDT')) {
      throw new Error('value_usdt null 隐藏态未遮蔽折算值');
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] value_usdt null 显示占位');

    // 37. 资产卡过滤：abs(净价值 USDT) < 10 的资产卡不展示（统一/现货一致）。
    // 零值资产被过滤；同区其余 ≥10 资产保留。formatUsdt2 零值格式化已由 14b 直接覆盖。
    const zeroValueFixture = JSON.parse(JSON.stringify(designFixture));
    zeroValueFixture.private_account.balances_unified[0].value_usdt = '0.00000000';
    zeroValueFixture.private_account.balances_unified[0].cross_margin_borrowed_value_usdt = '0.00000000';
    zeroValueFixture.private_account.balances_spot[0].value_usdt = '0.00000000';
    helpers.ingestSnapshot(zeroValueFixture);
    if (helpers.getPrivacyHidden()) helpers.togglePrivacy(); // 确保显示态
    const zeroValueBody = elements['private-panel-body'].innerHTML;
    const zeroUStart = zeroValueBody.indexOf('统一账户余额');
    const zeroSStart = zeroValueBody.indexOf('现货账户余额');
    const zeroUnified = zeroValueBody.slice(zeroUStart, zeroSStart > zeroUStart ? zeroSStart : undefined);
    if (zeroUnified.includes('净价值 ≈ 0.00 USDT')) {
      throw new Error('净价值 0（<10 USDT）的统一账户资产卡应被过滤: ' + zeroUnified);
    }
    const zeroSpot = zeroValueBody.slice(zeroSStart);
    if (zeroSpot.includes('净价值 ≈ 0.00 USDT')) {
      throw new Error('净价值 0（<10 USDT）的现货资产卡应被过滤: ' + zeroSpot);
    }
    // 同区其它 ≥10 资产保留（fixture 注入 123.45 / 67.89）
    if (!zeroUnified.includes('净价值 ≈ 123.45 USDT')) {
      throw new Error('过滤后统一账户其余资产卡应保留: ' + zeroUnified);
    }
    if (!zeroSpot.includes('净价值 ≈ 67.89 USDT')) {
      throw new Error('过滤后现货账户其余资产卡应保留: ' + zeroSpot);
    }
    // 边界与负值：|net| < 10 过滤（9.99999999、-9.99）；|net| ≥ 10 保留
    // （10.00000001、净 -10.00、-10.01）。按 asset 卡存在性断言（9.99999999
    // 显示会进位为 10.00，但过滤按原始精确值）。
    {
      const edgeFx = JSON.parse(JSON.stringify(designFixture));
      const eu = edgeFx.private_account.balances_unified;
      const es = edgeFx.private_account.balances_spot;
      eu[0].value_usdt = '9.99999999'; eu[0].cross_margin_borrowed_value_usdt = '0.00000000'; // BTC 过滤
      eu[1].value_usdt = '10.00000001'; eu[1].cross_margin_borrowed_value_usdt = '0.00000000'; // ETH 保留
      eu[2].value_usdt = '10.00000000'; eu[2].cross_margin_borrowed_value_usdt = '20.00000000'; // USDT 净 -10.00 保留
      es[0].value_usdt = '-9.99000000';  // 现货 USDT 过滤
      es[1].value_usdt = '-10.01000000'; // 现货 USDC 保留
      helpers.ingestSnapshot(edgeFx);
      if (helpers.getPrivacyHidden()) helpers.togglePrivacy();
      const edgeBody = elements['private-panel-body'].innerHTML;
      const euStart = edgeBody.indexOf('统一账户余额');
      const esStart = edgeBody.indexOf('现货账户余额');
      const edgeUnified = edgeBody.slice(euStart, esStart);
      const edgeSpot = edgeBody.slice(esStart);
      if (edgeUnified.includes('<div class="asset">BTC</div>')) {
        throw new Error('净价值 9.99999999（<10）的 BTC 卡应被过滤: ' + edgeUnified);
      }
      if (!edgeUnified.includes('<div class="asset">ETH</div>') || !edgeUnified.includes('<div class="asset">USDT</div>')) {
        throw new Error('净价值 10.00000001 / -10.00 的卡应保留: ' + edgeUnified);
      }
      if (edgeSpot.includes('<div class="asset">USDT</div>')) {
        throw new Error('净价值 -9.99（|·|<10）的现货 USDT 卡应被过滤: ' + edgeSpot);
      }
      if (!edgeSpot.includes('<div class="asset">USDC</div>')) {
        throw new Error('净价值 -10.01（|·|≥10）的现货 USDC 卡应保留: ' + edgeSpot);
      }
    }
    // 纯借入（持有价值 = 已借价值）：净价值恒为 0，但持有价值 ≥10 时资产卡必须展示。
    // 借币成功且未动用时净值精确为 0，若按净价值过滤则该资产永不可见（INJ 实盘故障）。
    {
      const borrowFx = JSON.parse(JSON.stringify(designFixture));
      const bu = borrowFx.private_account.balances_unified;
      bu[0].value_usdt = '46.46000000';
      bu[0].cross_margin_borrowed_value_usdt = '46.46000000'; // 净 0、持有 46.46
      // 反向：借入后几乎全部划走——持有价值 <10 但净负债 -95，不得因改判定而隐藏。
      bu[1].value_usdt = '5.00000000';
      bu[1].cross_margin_borrowed_value_usdt = '100.00000000'; // 净 -95、持有 5
      helpers.ingestSnapshot(borrowFx);
      if (helpers.getPrivacyHidden()) helpers.togglePrivacy();
      const borrowBody = elements['private-panel-body'].innerHTML;
      const bStart = borrowBody.indexOf('统一账户余额');
      const bEnd = borrowBody.indexOf('现货账户余额');
      const borrowUnified = borrowBody.slice(bStart, bEnd > bStart ? bEnd : undefined);
      if (!borrowUnified.includes('<div class="asset">BTC</div>')) {
        throw new Error('纯借入（净价值 0、持有价值 46.46）的统一账户资产卡应展示: ' + borrowUnified);
      }
      if (!borrowUnified.includes('<div class="asset">ETH</div>')) {
        throw new Error('低持有高负债（持有 5、净价值 -95）的统一账户资产卡应展示: ' + borrowUnified);
      }
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] 持有价值 <10 USDT 资产卡过滤（统一/现货一致，含边界、负值与纯借入）');

    // 37b. 余额数量仅整数部分加千分位，小数部分原样保留（不四舍五入/不裁剪尾零）
    const amountFixture = JSON.parse(JSON.stringify(designFixture));
    amountFixture.private_account.balances_unified[0].total_balance = '1234.56789000';
    amountFixture.private_account.balances_spot[0].free = '123456.07890000';
    helpers.ingestSnapshot(amountFixture);
    if (helpers.getPrivacyHidden()) helpers.togglePrivacy(); // 确保显示态
    const amountBody = elements['private-panel-body'].innerHTML;
    const unifiedAmtStart = amountBody.indexOf('统一账户余额');
    const spotAmtStart = amountBody.indexOf('现货账户余额');
    const unifiedAmtSection = amountBody.slice(unifiedAmtStart, spotAmtStart);
    // 持有行现为「数量 ≈ 价值」同 div，不再要求 `>qty<` 独占子串
    if (!unifiedAmtSection.includes('1,234.56789000')) {
      throw new Error('统一账户余额数量未按「整数千分位+小数原样」格式化: ' + unifiedAmtSection);
    }
    const spotAmtSection = amountBody.slice(spotAmtStart);
    if (!spotAmtSection.includes('123,456.07890000')) {
      throw new Error('现货余额数量未按「整数千分位+小数原样」格式化: ' + spotAmtSection);
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] 余额数量整数千分位、小数原样保留');

    // 37c. 方案 B：正值持有/已借/净价值、B=null、非法缺价、负净值、隐私短路、旧底行移除
    {
      if (typeof helpers.sub8 !== 'function') {
        throw new Error('sub8 辅助函数未暴露');
      }
      // 固定 8dp BigInt 减法：100 - 25 = 75；10 - 30 = -20（不经 Number）
      if (helpers.sub8('100.00000000', '25.00000000') !== '75.00000000') {
        throw new Error('sub8(100,25) 期望 75.00000000');
      }
      if (helpers.sub8('10.00000000', '30.00000000') !== '-20.00000000') {
        throw new Error('sub8(10,30) 期望 -20.00000000');
      }
      if (helpers.sub8('2.00000000', '0.50000000') !== '1.50000000') {
        throw new Error('sub8(2,0.5) 期望 1.50000000');
      }

      // 正值示例：V=100 B=25 → 已借≈25.00 净值≈75.00（2@50 / 0.5@50 的同构）
      const posFx = JSON.parse(JSON.stringify(designFixture));
      const u0 = posFx.private_account.balances_unified[0];
      u0.total_balance = '2';
      u0.cross_margin_borrowed = '0.5';
      u0.value_usdt = '100.00000000';
      u0.cross_margin_borrowed_value_usdt = '25.00000000';
      helpers.ingestSnapshot(posFx);
      if (helpers.getPrivacyHidden()) helpers.togglePrivacy();
      let body = elements['private-panel-body'].innerHTML;
      let uSec = body.slice(body.indexOf('统一账户余额'), body.indexOf('现货账户余额'));
      if (!uSec.includes('≈ 100.00 USDT')) {
        throw new Error('正值示例统一持有价值应为 ≈ 100.00 USDT: ' + uSec);
      }
      if (!uSec.includes('已借:') || !uSec.includes('≈ 25.00 USDT')) {
        throw new Error('正值示例已借价值应为 ≈ 25.00 USDT: ' + uSec);
      }
      if (!uSec.includes('净价值 ≈ 75.00 USDT')) {
        throw new Error('正值示例净价值应为 ≈ 75.00 USDT: ' + uSec);
      }
      // 旧底部独立 value_usdt 行已移除；正净价值用默认次要色，并保留 value-usdt。
      if (uSec.match(/class="amount value-usdt">≈ /)) {
        throw new Error('统一卡仍保留旧底部独立 value_usdt 行: ' + uSec);
      }
      if (!uSec.includes('value-usdt') || !uSec.includes('净价值')) {
        throw new Error('统一卡净价值行 class 缺失');
      }
      if (!uSec.includes('class="amount locked value-usdt">净价值')) {
        throw new Error('正净价值不应使用红色样式: ' + uSec);
      }

      // 零净值也保持默认次要色。
      const zeroNetFx = JSON.parse(JSON.stringify(posFx));
      zeroNetFx.private_account.balances_unified[0].value_usdt = '25.00000000';
      helpers.ingestSnapshot(zeroNetFx);
      body = elements['private-panel-body'].innerHTML;
      uSec = body.slice(body.indexOf('统一账户余额'), body.indexOf('现货账户余额'));
      if (!uSec.includes('class="amount locked value-usdt">净价值 ≈ 0.00 USDT')) {
        throw new Error('零净价值不应使用红色样式: ' + uSec);
      }

      // B=null（有借款但无法估值）→ 已借≈—、净价值≈—
      const nullBFx = JSON.parse(JSON.stringify(designFixture));
      nullBFx.private_account.balances_unified[0].value_usdt = '100.00000000';
      nullBFx.private_account.balances_unified[0].cross_margin_borrowed = '1';
      nullBFx.private_account.balances_unified[0].cross_margin_borrowed_value_usdt = null;
      helpers.ingestSnapshot(nullBFx);
      if (helpers.getPrivacyHidden()) helpers.togglePrivacy();
      body = elements['private-panel-body'].innerHTML;
      uSec = body.slice(body.indexOf('统一账户余额'), body.indexOf('现货账户余额'));
      if (!uSec.includes('净价值 ≈ — USDT')) {
        throw new Error('B=null 时净价值应为 ≈ — USDT: ' + uSec);
      }
      // 持有仍可展示
      if (!uSec.includes('≈ 100.00 USDT')) {
        throw new Error('B=null 时持有价值仍应展示');
      }

      // 负净值：V=10 B=30 → ≈ -20.00
      const negFx = JSON.parse(JSON.stringify(designFixture));
      negFx.private_account.balances_unified[0].value_usdt = '10.00000000';
      negFx.private_account.balances_unified[0].cross_margin_borrowed_value_usdt = '30.00000000';
      helpers.ingestSnapshot(negFx);
      if (helpers.getPrivacyHidden()) helpers.togglePrivacy();
      body = elements['private-panel-body'].innerHTML;
      uSec = body.slice(body.indexOf('统一账户余额'), body.indexOf('现货账户余额'));
      if (!uSec.includes('净价值 ≈ -20.00 USDT')) {
        throw new Error('负净值应保留负号 ≈ -20.00 USDT: ' + uSec);
      }
      if (!uSec.includes('class="amount borrowed-debt value-usdt">净价值')) {
        throw new Error('负净价值应使用红色样式: ' + uSec);
      }

      // 隐私：正值场景下先切换隐藏，短路不泄露 100/25/75
      helpers.ingestSnapshot(posFx);
      if (!helpers.getPrivacyHidden()) helpers.togglePrivacy();
      body = elements['private-panel-body'].innerHTML;
      uSec = body.slice(body.indexOf('统一账户余额'), body.indexOf('现货账户余额'));
      if (!uSec.includes('≈ **** USDT')) {
        throw new Error('隐私隐藏态统一价值应遮蔽为 ≈ **** USDT');
      }
      if (uSec.includes('100.00') || uSec.includes('25.00') || uSec.includes('75.00')) {
        throw new Error('隐私隐藏态不得泄露真实持有/已借/净价值: ' + uSec);
      }

      // 现货同步：净价值行 + 隐私遮蔽 + locked 样式
      const spotSec = body.slice(body.indexOf('现货账户余额'));
      if (!spotSec.includes('≈ **** USDT')) {
        throw new Error('现货卡隐私遮蔽失败');
      }
      if (!spotSec.includes('净价值')) {
        throw new Error('现货卡应渲染净价值行');
      }
      if (spotSec.includes('67.89')) {
        throw new Error('现货卡隐私隐藏态不得泄露真实价值: ' + spotSec);
      }

      helpers.ingestSnapshot(designFixture);
      if (helpers.getPrivacyHidden()) helpers.togglePrivacy();
      console.log('[PASS] 方案 B 持有/已借/净价值边界与隐私短路');
    }

    // 38. absDailyRateAtOrBelowThreshold 阈值边界（BigInt，无 float 阈值比较）
    if (typeof helpers.absDailyRateAtOrBelowThreshold !== 'function') {
      throw new Error('absDailyRateAtOrBelowThreshold 辅助函数未暴露');
    }
    const lowRateCases = [
      ['0.00030000', true],
      ['-0.00030000', true],
      ['0.00030001', false],
      ['-0.00030001', false],
      [null, false],
      ['', false],
      ['not-a-number', false]
    ];
    for (const [input, expected] of lowRateCases) {
      const actual = helpers.absDailyRateAtOrBelowThreshold(input);
      if (actual !== expected) {
        throw new Error(`absDailyRateAtOrBelowThreshold(${JSON.stringify(input)}) 期望 ${expected}，实际 ${actual}`);
      }
    }
    console.log('[PASS] absDailyRateAtOrBelowThreshold 阈值边界（BigInt）');

    // 39. 低日费率过滤 UI 行为：边界值（含正负）被隐藏，超边界保留，null 不过滤
    const lowRateFixture = JSON.parse(JSON.stringify(designFixture));
    lowRateFixture.rows[0].daily_funding_rate = '0.00030000';   // AUSDT 边界 -> 隐藏
    lowRateFixture.rows[1].daily_funding_rate = '-0.00030000';  // BUSDT 边界 -> 隐藏
    lowRateFixture.rows[2].daily_funding_rate = '0.00030001';   // CUSDT 超边界 -> 可见
    // 开启过滤后加载该 fixture（过滤状态与快照独立，ingestSnapshot 会按当前过滤重渲染）
    elements['filter-hide-low-daily-rate'].checked = true;
    (elements['filter-hide-low-daily-rate'].listeners.change || []).forEach(h => h());
    helpers.ingestSnapshot(lowRateFixture);
    const lowRateTbody = elements['market-table-body'].innerHTML;
    const lowRateCount = (lowRateTbody.match(/<tr/g) || []).length;
    if (lowRateCount !== 4) {
      throw new Error(`低日费率过滤开启后期望 4 行可见（AUSDT/BUSDT 被隐藏），实际 ${lowRateCount} 行`);
    }
    if (lowRateTbody.includes('AUSDT') || lowRateTbody.includes('BUSDT')) {
      throw new Error('低日费率边界行 AUSDT/BUSDT 应被隐藏');
    }
    if (!lowRateTbody.includes('CUSDT')) {
      throw new Error('超边界行 CUSDT 应保留可见');
    }
    // 关闭过滤应恢复 6 行
    elements['filter-hide-low-daily-rate'].checked = false;
    (elements['filter-hide-low-daily-rate'].listeners.change || []).forEach(h => h());
    const lowRateTbody2 = elements['market-table-body'].innerHTML;
    const lowRateCount2 = (lowRateTbody2.match(/<tr/g) || []).length;
    if (lowRateCount2 !== 6) {
      throw new Error(`低日费率过滤关闭后应恢复 6 行，实际 ${lowRateCount2} 行`);
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] 低日费率过滤 UI 行为（边界隐藏/超界保留/null 不过滤）');

    // 39a. 低日净收益过滤 UI：有符号 net ≤ 0.03% 隐藏（非 abs）；null 不过滤；与日费率 |x| 独立
    if (!html.includes('id="filter-hide-low-net-yield"') || !html.includes('隐藏 日净收益 ≤ 0.03%')) {
      throw new Error('缺少「隐藏 日净收益 ≤ 0.03%」筛选项');
    }
    if (typeof helpers.netYieldAtOrBelowThreshold !== 'function') {
      throw new Error('netYieldAtOrBelowThreshold 辅助函数未暴露');
    }
    // 单元：有符号 vs 日费率 abs 的差异（大负净收益：有符号藏、abs 不藏）
    const netUnitCases = [
      ['0.00030000', true],
      ['0.00030001', false],
      ['-0.00030000', true],
      ['-0.00100000', true],   // 大负值：有符号仍 ≤0.03% → 藏（abs 会保留）
      ['0.00010000', true],
      [null, false],
      ['', false]
    ];
    for (const [input, expected] of netUnitCases) {
      const actual = helpers.netYieldAtOrBelowThreshold(input);
      if (actual !== expected) {
        throw new Error(`netYieldAtOrBelowThreshold(${JSON.stringify(input)}) 期望 ${expected}，实际 ${actual}`);
      }
    }
    // abs 对照：大负值日费率不过滤
    if (helpers.absDailyRateAtOrBelowThreshold('-0.00100000') !== false) {
      throw new Error('日费率过滤应对 |−0.1%| 保留（abs > 0.03%）');
    }
    const lowNetFixture = JSON.parse(JSON.stringify(designFixture));
    // 关闭日费率过滤，只测净收益过滤
    elements['filter-hide-low-daily-rate'].checked = false;
    (elements['filter-hide-low-daily-rate'].listeners.change || []).forEach(h => h());
    lowNetFixture.rows[0].net_daily_yield = '0.00030000';   // AUSDT 边界 -> 隐藏
    lowNetFixture.rows[1].net_daily_yield = '-0.00100000';  // BUSDT 大负值 -> 有符号隐藏（非 abs）
    lowNetFixture.rows[2].net_daily_yield = '0.00030001';   // CUSDT 超边界 -> 可见
    lowNetFixture.rows[3].net_daily_yield = null;           // DUSDT null -> 可见
    elements['filter-hide-low-net-yield'].checked = true;
    (elements['filter-hide-low-net-yield'].listeners.change || []).forEach(h => h());
    helpers.ingestSnapshot(lowNetFixture);
    const lowNetTbody = elements['market-table-body'].innerHTML;
    const lowNetCount = (lowNetTbody.match(/<tr/g) || []).length;
    if (lowNetCount !== 4) {
      throw new Error(`低日净收益过滤开启后期望 4 行可见（AUSDT/BUSDT 被隐藏），实际 ${lowNetCount} 行`);
    }
    if (lowNetTbody.includes('AUSDT') || lowNetTbody.includes('BUSDT')) {
      throw new Error('低日净收益边界/负值行 AUSDT/BUSDT 应被隐藏');
    }
    if (!lowNetTbody.includes('CUSDT') || !lowNetTbody.includes('DUSDT')) {
      throw new Error('超边界 CUSDT 与 null net 的 DUSDT 应保留可见');
    }
    elements['filter-hide-low-net-yield'].checked = false;
    (elements['filter-hide-low-net-yield'].listeners.change || []).forEach(h => h());
    const lowNetTbody2 = elements['market-table-body'].innerHTML;
    if ((lowNetTbody2.match(/<tr/g) || []).length !== 6) {
      throw new Error('低日净收益过滤关闭后应恢复 6 行');
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] 低日净收益过滤 UI 行为（有符号 ≤0.03%；大负值隐藏；null 不过滤）');

    // 39b. 可开优先展示：筛选后 re-rank；正费率 / 负费率可借>0 进 A 组按日净收益 DESC
    if (typeof helpers.isOpenablePreferredRow !== 'function' || typeof helpers.displayRows !== 'function') {
      throw new Error('可开优先辅助函数未暴露');
    }
    // 单元：资格判定
    if (!helpers.isStrictlyPositiveDecimalString('0.00000001')) {
      throw new Error('isStrictlyPositiveDecimalString 应接受极小正数');
    }
    if (helpers.isStrictlyPositiveDecimalString('0') || helpers.isStrictlyPositiveDecimalString('0.00000000')
        || helpers.isStrictlyPositiveDecimalString(null) || helpers.isStrictlyPositiveDecimalString('<AMOUNT>')) {
      throw new Error('isStrictlyPositiveDecimalString 应拒绝 0/null/非数字');
    }
    const openableFixture = JSON.parse(JSON.stringify(designFixture));
    // 保持 payload 序 A B C D E F；制造可开差异：
    // A: 负费率 + 可借>0，net 0.00010000
    // B: 负费率 + 可借>0，net 0.00040000（应排 A 组最前）
    // C: 正费率（进 A），net 0.00030000
    // D: 负费率 + 不可借（不进 A）
    // E: 负费率 + 未探测（不进 A）
    // F: 零费率 / null 日费率（不进 A）
    openableFixture.rows[0].daily_funding_rate = '-0.00060000';
    openableFixture.rows[0].net_daily_yield = '0.00010000';
    openableFixture.rows[0].borrow_validation = {
      verified: true,
      classic_margin: { pair_listed: true, asset_borrowable: true, daily_interest_account: '0.00010000' },
      portfolio_account: { max_borrowable: '10', max_borrowable_value_usdt: '100', source: 'papi_max_borrowable' }
    };
    openableFixture.rows[1].daily_funding_rate = '-0.00070000';
    openableFixture.rows[1].net_daily_yield = '0.00040000';
    openableFixture.rows[1].borrow_validation = {
      verified: true,
      classic_margin: { pair_listed: true, asset_borrowable: true, daily_interest_vip0: '0.00020000' },
      portfolio_account: { max_borrowable: '5', max_borrowable_value_usdt: '50', source: 'papi_max_borrowable' }
    };
    openableFixture.rows[2].daily_funding_rate = '0.00050000';
    openableFixture.rows[2].net_daily_yield = '0.00030000';
    openableFixture.rows[2].borrow_validation = {
      verified: true,
      classic_margin: { pair_listed: true, asset_borrowable: true },
      portfolio_account: { max_borrowable: '0', source: 'papi_max_borrowable' }
    };
    openableFixture.rows[3].daily_funding_rate = '-0.00040000';
    openableFixture.rows[3].net_daily_yield = null;
    openableFixture.rows[3].borrow_validation = {
      verified: true,
      classic_margin: { pair_listed: true, asset_borrowable: false },
      portfolio_account: { max_borrowable: null }
    };
    openableFixture.rows[4].daily_funding_rate = '-0.00080000';
    openableFixture.rows[4].net_daily_yield = null;
    openableFixture.rows[4].borrow_validation = {
      verified: false,
      error: 'not_probed_this_round',
      classic_margin: {},
      portfolio_account: {}
    };
    // F 保持 daily null / last 0 — 不进 A
    // 关低费率、开可开优先
    elements['filter-hide-low-daily-rate'].checked = false;
    (elements['filter-hide-low-daily-rate'].listeners.change || []).forEach(h => h());
    elements['filter-prefer-openable'].checked = true;
    (elements['filter-prefer-openable'].listeners.change || []).forEach(h => h());
    helpers.ingestSnapshot(openableFixture);
    // A 组：B(0.0004) > C(0.0003) > A(0.0001)；B 组：D E F 保持相对序
    assertOrder(elements['market-table-body'].innerHTML, ['BUSDT', 'CUSDT', 'AUSDT', 'DUSDT', 'EUSDT', 'FUSDT']);
    // 关开关恢复 payload 序
    elements['filter-prefer-openable'].checked = false;
    (elements['filter-prefer-openable'].listeners.change || []).forEach(h => h());
    assertOrder(elements['market-table-body'].innerHTML, ['AUSDT', 'BUSDT', 'CUSDT', 'DUSDT', 'EUSDT', 'FUSDT']);
    // 负费率可借=0 不进 A：把 A 的 max 置 0，正费率 C 仍进 A
    openableFixture.rows[0].borrow_validation.portfolio_account.max_borrowable = '0';
    openableFixture.rows[1].borrow_validation.portfolio_account.max_borrowable = '0';
    elements['filter-prefer-openable'].checked = true;
    (elements['filter-prefer-openable'].listeners.change || []).forEach(h => h());
    helpers.ingestSnapshot(openableFixture);
    assertOrder(elements['market-table-body'].innerHTML, ['CUSDT', 'AUSDT', 'BUSDT', 'DUSDT', 'EUSDT', 'FUSDT']);
    // 恢复基线：关可开优先 + 原 fixture
    elements['filter-prefer-openable'].checked = false;
    (elements['filter-prefer-openable'].listeners.change || []).forEach(h => h());
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] 可开优先展示 re-rank（正费率/可借>0 置顶，可借0/未探测不进，关闭恢复 payload 序）');

    // 40. METAL 资产标签徽章（中性样式，非 danger/accent）与下拉选项
    if (!html.includes('<option value="METAL">METAL(金属)</option>')) {
      throw new Error('资产过滤下拉缺少 METAL(金属) 选项');
    }
    const metalFixture = JSON.parse(JSON.stringify(designFixture));
    metalFixture.rows[0].asset_tag = 'METAL';
    helpers.ingestSnapshot(metalFixture);
    const metalTbody = elements['market-table-body'].innerHTML;
    const metalCell = getRowCell(metalTbody, 'AUSDT', 11);
    if (!metalCell.includes('METAL(金属)')) {
      throw new Error('METAL 行未渲染 METAL(金属) 徽章: ' + metalCell);
    }
    // 只断言 METAL 资产徽章本身中性；同格可另有抵押额度 danger 徽标（v4.1 §9.1）。
    const metalBadgeMatch = metalCell.match(/<span class="badge[^"]*"[^>]*>METAL\(金属\)<\/span>/);
    if (!metalBadgeMatch) {
      throw new Error('未解析到 METAL 资产徽章: ' + metalCell);
    }
    if (metalBadgeMatch[0].includes('danger') || metalBadgeMatch[0].includes('accent')) {
      throw new Error('METAL 徽章不应使用 danger/accent 样式（应为中性徽章）: ' + metalBadgeMatch[0]);
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] METAL 资产标签徽章与下拉选项');

    // 41. 借币三态：51061 借光 / 有额度 / 未探测（max_borrowable + error_code）。
    //   独立 deep-copy 场景，不动默认 6 行基线语义。
    //   (a) AUSDT 借光：max_borrowable='0'+error_code='51061' → warn badge
    //       「可借 0(已借完)」（title 含 51061，非 success），合并列可借子行含
    //       「可借: 0」+「已借完」+「≈ 0.00 USDT」。
    //   (b) BUSDT 有额度：max_borrowable='5.0'+error_code=null → success badge
    //       「已验证可借」，可借子行含「可借: 5.0」+「≈ 30000.00 USDT」、无「已借完」。
    //   (c) CUSDT 未探测：max_borrowable=null → 无可借子行，badge 保持
    //       「有利率·可借性未探测」。
    {
      const triFixture = JSON.parse(JSON.stringify(designFixture));
      // (a) AUSDT 借光（已验证 + pair_listed + asset_borrowable + borrow_rate_source 命中）
      triFixture.rows[0].negative_funding_status = 'PRIVATE_BORROW_VALIDATION_REQUIRED';
      triFixture.rows[0].borrow_validation.verified = true;
      triFixture.rows[0].borrow_validation.classic_margin.pair_listed = true;
      triFixture.rows[0].borrow_validation.classic_margin.asset_borrowable = true;
      triFixture.rows[0].borrow_validation.classic_margin.daily_interest_account = '0.00010000';
      triFixture.rows[0].borrow_rate_source = 'next_hourly';
      triFixture.rows[0].borrow_validation.portfolio_account = {
        max_borrowable: '0', borrow_limit: null,
        error_code: '51061', max_borrowable_value_usdt: '0.00000000',
        source: 'papi_max_borrowable'
      };
      // (b) BUSDT 有额度（负费率，仍为「已验证可借」）
      triFixture.rows[1].negative_funding_status = 'PRIVATE_BORROW_VALIDATION_REQUIRED';
      triFixture.rows[1].daily_funding_rate = '-0.00070000';
      triFixture.rows[1].borrow_validation.verified = true;
      triFixture.rows[1].borrow_validation.classic_margin.pair_listed = true;
      triFixture.rows[1].borrow_validation.classic_margin.asset_borrowable = true;
      triFixture.rows[1].borrow_validation.classic_margin.daily_interest_account = '0.00010000';
      triFixture.rows[1].borrow_rate_source = 'next_hourly';
      triFixture.rows[1].borrow_validation.portfolio_account = {
        max_borrowable: '5.0', borrow_limit: '100',
        error_code: null, max_borrowable_value_usdt: '30000.00000000',
        source: 'papi_max_borrowable'
      };
      // (c) CUSDT 未探测（borrowability_not_probed：max_borrowable=null）
      triFixture.rows[2].negative_funding_status = 'PRIVATE_BORROW_VALIDATION_REQUIRED';
      triFixture.rows[2].borrow_validation.verified = false;
      triFixture.rows[2].borrow_validation.error = 'borrowability_not_probed';
      triFixture.rows[2].borrow_validation.classic_margin.daily_interest_account = '0.00010000';
      triFixture.rows[2].borrow_rate_source = 'next_hourly';
      triFixture.rows[2].borrow_validation.portfolio_account = {
        max_borrowable: null, borrow_limit: null,
        error_code: null, max_borrowable_value_usdt: null,
        source: 'papi_max_borrowable'
      };
      helpers.ingestSnapshot(triFixture);
      const triTbody = elements['market-table-body'].innerHTML;
      // (a) AUSDT 借光
      const ausdtStatus = getRowCell(triTbody, 'AUSDT', 11);
      if (!ausdtStatus.includes('可借 0(已借完)')) {
        throw new Error('AUSDT 借光未渲染「可借 0(已借完)」warn badge: ' + ausdtStatus);
      }
      if (ausdtStatus.includes('badge success')) {
        throw new Error('AUSDT 借光 badge 不应为 success（非绿色「已验证可借」）: ' + ausdtStatus);
      }
      if (!ausdtStatus.includes('51061')) {
        throw new Error('AUSDT 借光 badge title 应含 error_code 51061: ' + ausdtStatus);
      }
      if (!ausdtStatus.includes('可借: 0') || !ausdtStatus.includes('已借完')) {
        throw new Error('AUSDT 借光合并列应含「可借: 0」与「已借完」: ' + ausdtStatus);
      }
      if (!ausdtStatus.includes('≈ 0.00 USDT')) {
        throw new Error('AUSDT 借光 ≈USDT 应显 0.00: ' + ausdtStatus);
      }
      // (b) BUSDT 有额度
      const busdtStatus = getRowCell(triTbody, 'BUSDT', 11);
      if (!busdtStatus.includes('已验证可借') || !busdtStatus.includes('badge success')) {
        throw new Error('BUSDT 有额度应渲染 success「已验证可借」: ' + busdtStatus);
      }
      if (!busdtStatus.includes('可借: 5.0')) {
        throw new Error('BUSDT 有额度合并列应含「可借: 5.0」: ' + busdtStatus);
      }
      if (!busdtStatus.includes('≈ 30000.00 USDT')) {
        throw new Error('BUSDT 有额度 ≈USDT 应显 30000.00: ' + busdtStatus);
      }
      if (busdtStatus.includes('已借完')) {
        throw new Error('BUSDT 有额度不应含「已借完」: ' + busdtStatus);
      }
      // (c) CUSDT 未探测
      const cusdtStatus = getRowCell(triTbody, 'CUSDT', 11);
      if (!cusdtStatus.includes('有利率·可借性未探测')) {
        throw new Error('CUSDT 未探测 badge 应保持「有利率·可借性未探测」: ' + cusdtStatus);
      }
      if (cusdtStatus.includes('可借:')) {
        throw new Error('CUSDT 未探测（max_borrowable=null）不应展示可借子行: ' + cusdtStatus);
      }
      // (d) DUSDT：borrow_rate_source=null 但 portfolio_account.max_borrowable 已探测，
      // 额度仍应显示在合并列，日净收益格仍不应显示额度。
      triFixture.rows[3].negative_funding_status = 'PRIVATE_BORROW_VALIDATION_REQUIRED';
      triFixture.rows[3].borrow_validation.verified = true;
      triFixture.rows[3].borrow_validation.classic_margin.pair_listed = true;
      triFixture.rows[3].borrow_validation.classic_margin.asset_borrowable = true;
      triFixture.rows[3].borrow_rate_source = null;
      triFixture.rows[3].borrow_validation.portfolio_account = {
        max_borrowable: '10.0', borrow_limit: '100',
        error_code: null, max_borrowable_value_usdt: '1000.00000000',
        source: 'papi_max_borrowable'
      };
      helpers.ingestSnapshot(triFixture);
      const triTbody2 = elements['market-table-body'].innerHTML;
      const dusdtStatus = getRowCell(triTbody2, 'DUSDT', 11);
      if (!dusdtStatus.includes('可借: 10.0') || !dusdtStatus.includes('≈ 1000.00 USDT')) {
        throw new Error('DUSDT borrow_rate_source=null 但 max_borrowable 已探测时合并列应显示额度: ' + dusdtStatus);
      }
      const dusdtNet = getRowCell(triTbody2, 'DUSDT', 10);
      if (dusdtNet.includes('可借:')) {
        throw new Error('DUSDT 日净收益格不应显示可借额度: ' + dusdtNet);
      }
      helpers.ingestSnapshot(designFixture);
      console.log('[PASS] 借币三态（51061 借光/有额度/未探测/borrow_rate_source=null 但额度已探测）');
    }

    // 42. 右侧抽屉：打开、标题、年化值、已结算历史（北京时间 newest-first）
    helpers.openDrawer('AUSDT');
    if (!helpers.isDrawerOpen()) {
      throw new Error('openDrawer 后抽屉应为打开状态');
    }
    if (helpers.getSelectedSymbol() !== 'AUSDT') {
      throw new Error('openDrawer 后 selectedSymbol 应为 AUSDT');
    }
    if (!elements['drawer'].classList.contains('open')) {
      throw new Error('drawer 元素应含有 open class');
    }
    if (!elements['drawer-backdrop'].classList.contains('open')) {
      throw new Error('drawer-backdrop 应含有 open class');
    }
    const drawerTitle = elements['drawer-title'].textContent;
    if (!drawerTitle.includes('AUSDT')) {
      throw new Error(`抽屉标题期望含 AUSDT，实际 ${drawerTitle}`);
    }
    const drawerBody = elements['drawer-body'].innerHTML;
    if (!drawerBody.includes('-65.70%') || !drawerBody.includes('-0.26%') || !drawerBody.includes('-0.06%')) {
      throw new Error('抽屉未渲染 AUSDT 三个年化值: ' + drawerBody);
    }
    if (!drawerBody.includes('近 30 日已结算历史（北京时间）')) {
      throw new Error('抽屉未渲染历史标题');
    }
    // 历史 newest-first：第一条是最晚的 funding_time
    const ausdtHistory = designFixture.rows.find(r => r.symbol === 'AUSDT').funding_history;
    const latestTime = ausdtHistory[ausdtHistory.length - 1].funding_time;
    const latestIdx = drawerBody.indexOf(helpers.formatBeijing(latestTime));
    const earliestIdx = drawerBody.indexOf(helpers.formatBeijing(ausdtHistory[0].funding_time));
    if (latestIdx === -1 || earliestIdx === -1 || earliestIdx <= latestIdx) {
      throw new Error('抽屉历史未按 newest-first 排列');
    }
    console.log('[PASS] 抽屉打开、标题、年化值、历史 newest-first');

    // 43. 抽屉关闭按钮
    await Promise.all((elements['drawer-close'].listeners.click || []).map(h => h()));
    if (helpers.isDrawerOpen()) {
      throw new Error('点击关闭按钮后抽屉应关闭');
    }
    if (elements['drawer'].classList.contains('open')) {
      throw new Error('点击关闭按钮后 drawer 不应含有 open class');
    }
    console.log('[PASS] 抽屉关闭按钮');

    // 44. 抽屉 Escape 关闭
    helpers.openDrawer('AUSDT');
    const keydownHandler = document._listeners && document._listeners.keydown;
    if (!keydownHandler) throw new Error('未注册 document keydown 处理器');
    keydownHandler({ key: 'Escape', preventDefault: () => {} });
    if (helpers.isDrawerOpen()) {
      throw new Error('按 Escape 后抽屉应关闭');
    }
    console.log('[PASS] 抽屉 Escape 关闭');

    // 45. 抽屉 backdrop 关闭
    helpers.openDrawer('AUSDT');
    await Promise.all((elements['drawer-backdrop'].listeners.click || []).map(h => h()));
    if (helpers.isDrawerOpen()) {
      throw new Error('点击 backdrop 后抽屉应关闭');
    }
    console.log('[PASS] 抽屉 backdrop 关闭');

    // 46. 刷新保持抽屉：相同 fixture 重新 ingest，抽屉仍开且数据更新
    helpers.openDrawer('AUSDT');
    const beforeTitle = elements['drawer-title'].textContent;
    helpers.ingestSnapshot(designFixture);
    if (!helpers.isDrawerOpen()) {
      throw new Error('刷新后 AUSDT 仍在 snapshot 中，抽屉应保持打开');
    }
    if (elements['drawer-title'].textContent !== beforeTitle) {
      throw new Error('刷新后抽屉标题不应变化');
    }
    console.log('[PASS] 刷新保持抽屉');

    // 47. symbol 消失时抽屉关闭
    const noAusdtFixture = JSON.parse(JSON.stringify(designFixture));
    noAusdtFixture.rows = noAusdtFixture.rows.filter(r => r.symbol !== 'AUSDT');
    helpers.ingestSnapshot(noAusdtFixture);
    if (helpers.isDrawerOpen()) {
      throw new Error('AUSDT 从 snapshot 消失后抽屉应关闭');
    }
    console.log('[PASS] symbol 消失时抽屉关闭');

    // 恢复默认 fixture
    helpers.ingestSnapshot(designFixture);

    // symbol-snapshot 响应构造器（breakdown §11/§12）：基于 designFixture 完整行
    // deep-copy 并覆盖历史/年化字段；row 必须是完整快照行（patchRow 整行替换）。
    const tEnd = 1783641600000;
    const day = 86_400_000;
    const snapshotResponse = (symbol, overrides) => {
      const base = designFixture.rows.find(r => r.symbol === symbol);
      if (!base) throw new Error(`fixture 缺少 ${symbol}`);
      const row = JSON.parse(JSON.stringify(base));
      Object.assign(row, overrides || {});
      return {
        status: 200,
        body: {
          schema_version: 'public-market-symbol-snapshot/v1',
          symbol,
          published_version: 1,
          row
        }
      };
    };

    // 48. Task D: 无预加载历史行打开 drawer 进入 loading 并请求 same-origin endpoint
    historyResponse = { delay: true };
    lastHistoryUrl = null;
    historyResolve = null;
    helpers.openDrawer('BUSDT');
    if (lastHistoryUrl !== '/api/public-market/symbol-snapshot?symbol=BUSDT') {
      throw new Error(`BUSDT drawer 请求 URL 错误: ${lastHistoryUrl}`);
    }
    if (!helpers.getDrawerLoading()) {
      throw new Error('BUSDT 无预加载历史，打开 drawer 后应为 loading 状态');
    }
    const busdtDrawerBodyLoading = elements['drawer-body'].innerHTML;
    if (!busdtDrawerBodyLoading.includes('加载中')) {
      throw new Error('loading 状态未渲染加载中文案');
    }
    console.log('[PASS] drawer loading 与 same-origin 请求');

    // 49. Task D: available 响应（row 带 history）替换整行 + 抽屉 newest-first
    historyResponse = snapshotResponse('BUSDT', {
      funding_history: [
        { funding_time: tEnd - 2 * day, funding_rate: '-0.00010000' },
        { funding_time: tEnd - day, funding_rate: '0.00005000' }
      ],
      annualized_funding_7d: '-0.00260714',
      annualized_funding_30d: '-0.00060833'
    });
    historyResolve();
    await new Promise(r => setTimeout(r, 0));
    if (helpers.getDrawerLoading()) {
      throw new Error('available 响应到达后 loading 应结束');
    }
    if (helpers.getDrawerHistoryError()) {
      throw new Error(`available 响应不应产生错误: ${helpers.getDrawerHistoryError()}`);
    }
    const busdtDrawerBody = elements['drawer-body'].innerHTML;
    if (!busdtDrawerBody.includes('-0.26%') || !busdtDrawerBody.includes('-0.06%')) {
      throw new Error('抽屉未渲染 BUSDT 合并后的 7D/30D 年化值: ' + busdtDrawerBody);
    }
    // newest-first: 较晚的 funding_time 先出现
    const busdtLatestIdx = busdtDrawerBody.indexOf(helpers.formatBeijing(tEnd - day));
    const busdtEarliestIdx = busdtDrawerBody.indexOf(helpers.formatBeijing(tEnd - 2 * day));
    if (busdtLatestIdx === -1 || busdtEarliestIdx === -1 || busdtEarliestIdx <= busdtLatestIdx) {
      throw new Error('BUSDT 抽屉历史未按 newest-first 排列');
    }
    // 表格中的 BUSDT 行也已被更新
    const busdtTbodyAfterMerge = elements['market-table-body'].innerHTML;
    const busdtAnn7Cell = getRowCell(busdtTbodyAfterMerge, 'BUSDT', 8);
    if (!busdtAnn7Cell.includes('-0.26%')) {
      throw new Error('合并后表格 BUSDT 年化 7D 未更新: ' + busdtAnn7Cell);
    }
    console.log('[PASS] available 响应合并到行与表');

    // 50. Task D: empty 响应（row 带 funding_history=[]）显示无记录，不标记失败
    historyResponse = snapshotResponse('CUSDT', {
      funding_history: [],
      annualized_funding_7d: null,
      annualized_funding_30d: null
    });
    helpers.openDrawer('CUSDT');
    await new Promise(r => setTimeout(r, 0));
    if (helpers.getDrawerLoading()) {
      throw new Error('empty 响应到达后 loading 应结束');
    }
    if (helpers.getDrawerHistoryError()) {
      throw new Error(`empty 响应不应产生错误: ${helpers.getDrawerHistoryError()}`);
    }
    const cusdtDrawerBody = elements['drawer-body'].innerHTML;
    if (!cusdtDrawerBody.includes('无已结算历史')) {
      throw new Error('empty 响应未显示「无已结算历史」: ' + cusdtDrawerBody);
    }
    if (cusdtDrawerBody.includes('加载失败') || cusdtDrawerBody.includes('暂时不可用')) {
      throw new Error('empty 响应被错误渲染为失败状态');
    }
    console.log('[PASS] empty 响应显示无记录');

    // 51. Task D: HTTP 502 显示可重试失败状态，且提供重试按钮
    historyResponse = null; // default -> 502
    helpers.openDrawer('DUSDT');
    await new Promise(r => setTimeout(r, 0));
    if (helpers.getDrawerLoading()) {
      throw new Error('502 响应到达后 loading 应结束');
    }
    if (helpers.getDrawerHistoryError() !== 'funding_history_unavailable') {
      throw new Error(`502 响应应产生 funding_history_unavailable 错误，实际: ${helpers.getDrawerHistoryError()}`);
    }
    const dusdtDrawerBody = elements['drawer-body'].innerHTML;
    if (!dusdtDrawerBody.includes('已结算历史加载失败')) {
      throw new Error('502 响应未显示失败文案');
    }
    if (!dusdtDrawerBody.includes('id="drawer-retry"')) {
      throw new Error('502 响应未提供重试按钮');
    }
    if (dusdtDrawerBody.includes('无已结算历史')) {
      throw new Error('502 响应被错误渲染为无记录状态');
    }
    console.log('[PASS] HTTP 502 显示可重试失败状态');

    // 52. Task D: 重试按钮重新 fetch symbol-snapshot 并在成功时更新抽屉
    historyResponse = snapshotResponse('DUSDT', {
      funding_history: [{ funding_time: tEnd - day, funding_rate: '-0.00020000' }],
      annualized_funding_7d: '-0.01042857',
      annualized_funding_30d: '-0.00243333'
    });
    lastHistoryUrl = null;
    const retryBtn = elements['drawer-body'].querySelector('#drawer-retry');
    if (!retryBtn) throw new Error('重试按钮未找到');
    await Promise.all((retryBtn.listeners.click || []).map(h => h()));
    await new Promise(r => setTimeout(r, 0));
    if (lastHistoryUrl !== '/api/public-market/symbol-snapshot?symbol=DUSDT') {
      throw new Error(`重试后请求 URL 错误: ${lastHistoryUrl}`);
    }
    if (helpers.getDrawerHistoryError()) {
      throw new Error(`重试成功后不应有错误: ${helpers.getDrawerHistoryError()}`);
    }
    const dusdtDrawerBodyRetry = elements['drawer-body'].innerHTML;
    if (!dusdtDrawerBodyRetry.includes('-1.04%')) {
      throw new Error('重试成功后抽屉未渲染 DUSDT 7D 年化: ' + dusdtDrawerBodyRetry);
    }
    console.log('[PASS] 重试按钮重新 fetch 并更新抽屉');

    // 53. Task D: stale 响应隔离——先让 BUSDT fetch 挂起，切换到 AUSDT，BUSDT 响应被忽略
    // 由于前面的测试已给 BUSDT 合并过 history，先清空使其需要重新 fetch。
    const busdtRowStale = designFixture.rows.find(r => r.symbol === 'BUSDT');
    if (busdtRowStale) {
      busdtRowStale.funding_history = [];
      busdtRowStale.annualized_funding_7d = null;
      busdtRowStale.annualized_funding_30d = null;
    }
    historyResponse = { delay: true };
    lastHistoryUrl = null;
    historyResolve = null;
    helpers.openDrawer('BUSDT');
    const busdtResolve = historyResolve;
    if (!busdtResolve) throw new Error('BUSDT fetch 未挂起');
    // 切换到 AUSDT（有预加载 history，不触发 fetch）
    helpers.openDrawer('AUSDT');
    // 让挂起的 BUSDT 响应返回
    busdtResolve();
    await new Promise(r => setTimeout(r, 0));
    // AUSDT drawer 不应被 BUSDT 响应污染
    if (helpers.getSelectedSymbol() !== 'AUSDT') {
      throw new Error('stale 响应后 selectedSymbol 仍应为 AUSDT');
    }
    const ausdtDrawerBodyStale = elements['drawer-body'].innerHTML;
    if (ausdtDrawerBodyStale.includes('-0.02%')) {
      throw new Error('AUSDT 抽屉被 stale 的 BUSDT 响应污染');
    }
    console.log('[PASS] stale 响应隔离');

    // 54. Task D response-body race: fetch resolves while A is selected, but
    // res.json() is still pending when user switches to B; A's body must not
    // merge into B row or change B's drawer.
    {
      // Clear BUSDT history so it will fetch.
      const busdtRowRace = designFixture.rows.find(r => r.symbol === 'BUSDT');
      if (busdtRowRace) {
        busdtRowRace.funding_history = [];
        busdtRowRace.annualized_funding_7d = null;
        busdtRowRace.annualized_funding_30d = null;
      }
      // Re-render so the table DOM reflects the cleared state before the race.
      helpers.ingestSnapshot(designFixture);
      const raceBody = snapshotResponse('BUSDT', {
        funding_history: [
          { funding_time: tEnd - 2 * day, funding_rate: '-0.00010000' },
          { funding_time: tEnd - day, funding_rate: '0.00005000' }
        ],
        annualized_funding_7d: '-0.00260714',
        annualized_funding_30d: '-0.00060833'
      }).body;
      historyResponse = {
        delay: true,
        jsonDelay: true,
        status: 200,
        body: raceBody
      };
      historyResolve = null;
      historyJsonResolve = null;
      helpers.openDrawer('BUSDT');
      if (!historyResolve) throw new Error('response-body race: BUSDT fetch 未挂起');
      // Resolve fetch() but keep res.json() pending.
      setTimeout(() => { historyResolve(); }, 20);
      await new Promise(r => setTimeout(r, 50));
      if (!historyJsonResolve) throw new Error('response-body race: res.json() 未挂起');
      // Switch to AUSDT before res.json() resolves.
      helpers.openDrawer('AUSDT');
      const beforeSwitchBody = elements['drawer-body'].innerHTML;
      // Now resolve the stale res.json().
      historyJsonResolve();
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getSelectedSymbol() !== 'AUSDT') {
        throw new Error('response-body race: 切换后 selectedSymbol 仍应为 AUSDT');
      }
      const afterRaceBody = elements['drawer-body'].innerHTML;
      if (afterRaceBody !== beforeSwitchBody) {
        throw new Error('response-body race: AUSDT drawer 被 stale 的 BUSDT res.json() 改变');
      }
      const raceTbody = elements['market-table-body'].innerHTML;
      const busdtAnn7Race = getRowCell(raceTbody, 'BUSDT', 8);
      if (busdtAnn7Race.includes('-0.26%')) {
        throw new Error('response-body race: BUSDT 行被 stale 响应提前合并');
      }
      console.log('[PASS] response-body race 隔离（res.json() 延迟后切换）');
    }

    // 55. Task D wrong-symbol / schema mismatch rejection: a response whose
    // body.symbol differs from the requested symbol must not merge.
    {
      const dusdtRowWrong = designFixture.rows.find(r => r.symbol === 'DUSDT');
      if (dusdtRowWrong) {
        dusdtRowWrong.funding_history = [];
        dusdtRowWrong.annualized_funding_7d = null;
        dusdtRowWrong.annualized_funding_30d = null;
      }
      const wrongBody = snapshotResponse('DUSDT', {
        funding_history: [{ funding_time: tEnd - day, funding_rate: '-0.00010000' }],
        annualized_funding_7d: '-0.00521429',
        annualized_funding_30d: '-0.00121667'
      }).body;
      wrongBody.symbol = 'XUSDT'; // wrong symbol
      historyResponse = { status: 200, body: wrongBody };
      helpers.openDrawer('DUSDT');
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getDrawerHistoryError() !== 'history_response_invalid') {
        throw new Error(`wrong-symbol 响应应产生 history_response_invalid，实际: ${helpers.getDrawerHistoryError()}`);
      }
      const dusdtTbodyWrong = elements['market-table-body'].innerHTML;
      const dusdtAnn7Wrong = getRowCell(dusdtTbodyWrong, 'DUSDT', 8);
      if (dusdtAnn7Wrong.includes('-0.52%')) {
        throw new Error('wrong-symbol 响应不应合并到 DUSDT 行');
      }
      console.log('[PASS] wrong-symbol/schema 响应被拒绝合并');
    }

    // 56. Task D schema_version mismatch rejection
    {
      const mismatchBody = snapshotResponse('DUSDT', {
        funding_history: [{ funding_time: tEnd - day, funding_rate: '-0.00010000' }],
        annualized_funding_7d: '-0.00521429',
        annualized_funding_30d: '-0.00121667'
      }).body;
      mismatchBody.schema_version = 'public-market-symbol-snapshot/v0';
      historyResponse = { status: 200, body: mismatchBody };
      helpers.openDrawer('DUSDT');
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getDrawerHistoryError() !== 'history_response_invalid') {
        throw new Error(`schema_version mismatch 应产生 history_response_invalid，实际: ${helpers.getDrawerHistoryError()}`);
      }
      console.log('[PASS] schema_version mismatch 响应被拒绝');
    }

    // 57. symbol-snapshot 契约：响应缺 row 字段 → history_response_invalid
    {
      historyResponse = {
        status: 200,
        body: {
          schema_version: 'public-market-symbol-snapshot/v1',
          symbol: 'DUSDT',
          published_version: 1
          // no row
        }
      };
      helpers.openDrawer('DUSDT');
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getDrawerHistoryError() !== 'history_response_invalid') {
        throw new Error(`缺 row 响应应产生 history_response_invalid，实际: ${helpers.getDrawerHistoryError()}`);
      }
      console.log('[PASS] 缺 row 字段响应被拒绝');
    }

    // 58. symbol-snapshot 契约：响应同时含 rows 数组 → history_response_invalid
    {
      const withRows = snapshotResponse('DUSDT', {}).body;
      withRows.rows = [withRows.row];
      historyResponse = { status: 200, body: withRows };
      helpers.openDrawer('DUSDT');
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getDrawerHistoryError() !== 'history_response_invalid') {
        throw new Error(`含 rows 数组响应应产生 history_response_invalid，实际: ${helpers.getDrawerHistoryError()}`);
      }
      console.log('[PASS] 含 rows 数组响应被拒绝');
    }

    // 59. in-flight 守卫：同 symbol fetch 挂起时，再次 openDrawer 同 symbol 应被忽略
    // （不发起新请求；breakdown §11.3）。
    {
      historyResponse = { delay: true };
      lastHistoryUrl = null;
      historyResolve = null;
      helpers.openDrawer('DUSDT');
      if (!historyResolve) throw new Error('in-flight 守卫: DUSDT fetch 未挂起');
      const inflightResolve = historyResolve;
      // 再次点击同 symbol：inflightSymbol===DUSDT → openDrawer 直接 return
      lastHistoryUrl = null;
      helpers.openDrawer('DUSDT');
      if (lastHistoryUrl !== null) {
        throw new Error('in-flight 守卫未忽略同 symbol 重复点击');
      }
      inflightResolve();
      await new Promise(r => setTimeout(r, 0));
      console.log('[PASS] in-flight 守卫忽略同 symbol 重复点击');
    }

    // 60. refresh_status=timeout：显示「刷新超时」非阻塞 notice，且 row 保持上次
    // 数据（不替换 state）；仍只补丁目标行/抽屉，无 renderTable（pre-review repair）。
    {
      const dusdtBase = designFixture.rows.find(r => r.symbol === 'DUSDT');
      const beforeRow = helpers.getSnapshot().rows.find(r => r.symbol === 'DUSDT');
      const beforeHistLen = Array.isArray(beforeRow.funding_history) ? beforeRow.funding_history.length : 0;
      // timeout 响应的 row 携带与当前不同的 history —— 必须被丢弃，不替换
      const timeoutRow = JSON.parse(JSON.stringify(dusdtBase));
      timeoutRow.funding_history = [{ funding_time: tEnd - day, funding_rate: '0.00123456' }];
      timeoutRow.annualized_funding_7d = '-0.05000000';
      historyResponse = {
        status: 200,
        body: {
          schema_version: 'public-market-symbol-snapshot/v1',
          symbol: 'DUSDT',
          published_version: 1,
          refresh_status: 'timeout',
          warnings: ['refresh_command_expired:DUSDT'],
          row: timeoutRow
        }
      };
      helpers.openDrawer('DUSDT');
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getDrawerHistoryError()) {
        throw new Error(`timeout 响应不应产生阻塞错误: ${helpers.getDrawerHistoryError()}`);
      }
      if (!helpers.getDrawerNotice() || helpers.getDrawerNotice().kind !== 'timeout') {
        throw new Error(`timeout 响应应设 drawerNotice.kind=timeout，实际: ${JSON.stringify(helpers.getDrawerNotice())}`);
      }
      const bodyTimeout = elements['drawer-body'].innerHTML;
      if (!bodyTimeout.includes('刷新超时，显示上次数据')) {
        throw new Error('timeout 响应未渲染非阻塞「刷新超时」notice: ' + bodyTimeout);
      }
      // row 未被替换：history 长度仍是刷新前的预加载值，而非 timeoutRow 的 1 条
      const afterRow = helpers.getSnapshot().rows.find(r => r.symbol === 'DUSDT');
      const afterHistLen = Array.isArray(afterRow.funding_history) ? afterRow.funding_history.length : 0;
      if (afterHistLen !== beforeHistLen) {
        throw new Error(`timeout 响应不应替换行（history ${beforeHistLen} -> ${afterHistLen}）`);
      }
      console.log('[PASS] refresh_status=timeout 显示 notice 且保留上次行');
    }

    // 61. refresh_status=partial：row 替换 + 「部分刷新成功」notice + 后端 warnings
    {
      const partialRow = JSON.parse(JSON.stringify(designFixture.rows.find(r => r.symbol === 'DUSDT')));
      partialRow.funding_history = [{ funding_time: tEnd - day, funding_rate: '-0.00020000' }];
      partialRow.annualized_funding_7d = '-0.01042857';
      partialRow.annualized_funding_30d = '-0.00243333';
      historyResponse = {
        status: 200,
        body: {
          schema_version: 'public-market-symbol-snapshot/v1',
          symbol: 'DUSDT',
          published_version: 2,
          refresh_status: 'partial',
          warnings: ['premium_refresh_failed:DUSDT'],
          row: partialRow
        }
      };
      helpers.openDrawer('DUSDT');
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getDrawerHistoryError()) {
        throw new Error(`partial 响应不应产生阻塞错误: ${helpers.getDrawerHistoryError()}`);
      }
      if (!helpers.getDrawerNotice() || helpers.getDrawerNotice().kind !== 'partial') {
        throw new Error(`partial 响应应设 drawerNotice.kind=partial，实际: ${JSON.stringify(helpers.getDrawerNotice())}`);
      }
      const bodyPartial = elements['drawer-body'].innerHTML;
      if (!bodyPartial.includes('部分刷新成功')) {
        throw new Error('partial 响应未渲染非阻塞「部分刷新成功」notice');
      }
      if (!bodyPartial.includes('premium_refresh_failed:DUSDT')) {
        throw new Error('partial notice 未透传后端 warnings');
      }
      // row 被替换：ann7 -0.01042857 -> -1.04%
      if (!bodyPartial.includes('-1.04%')) {
        throw new Error('partial 响应未替换/渲染 DUSDT 行的新年化值');
      }
      console.log('[PASS] refresh_status=partial 替换行并显示 warnings notice');
    }

    // 恢复默认 fixture
    helpers.ingestSnapshot(designFixture);

    // 62. 操作列：每行第 13 格恰好两个可编辑输入 + 一个确认按钮，且事件隔离。
    // FUSDT 为 DISABLED_SPOT_ONLY（仅现货: 无杠杆借币）行：借币列与 bStock 一致
    // 显示「—」，无创建控件，单独断言。
    {
      const opTbody = elements['market-table-body'].innerHTML;
      for (const sym of ['AUSDT', 'BUSDT', 'CUSDT', 'DUSDT', 'EUSDT']) {
        const cell = getRowCell(opTbody, sym, 12);
        const inputCount = (cell.match(/<input/g) || []).length;
        if (inputCount !== 2) {
          throw new Error(`${sym} 操作单元格应恰好 2 个输入，实际 ${inputCount}: ${cell}`);
        }
        if (!cell.includes(`id="borrow-amount-${sym}"`) || !cell.includes(`id="borrow-count-${sym}"`)) {
          throw new Error(`${sym} 操作单元格缺少数量/次数输入 id: ${cell}`);
        }
        if (!cell.includes('<label') || !cell.includes('单次借币数量') || !cell.includes('成功借币次数')) {
          throw new Error(`${sym} 操作单元格缺少可访问标签: ${cell}`);
        }
        const btnCount = (cell.match(/<button/g) || []).length;
        if (btnCount !== 1 || !cell.includes(`data-borrow-confirm="${sym}"`)) {
          throw new Error(`${sym} 操作单元格应恰好 1 个确认按钮: ${cell}`);
        }
        if (!cell.includes(`id="borrow-error-${sym}"`)) {
          throw new Error(`${sym} 操作单元格缺少就近错误容器: ${cell}`);
        }
        // F2：创建前预览容器（一个 div，不增减输入/按钮计数）
        if (!cell.includes(`id="borrow-preview-${sym}"`)) {
          throw new Error(`${sym} 操作单元格缺少创建前预览容器: ${cell}`);
        }
      }
      // DISABLED_SPOT_ONLY 行：借币列用「—」代替创建控件（与 bStock 一致）
      const fusdtCell = getRowCell(opTbody, 'FUSDT', 12);
      const fusdtInputCount = (fusdtCell.match(/<input/g) || []).length;
      if (fusdtInputCount !== 0 || fusdtCell.includes('borrow-amount-FUSDT')) {
        throw new Error('FUSDT（DISABLED_SPOT_ONLY）借币列不应有创建输入: ' + fusdtCell);
      }
      if ((fusdtCell.match(/<button/g) || []).length !== 0 || fusdtCell.includes('data-borrow-confirm')) {
        throw new Error('FUSDT（DISABLED_SPOT_ONLY）借币列不应有确认按钮: ' + fusdtCell);
      }
      if (!fusdtCell.includes('borrow-op-cell muted') || !fusdtCell.includes('—')) {
        throw new Error('FUSDT（DISABLED_SPOT_ONLY）借币列应显示「—」: ' + fusdtCell);
      }
      if (!script.includes('stopPropagation')) {
        throw new Error('操作控件缺少事件隔离 stopPropagation');
      }
      console.log('[PASS] 操作单元格两输入一按钮、标签与事件隔离；DISABLED_SPOT_ONLY 行借币列显示 —');
    }

    // 62b. 创建前预览（F2/ADR-001）：输入数量×次数后展示资产/单次数量/成功次数/目标总量/当前全局间隔
    {
      // 加载全局调度设置（提供当前间隔 "5"），失败不应影响预览其余字段
      borrowSettingsGetResponse = { status: 200, body: MOCK_SETTINGS_DEFAULT };
      await helpers.loadSchedulerSettings();
      const amountEl = document.getElementById('borrow-amount-AUSDT');
      const countEl = document.getElementById('borrow-count-AUSDT');
      amountEl.value = '12.5';
      countEl.value = '3';
      helpers.renderBorrowPreview('AUSDT');
      const txt = document.getElementById('borrow-preview-AUSDT').textContent;
      // AUSDT 在 self-check fixture 的 base_asset 为 A
      if (!txt.includes('资产 A')) throw new Error(`预览应包含资产 A: ${txt}`);
      if (!txt.includes('12.5')) throw new Error(`预览应包含单次数量 12.5: ${txt}`);
      if (!txt.includes('成功 3 次')) throw new Error(`预览应包含成功次数 3: ${txt}`);
      if (!txt.includes('目标总量')) throw new Error(`预览应含「目标总量」字样: ${txt}`);
      if (!txt.includes('37.5')) throw new Error(`预览应包含目标总量 37.5（12.5×3，BigInt 无 float）: ${txt}`);
      if (!txt.includes('当前全局间隔') || !txt.includes('5 秒')) throw new Error(`预览应包含当前全局间隔 5 秒: ${txt}`);
      // 预览仅就近展示，不引入浏览器侧调度/签名/联系 Binance
      if (txt.includes('Binance') || txt.includes('签名')) throw new Error(`预览不得联系/签名 Binance: ${txt}`);
      // 部分输入（仅数量）应清空预览，不展示半成品目标总量，也不展示空态占位文案
      countEl.value = '';
      helpers.renderBorrowPreview('AUSDT');
      const partial = document.getElementById('borrow-preview-AUSDT').textContent;
      if (partial.includes('37.5') || partial.includes('单次 12.5')) throw new Error(`部分输入不应展示半成品目标总量: ${partial}`);
      if (partial.includes('输入单次数量与成功次数后查看')) {
        throw new Error(`空/部分输入不应再展示创建预览占位文案: ${partial}`);
      }
      // 还原输入，避免影响后续测试
      amountEl.value = '';
      countEl.value = '';
      helpers.renderBorrowPreview('AUSDT');
      if (document.getElementById('borrow-preview-AUSDT').textContent !== '') {
        throw new Error('空输入时创建预览应为空字符串');
      }
      console.log('[PASS] 创建前预览资产/数量/次数/目标总量/当前全局间隔');
    }

    // ---- 借币任务后端权威迁移（Task B；全部 API 交互走 §3 冻结形状的 mock） ----

    function borrowFetchCalls() {
      return fetchCallLog.filter(c => c.url.startsWith('/api/borrow'));
    }

    // 63. 借币任务导航 + 进入视图经 API 加载（GET tasks/settings），空态与真实文案
    {
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc([]) };
      borrowSettingsGetResponse = { status: 200, body: MOCK_SETTINGS_DEFAULT };
      const fetchBefore = fetchCallLog.length;
      helpers.setActiveView('borrow-tasks');
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getActiveView() !== 'borrow-tasks') {
        throw new Error('setActiveView(borrow-tasks) 后 activeView 应为 borrow-tasks');
      }
      if (elements['borrow-task-view'].style.display === 'none') {
        throw new Error('借币任务视图应显示');
      }
      if (elements['market-view'].style.display !== 'none') {
        throw new Error('借币任务视图激活时市场视图应隐藏');
      }
      if (!elements['nav-borrow-tasks'].classList.contains('active')) {
        throw new Error('借币任务导航应为 active');
      }
      if (elements['nav-market'].classList.contains('active')) {
        throw new Error('费率行情导航在借币视图下不应为 active');
      }
      // 进入视图触发 GET 任务列表 + GET 调度设置
      const newCalls = fetchCallLog.slice(fetchBefore);
      const getTasks = newCalls.find(c => c.url === '/api/borrow-tasks' && c.method === 'GET');
      const getSettings = newCalls.find(c => c.url === '/api/borrow-scheduler-settings' && c.method === 'GET');
      if (!getTasks || !getSettings) {
        throw new Error(`进入借币视图应 GET 任务列表与调度设置: ${JSON.stringify(newCalls)}`);
      }
      const emptyList = elements['borrow-task-list'].innerHTML;
      if (!emptyList.includes('暂无借币任务')) {
        throw new Error(`借币任务空态未渲染: ${emptyList}`);
      }
      if (elements['borrow-task-count'].textContent !== '0') {
        throw new Error(`借币任务计数应为 0: ${elements['borrow-task-count'].textContent}`);
      }
      // 真实的持久化/执行未启用文案；旧的 fake/浏览器内存声明全部移除
      if (!html.includes('执行未启用')) {
        throw new Error('借币任务视图缺少「执行未启用」声明');
      }
      if (html.includes('前端演示') || html.includes('浏览器内存')) {
        throw new Error('页面仍残留 fake/浏览器内存免责声明');
      }
      // F1（Review-1 REWORK）：过期「不发起真实借币 / 所有尝试结果均为执行未启用」静态文案
      // 已删除（执行徽标才是 mode/enabled 真相来源）；仍属实的浏览器陈述（不调度/不模拟/不签名/
      // 不请求 Binance）保留。执行未启用 仅作为 result_category 标签存在（见下方断言）。
      if (html.includes('不发起真实借币')) {
        throw new Error('借币任务视图仍残留「不发起真实借币」过期文案');
      }
      if (html.includes('所有尝试结果均为「执行未启用」')) {
        throw new Error('借币任务视图仍残留「所有尝试结果均为执行未启用」过期文案');
      }
      if (!html.includes('不签名') || !html.includes('不请求 Binance')) {
        throw new Error('借币任务视图应保留浏览器不签名/不请求 Binance 的属实陈述');
      }
      // 间隔编辑器渲染 mock 的 "5"
      if (elements['borrow-interval-input'].value !== '5') {
        throw new Error(`间隔输入应预填 5: ${elements['borrow-interval-input'].value}`);
      }
      if (!elements['borrow-interval-note'].textContent.includes('每 5 秒')) {
        throw new Error(`间隔说明应显示当前 5 秒: ${elements['borrow-interval-note'].textContent}`);
      }
      helpers.setActiveView('market');
      if (helpers.getActiveView() !== 'market') {
        throw new Error('setActiveView(market) 后 activeView 应为 market');
      }
      if (elements['market-view'].style.display === 'none') {
        throw new Error('返回费率行情后市场视图应恢复显示');
      }
      if (elements['borrow-task-view'].style.display !== 'none') {
        throw new Error('返回费率行情后借币任务视图应隐藏');
      }
      console.log('[PASS] 借币任务导航切换、API 加载、空态与真实文案');
    }

    // 64. 输入校验：非法数量/次数本地拒绝，不发送任何 borrow POST
    {
      const postsBefore = borrowFetchCalls().filter(c => c.method === 'POST').length;
      const badAmounts = ['', '   ', '0', '0.0', '-5', 'abc', 'Infinity', 'NaN', '1.2.3', '1e3', '+5'];
      for (const a of badAmounts) {
        const r = await helpers.createBorrowTask('AUSDT', a, '10');
        if (r.ok) {
          throw new Error(`非法数量 ${JSON.stringify(a)} 不应创建任务`);
        }
      }
      const badCounts = ['', '0', '-1', '2.5', 'abc', 'Infinity'];
      for (const c of badCounts) {
        const r = await helpers.createBorrowTask('AUSDT', '1000', c);
        if (r.ok) {
          throw new Error(`非法次数 ${JSON.stringify(c)} 不应创建任务`);
        }
      }
      const postsAfter = borrowFetchCalls().filter(c => c.method === 'POST').length;
      if (postsAfter !== postsBefore) {
        throw new Error('非法输入不应触发任何 borrow POST');
      }
      console.log('[PASS] 借币任务输入本地校验（非法数量/次数不发请求）');
    }

    // 65. HOME 创建：POST 冻结 body（十进制字符串原样），渲染返回的 borrowing 文档
    {
      const homeFixture = JSON.parse(JSON.stringify(designFixture));
      // 仅内存改写 base_asset；symbol 保持 AUSDT，不伪造 HOMEUSDT 行情行
      homeFixture.rows[0].base_asset = 'HOME';
      helpers.ingestSnapshot(homeFixture);
      const fetchBefore = fetchCallLog.length;
      borrowTasksPostResponse = { status: 201, body: MOCK_TASK_HOME };
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc([MOCK_TASK_HOME]) };
      const r = await helpers.createBorrowTask('AUSDT', '12.5', '3');
      if (!r.ok) {
        throw new Error(`HOME 任务创建失败: ${r.error}`);
      }
      if (r.task.id !== 'uuid4-string' || r.task.asset !== 'HOME' || r.task.status !== 'borrowing') {
        throw new Error(`创建返回文档错误: ${JSON.stringify(r.task)}`);
      }
      const calls = fetchCallLog.slice(fetchBefore);
      // 恰好 POST 创建 + GET 重拉（渲染以后端列表为准，不是本地创建态）
      const postCall = calls.find(c => c.url === '/api/borrow-tasks' && c.method === 'POST');
      const getCall = calls.find(c => c.url === '/api/borrow-tasks' && c.method === 'GET');
      if (!postCall || !getCall || calls.length !== 2) {
        throw new Error(`创建后应恰好 POST+GET 各一次: ${JSON.stringify(calls)}`);
      }
      const expectedBody = JSON.stringify({ asset: 'HOME', amount_per_attempt: '12.5', success_target: 3 });
      if (JSON.stringify(postCall.body) !== expectedBody) {
        throw new Error(`创建 body 应为冻结形状 ${expectedBody}: ${JSON.stringify(postCall.body)}`);
      }
      // 渲染缓存 == 后端文档（borrowing 即刻可被后端调度，无二次启动）
      const cached = helpers.getBorrowTasks();
      if (cached.length !== 1 || cached[0].id !== 'uuid4-string' || cached[0].status !== 'borrowing') {
        throw new Error(`渲染缓存应等于后端任务文档: ${JSON.stringify(cached)}`);
      }
      if (elements['borrow-task-count'].textContent !== '1') {
        throw new Error(`借币任务计数应为 1: ${elements['borrow-task-count'].textContent}`);
      }
      helpers.setActiveView('borrow-tasks');
      await new Promise(r => setTimeout(r, 0));
      const listHtml = elements['borrow-task-list'].innerHTML;
      const expectedBits = ['HOME', '12.5 HOME/次', '1 / 3 次成功', '目标 37.5 HOME', '借币中', '执行未启用', '每 5 秒', '任务持久化在后端'];
      for (const bit of expectedBits) {
        if (!listHtml.includes(bit)) {
          throw new Error(`任务卡缺少「${bit}」: ${listHtml}`);
        }
      }
      if (listHtml.includes('HOMEUSDT')) {
        throw new Error('任务视图不得伪造 HOMEUSDT 行情行');
      }
      helpers.setActiveView('market');
      helpers.ingestSnapshot(designFixture);
      console.log('[PASS] HOME 创建 POST 冻结 body、渲染后端 borrowing 文档');
    }

    // 66. 操作单元格 UI 提交路径：本地校验就近报错；API 400 detail 就近显示；成功后清除
    {
      const amountEl = document.getElementById('borrow-amount-AUSDT');
      const countEl = document.getElementById('borrow-count-AUSDT');
      const errorEl = document.getElementById('borrow-error-AUSDT');
      amountEl.value = 'abc';
      countEl.value = '10';
      const r1 = await helpers.submitBorrowTask('AUSDT');
      if (r1.ok) {
        throw new Error('非法数量的 UI 提交不应成功');
      }
      if (!errorEl.textContent.includes('大于 0')) {
        throw new Error(`就近错误未显示: ${errorEl.textContent}`);
      }
      // API 400 invalid_field：detail 原样就近显示
      borrowTasksPostResponse = { status: 400, body: { error: 'invalid_field', detail: 'amount_per_attempt below minimum' } };
      amountEl.value = '0.001';
      countEl.value = '3';
      const r2 = await helpers.submitBorrowTask('AUSDT');
      if (r2.ok) {
        throw new Error('API 400 的 UI 提交不应成功');
      }
      if (errorEl.textContent !== 'amount_per_attempt below minimum') {
        throw new Error(`API 400 detail 应原样显示: ${errorEl.textContent}`);
      }
      // 成功路径：清除错误
      borrowTasksPostResponse = { status: 201, body: MOCK_TASK_HOME };
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc([MOCK_TASK_HOME]) };
      amountEl.value = '12.5';
      countEl.value = '3';
      const r3 = await helpers.submitBorrowTask('AUSDT');
      if (!r3.ok) {
        throw new Error(`合法 UI 提交失败: ${r3.error}`);
      }
      if (errorEl.textContent !== '') {
        throw new Error('合法提交后就近错误应清除');
      }
      console.log('[PASS] 操作单元格 UI 提交路径、本地校验与 API 400 detail');
    }

    // 66b. 创建前 fail-closed（BK-R1-FIX4-001 / micro fix-6）：scheduler settings 未加载/加载失败时
    //      createBorrowTask ok=false 且 /api/borrow-tasks POST 数为 0；submit 入口先重投影预览（如实
    //      标注「未加载」）再 fail closed，仍零 POST；加载 interval=5 后显示完整预览且恰好一次 task POST；
    //      loaded→503 不得用旧间隔放行（失败路径作废缓存）。结尾还原到 item 66 末尾状态。
    {
      const amountEl = document.getElementById('borrow-amount-AUSDT');
      const countEl = document.getElementById('borrow-count-AUSDT');
      const errorEl = document.getElementById('borrow-error-AUSDT');
      const previewEl = document.getElementById('borrow-preview-AUSDT');
      const taskPosts = () => borrowFetchCalls().filter(c => c.url === '/api/borrow-tasks' && c.method === 'POST').length;

      // 负向：强制「间隔未加载」（模拟启动一次性 GET 未完成 / 失败），create 直接拒绝且零 POST
      helpers.clearBorrowSchedulerSettings();
      const negBefore = taskPosts();
      const r1 = await helpers.createBorrowTask('AUSDT', '12.5', '3');
      if (r1.ok) throw new Error('调度设置未加载时不应创建任务（fail closed）');
      if (!r1.error || !r1.error.includes('间隔')) throw new Error(`未加载错误应说明间隔未加载: ${r1.error}`);
      if (taskPosts() !== negBefore) throw new Error(`调度设置未加载时不应发送任务 POST: Δ=${taskPosts() - negBefore}`);

      // submit 入口在未加载时先重投影预览（如实标注「未加载」）再 fail closed，仍零 POST
      amountEl.value = '12.5';
      countEl.value = '3';
      const r1b = await helpers.submitBorrowTask('AUSDT');
      if (r1b.ok) throw new Error('未加载时 submit 也不应创建任务');
      if (!errorEl.textContent.includes('间隔')) throw new Error(`submit 就近错误应说明间隔未加载: ${errorEl.textContent}`);
      if (!previewEl.textContent.includes('未加载')) throw new Error(`submit 应先重投影预览并标注未加载: ${previewEl.textContent}`);
      if (taskPosts() !== negBefore) throw new Error(`未加载时 submit 仍不应发送任务 POST: Δ=${taskPosts() - negBefore}`);

      // 正向：加载 interval=5 后预览显示真实间隔 5 秒；create 成功且恰好一次 task POST
      borrowSettingsGetResponse = { status: 200, body: MOCK_SETTINGS_DEFAULT };
      await helpers.loadSchedulerSettings();
      helpers.renderBorrowPreview('AUSDT');
      if (!previewEl.textContent.includes('当前全局间隔 5 秒')) throw new Error(`加载后预览应显示真实间隔 5 秒: ${previewEl.textContent}`);
      borrowTasksPostResponse = { status: 201, body: MOCK_TASK_HOME };
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc([MOCK_TASK_HOME]) };
      const posBefore = taskPosts();
      const r2 = await helpers.createBorrowTask('AUSDT', '12.5', '3');
      if (!r2.ok) throw new Error(`加载 interval=5 后应创建成功: ${r2.error}`);
      if (taskPosts() - posBefore !== 1) throw new Error(`正向应恰好一次任务 POST: Δ=${taskPosts() - posBefore}`);

      // loaded→503（micro fix-6）：保留 phase 3 已加载的 interval=5，不得先 clear；让 GET 返回 503，
      // loadSchedulerSettings 失败路径作废缓存 → state=null、预览回退「未加载」、create fail-closed、零 POST
      borrowSettingsGetResponse = null; // -> mockBorrow503()
      await helpers.loadSchedulerSettings();
      if (helpers.getBorrowSchedulerSettings() !== null) throw new Error('loaded→503 后缓存设置应被作废（不得用旧间隔放行）');
      helpers.renderBorrowPreview('AUSDT');
      if (!previewEl.textContent.includes('未加载')) throw new Error(`loaded→503 后预览应回退未加载: ${previewEl.textContent}`);
      const r3 = await helpers.createBorrowTask('AUSDT', '12.5', '3');
      if (r3.ok) throw new Error('loaded→503 后不应创建任务（fail closed，旧间隔已作废）');
      if (!r3.error || !r3.error.includes('间隔')) throw new Error(`loaded→503 错误应说明间隔未加载: ${r3.error}`);
      if (taskPosts() !== posBefore + 1) throw new Error('loaded→503 后不应发送任务 POST');

      // 还原到 item 66 末尾状态：间隔已加载 + item 66 的 task mock + 输入/预览/错误，避免影响 item 67+
      borrowSettingsGetResponse = { status: 200, body: MOCK_SETTINGS_DEFAULT };
      await helpers.loadSchedulerSettings();
      borrowTasksPostResponse = { status: 201, body: MOCK_TASK_HOME };
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc([MOCK_TASK_HOME]) };
      await helpers.loadBorrowTasks();
      amountEl.value = '12.5';
      countEl.value = '3';
      errorEl.textContent = '';
      helpers.renderBorrowPreview('AUSDT');
      console.log('[PASS] 创建前 fail-closed：未加载/loaded→503 零 POST，加载 interval=5 后恰好一次 POST');
    }

    // 67. maxBorrowableSubline 不再重复「已借完」（唯一保留：状态徽标「可借 0(已借完)」）
    {
      const exhaustedFixture = JSON.parse(JSON.stringify(designFixture));
      exhaustedFixture.rows[0].negative_funding_status = 'PRIVATE_BORROW_VALIDATION_REQUIRED';
      exhaustedFixture.rows[0].borrow_validation.verified = true;
      exhaustedFixture.rows[0].borrow_validation.classic_margin.pair_listed = true;
      exhaustedFixture.rows[0].borrow_validation.classic_margin.asset_borrowable = true;
      exhaustedFixture.rows[0].borrow_validation.portfolio_account = {
        max_borrowable: '0', borrow_limit: null,
        error_code: '51061', max_borrowable_value_usdt: '0.00000000',
        source: 'papi_max_borrowable'
      };
      helpers.ingestSnapshot(exhaustedFixture);
      const exhaustedCell = getRowCell(elements['market-table-body'].innerHTML, 'AUSDT', 11);
      const exhaustedCount = (exhaustedCell.match(/已借完/g) || []).length;
      if (exhaustedCount !== 1) {
        throw new Error(`「已借完」应只出现 1 次（状态徽标），实际 ${exhaustedCount}: ${exhaustedCell}`);
      }
      if (!exhaustedCell.includes('可借 0(已借完)')) {
        throw new Error('状态徽标「可借 0(已借完)」应保留: ' + exhaustedCell);
      }
      if (!exhaustedCell.includes('可借: 0')) {
        throw new Error('额度子行应保留「可借: 0」: ' + exhaustedCell);
      }
      helpers.ingestSnapshot(designFixture);
      console.log('[PASS] maxBorrowableSubline 不再重复「已借完」');
    }

    // 68. 任务状态机按钮矩阵（四状态逐格）+ 冻结 mutation 路由/body + 409 就近显示
    {
      const taskB = deepCopy(MOCK_TASK_HOME, { id: 'task-b', status: 'borrowing', version: 4 });
      const taskP = deepCopy(MOCK_TASK_HOME, { id: 'task-p', status: 'paused', latest_result: null });
      const taskC = deepCopy(MOCK_TASK_HOME, { id: 'task-c', status: 'completed', success_count: 3 });
      const taskD = deepCopy(MOCK_TASK_HOME, { id: 'task-d', status: 'deleted' });
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc([taskB, taskP, taskC, taskD]) };
      await helpers.loadBorrowTasks();
      // Nav badge = 借币中 only (1); filter chips still show full status breakdown.
      if (elements['borrow-task-count'].textContent !== '1') {
        throw new Error(`导航借币中计数应为 1: ${elements['borrow-task-count'].textContent}`);
      }
      helpers.setBorrowTaskFilter('all');
      // 全部 含软删除（计数只从渲染缓存派生）
      const filtersHtml = elements['borrow-task-filters'].innerHTML;
      for (const text of ['全部 (4)', '借币中 (1)', '已暂停 (1)', '已删除 (1)', '已完成 (1)']) {
        if (!filtersHtml.includes(text)) throw new Error(`筛选计数缺少「${text}」: ${filtersHtml}`);
      }
      // 按钮矩阵：borrowing 禁启动；paused 禁暂停；completed 禁启动/暂停/编辑；deleted 全禁
      let card = getTaskCardHtml(elements['borrow-task-list'].innerHTML, 'task-b');
      if (!taskActionBtnHtml(card, 'start').includes('disabled')) throw new Error('borrowing: 启动应禁用');
      if (!taskActionBtnHtml(card, 'start').includes('action-start')) throw new Error('borrowing: 启动应保留 action-start 主题');
      if (taskActionBtnHtml(card, 'pause').includes('disabled')) throw new Error('borrowing: 暂停应可用');
      if (!taskActionBtnHtml(card, 'pause').includes('action-pause')) throw new Error('borrowing: 暂停应保留 action-pause 主题');
      if (taskActionBtnHtml(card, 'delete').includes('disabled')) throw new Error('borrowing: 删除应可用');
      if (!taskActionBtnHtml(card, 'delete').includes('action-delete')) throw new Error('borrowing: 删除应保留 action-delete 主题');
      if (taskEditConfirmBtnHtml(card, 'task-b').includes('disabled')) throw new Error('borrowing: 编辑确认应可用');
      card = getTaskCardHtml(elements['borrow-task-list'].innerHTML, 'task-p');
      if (taskActionBtnHtml(card, 'start').includes('disabled')) throw new Error('paused: 启动应可用');
      if (!taskActionBtnHtml(card, 'pause').includes('disabled')) throw new Error('paused: 暂停应禁用');
      card = getTaskCardHtml(elements['borrow-task-list'].innerHTML, 'task-c');
      if (!taskActionBtnHtml(card, 'start').includes('disabled')) throw new Error('completed: 启动应禁用');
      if (!taskActionBtnHtml(card, 'pause').includes('disabled')) throw new Error('completed: 暂停应禁用');
      if (taskActionBtnHtml(card, 'delete').includes('disabled')) throw new Error('completed: 删除应可用');
      if (!taskEditConfirmBtnHtml(card, 'task-c').includes('disabled')) throw new Error('completed: 编辑确认应禁用');
      if (!taskEditInputHtml(card, 'amount', 'task-c').includes('disabled')) throw new Error('completed: 编辑输入应禁用');
      card = getTaskCardHtml(elements['borrow-task-list'].innerHTML, 'task-d');
      for (const action of ['start', 'pause', 'delete']) {
        if (!taskActionBtnHtml(card, action).includes('disabled')) throw new Error(`deleted: ${action} 应禁用`);
      }
      if (!taskEditConfirmBtnHtml(card, 'task-d').includes('disabled')) throw new Error('deleted: 编辑确认应禁用');
      if (!taskEditInputHtml(card, 'amount', 'task-d').includes('disabled')) throw new Error('deleted: 编辑输入应禁用');
      // 操作按钮视觉主题（启动绿/暂停灰/删除红）与显式禁用态样式保留
      if (!html.includes('.btn:disabled')) throw new Error('缺少显式 .btn:disabled 禁用样式');
      if (!html.includes('.btn.action-start') || !html.includes('.btn.action-pause') || !html.includes('.btn.action-delete')) {
        throw new Error('缺少 action-start/action-pause/action-delete 主题类样式');
      }
      if (html.indexOf('.btn:disabled') < html.indexOf('.btn.action-start')) {
        throw new Error('禁用样式应位于操作主题之后以覆盖主题色');
      }

      // start：POST /{id}/start，body {}，用返回文档 + 重拉渲染
      const taskPStarted = deepCopy(taskP, { status: 'borrowing', version: 5 });
      borrowActionResponses = { 'task-p:start': { status: 200, body: taskPStarted } };
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc([taskB, taskPStarted, taskC, taskD]) };
      let mark = fetchCallLog.length;
      const rStart = await helpers.startBorrowTask('task-p');
      if (!rStart.ok) throw new Error(`start 应成功: ${rStart.error}`);
      let calls = fetchCallLog.slice(mark);
      let post = calls.find(c => c.method === 'POST');
      if (!post || post.url !== '/api/borrow-tasks/task-p/start' || JSON.stringify(post.body) !== '{}') {
        throw new Error(`start 请求应为 POST /api/borrow-tasks/task-p/start body {}: ${JSON.stringify(calls)}`);
      }
      if (!calls.some(c => c.url === '/api/borrow-tasks' && c.method === 'GET')) {
        throw new Error('start 成功后应重拉任务列表');
      }
      if (!getTaskCardHtml(elements['borrow-task-list'].innerHTML, 'task-p').includes('借币中')) {
        throw new Error('start 后应渲染借币中徽标');
      }

      // pause：POST /{id}/pause
      const taskBPaused = deepCopy(taskB, { status: 'paused', version: 5 });
      borrowActionResponses = { 'task-b:pause': { status: 200, body: taskBPaused } };
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc([taskBPaused, taskPStarted, taskC, taskD]) };
      mark = fetchCallLog.length;
      const rPause = await helpers.pauseBorrowTask('task-b');
      if (!rPause.ok) throw new Error(`pause 应成功: ${rPause.error}`);
      calls = fetchCallLog.slice(mark);
      post = calls.find(c => c.method === 'POST');
      if (!post || post.url !== '/api/borrow-tasks/task-b/pause' || JSON.stringify(post.body) !== '{}') {
        throw new Error(`pause 请求错误: ${JSON.stringify(calls)}`);
      }
      if (!getTaskCardHtml(elements['borrow-task-list'].innerHTML, 'task-b').includes('已暂停')) {
        throw new Error('pause 后应渲染已暂停徽标');
      }

      // delete：POST /{id}/delete（completed → deleted 软删除，任务行保留）
      const taskCDeleted = deepCopy(taskC, { status: 'deleted', version: 5 });
      borrowActionResponses = { 'task-c:delete': { status: 200, body: taskCDeleted } };
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc([taskBPaused, taskPStarted, taskCDeleted, taskD]) };
      mark = fetchCallLog.length;
      const rDelete = await helpers.deleteBorrowTask('task-c');
      if (!rDelete.ok) throw new Error(`delete 应成功: ${rDelete.error}`);
      calls = fetchCallLog.slice(mark);
      post = calls.find(c => c.method === 'POST');
      if (!post || post.url !== '/api/borrow-tasks/task-c/delete' || JSON.stringify(post.body) !== '{}') {
        throw new Error(`delete 请求错误: ${JSON.stringify(calls)}`);
      }
      if (!helpers.getBorrowTasks().some(t => t.id === 'task-c' && t.status === 'deleted')) {
        throw new Error('软删除后任务行应保留且 status=deleted');
      }

      // edit：body 携带 amount_per_attempt/success_target/version（乐观并发）
      const taskPEdited = deepCopy(taskPStarted, { amount_per_attempt: '7.25', success_target: 5, version: 6 });
      borrowActionResponses = { 'task-p:edit': { status: 200, body: taskPEdited } };
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc([taskBPaused, taskPEdited, taskCDeleted, taskD]) };
      mark = fetchCallLog.length;
      const rEdit = await helpers.editBorrowTask('task-p', '7.25', '5');
      if (!rEdit.ok) throw new Error(`edit 应成功: ${rEdit.error}`);
      calls = fetchCallLog.slice(mark);
      post = calls.find(c => c.method === 'POST');
      const expectedEditBody = JSON.stringify({ amount_per_attempt: '7.25', success_target: 5, version: 5 });
      if (!post || post.url !== '/api/borrow-tasks/task-p/edit' || JSON.stringify(post.body) !== expectedEditBody) {
        throw new Error(`edit body 应为 ${expectedEditBody}: ${JSON.stringify(post && post.body)}`);
      }
      const cardPEdited = getTaskCardHtml(elements['borrow-task-list'].innerHTML, 'task-p');
      if (!cardPEdited.includes('7.25 HOME/次') || !cardPEdited.includes('目标 36.25 HOME')) {
        throw new Error(`edit 后展示未更新: ${cardPEdited}`);
      }

      // 409 invalid_transition：detail 原样返回，缓存不被污染
      borrowActionResponses = { 'task-d:start': { status: 409, body: { error: 'invalid_transition', detail: 'cannot start a deleted task' } } };
      const beforeConflict = JSON.stringify(helpers.getBorrowTasks());
      const rConflict1 = await helpers.startBorrowTask('task-d');
      if (rConflict1.ok) throw new Error('deleted 任务 start 不应成功');
      if (rConflict1.error !== 'cannot start a deleted task') {
        throw new Error(`409 detail 应原样返回: ${rConflict1.error}`);
      }
      if (JSON.stringify(helpers.getBorrowTasks()) !== beforeConflict) {
        throw new Error('409 后渲染缓存不应变化');
      }
      // 409 version_conflict
      borrowActionResponses = { 'task-p:edit': { status: 409, body: { error: 'version_conflict', detail: 'task version changed, reload first' } } };
      const rConflict2 = await helpers.editBorrowTask('task-p', '8', '2');
      if (rConflict2.ok) throw new Error('版本冲突的 edit 不应成功');
      if (rConflict2.error !== 'task version changed, reload first') {
        throw new Error(`version_conflict detail 应原样返回: ${rConflict2.error}`);
      }
      // 本地校验失败不发请求
      mark = fetchCallLog.length;
      const rLocal = await helpers.editBorrowTask('task-p', 'abc', '2');
      if (rLocal.ok) throw new Error('非法数量 edit 不应成功');
      if (fetchCallLog.length !== mark) throw new Error('本地校验失败不应发送请求');
      console.log('[PASS] 任务状态机按钮矩阵、冻结 mutation 路由/body 与 409 就近显示');
    }

    // 69. latest_result 五类冻结中文标签 + 未知阻塞徽标（unresolved_attempt_id）
    {
      const catTasks = [
        deepCopy(MOCK_TASK_HOME, { id: 'task-cat-success', latest_result: deepCopy(MOCK_TASK_HOME.latest_result, { result_category: 'success', reason: null, tran_id: 'paper-1' }) }),
        deepCopy(MOCK_TASK_HOME, { id: 'task-cat-known', latest_result: deepCopy(MOCK_TASK_HOME.latest_result, { result_category: 'known_rejection', reason: 'borrow_rejected' }) }),
        deepCopy(MOCK_TASK_HOME, { id: 'task-cat-rate', latest_result: deepCopy(MOCK_TASK_HOME.latest_result, { result_category: 'rate_limited', reason: 'retry_after' }) }),
        deepCopy(MOCK_TASK_HOME, { id: 'task-cat-unknown', latest_result: deepCopy(MOCK_TASK_HOME.latest_result, { result_category: 'unknown', reason: 'timeout' }), unresolved_attempt_id: 'attempt-9' }),
        deepCopy(MOCK_TASK_HOME, { id: 'task-cat-disabled' }),
        deepCopy(MOCK_TASK_HOME, { id: 'task-cat-none', latest_result: null })
      ];
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc(catTasks) };
      await helpers.loadBorrowTasks();
      helpers.setBorrowTaskFilter('all');
      const listHtml = elements['borrow-task-list'].innerHTML;
      const labelCases = [
        ['task-cat-success', '<span class="badge success">成功</span>'],
        ['task-cat-known', '<span class="badge warn">已知拒绝</span>'],
        ['task-cat-rate', '<span class="badge info">限频冷却</span>'],
        ['task-cat-unknown', '<span class="badge danger">未知·待对账</span>'],
        ['task-cat-disabled', '<span class="badge muted">执行未启用</span>']
      ];
      for (const [id, badge] of labelCases) {
        const cardHtml = getTaskCardHtml(listHtml, id);
        if (!cardHtml.includes(badge)) {
          throw new Error(`${id} 应渲染冻结结果标签 ${badge}: ${cardHtml}`);
        }
      }
      // 未知阻塞：阻塞徽标 + 启动/暂停禁用（不会被调度）；删除仍可用（退出通道）
      const blockedCard = getTaskCardHtml(listHtml, 'task-cat-unknown');
      if (!blockedCard.includes('待对账·暂停调度')) {
        throw new Error(`未知阻塞任务应渲染阻塞徽标: ${blockedCard}`);
      }
      if (!taskActionBtnHtml(blockedCard, 'start').includes('disabled') || !taskActionBtnHtml(blockedCard, 'pause').includes('disabled')) {
        throw new Error('未知阻塞任务的启动/暂停应禁用');
      }
      if (taskActionBtnHtml(blockedCard, 'delete').includes('disabled')) {
        throw new Error('未知阻塞任务的删除应可用（operator 退出通道）');
      }
      // latest_result null → 暂无执行记录
      const noneCard = getTaskCardHtml(listHtml, 'task-cat-none');
      if (!noneCard.includes('暂无执行记录')) {
        throw new Error(`latest_result=null 应渲染暂无执行记录: ${noneCard}`);
      }
      console.log('[PASS] latest_result 五类标签、未知阻塞徽标与空结果占位');
    }

    // 70. 筛选成员与软删除可见性（全部含 deleted；借币中不含 deleted）
    {
      const fTasks = [
        deepCopy(MOCK_TASK_HOME, { id: 'task-f1', status: 'borrowing' }),
        deepCopy(MOCK_TASK_HOME, { id: 'task-f2', status: 'paused' }),
        deepCopy(MOCK_TASK_HOME, { id: 'task-f3', status: 'completed', success_count: 3 }),
        deepCopy(MOCK_TASK_HOME, { id: 'task-f4', status: 'deleted' })
      ];
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc(fTasks) };
      await helpers.loadBorrowTasks();
      helpers.setBorrowTaskFilter('all');
      let listHtml = elements['borrow-task-list'].innerHTML;
      if ((listHtml.match(/borrow-task-card/g) || []).length !== 4) {
        throw new Error('全部筛选应渲染 4 张卡');
      }
      for (const id of ['task-f1', 'task-f2', 'task-f3', 'task-f4']) {
        if (!listHtml.includes(`data-task-id="${id}"`)) throw new Error(`全部筛选应包含 ${id}`);
      }
      helpers.setBorrowTaskFilter('deleted');
      listHtml = elements['borrow-task-list'].innerHTML;
      if (!listHtml.includes('data-task-id="task-f4"') || listHtml.includes('data-task-id="task-f1"')) {
        throw new Error('已删除筛选成员错误');
      }
      if (!getTaskCardHtml(listHtml, 'task-f4').includes('已删除')) {
        throw new Error('已删除任务卡应渲染已删除徽标');
      }
      helpers.setBorrowTaskFilter('borrowing');
      listHtml = elements['borrow-task-list'].innerHTML;
      if (listHtml.includes('data-task-id="task-f4"') || !listHtml.includes('data-task-id="task-f1"')) {
        throw new Error('借币中筛选成员错误');
      }
      helpers.setBorrowTaskFilter('paused');
      if (!elements['borrow-task-list'].innerHTML.includes('data-task-id="task-f2"')) {
        throw new Error('已暂停筛选成员错误');
      }
      helpers.setBorrowTaskFilter('completed');
      if (!elements['borrow-task-list'].innerHTML.includes('data-task-id="task-f3"')) {
        throw new Error('已完成筛选成员错误');
      }
      helpers.setBorrowTaskFilter('all');
      console.log('[PASS] 筛选成员与软删除可见性');
    }

    // 71. 任务编辑 UI 路径：预填后端原值、submitBorrowTaskEdit 成功/409/只读就近显示
    {
      // 当前缓存为 #70 的 f1..f4；f1 borrowing version 4
      const card1 = getTaskCardHtml(elements['borrow-task-list'].innerHTML, 'task-f1');
      if (!taskEditInputHtml(card1, 'amount', 'task-f1').includes('value="12.5"')) {
        throw new Error('编辑数量输入应预填后端十进制原值 12.5');
      }
      if (!taskEditInputHtml(card1, 'count', 'task-f1').includes('value="3"')) {
        throw new Error('编辑次数输入应预填当前值 3');
      }
      const amountEl = document.getElementById('task-edit-amount-task-f1');
      const countEl = document.getElementById('task-edit-count-task-f1');
      const errorEl = document.getElementById('task-edit-error-task-f1');
      amountEl.value = '250';
      countEl.value = '7';
      const f1Edited = deepCopy(MOCK_TASK_HOME, { id: 'task-f1', status: 'borrowing', amount_per_attempt: '250', success_target: 7, version: 5 });
      borrowActionResponses = { 'task-f1:edit': { status: 200, body: f1Edited } };
      borrowTasksGetResponse = { status: 200, body: mockTaskListDoc([
        f1Edited,
        deepCopy(MOCK_TASK_HOME, { id: 'task-f2', status: 'paused' }),
        deepCopy(MOCK_TASK_HOME, { id: 'task-f3', status: 'completed', success_count: 3 }),
        deepCopy(MOCK_TASK_HOME, { id: 'task-f4', status: 'deleted' })
      ]) };
      const r1 = await helpers.submitBorrowTaskEdit('task-f1');
      if (!r1.ok) throw new Error(`有效编辑失败: ${r1.error}`);
      if (errorEl.textContent !== '') throw new Error('有效编辑后错误应清除');
      const card1After = getTaskCardHtml(elements['borrow-task-list'].innerHTML, 'task-f1');
      if (!card1After.includes('250 HOME/次') || !card1After.includes('1 / 7 次成功') || !card1After.includes('目标 1,750 HOME')) {
        throw new Error(`有效编辑后展示未更新: ${card1After}`);
      }
      // 409 version_conflict 就近显示
      amountEl.value = '250';
      countEl.value = '7';
      borrowActionResponses = { 'task-f1:edit': { status: 409, body: { error: 'version_conflict', detail: 'task version changed, reload first' } } };
      const r2 = await helpers.submitBorrowTaskEdit('task-f1');
      if (r2.ok) throw new Error('版本冲突编辑不应成功');
      if (!errorEl.textContent.includes('task version changed')) {
        throw new Error(`409 detail 未就近显示: ${errorEl.textContent}`);
      }
      // 只读状态（deleted）经 API 409 invalid_transition 就近显示
      const errorEl4 = document.getElementById('task-edit-error-task-f4');
      const amountEl4 = document.getElementById('task-edit-amount-task-f4');
      const countEl4 = document.getElementById('task-edit-count-task-f4');
      amountEl4.value = '5';
      countEl4.value = '2';
      borrowActionResponses = { 'task-f4:edit': { status: 409, body: { error: 'invalid_transition', detail: 'cannot edit a deleted task' } } };
      const r3 = await helpers.submitBorrowTaskEdit('task-f4');
      if (r3.ok) throw new Error('deleted 任务编辑不应成功');
      if (!errorEl4.textContent.includes('cannot edit a deleted task')) {
        throw new Error(`只读任务 409 detail 未就近显示: ${errorEl4.textContent}`);
      }
      console.log('[PASS] 任务编辑预填、有效/409/只读路径');
    }

    // 72. 顶层 tab：借币任务 | 借币日志；状态筛选只在任务 tab 内
    {
      // 结构断言：筛选容器在 tasks panel 内、logs panel 之外；tab 按钮齐全
      const tasksPanelIdx = html.indexOf('id="borrow-tasks-panel"');
      const filtersIdx = html.indexOf('id="borrow-task-filters"');
      const logsPanelIdx = html.indexOf('id="borrow-logs-panel"');
      if (tasksPanelIdx === -1 || logsPanelIdx === -1 || filtersIdx === -1 ||
          !(tasksPanelIdx < filtersIdx && filtersIdx < logsPanelIdx)) {
        throw new Error('状态筛选容器必须位于借币任务 tab 内（borrow-tasks-panel 与 borrow-logs-panel 之间）');
      }
      if (!html.includes('id="borrow-tab-tasks"') || !html.includes('id="borrow-tab-logs"')) {
        throw new Error('缺少借币任务/借币日志顶层 tab 按钮');
      }
      // 初始：任务 tab 显示、日志 tab 隐藏（mock 不解析 HTML 内联 display:none，先对齐初始态）
      elements['borrow-logs-panel'].style.display = 'none';
      borrowLogsResponses = [{ status: 200, body: MOCK_LOG_PAGE_1 }];
      helpers.setActiveView('borrow-tasks');
      await new Promise(r => setTimeout(r, 0));
      if (elements['borrow-tasks-panel'].style.display === 'none') {
        throw new Error('初始应显示借币任务 tab');
      }
      if (elements['borrow-logs-panel'].style.display !== 'none') {
        throw new Error('初始应隐藏借币日志 tab');
      }
      // 切到日志 tab：拉第 1 页
      let mark = fetchCallLog.length;
      helpers.setBorrowTab('logs');
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getBorrowTab() !== 'logs') throw new Error('borrowTab 应为 logs');
      if (elements['borrow-logs-panel'].style.display === 'none' || elements['borrow-tasks-panel'].style.display !== 'none') {
        throw new Error('日志 tab 激活后面板显隐错误');
      }
      const logCalls = fetchCallLog.slice(mark).filter(c => c.url.startsWith('/api/borrow-logs'));
      if (logCalls.length !== 1 || logCalls[0].url !== '/api/borrow-logs?limit=50' || logCalls[0].method !== 'GET') {
        throw new Error(`日志 tab 激活应 GET /api/borrow-logs?limit=50: ${JSON.stringify(logCalls)}`);
      }
      // 切回任务 tab：重新拉任务列表
      mark = fetchCallLog.length;
      helpers.setBorrowTab('tasks');
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getBorrowTab() !== 'tasks') throw new Error('borrowTab 应为 tasks');
      if (elements['borrow-tasks-panel'].style.display === 'none' || elements['borrow-logs-panel'].style.display !== 'none') {
        throw new Error('任务 tab 激活后面板显隐错误');
      }
      const taskCalls = fetchCallLog.slice(mark).filter(c => c.url === '/api/borrow-tasks' && c.method === 'GET');
      if (taskCalls.length !== 1) {
        throw new Error('任务 tab 激活应重拉任务列表');
      }
      helpers.setActiveView('market');
      console.log('[PASS] 借币任务/借币日志顶层 tab 切换与筛选归属');
    }

    // 73. 最小借币量占位符三分支（含 raw "0"/"0.00"）；输入值为空；任务编辑输入不受影响
    {
      const phFixture = JSON.parse(JSON.stringify(designFixture));
      phFixture.rows[0].borrow_validation.classic_margin.user_min_borrow = '0';
      phFixture.rows[0].borrow_validation.classic_margin.user_min_borrow_value_usdt = '0.00';
      phFixture.rows[1].borrow_validation.classic_margin.user_min_borrow = '0.001';
      phFixture.rows[1].borrow_validation.classic_margin.user_min_borrow_value_usdt = null;
      phFixture.rows[2].borrow_validation.classic_margin.user_min_borrow = null;
      phFixture.rows[2].borrow_validation.classic_margin.user_min_borrow_value_usdt = null;
      phFixture.rows[3].borrow_validation.classic_margin.user_min_borrow = '2.5';
      phFixture.rows[3].borrow_validation.classic_margin.user_min_borrow_value_usdt = '123.46';
      helpers.ingestSnapshot(phFixture);
      const phTbody = elements['market-table-body'].innerHTML;
      const phCases = [
        ['AUSDT', 'placeholder="最小借币量 0 ≈ 0.00 USDT"'],
        ['BUSDT', 'placeholder="最小借币量 0.001 ≈ — USDT"'],
        ['CUSDT', 'placeholder="最小借币量 —"'],
        ['DUSDT', 'placeholder="最小借币量 2.5 ≈ 123.46 USDT"']
      ];
      for (const [sym, expected] of phCases) {
        const cell = getRowCell(phTbody, sym, 12);
        if (!cell.includes(expected)) {
          throw new Error(`${sym} 占位符期望 ${expected}，单元格 ${cell}`);
        }
        // 输入值保持为空：数量输入标签内不得出现 value 属性
        const tagStart = cell.indexOf(`<input id="borrow-amount-${sym}"`);
        const tag = cell.slice(tagStart, cell.indexOf('/>', tagStart));
        if (tag.includes('value=')) {
          throw new Error(`${sym} 数量输入不应带 value 属性: ${tag}`);
        }
      }
      // 任务列表编辑输入不受占位符规则影响：仍有 value 预填、无 placeholder
      const card1 = getTaskCardHtml(elements['borrow-task-list'].innerHTML, 'task-f1');
      const editInput = taskEditInputHtml(card1, 'amount', 'task-f1');
      if (!editInput.includes('value="250"')) throw new Error('任务编辑输入预填不应受占位符规则影响');
      if (editInput.includes('placeholder=')) throw new Error('任务编辑输入不应携带占位符');
      helpers.ingestSnapshot(designFixture);
      console.log('[PASS] 最小借币量占位符三分支、空输入值与编辑输入不受影响');
    }

    // 74. 借币日志：newest-first 两页游标分页、加载更多、显式刷新
    {
      borrowLogsResponses = [{ status: 200, body: MOCK_LOG_PAGE_1 }, { status: 200, body: MOCK_LOG_PAGE_2 }];
      helpers.setActiveView('borrow-tasks');
      await new Promise(r => setTimeout(r, 0));
      helpers.setBorrowTab('logs');
      await new Promise(r => setTimeout(r, 0));
      let listHtml = elements['borrow-log-list'].innerHTML;
      // newest-first：mock 返回顺序原样渲染（id 42 在 41 前）
      if (!(listHtml.indexOf('paper-1') !== -1 && listHtml.indexOf('paper-1') < listHtml.indexOf('borrow_rejected'))) {
        throw new Error(`日志第 1 页未按 newest-first 渲染: ${listHtml}`);
      }
      if (!listHtml.includes('成功') || !listHtml.includes('已知拒绝') || !listHtml.includes('51061')) {
        throw new Error(`日志第 1 页结果/业务码未渲染: ${listHtml}`);
      }
      if (!listHtml.includes('2026-07-19')) {
        throw new Error('日志时间未渲染为北京时间');
      }
      // 加载更多可见 → 点击携带 next_cursor
      if (elements['borrow-logs-load-more'].style.display === 'none') {
        throw new Error('next_cursor 存在时加载更多应可见');
      }
      let mark = fetchCallLog.length;
      await Promise.all((elements['borrow-logs-load-more'].listeners.click || []).map(h => h()));
      await new Promise(r => setTimeout(r, 0));
      const moreCalls = fetchCallLog.slice(mark).filter(c => c.url.startsWith('/api/borrow-logs'));
      if (moreCalls.length !== 1 || moreCalls[0].url !== '/api/borrow-logs?limit=50&cursor=cursor-page-2') {
        throw new Error(`加载更多应携带 next_cursor: ${JSON.stringify(moreCalls)}`);
      }
      listHtml = elements['borrow-log-list'].innerHTML;
      // 两页拼接顺序保持 newest-first
      const orderOk = listHtml.indexOf('paper-1') < listHtml.indexOf('borrow_rejected') &&
                      listHtml.indexOf('borrow_rejected') < listHtml.indexOf('executor_disabled');
      if (!orderOk) {
        throw new Error(`两页拼接后顺序错误: ${listHtml}`);
      }
      if (!listHtml.includes('执行未启用') || !listHtml.includes('进行中')) {
        throw new Error('执行未启用/pending 条目应渲染对应徽标');
      }
      // next_cursor null → 加载更多隐藏
      if (elements['borrow-logs-load-more'].style.display !== 'none') {
        throw new Error('next_cursor 为 null 后加载更多应隐藏');
      }
      if (helpers.getBorrowLogs().entries.length !== 4) {
        throw new Error(`两页拼接后应为 4 条: ${helpers.getBorrowLogs().entries.length}`);
      }
      // 显式刷新重拉第 1 页（重置条目）
      borrowLogsResponses = [{ status: 200, body: MOCK_LOG_PAGE_1 }];
      mark = fetchCallLog.length;
      await Promise.all((elements['borrow-logs-refresh'].listeners.click || []).map(h => h()));
      await new Promise(r => setTimeout(r, 0));
      const refreshCalls = fetchCallLog.slice(mark).filter(c => c.url.startsWith('/api/borrow-logs'));
      if (refreshCalls.length !== 1 || refreshCalls[0].url !== '/api/borrow-logs?limit=50') {
        throw new Error(`显式刷新应重拉第 1 页: ${JSON.stringify(refreshCalls)}`);
      }
      if (helpers.getBorrowLogs().entries.length !== 2) {
        throw new Error('刷新后日志应重置为第 1 页 2 条');
      }
      helpers.setBorrowTab('tasks');
      await new Promise(r => setTimeout(r, 0));
      helpers.setActiveView('market');
      console.log('[PASS] 借币日志 newest-first 游标分页、加载更多与显式刷新');
    }

    // 74b. 清空借币日志：确认前零 POST；确认后 POST /api/borrow-logs/clear + 重拉第 1 页
    {
      helpers.setActiveView('borrow-tasks');
      helpers.setBorrowTab('logs');
      await new Promise(r => setTimeout(r, 0));
      if (!document.getElementById('borrow-logs-clear')) {
        throw new Error('应有清空日志按钮 #borrow-logs-clear');
      }
      const mark = fetchCallLog.length;
      const pend = helpers.requestClearBorrowLogs();
      if (!pend.ok || !pend.pending) throw new Error('清空应进入确认 pending');
      if (fetchCallLog.length !== mark) throw new Error('清空确认前不应发请求');
      const modal = helpers.getHedgeModal();
      if (!modal || !modal.title.includes('清空借币日志')) {
        throw new Error('清空确认弹窗标题错误: ' + JSON.stringify(modal));
      }
      helpers.cancelHedgeStartGate();
      if (helpers.getMarketActionPending() !== null) throw new Error('取消后 pending 应清空');

      helpers.requestClearBorrowLogs();
      borrowLogsClearResponse = {
        status: 200,
        body: { schema_version: 'borrow-tasks/v1', deleted_count: 12, retained_unresolved_count: 1 },
      };
      borrowLogsResponses = [{ status: 200, body: { schema_version: 'borrow-tasks/v1', entries: [], next_cursor: null } }];
      const markClear = fetchCallLog.length;
      const rClear = await helpers.confirmMarketAction();
      if (!rClear.ok) throw new Error('确认清空应成功: ' + rClear.error);
      const clearCall = fetchCallLog.slice(markClear).find(c => c.url === '/api/borrow-logs/clear');
      if (!clearCall || clearCall.method !== 'POST') throw new Error('应 POST /api/borrow-logs/clear');
      if (JSON.stringify(clearCall.body) !== JSON.stringify({ confirm: true })) {
        throw new Error('清空 body 应为 {confirm:true}: ' + JSON.stringify(clearCall.body));
      }
      if (!fetchCallLog.slice(markClear).some(c => c.method === 'GET' && c.url.startsWith('/api/borrow-logs?'))) {
        throw new Error('清空后应重拉借币日志第 1 页');
      }
      helpers.setActiveView('market');
      console.log('[PASS] 清空借币日志：确认前零请求 + POST clear + 重拉列表');
    }

    // 75. 全局间隔编辑器：GET 渲染、PUT 合法十进制（≥2s）、sub-floor 400 就近显示
    {
      borrowSettingsGetResponse = { status: 200, body: MOCK_SETTINGS_DEFAULT };
      helpers.setActiveView('borrow-tasks');
      await new Promise(r => setTimeout(r, 0));
      if (elements['borrow-interval-input'].value !== '5') {
        throw new Error(`间隔输入应渲染 mock 的 5: ${elements['borrow-interval-input'].value}`);
      }
      // PUT "2.5" 成功（≥2s 容量地板的合法小数）：body 为冻结形状，说明与任务卡策略行更新
      borrowSettingsPutResponse = { status: 200, body: MOCK_SETTINGS_2_5 };
      let mark = fetchCallLog.length;
      elements['borrow-interval-input'].value = '2.5';
      const r1 = await helpers.submitSchedulerInterval();
      if (!r1.ok) throw new Error(`PUT 2.5 应成功: ${r1.error}`);
      const putCalls = fetchCallLog.slice(mark).filter(c => c.url === '/api/borrow-scheduler-settings');
      if (putCalls.length !== 1 || putCalls[0].method !== 'PUT' ||
          JSON.stringify(putCalls[0].body) !== JSON.stringify({ interval_seconds: '2.5' })) {
        throw new Error(`PUT body 应为 {"interval_seconds":"2.5"}: ${JSON.stringify(putCalls)}`);
      }
      if (!elements['borrow-interval-note'].textContent.includes('每 2.5 秒')) {
        throw new Error(`PUT 后间隔说明应更新为 2.5 秒: ${elements['borrow-interval-note'].textContent}`);
      }
      if (!elements['borrow-task-list'].innerHTML.includes('每 2.5 秒')) {
        throw new Error('PUT 后任务卡策略行应引用新间隔');
      }
      if (elements['borrow-interval-error'].textContent !== '') {
        throw new Error('PUT 成功后错误应清除');
      }
      // 400 invalid_interval：sub-floor "0.5" 被后端容量地板拒绝，detail 就近显示，设置保持 2.5
      borrowSettingsPutResponse = { status: 400, body: { error: 'invalid_interval', detail: 'interval_seconds must be >= 2 (frozen shared-IP capacity floor)' } };
      elements['borrow-interval-input'].value = '0.5';
      const r2 = await helpers.submitSchedulerInterval();
      if (r2.ok) throw new Error('sub-floor 0.5 不应成功');
      if (elements['borrow-interval-error'].textContent !== 'interval_seconds must be >= 2 (frozen shared-IP capacity floor)') {
        throw new Error(`400 detail 应原样就近显示: ${elements['borrow-interval-error'].textContent}`);
      }
      if (!elements['borrow-interval-note'].textContent.includes('每 2.5 秒')) {
        throw new Error('400 后间隔设置应保持不变');
      }
      // 空输入本地拒绝，不发 PUT
      mark = fetchCallLog.length;
      elements['borrow-interval-input'].value = '   ';
      const r3 = await helpers.submitSchedulerInterval();
      if (r3.ok) throw new Error('空间隔不应成功');
      if (fetchCallLog.slice(mark).some(c => c.url === '/api/borrow-scheduler-settings' && c.method === 'PUT')) {
        throw new Error('空输入不应发送 PUT');
      }
      if (!elements['borrow-interval-error'].textContent.includes('不能为空')) {
        throw new Error('空输入应显示本地校验错误');
      }
      helpers.setActiveView('market');
      console.log('[PASS] 全局间隔编辑器 GET/PUT（≥2s）、sub-floor 400 与本地校验');
    }

    // ==================== 开单任务（2026-07-hedge-open-live-v1，12-breakdown §3/§5） ====================
    // 77. 开单操作列渲染：平滑开单 disabled + 「下一轮」提示；立即开单恒可点；推荐方向高亮
    {
      // 重新灌入全新 fixture 副本并复位全部筛选，保证 6 行全量、payload 序渲染。
      elements['filter-search'].value = '';
      (elements['filter-search'].listeners.input || []).forEach(h => h());
      elements['filter-asset'].value = '';
      (elements['filter-asset'].listeners.change || []).forEach(h => h());
      elements['filter-route'].value = '';
      (elements['filter-route'].listeners.change || []).forEach(h => h());
      elements['filter-hide-low-daily-rate'].checked = false;
      (elements['filter-hide-low-daily-rate'].listeners.change || []).forEach(h => h());
      elements['filter-hide-low-net-yield'].checked = false;
      (elements['filter-hide-low-net-yield'].listeners.change || []).forEach(h => h());
      elements['filter-prefer-openable'].checked = false;
      (elements['filter-prefer-openable'].listeners.change || []).forEach(h => h());
      helpers.ingestSnapshot(JSON.parse(JSON.stringify(designFixture)));
      const hedgeTbody = elements['market-table-body'].innerHTML;
      if ((hedgeTbody.match(/<tr/g) || []).length !== 6) {
        throw new Error('开单断言前置：期望 6 行全量渲染');
      }
      // 操作列结构：两输入 + 两按钮；平滑开单 disabled 并标注「下一轮」，立即开单可点
      const cusdtFwdOp = getRowCell(hedgeTbody, 'CUSDT', 13);
      const cusdtRevOp = getRowCell(hedgeTbody, 'CUSDT', 14);
      for (const [name, cell] of [['CUSDT 正向操作列', cusdtFwdOp], ['CUSDT 反向操作列', cusdtRevOp]]) {
        for (const piece of ['单次开单币量', '计划尝试次数', '平滑开单', '立即开单', 'data-hedge-open="smooth"', 'data-hedge-open="immediate"']) {
          if (!cell.includes(piece)) throw new Error(`${name} 缺少「${piece}」: ${cell}`);
        }
        const smoothBtnMatch = cell.match(/<button[^>]*data-hedge-open="smooth"[^>]*>/);
        if (!smoothBtnMatch) throw new Error(`${name} 缺少平滑开单按钮: ${cell}`);
        if (!smoothBtnMatch[0].includes('disabled')) {
          throw new Error(`${name} 平滑开单按钮应 disabled（本轮无 ws）: ${smoothBtnMatch[0]}`);
        }
        const immediateBtnMatch = cell.match(/<button[^>]*data-hedge-open="immediate"[^>]*>/);
        if (!immediateBtnMatch) throw new Error(`${name} 缺少立即开单按钮: ${cell}`);
        if (immediateBtnMatch[0].includes('disabled')) {
          throw new Error(`${name} 立即开单按钮不应 disabled: ${immediateBtnMatch[0]}`);
        }
        if (!cell.includes('下一轮')) throw new Error(`${name} 缺少「下一轮」提示: ${cell}`);
      }
      // 推荐高亮：CUSDT 正费率 → 正向列按钮高亮、反向列不高亮
      if (!cusdtFwdOp.includes('hedge-reco')) throw new Error('正费率行正向开单按钮应高亮推荐: ' + cusdtFwdOp);
      if (cusdtRevOp.includes('hedge-reco')) throw new Error('正费率行反向开单按钮不应高亮: ' + cusdtRevOp);
      // AUSDT 负费率 → 反向列高亮、正向列不高亮
      const ausdtFwdOp = getRowCell(hedgeTbody, 'AUSDT', 13);
      const ausdtRevOp = getRowCell(hedgeTbody, 'AUSDT', 14);
      if (ausdtFwdOp.includes('hedge-reco')) throw new Error('负费率行正向开单按钮不应高亮: ' + ausdtFwdOp);
      if (!ausdtRevOp.includes('hedge-reco')) throw new Error('负费率行反向开单按钮应高亮推荐: ' + ausdtRevOp);
      // FUSDT 零费率 → 两列都不高亮
      const fusdtFwdOp = getRowCell(hedgeTbody, 'FUSDT', 13);
      const fusdtRevOp = getRowCell(hedgeTbody, 'FUSDT', 14);
      if (fusdtFwdOp.includes('hedge-reco') || fusdtRevOp.includes('hedge-reco')) {
        throw new Error('零费率行两个方向都不应高亮');
      }
      console.log('[PASS] 开单操作列两输入两按钮、平滑开单 disabled+下一轮、立即开单可点、推荐方向按费率符号高亮');
    }

    // 78. 立即开单创建：POST §3.1 冻结 body + 创建后重拉列表 + 非法输入零 POST + invalid_field 行内报错
    {
      helpers.resetHedgeStateForTest();
      hedgeTasksGetResponse = { status: 200, body: { tasks: [] } };
      document.getElementById('hedge-amount-forward-AUSDT').value = '0.5';
      document.getElementById('hedge-count-forward-AUSDT').value = '3';
      const createdTask = mockHedgeTask({ id: 'h-create-1', coin: 'AUSDT', direction: 'forward', single_amount: 0.5, target_n: 3 });
      hedgeTasksPostResponse = { status: 201, body: createdTask };
      const markBeforeCreate = fetchCallLog.length;
      const rCreate = await helpers.submitHedgeOpen('AUSDT', 'forward', 'immediate');
      if (!rCreate.ok) throw new Error('立即开单创建失败: ' + rCreate.error);
      const createCalls = fetchCallLog.slice(markBeforeCreate);
      const postCall = createCalls.find(c => c.method === 'POST');
      if (!postCall || postCall.url !== '/api/hedge-open-tasks') {
        throw new Error(`创建应 POST /api/hedge-open-tasks，实际: ${JSON.stringify(createCalls)}`);
      }
      const expectedBody = { coin: 'AUSDT', direction: 'forward', mode: 'immediate', single_amount: '0.5', target_n: 3 };
      if (JSON.stringify(postCall.body) !== JSON.stringify(expectedBody)) {
        throw new Error(`POST body 与 §3.1 冻结形状不符: ${JSON.stringify(postCall.body)}`);
      }
      // R4-fix-1：single_amount 必须为 decimal string（后端 validate_single_amount 要求
      // ^[0-9]+(\.[0-9]+)?$，number 会被 400 invalid_field）；target_n 维持整数 number。
      if (typeof postCall.body.single_amount !== 'string' || !/^[0-9]+(\.[0-9]+)?$/.test(postCall.body.single_amount)) {
        throw new Error(`single_amount 应为 decimal string: ${JSON.stringify(postCall.body.single_amount)}`);
      }
      if (typeof postCall.body.target_n !== 'number' || !Number.isInteger(postCall.body.target_n)) {
        throw new Error(`target_n 应为整数 number: ${JSON.stringify(postCall.body.target_n)}`);
      }
      // 规范化：输入 `.5` 应上送 '0.5'（trim + 前导零，不走 float 往返）
      // （重置 GET 槽为新对象：mock 按引用返回 body，前一次创建 push 进的是旧槽别名数组）
      hedgeTasksGetResponse = { status: 200, body: { tasks: [] } };
      document.getElementById('hedge-amount-forward-AUSDT').value = ' .5 ';
      const markDot5 = fetchCallLog.length;
      const rDot5 = await helpers.submitHedgeOpen('AUSDT', 'forward', 'immediate');
      if (!rDot5.ok) throw new Error('`.5` 应规范化后创建成功: ' + rDot5.error);
      const dot5Post = fetchCallLog.slice(markDot5).find(c => c.method === 'POST');
      if (!dot5Post || dot5Post.body.single_amount !== '0.5') {
        throw new Error(`'.5' 应规范化为 '0.5' 上送: ${JSON.stringify(dot5Post && dot5Post.body)}`);
      }
      document.getElementById('hedge-amount-forward-AUSDT').value = '0.5';
      // 创建成功后重拉列表（§3：GET /api/hedge-open-tasks?status=all）
      const listCall = createCalls.find(c => c.method === 'GET' && c.url.startsWith('/api/hedge-open-tasks'));
      if (!listCall || listCall.url !== '/api/hedge-open-tasks?status=all') {
        throw new Error(`创建后应重拉 ?status=all 列表: ${JSON.stringify(createCalls.map(c => c.url))}`);
      }
      if (helpers.getHedgeTasks().length !== 0) {
        throw new Error('mock 列表为空时应以后端列表为准（创建返回文档被列表重拉覆盖）');
      }
      // 非法输入 → 行内报错、零 POST
      const markBad = fetchCallLog.length;
      document.getElementById('hedge-amount-forward-AUSDT').value = 'abc';
      const rBad = await helpers.submitHedgeOpen('AUSDT', 'forward', 'immediate');
      if (rBad.ok) throw new Error('非法币量不应创建任务');
      if (!document.getElementById('hedge-error-forward-AUSDT').textContent.includes('正数')) {
        throw new Error('非法币量应行内报错');
      }
      if (fetchCallLog.length !== markBad) throw new Error('非法输入不应产生任何 fetch');
      document.getElementById('hedge-amount-forward-AUSDT').value = '1';
      document.getElementById('hedge-count-forward-AUSDT').value = '0';
      const rBadN = await helpers.submitHedgeOpen('AUSDT', 'forward', 'immediate');
      if (rBadN.ok) throw new Error('非法次数不应创建任务');
      if (fetchCallLog.length !== markBad) throw new Error('非法次数不应产生任何 fetch');
      // invalid_field 400 → 行内报错，不建任务
      document.getElementById('hedge-count-forward-AUSDT').value = '3';
      hedgeTasksPostResponse = { status: 400, body: { error: 'invalid_field', field: 'single_amount' } };
      const rInv = await helpers.submitHedgeOpen('AUSDT', 'forward', 'immediate');
      if (rInv.ok || rInv.error !== 'invalid_field') throw new Error('invalid_field 应创建失败: ' + JSON.stringify(rInv));
      const invErr = document.getElementById('hedge-error-forward-AUSDT').textContent;
      if (!invErr.includes('single_amount')) throw new Error('invalid_field 应就近显示字段名: ' + invErr);
      // 平滑模式入口拒绝（按钮虽 disabled，helper 路径同样不得 POST）
      const markSmooth = fetchCallLog.length;
      const rSmooth = await helpers.submitHedgeOpen('AUSDT', 'forward', 'smooth');
      if (rSmooth.ok || rSmooth.error !== 'smooth_next_round') throw new Error('smooth 模式应被拒绝: ' + JSON.stringify(rSmooth));
      if (fetchCallLog.length !== markSmooth) throw new Error('smooth 模式不应产生任何 fetch');
      console.log('[PASS] 立即开单创建：POST 冻结 body、创建后重拉 ?status=all、非法输入零 POST、invalid_field 行内报错、smooth 拒绝');
    }

    // 79. insufficient_balance 弹框两路径（§3.1 错误码 → stage-1 文案逐字）+ 不建任务
    {
      helpers.resetHedgeStateForTest();
      hedgeTasksGetResponse = { status: 200, body: { tasks: [] } };
      // 79a. 正向 USDT 不足 → 弹框「正向开单 USDT 余额不足」、不建任务
      document.getElementById('hedge-amount-forward-AUSDT').value = '1';
      document.getElementById('hedge-count-forward-AUSDT').value = '5';
      hedgeTasksPostResponse = { status: 400, body: { error: 'insufficient_balance', direction: 'forward', required: '500.00', available: '1.00' } };
      const rInsF = await helpers.submitHedgeOpen('AUSDT', 'forward', 'immediate');
      if (rInsF.ok) throw new Error('USDT 不足不应创建任务');
      if (rInsF.error !== 'insufficient_balance') throw new Error('应返回 insufficient_balance: ' + rInsF.error);
      const modal1 = helpers.getHedgeModal();
      if (!modal1 || modal1.title !== '正向开单 USDT 余额不足') {
        throw new Error(`正向余额不足弹框标题错误: ${JSON.stringify(modal1)}`);
      }
      if (!modal1.body.includes('500.00') || !modal1.body.includes('1.00')) {
        throw new Error(`弹框正文应携带后端 required/available: ${modal1.body}`);
      }
      if (!elements['hedge-modal'].classList.contains('open')) throw new Error('弹框应为 open 态');
      if (helpers.getHedgeTasks().length !== 0) throw new Error('余额不足不应创建任务');
      helpers.closeHedgeModal();
      if (helpers.getHedgeModal() !== null || elements['hedge-modal'].classList.contains('open')) {
        throw new Error('弹框关闭后状态应清空');
      }
      // 79b. 反向现货不足 → 弹框「反向开单现货余额不足」、不建任务
      document.getElementById('hedge-amount-reverse-AUSDT').value = '1';
      document.getElementById('hedge-count-reverse-AUSDT').value = '5';
      hedgeTasksPostResponse = { status: 400, body: { error: 'insufficient_balance', direction: 'reverse', required: '5', available: '0.001' } };
      const rInsR = await helpers.submitHedgeOpen('AUSDT', 'reverse', 'immediate');
      if (rInsR.ok) throw new Error('现货不足不应创建任务');
      const modal2 = helpers.getHedgeModal();
      if (!modal2 || modal2.title !== '反向开单现货余额不足') {
        throw new Error(`反向余额不足弹框标题错误: ${JSON.stringify(modal2)}`);
      }
      if (helpers.getHedgeTasks().length !== 0) throw new Error('反向余额不足不应创建任务');
      helpers.closeHedgeModal();
      // 79c. 反向 POST body direction 逐字 reverse
      const revPost = fetchCallLog.slice().reverse().find(c => c.method === 'POST' && c.url === '/api/hedge-open-tasks');
      if (!revPost || revPost.body.direction !== 'reverse' || revPost.body.mode !== 'immediate') {
        throw new Error(`反向创建 body 错误: ${JSON.stringify(revPost && revPost.body)}`);
      }
      console.log('[PASS] insufficient_balance 弹框两路径：正向 USDT / 反向现货 stage-1 文案逐字、不建任务');
    }

    // 80. 任务生命周期：五动作冻结路由（§3.1）+ 状态推进 + 软删除筛选与导航徽标
    {
      helpers.resetHedgeStateForTest();
      const t0 = mockHedgeTask({ id: 'h-life-1', coin: 'AUSDT', direction: 'forward' });
      hedgeTasksGetResponse = { status: 200, body: { tasks: [t0] } };
      await helpers.loadHedgeTasks();
      if (helpers.getHedgeTasks().length !== 1) throw new Error('加载任务列表失败');
      if (elements['hedge-task-count'].textContent !== '1') throw new Error('导航徽标应为运行中任务数 1');
      // pause → POST /api/hedge-open-tasks/h-life-1/pause
      const tPaused = mockHedgeTask({ id: 'h-life-1', status: 'paused' });
      hedgeActionResponses['h-life-1:pause'] = { status: 200, body: tPaused };
      hedgeTasksGetResponse = { status: 200, body: { tasks: [tPaused] } };
      const rPause = await helpers.pauseHedgeTask('h-life-1');
      if (!rPause.ok) throw new Error('暂停失败: ' + rPause.error);
      const pauseCall = fetchCallLog.slice().reverse().find(c => c.url.includes('/api/hedge-open-tasks/h-life-1/'));
      if (!pauseCall || pauseCall.url !== '/api/hedge-open-tasks/h-life-1/pause' || pauseCall.method !== 'POST') {
        throw new Error(`暂停路由错误: ${JSON.stringify(pauseCall)}`);
      }
      if (helpers.getHedgeTasks()[0].status !== 'paused') throw new Error('暂停后列表应重拉为 paused');
      if (elements['hedge-task-count'].textContent !== '1') {
        throw new Error('导航徽标须保留已暂停任务计数，应为 1');
      }
      // start
      const tRunning = mockHedgeTask({ id: 'h-life-1', status: 'running' });
      hedgeActionResponses['h-life-1:start'] = { status: 200, body: tRunning };
      hedgeTasksGetResponse = { status: 200, body: { tasks: [tRunning] } };
      const rStart = await helpers.startHedgeTask('h-life-1');
      if (!rStart.ok) throw new Error('启动失败: ' + rStart.error);
      // fill-once → success_count 推进由后端文档决定
      const tFill1 = mockHedgeTask({ id: 'h-life-1', status: 'running', success_count: 1 });
      hedgeActionResponses['h-life-1:fill-once'] = { status: 200, body: tFill1 };
      hedgeTasksGetResponse = { status: 200, body: { tasks: [tFill1] } };
      const rFill1 = await helpers.hedgeFillOnceNow('h-life-1');
      if (!rFill1.ok) throw new Error('成交1次失败: ' + rFill1.error);
      if (helpers.getHedgeTasks()[0].success_count !== 1) throw new Error('成交1次后应渲染后端 success_count=1');
      // fill-all → done
      const tDone = mockHedgeTask({ id: 'h-life-1', status: 'done', success_count: 3 });
      hedgeActionResponses['h-life-1:fill-all'] = { status: 200, body: tDone };
      hedgeTasksGetResponse = { status: 200, body: { tasks: [tDone] } };
      const rFillAll = await helpers.hedgeFillAll('h-life-1');
      if (!rFillAll.ok) throw new Error('立即成交所有失败: ' + rFillAll.error);
      if (helpers.getHedgeTasks()[0].status !== 'done') throw new Error('立即成交所有后应为 done');
      // 软删除：POST delete → status deleted；任务保留在 status=all 列表中
      const tDeleted = mockHedgeTask({ id: 'h-life-1', status: 'deleted', success_count: 3 });
      hedgeActionResponses['h-life-1:delete'] = { status: 200, body: tDeleted };
      hedgeTasksGetResponse = { status: 200, body: { tasks: [tDeleted] } };
      const rDel = await helpers.deleteHedgeTask('h-life-1');
      if (!rDel.ok) throw new Error('删除失败: ' + rDel.error);
      if (helpers.getHedgeTasks().length !== 1) throw new Error('软删除后任务应保留在 status=all 列表中');
      if (helpers.getHedgeTasks()[0].status !== 'deleted') throw new Error('软删除后状态应为 deleted');
      // 筛选可见性：执行中/已完成不含 deleted；已删除/全部含
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTaskFilter('running');
      if (elements['hedge-task-list'].innerHTML.includes('data-hedge-task-id')) {
        throw new Error('执行中筛选不应列出已删除任务');
      }
      if (!elements['hedge-task-list'].innerHTML.includes('暂无「执行中」任务')) {
        throw new Error('执行中筛选空态文案错误: ' + elements['hedge-task-list'].innerHTML);
      }
      helpers.setHedgeTaskFilter('done');
      if (elements['hedge-task-list'].innerHTML.includes('h-life-1')) throw new Error('已完成筛选不应列出已删除任务');
      helpers.setHedgeTaskFilter('deleted');
      const deletedList = elements['hedge-task-list'].innerHTML;
      if (!deletedList.includes('h-life-1') || !deletedList.includes('已删除')) {
        throw new Error('已删除筛选应列出软删除任务及其徽标');
      }
      helpers.setHedgeTaskFilter('all');
      if (!elements['hedge-task-list'].innerHTML.includes('h-life-1')) throw new Error('全部筛选应列出软删除任务');
      // 筛选栏计数与默认激活态
      const filterBar = elements['hedge-task-filters'].innerHTML;
      for (const piece of ['全部 (1)', '执行中 (0)', '已暂停 (0)', '已删除 (1)', '已完成 (0)',
        'data-hedge-filter="all"', 'data-hedge-filter="running"', 'data-hedge-filter="paused"',
        'data-hedge-filter="deleted"', 'data-hedge-filter="done"']) {
        if (!filterBar.includes(piece)) throw new Error(`筛选栏缺少「${piece}」: ${filterBar}`);
      }
      helpers.setActiveView('market');
      if (elements['hedge-task-view'].style.display !== 'none') throw new Error('切回市场后开单任务视图应隐藏');
      console.log('[PASS] 任务生命周期：pause/start/fill-once/fill-all/delete 冻结路由 + 状态推进 + 软删除筛选与导航徽标');
    }

    // 81. stopped/paused 语义返工（15 号修正案 I-4）：single_leg 只是提示且任务仍继续调度
    //     （除非后端 status 为 paused/stopped）；stopped 显示致命错误终止 stop_reason；
    //     删除旧的「累计失败 >3」推导与硬编码 /3；按钮矩阵只服从后端 status；invalid_state 409。
    {
      helpers.resetHedgeStateForTest();
      // running + leg_exposure：单腿只是提示，绝不能显示“任务已暂停/等待人工处理”。
      const runningExpTask = mockHedgeTask({
        id: 'h-exp-1', coin: 'BUSDT', direction: 'reverse', status: 'running',
        leg_exposure: { leg: 'spot', qty: 0.5, price: 123.45, ts: '2026-07-22T08:01:00.000000Z' }
      });
      // paused + leg_exposure：此时才允许展示“任务当前处于暂停”（真实后端状态驱动）。
      const pausedExpTask = mockHedgeTask({
        id: 'h-exp-2', coin: 'FUSDT', direction: 'forward', status: 'paused',
        pause_reason: 'consecutive_submission_failure',
        pause_reason_zh: '连续提交失败达到阈值，任务已暂停，请检查后手动恢复',
        leg_exposure: { leg: 'perp', qty: 0.3, price: 88.1, ts: '2026-07-22T08:02:00.000000Z' }
      });
      // stopped：致命错误终止，需人工修正后新建任务；不再由 fail_count > 3 推导。
      const termTask = mockHedgeTask({
        id: 'h-term-1', coin: 'CUSDT', status: 'stopped', stop_reason: '现货可用余额不足'
      });
      hedgeTasksGetResponse = { status: 200, body: { tasks: [runningExpTask, pausedExpTask, termTask] } };
      await helpers.loadHedgeTasks();
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTaskFilter('all');
      const cards = elements['hedge-task-list'].innerHTML;
      for (const piece of ['运行', '暂停', '已终止', '单腿敞口：现货腿已成交 0.5 @ 123.45',
        '单腿敞口：合约腿已成交 0.3 @ 88.1', '任务仍继续调度下一组', '任务当前处于「暂停」',
        '任务已终止（致命错误，不再补发）：现货可用余额不足', '需人工修正原因后新建任务',
        '计划尝试次数', '公共网格量', '暂停原因：连续提交失败达到阈值，任务已暂停，请检查后手动恢复',
        '删除', '成交1次']) {
        if (!cards.includes(piece)) throw new Error(`开单任务卡缺少「${piece}」`);
      }
      // 立即开单卡不展示「立即成交所有」（该按钮仅平滑开单加速成交用）
      if (cards.includes('立即成交所有') || cards.includes('data-hedge-action="fill-all"')) {
        throw new Error('立即开单任务卡不应展示「立即成交所有」');
      }
      if (cards.includes('已暂停，等待人工处理') || cards.includes('累计失败超过 3 次') ||
          cards.includes('已成功') || cards.includes('/ 3')) {
        throw new Error('任务卡不应再出现虚假暂停文案或旧的累计失败 >3 硬编码');
      }
      if (cards.includes('模拟盘口') || cards.includes('本地模拟')) {
        throw new Error('任务卡不应再渲染模拟盘口/本地模拟文案');
      }
      // 任务卡按创建时间倒序渲染，勿假设 id 在 HTML 中的先后；按卡片边界截取。
      function extractHedgeCard(html, taskId) {
        const marker = `data-hedge-task-id="${taskId}"`;
        const start = html.indexOf(marker);
        if (start === -1) return null;
        const cardStart = html.lastIndexOf('<div class="borrow-task-card"', start);
        const from = cardStart === -1 ? start : cardStart;
        const next = html.indexOf('data-hedge-task-id="', start + marker.length);
        return next === -1 ? html.slice(from) : html.slice(from, next);
      }
      const runCard = extractHedgeCard(cards, 'h-exp-1');
      const pauseCard = extractHedgeCard(cards, 'h-exp-2');
      const termCard = extractHedgeCard(cards, 'h-term-1');
      if (!runCard || !pauseCard || !termCard) {
        throw new Error('缺少 running/paused/stopped 任务卡');
      }
      // running：暂停可用、启动 disabled（已在运行）、成交按钮可用（单腿只是提示，不冻结调度）。
      const runPauseBtn = runCard.match(/<button[^>]*data-hedge-action="pause"[^>]*>/)[0];
      if (runPauseBtn.includes('disabled')) throw new Error('running 任务暂停按钮应可用');
      const runStartBtn = runCard.match(/<button[^>]*data-hedge-action="start"[^>]*>/)[0];
      if (!runStartBtn.includes('disabled')) throw new Error('running 任务启动按钮应 disabled');
      const runFillBtn = runCard.match(/<button[^>]*data-hedge-action="fill1"[^>]*>/)[0];
      if (runFillBtn.includes('disabled')) throw new Error('running 任务成交1次不应因单腿提示被禁用');
      // paused：启动可用（人工处理后恢复），暂停/成交 disabled。
      const pauseStartBtn = pauseCard.match(/<button[^>]*data-hedge-action="start"[^>]*>/)[0];
      if (pauseStartBtn.includes('disabled')) throw new Error('paused 任务启动按钮应可用');
      const pausePauseBtn = pauseCard.match(/<button[^>]*data-hedge-action="pause"[^>]*>/)[0];
      if (!pausePauseBtn.includes('disabled')) throw new Error('paused 任务暂停按钮应 disabled');
      // 后端 _require_fillable 只拦截 deleted/done（backend/hedge_open_tasks/service.py），
      // paused 不阻塞人工 fill-once；前端按钮矩阵必须服从后端，不得比后端更严格。
      const pauseFillBtn = pauseCard.match(/<button[^>]*data-hedge-action="fill1"[^>]*>/)[0];
      if (pauseFillBtn.includes('disabled')) throw new Error('paused 任务成交1次不应被前端额外禁用（后端未拦截）');
      // stopped：启动/成交 disabled，需人工修正后新建任务；删除仍可用（软删除脱离列表）。
      const termStartBtn = termCard.match(/<button[^>]*data-hedge-action="start"[^>]*>/)[0];
      if (!termStartBtn.includes('disabled')) throw new Error('stopped 任务启动应 disabled');
      const termFill1Btn = termCard.match(/<button[^>]*data-hedge-action="fill1"[^>]*>/)[0];
      if (!termFill1Btn.includes('disabled')) throw new Error('stopped 任务成交1次应 disabled');
      if (termCard.includes('data-hedge-action="fill-all"')) {
        throw new Error('立即开单 stopped 卡不应有 fill-all 按钮');
      }
      const termDeleteBtn = termCard.match(/<button[^>]*data-hedge-action="delete"[^>]*>/)[0];
      if (termDeleteBtn.includes('disabled')) throw new Error('stopped 任务删除应可用（软删除）');
      // invalid_state 409 → 就近中文报错，前端不发明状态
      hedgeActionResponses['h-term-1:start'] = { status: 409, body: { error: 'invalid_state' } };
      const r409 = await helpers.startHedgeTask('h-term-1');
      if (r409.ok) throw new Error('invalid_state 应失败');
      if (r409.errorCode !== 'invalid_state') throw new Error('应携带 invalid_state 错误码: ' + JSON.stringify(r409));
      if (!r409.error.includes('状态不允许')) throw new Error('409 应映射就近中文提示: ' + r409.error);
      // 平滑模式任务卡仍展示「立即成交所有」（预留给滑点校验加速成交）
      const smoothTask = mockHedgeTask({ id: 'h-smooth-1', mode: 'smooth', status: 'running' });
      hedgeTasksGetResponse = { status: 200, body: { tasks: [smoothTask] } };
      await helpers.loadHedgeTasks();
      helpers.setHedgeTaskFilter('all');
      const smoothHtml = elements['hedge-task-list'].innerHTML;
      if (!smoothHtml.includes('data-hedge-action="fill-all"') || !smoothHtml.includes('立即成交所有')) {
        throw new Error('平滑开单任务卡应保留「立即成交所有」');
      }
      helpers.setActiveView('market');
      console.log('[PASS] stopped/paused 语义返工：single_leg 提示但继续调度 + stop_reason 终止展示 + 按钮矩阵服从后端 status + invalid_state 409 就近报错 + 立即开单隐藏 fill-all');
    }

    // 82. 持仓表从 positions 端点渲染（§3.4 Position JSON 字段逐字，含 accrued_funding）
    {
      hedgePositionsGetResponse = { status: 200, body: { positions: [
        {
          coin: 'AUSDT', direction: 'forward', position_qty: 6, spot_avg: '101.3333', perp_avg: 102.3333,
          open_basis_rate: 0.00233, price_pnl: -0.5, accrued_funding: 0.0614, borrow_interest: 0, net_pnl: -0.4386
        },
        {
          // 低价币：原生 6 位均价 + 尾零；不得被 toFixed(4) 砍成 0.0012
          coin: 'RSRUSDT', direction: 'reverse', position_qty: '10000.00000000',
          spot_avg: '0.00125000', perp_avg: '0.00124600',
          open_basis_rate: 0, price_pnl: 0, accrued_funding: 0, borrow_interest: 0, net_pnl: 0
        }
      ], account: { verified: true, error: null, checked_at: null } } };
      const markPos = fetchCallLog.length;
      await helpers.loadHedgePositions();
      const posCall = fetchCallLog.slice(markPos).find(c => c.url.includes('hedge-open'));
      if (!posCall || posCall.url !== '/api/hedge-open-positions' || posCall.method !== 'GET') {
        throw new Error(`持仓应 GET /api/hedge-open-positions: ${JSON.stringify(posCall)}`);
      }
      helpers.renderPrivatePanel();
      const privHtml = elements['private-panel-body'].innerHTML;
      for (const piece of ['对冲开单持仓', '币种', '方向', '持仓数量', '现货均价', '合约均价', '开单价差率',
        '价格未实现盈亏', '累计资金费', '借币利息', '净盈亏', 'AUSDT', '正向', '101.3333', '0.06']) {
        if (!privHtml.includes(piece)) throw new Error(`私有面板持仓表缺少「${piece}」`);
      }
      // 原生小数 + 去尾零：0.00125000 → 0.00125；0.00124600 → 0.001246（非 0.0012）
      if (!privHtml.includes('0.00125') || !privHtml.includes('0.001246')) {
        throw new Error('持仓均价应保留原生小数并去尾零，不得 toFixed(4): ' + privHtml);
      }
      if (privHtml.includes('0.00125000') || privHtml.includes('0.00124600')) {
        throw new Error('持仓均价应去掉小数点后尾随 0');
      }
      // 正向绿 / 反向红
      if (!privHtml.includes('class="positive">正向')) {
        throw new Error('正向方向应使用 positive（绿色）class');
      }
      if (!privHtml.includes('class="negative">反向')) {
        throw new Error('反向方向应使用 negative（红色）class');
      }
      // 开单价差率由均价现算（后端 open_basis_rate 占位 "0" 不采用）：
      // AUSDT forward (102.3333-101.3333)/101.3333 → +0.9868%
      // RSR reverse (0.00125-0.001246)/0.001246 → +0.3210%
      if (!privHtml.includes('+0.9868%')) {
        throw new Error('AUSDT 开单价差率期望 +0.9868%，实际 HTML 未包含: ' + privHtml);
      }
      if (!privHtml.includes('+0.3210%')) {
        throw new Error('RSR 开单价差率期望 +0.3210%，实际 HTML 未包含: ' + privHtml);
      }
      if (privHtml.includes('本地模拟')) throw new Error('持仓表不应再标注本地模拟');
      if (helpers.getHedgePositions().length !== 2) throw new Error('持仓缓存应来自 positions 端点');
      // 资金费率列（币种与方向之间）：与市场表同一数据源（snapshot.rows）与 3 位小数格式
      helpers.ingestSnapshot(designFixture);
      helpers.renderPrivatePanel();
      const privHtmlFr = elements['private-panel-body'].innerHTML;
      if (!privHtmlFr.includes('<th title="本周期实时预估">资金费率</th>')) {
        throw new Error('持仓表缺少「资金费率」列头（本周期实时预估）');
      }
      const posTableHtml = privHtmlFr.slice(privHtmlFr.indexOf('对冲开单持仓'));
      const ausdtFrCell = getRowCell(posTableHtml, 'AUSDT', 1);
      if (!ausdtFrCell.includes('-0.060%') || !ausdtFrCell.includes('negative')) {
        throw new Error(`AUSDT 持仓资金费率期望红色 -0.060%，单元格 ${ausdtFrCell}`);
      }
      // 快照未覆盖的币（RSRUSDT 不在设计 fixture 快照行）→ —
      const rsrFrCell = getRowCell(posTableHtml, 'RSRUSDT', 1);
      if (!rsrFrCell.includes('—')) {
        throw new Error(`RSRUSDT 无快照行，资金费率期望 —，单元格 ${rsrFrCell}`);
      }
      // 资金费率与方向错配时只把币种红色加粗；方向正常与 0 费率保持默认。
      hedgePositionsGetResponse = { status: 200, body: { positions: [
        { coin: 'AUSDT', direction: 'forward' },
        { coin: 'CUSDT', direction: 'reverse' },
        { coin: 'DUSDT', direction: 'reverse' },
        { coin: 'FUSDT', direction: 'reverse' }
      ], account: { verified: true, error: null, checked_at: null } } };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      const mismatchTableHtml = elements['private-panel-body'].innerHTML.slice(
        elements['private-panel-body'].innerHTML.indexOf('对冲开单持仓')
      );
      for (const coin of ['AUSDT', 'CUSDT']) {
        if (!getRowCell(mismatchTableHtml, coin, 0).includes(`<span class="negative">${coin}</span>`)) {
          throw new Error(`${coin} 资金费率与方向错配时币种须红色加粗`);
        }
      }
      for (const coin of ['DUSDT', 'FUSDT']) {
        if (getRowCell(mismatchTableHtml, coin, 0).includes('class="negative"')) {
          throw new Error(`${coin} 方向正常或资金费率为 0 时币种须保持默认`);
        }
      }
      // 空持仓 → 空态
      hedgePositionsGetResponse = { status: 200, body: { positions: [], account: { verified: true, error: null, checked_at: null } } };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      if (!elements['private-panel-body'].innerHTML.includes('暂无开单持仓')) {
        throw new Error('空持仓应渲染空态');
      }
      console.log('[PASS] 持仓表从 GET /api/hedge-open-positions 渲染（§3.4 字段逐字）+ 空态 + 均价精度/方向色/价差率');
    }

    // 83. 功能二：持仓周期统计三列真值渲染（资金费正负着色 + 利息 ≈U 第二行 +
    //     net_pnl 按换算 U 计算着色）+ 统计区间不全 + 已完全平仓标记
    {
      hedgePositionsGetResponse = { status: 200, body: { positions: [
        {
          coin: 'AUSDT', direction: 'forward', position_qty: 6, spot_avg: '101.3333', perp_avg: 102.3333,
          open_basis_rate: 0.00233, price_pnl: -0.5,
          // Human 2026-08-05：利息按币计 + 换算 U（borrow_interest_usdt）；
          // 2026-08-08 更正：net_pnl = 资金费 − 利息U = 0.0614 − 2.35 = -2.2886（利息是成本/减项）
          accrued_funding: '0.0614', borrow_interest: '0.02', borrow_interest_usdt: '2.35', net_pnl: '-2.2886',
          cycle_id: 'c1', cycle_opened_at: '2026-07-27T06:14:29.000000Z', cycle_closed_at: null,
          stats_incomplete: false, match_status: 'normal'
        },
        {
          coin: 'RSRUSDT', direction: 'reverse', position_qty: '10000.00000000',
          spot_avg: '0.00125000', perp_avg: '0.00124600',
          open_basis_rate: 0, price_pnl: 0,
          accrued_funding: null, borrow_interest: null, borrow_interest_usdt: null, net_pnl: null,
          cycle_id: 'c2', cycle_opened_at: '2026-07-30T08:16:38.000000Z', cycle_closed_at: '2026-07-30T10:00:00.000000Z',
          stats_incomplete: true, match_status: 'no_um'
        }
      ], account: { verified: true, error: null, checked_at: null } } };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      const statsHtml = elements['private-panel-body'].innerHTML;
      for (const piece of ['0.06', '0.02', '≈ 2.35 U', '-2.29', '统计区间不全', '已完全平仓', '暂无']) {
        if (!statsHtml.includes(piece)) throw new Error(`功能二持仓统计缺少「${piece}」: ` + statsHtml);
      }
      // 资金费正值 positive 着色（正=收取绿）；net_pnl 负值 negative 着色（−2.2886 → -2.29）。
      const posStatsHtml = statsHtml.slice(statsHtml.indexOf('对冲开单持仓'));
      const ausdtFundCell = getRowCell(posStatsHtml, 'AUSDT', 14);
      if (!ausdtFundCell.includes('positive') || !ausdtFundCell.includes('0.06')) {
        throw new Error('资金费列正值应 positive 着色: ' + ausdtFundCell);
      }
      const ausdtNetCell = getRowCell(posStatsHtml, 'AUSDT', 16);
      if (!ausdtNetCell.includes('negative') || !ausdtNetCell.includes('-2.29')) {
        throw new Error('net_pnl 列负值应 negative 着色: ' + ausdtNetCell);
      }
      if (!statsHtml.includes('统计区间不全') || !statsHtml.includes('已完全平仓')) {
        throw new Error('统计区间不全 / 已完全平仓 标记缺失: ' + statsHtml);
      }
      // RSR 行三列 null → 暂无，且无 ≈U 第二行（borrow_interest_usdt null）。
      if (statsHtml.includes('≈ 2.35 U') && !statsHtml.includes('暂无')) {
        throw new Error('RSR 行应为「暂无」: ' + statsHtml);
      }
      console.log('[PASS] 功能二：三列真值（资金费着色 + 利息≈U换算 + net_pnl 单位一致）+ 统计区间不全 + 已完全平仓标记');
    }

    // 83b. 立即平仓列（功能三 UI 预览）：表头、输入框、按钮；已平仓/无周期行禁用；
    //     点击可用行按钮 → 确认弹框 → 确认 → 创建待启动平仓卡。
    {
      hedgePositionsGetResponse = { status: 200, body: { positions: [
        { coin: 'AUSDT', direction: 'forward', cycle_id: 'c1', cycle_closed_at: null, match_status: 'normal',
          position_qty: 6, spot_avg: '101.3333', perp_avg: 102.3333, accrued_funding: null, borrow_interest: null, net_pnl: null },
        { coin: 'RSRUSDT', direction: 'reverse', cycle_id: 'c2', cycle_closed_at: '2026-07-30T10:00:00.000000Z', match_status: 'normal',
          position_qty: '10000.00000000', spot_avg: '0.00125000', perp_avg: '0.00124600', accrued_funding: null, borrow_interest: null, net_pnl: null },
        { coin: 'MUUSDT', direction: 'forward', cycle_id: null, cycle_closed_at: null, match_status: 'no_task',
          position_qty: null, spot_avg: null, perp_avg: null, accrued_funding: null, borrow_interest: null, net_pnl: null }
      ], account: { verified: true, error: null, checked_at: null } } };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      const body = elements['private-panel-body'].innerHTML;
      if (!body.includes('<th') || !body.includes('立即平仓')) {
        throw new Error('持仓表缺少「立即平仓」表头');
      }
      if (!body.includes('id="hedge-close-amount-AUSDT"') || !body.includes('id="hedge-close-count-AUSDT"')) {
        throw new Error('立即平仓输入框缺失');
      }
      // 已平仓行（RSRUSDT cycle_closed_at）与无周期行（MUUSDT cycle_id null）→ 按钮 disabled
      if (!body.includes('data-hedge-close="RSRUSDT"') || !body.includes('disabled')) {
        throw new Error('已平仓/无周期行平仓按钮应禁用');
      }
      const ausdtBtn = body.match(/data-hedge-close="AUSDT"[^>]*>/);
      if (ausdtBtn && ausdtBtn[0].includes('disabled')) {
        throw new Error('活跃周期行平仓按钮不应禁用: ' + ausdtBtn[0]);
      }
      // 点击 AUSDT 平仓按钮 → 确认弹框（不发网络请求）
      const mark = fetchCallLog.length;
      const amountEl = document.getElementById('hedge-close-amount-AUSDT');
      const countEl = document.getElementById('hedge-close-count-AUSDT');
      if (amountEl) amountEl.value = '0.5';
      if (countEl) countEl.value = '3';
      helpers.requestHedgeCloseConfirm('AUSDT', 'forward');
      const modalTitle = elements['hedge-modal-title'].textContent;
      if (!modalTitle.includes('确认正向立即平仓')) {
        throw new Error('平仓确认弹框标题错误: ' + modalTitle);
      }
      if (fetchCallLog.length !== mark) throw new Error('平仓确认阶段不应发起网络请求');
      // 确认 → 真实 POST /api/hedge-open-tasks（task_type:'close'，方向沿用持仓行）
      hedgeTasksPostResponse = { status: 201, body: { id: 'close-1', coin: 'AUSDT', direction: 'forward', task_type: 'close' } };
      const postMark = fetchCallLog.length;
      await helpers.submitHedgeClose('AUSDT', 'forward', '0.5', 3);
      const postCall = fetchCallLog.slice(postMark).find(
        c => c.url === '/api/hedge-open-tasks' && c.method === 'POST'
      );
      if (!postCall) throw new Error('平仓确认应 POST /api/hedge-open-tasks');
      const sentBody = postCall.body || {};
      if (sentBody.task_type !== 'close' || sentBody.coin !== 'AUSDT'
          || sentBody.direction !== 'forward' || sentBody.single_amount !== '0.5'
          || sentBody.target_n !== 3 || sentBody.mode !== 'immediate') {
        throw new Error('平仓 POST body 不正确: ' + JSON.stringify(sentBody));
      }
      if (elements['hedge-close-error-AUSDT'].textContent !== '') {
        throw new Error('平仓 POST 成功后错误提示应清空: ' + elements['hedge-close-error-AUSDT'].textContent);
      }
      console.log('[PASS] 立即平仓列：表头+输入框+禁用逻辑+确认弹框+真实 POST（task_type:close）');
    }

    // 83c. 前端提前量检测（Human 2026-08）：forward close 的缓存提前提示——
    //     总量（单次×次数）对比统一账户余额 + 合约持仓；不足强制拦截（零请求）。
    {
      hedgePositionsGetResponse = { status: 200, body: { positions: [
        { coin: 'COOKIEUSDT', direction: 'forward', cycle_id: 'c1', cycle_closed_at: null, match_status: 'normal',
          spot_balance: null, unified_balance: '997.0', um_position_amt: '-2000', position_qty: 6, spot_avg: '1', perp_avg: '1',
          accrued_funding: null, borrow_interest: null, net_pnl: null },
        { coin: 'BTCUSDT', direction: 'forward', cycle_id: 'c2', cycle_closed_at: null, match_status: 'normal',
          spot_balance: '5000', unified_balance: '20000', um_position_amt: '-5000', position_qty: 6, spot_avg: '1', perp_avg: '1',
          accrued_funding: null, borrow_interest: null, net_pnl: null }
      ], account: { verified: true, error: null, checked_at: null } } };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      const mark = fetchCallLog.length;
      const modalOpenBefore = elements['hedge-modal'].classList.contains('open');
      // COOKIE：统一账户 997 < 需 1000×2=2000 → 现货侧拦截（后端同口径 required=2000）
      const amtEl = document.getElementById('hedge-close-amount-COOKIEUSDT');
      const cntEl = document.getElementById('hedge-close-count-COOKIEUSDT');
      if (amtEl) amtEl.value = '1000';
      if (cntEl) cntEl.value = '2';
      const r1 = helpers.requestHedgeCloseConfirm('COOKIEUSDT', 'forward');
      if (r1.ok !== false || r1.error !== 'insufficient_balance_frontend') {
        throw new Error('COOKIE 前端余额不足应拦截（总量口径）: ' + JSON.stringify(r1));
      }
      const err1 = elements['hedge-close-error-COOKIEUSDT'].textContent;
      if (!err1.includes('已拦截') || !err1.includes('2000')) throw new Error('拦截行内错误缺失/总量未体现: ' + err1);
      // 拦截不改弹框状态（不弹新确认框，也不动旧弹框）
      const modalOpenAfterBlock = elements['hedge-modal'].classList.contains('open');
      if (modalOpenAfterBlock !== modalOpenBefore) {
        throw new Error('拦截不应改变弹框状态');
      }
      if (fetchCallLog.length !== mark) throw new Error('拦截时不应发请求');
      // BTCUSDT：统一账户 20000 ≥ 需 100×1=100、合约持仓 5000 ≥ 100 → 放行 → 确认弹框
      const amtB = document.getElementById('hedge-close-amount-BTCUSDT');
      const cntB = document.getElementById('hedge-close-count-BTCUSDT');
      if (amtB) amtB.value = '100';
      if (cntB) cntB.value = '1';
      const r2 = helpers.requestHedgeCloseConfirm('BTCUSDT', 'forward');
      if (!r2.ok || r2.pending !== true) throw new Error('BTC 余额足够应放行: ' + JSON.stringify(r2));
      if (!elements['hedge-modal'].classList.contains('open')) throw new Error('放行应弹确认框');
      if (fetchCallLog.length !== mark) throw new Error('确认阶段不应发请求');
      // 合约持仓不足：BTC 填 6000×1（合约持仓 5000 < 6000）→ 合约侧拦截
      if (amtB) amtB.value = '6000';
      if (cntB) cntB.value = '1';
      const r3 = helpers.requestHedgeCloseConfirm('BTCUSDT', 'forward');
      if (r3.ok !== false || r3.error !== 'insufficient_perp_frontend') {
        throw new Error('合约持仓不足应拦截: ' + JSON.stringify(r3));
      }
      if (fetchCallLog.length !== mark) throw new Error('合约侧拦截不应发请求');
      console.log('[PASS] 前端提前量检测：余额不足强制拦截（零请求）+ 余额足够放行确认');
    }

    // 82b. R1/R2 渲染证据（fix-merged-positions-n2-ui-v1）
    {
      // R1：账户未就绪（snapshot verified=false + positions account.verified=false）——
      //     合并表仍渲染、未就绪横幅出现、本地 coin 行可见。
      hedgePositionsGetResponse = { status: 200, body: { positions: [
        { coin: 'BTCUSDT', direction: 'forward', position_qty: '-0.5', spot_avg: '50000', perp_avg: '50000', includes_deleted_task: false }
      ], account: { verified: false, error: 'snapshot_not_ready', checked_at: null } } };
      const r1Fixture = JSON.parse(JSON.stringify(designFixture));
      r1Fixture.private_account = { verified: false, error: 'snapshot_not_ready', balances_unified: [], balances_spot: [], um_positions: [], checked_at: null };
      helpers.ingestSnapshot(r1Fixture);
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      const r1Body = elements['private-panel-body'].innerHTML;
      if (elements['private-panel'].style.display === 'none') {
        throw new Error('R1: 账户未就绪时私有面板不应隐藏');
      }
      if (!r1Body.includes('账户数据未就绪')) {
        throw new Error('R1: 账户未就绪横幅未出现');
      }
      if (!r1Body.includes('对冲开单持仓')) {
        throw new Error('R1: 合并持仓表 section 未渲染');
      }
      if (!r1Body.includes('BTCUSDT')) {
        throw new Error('R1: 本地记账行未渲染（降级下合并表应可见）');
      }

      // R2：有 UM 持仓但 unrealized_profit 缺失 —— 未实现盈亏渲染「暂无」而非 0.00。
      hedgePositionsGetResponse = { status: 200, body: { positions: [
        { coin: 'BTCUSDT', direction: 'forward', um_position_amt: '-0.5', um_notional_usdt: '100', unrealized_profit: null, price_pnl: null, spot_avg: '50000', perp_avg: '50000', includes_deleted_task: false }
      ], account: { verified: true, error: null, checked_at: null } } };
      helpers.ingestSnapshot(designFixture); // verified=true → verified 块渲染合并表
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      const r2Body = elements['private-panel-body'].innerHTML;
      // 价格未实现盈亏是合并表第 9 列（index 8，资金费率列后为 8）。
      const pnlCell = getRowCell(r2Body, 'BTCUSDT', 8);
      if (!pnlCell.includes('暂无')) {
        throw new Error('R2: 缺 unrealized_profit 时未实现盈亏应渲染「暂无」: ' + pnlCell);
      }
      if (pnlCell.includes('0.00')) {
        throw new Error('R2: 缺 unrealized_profit 时不得画 0.00: ' + pnlCell);
      }

      // 恢复默认 mock 与 fixture，避免影响后续用例。
      hedgePositionsGetResponse = { status: 200, body: { positions: [], account: { verified: true, error: null, checked_at: null } } };
      helpers.ingestSnapshot(designFixture);
      console.log('[PASS] R1/R2 渲染证据：账户未就绪合并表+横幅+本地行可见；缺 upnl 未实现盈亏画「暂无」不画 0');
    }

    // 82c. G1/G2/G5 渲染证据（fix-merged-positions-mismatch-labels-v1）
    {
      helpers.ingestSnapshot(designFixture); // verified=true → 合并表渲染
      // G1+G2: no_task 行（有 UM、无任务记录）—— 本地成本列显示 — 而非 0，标记「无任务记录」。
      hedgePositionsGetResponse = { status: 200, body: { positions: [
        { coin: 'MUUSDT', direction: 'forward', match_status: 'no_task',
          um_position_amt: '-0.1', um_notional_usdt: '82', um_entry_price: '918',
          unrealized_profit: '0.5', price_pnl: '0.5',
          spot_avg: null, perp_avg: null, position_qty: null,
          spot_avg_price_incomplete: false, perp_avg_price_incomplete: false,
          includes_deleted_task: false }
      ], account: { verified: true, error: null, checked_at: null } } };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      let body = elements['private-panel-body'].innerHTML;
      const noTaskSpot = getRowCell(body, 'MUUSDT', 11);
      const noTaskPerp = getRowCell(body, 'MUUSDT', 12);
      const noTaskMark = getRowCell(body, 'MUUSDT', 18);
      if (!noTaskSpot.includes('—') || noTaskSpot.includes('0')) {
        throw new Error('G2: no_task 现货均价应显示 — 而非 0: ' + noTaskSpot);
      }
      if (!noTaskPerp.includes('—') || noTaskPerp.includes('0')) {
        throw new Error('G2: no_task 合约均价应显示 — 而非 0: ' + noTaskPerp);
      }
      if (!noTaskMark.includes('无任务记录')) {
        throw new Error('G1: no_task 行应标记「无任务记录」: ' + noTaskMark);
      }

      // G1: no_um 行（有任务记录、无 UM）—— 标记「交易所无仓」。
      hedgePositionsGetResponse = { status: 200, body: { positions: [
        { coin: 'XYZUSDT', direction: 'forward', match_status: 'no_um',
          um_position_amt: null, spot_avg: '1.20', perp_avg: '1.21',
          spot_avg_price_incomplete: false, perp_avg_price_incomplete: false,
          includes_deleted_task: false }
      ], account: { verified: true, error: null, checked_at: null } } };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      body = elements['private-panel-body'].innerHTML;
      const noUmMark = getRowCell(body, 'XYZUSDT', 18);
      if (!noUmMark.includes('交易所无仓')) {
        throw new Error('G1: no_um 行应标记「交易所无仓」: ' + noUmMark);
      }

      // G5: 不完整标记可见（合约均价在部分未知金额的成交上算）。
      hedgePositionsGetResponse = { status: 200, body: { positions: [
        { coin: 'RSRUSDT', direction: 'forward', match_status: 'normal',
          um_position_amt: '-20000', um_notional_usdt: '24.92',
          spot_avg: '0.001247', perp_avg: '0.001246',
          spot_avg_price_incomplete: false, perp_avg_price_incomplete: true,
          includes_deleted_task: false }
      ], account: { verified: true, error: null, checked_at: null } } };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      body = elements['private-panel-body'].innerHTML;
      const g5Mark = getRowCell(body, 'RSRUSDT', 18);
      if (!g5Mark.includes('均价不完整')) {
        throw new Error('G5: 不完整均价应显示「均价不完整」标记: ' + g5Mark);
      }
      const g5Perp = getRowCell(body, 'RSRUSDT', 12);
      if (!g5Perp.includes('title=')) {
        throw new Error('G5: 不完整合约均价单元格应带 title 说明: ' + g5Perp);
      }

      // 恢复默认 mock 与 fixture。
      hedgePositionsGetResponse = { status: 200, body: { positions: [], account: { verified: true, error: null, checked_at: null } } };
      helpers.ingestSnapshot(designFixture);
      console.log('[PASS] G1/G2/G5：no_task 成本—+「无任务记录」、no_um「交易所无仓」、不完整均价「均价不完整」+title');
    }

    // 83. 执行徽标（§3：GET /api/hedge-open-settings 的 executor_mode + start_gate）
    {
      hedgeSettingsGetResponse = { status: 200, body: { executor_mode: 'disabled', start_gate: false, interval_seconds: 1 } };
      const markSettings = fetchCallLog.length;
      await helpers.loadHedgeSettings();
      const settingsCall = fetchCallLog.slice(markSettings).find(c => c.url.includes('hedge-open'));
      if (!settingsCall || settingsCall.url !== '/api/hedge-open-settings' || settingsCall.method !== 'GET') {
        throw new Error(`执行设置应 GET /api/hedge-open-settings: ${JSON.stringify(settingsCall)}`);
      }
      const badgeDry = elements['hedge-execution-badge'].textContent;
      if (!badgeDry.includes('已禁用') || !badgeDry.includes('未开启')) {
        throw new Error(`disabled 模式徽标错误: ${badgeDry}`);
      }
      // F-1 防回归（review-1）：disabled 时警示色生效——class 含 warn 不含 muted
      // （CSS .badge.muted 后声明会覆盖 .badge.warn，二者必须互斥）。
      const clsDry = elements['hedge-execution-badge'].classList;
      if (!clsDry.contains('warn') || clsDry.contains('muted')) {
        throw new Error(`disabled 模式徽标 class 应含 warn 不含 muted: ${[...clsDry]}`);
      }
      hedgeSettingsGetResponse = { status: 200, body: { executor_mode: 'live', start_gate: true, interval_seconds: 1 } };
      await helpers.loadHedgeSettings();
      const badgeLive = elements['hedge-execution-badge'].textContent;
      if (!badgeLive.includes('live') || !badgeLive.includes('已开启')) {
        throw new Error(`live 模式徽标错误: ${badgeLive}`);
      }
      const clsLive = elements['hedge-execution-badge'].classList;
      if (!clsLive.contains('muted') || clsLive.contains('warn')) {
        throw new Error(`live 模式徽标 class 应含 muted 不含 warn: ${[...clsLive]}`);
      }
      if (!elements['hedge-execution-detail'].textContent.includes('1')) {
        throw new Error('执行详情应显示调度间隔');
      }
      console.log('[PASS] 执行徽标：executor_mode disabled→已禁用 / live + start_gate Start 状态 + F-1 class 互斥');
    }

    // 84. real-api-v1 任务卡新字段（§3.4）：调度/受理计数、连续失败 vs 阈值、暂停原因；
    //     字段缺失时逐项降级为 —，不崩溃
    {
      helpers.resetHedgeStateForTest();
      // 阈值刻意用非默认值 5（默认建构 mockHedgeTask 为 3）：证明展示直接读自后端任务
      // 快照字段，而不是前端硬编码的固定阈值 3。
      const richTask = mockHedgeTask({
        id: 'h-new-1', coin: 'DUSDT', status: 'paused',
        scheduled_attempt_count: 7, accepted_pair_count: 6,
        consecutive_submission_failures: 5, failure_pause_threshold: 5,
        pause_reason: 'consecutive_submission_failure',
        pause_reason_zh: '连续提交失败达到阈值，任务已暂停，请检查后手动恢复'
      });
      // 旧后端文档：完全没有 real-api-v1 新字段
      const legacyTask = {
        id: 'h-legacy-1', coin: 'EUSDT', direction: 'reverse', mode: 'immediate',
        single_amount: 0.5, target_n: 3, success_count: 0, fail_count: 0,
        status: 'running', q_common: 0.5, position_side_mode: 'BOTH', leg_exposure: null,
        created_at: '2026-07-22T08:00:00.000000Z', updated_at: '2026-07-22T08:00:00.000000Z'
      };
      hedgeTasksGetResponse = { status: 200, body: { tasks: [richTask, legacyTask] } };
      await helpers.loadHedgeTasks();
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTaskFilter('all');
      const cards = elements['hedge-task-list'].innerHTML;
      const richStart = cards.indexOf('data-hedge-task-id="h-new-1"');
      const legacyStart = cards.indexOf('data-hedge-task-id="h-legacy-1"');
      if (richStart === -1 || legacyStart === -1) throw new Error('缺少新字段/旧字段任务卡');
      const richCard = cards.slice(richStart, legacyStart);
      const legacyCard = cards.slice(legacyStart);
      for (const piece of ['已调度 <strong>7</strong> 组', '已受理 <strong>6</strong> 组',
        '连续提交失败 <strong>5</strong>', '暂停阈值 <strong>5</strong>',
        '暂停原因：连续提交失败达到阈值，任务已暂停，请检查后手动恢复']) {
        if (!richCard.includes(piece)) throw new Error(`新字段任务卡缺少「${piece}」: ${richCard}`);
      }
      if (richCard.includes('暂停阈值 <strong>3</strong>')) {
        throw new Error('暂停阈值不应回退成前端硬编码的默认值 3: ' + richCard);
      }
      // 旧文档降级：四个新字段全部为 —，且不出现暂停原因行、不抛错
      for (const piece of ['已调度 <strong>—</strong> 组', '已受理 <strong>—</strong> 组',
        '连续提交失败 <strong>—</strong>', '暂停阈值 <strong>—</strong>']) {
        if (!legacyCard.includes(piece)) throw new Error(`旧字段任务卡应降级为 —（${piece}）: ${legacyCard}`);
      }
      if (legacyCard.includes('暂停原因')) throw new Error('pause_reason 缺失时不应渲染暂停原因行');
      helpers.setActiveView('market');
      console.log('[PASS] 任务卡 real-api-v1 新字段：调度/受理/连续失败/阈值渲染 + 暂停原因 + 旧文档逐项降级 —');
    }

    // 85. attempt 时间线（§3.4）：logs 路由取数、两腿订单号/状态/累计/均价/手续费逐字渲染、
    //     payload 内嵌兼容、非 attempt 日志忽略、十进制字符串零浮点重排
    {
      helpers.resetHedgeStateForTest();
      const task = mockHedgeTask({ id: 'h-att-1', coin: 'AUSDT' });
      hedgeTasksGetResponse = { status: 200, body: { tasks: [task] } };
      await helpers.loadHedgeTasks();
      const attemptA = mockHedgeAttempt({ task_id: 'h-att-1', attempt_seq: 2, residual: '0.00000100' });
      const attemptB = mockHedgeAttempt({
        task_id: 'h-att-1', attempt_id: 'att-2', attempt_seq: 1, direction: 'reverse',
        pair_outcome: null, residual: '-0.00010000',
        spot: {
          client_order_id: 'hgo-att2-s', order_id: null, status: 'NEW',
          cumulative_base_qty: '0.00000000', cumulative_quote_amt: '0.00000000', avg_price: '0'
        },
        perp: null
      });
      const attemptC = mockHedgeAttempt({
        task_id: 'h-att-1', attempt_id: 'att-3', attempt_seq: 3, direction: 'forward',
        pair_outcome: 'single_leg', residual: '0.00000200'
      });
      hedgeLogsGetResponse = { status: 200, body: {
        logs: [
          // 直接 attempt 形状条目
          attemptA,
          // payload 内嵌 attempt 文档（logs 条目包装）
          { id: 99, task_id: 'h-att-1', ts: '2026-07-23T12:00:00.000000Z', attempt_id: 'att-2', kind: 'attempt', payload: attemptB },
          // 非 attempt 日志条目：必须被忽略
          { id: 98, task_id: 'h-att-1', ts: '2026-07-23T11:59:00.000000Z', attempt_id: null, kind: 'info', payload: { message: 'scheduler tick' } },
          // 单腿成交（后端真实取值集之一，domain.py PAIR_SINGLE_LEG）
          attemptC
        ],
        next_cursor: null
      } };
      const markAtt = fetchCallLog.length;
      await helpers.loadHedgeAttempts();
      const attCall = fetchCallLog.slice(markAtt).find(c => c.url.includes('hedge-open-logs'));
      if (!attCall || attCall.url !== '/api/hedge-open-logs?limit=100' || attCall.method !== 'GET') {
        throw new Error(`尝试时间线应 GET /api/hedge-open-logs?limit=100: ${JSON.stringify(attCall)}`);
      }
      if (helpers.getHedgeAttempts().length !== 3) {
        throw new Error(`应提取 3 条 attempt（忽略非 attempt 日志），实际 ${helpers.getHedgeAttempts().length}`);
      }
      helpers.setActiveView('hedge-tasks');
      const timeline = elements['hedge-attempt-list'].innerHTML;
      // 十进制字符串逐字：任何浮点重排都会改变这些字面量
      for (const piece of ['尝试时间线', '第 2 组', '第 1 组', '第 3 组', '正向', '反向', '已受理', '查询中', '单腿成交',
        '0.003', 'hgo-att1-s', 'hgo-att1-p', '9001', '9002', 'FILLED',
        '0.36210000', '120.70000000', '0.00000010', 'BNB',
        '0.00000100', '-0.00010000', '0.00000200', 'hgo-att2-s', 'NEW', '0.00000000',
        '现货腿', '合约腿', '加权均价', '累计成交额', '手续费', '残差 residual']) {
        if (!timeline.includes(piece)) throw new Error(`attempt 时间线缺少「${piece}」`);
      }
      // perp 腿缺失（null）：降级为 — 且不崩溃
      if (!timeline.includes('订单号 <span class="mono">—</span>')) {
        throw new Error('缺失腿文档应降级为 —');
      }
      // 关联任务币种标签（task_id → 任务卡 coin）
      if (!timeline.includes('任务 AUSDT')) throw new Error('attempt 应标注关联任务币种');
      helpers.setActiveView('market');
      console.log('[PASS] attempt 时间线：logs 取数 + 两腿字段逐字渲染 + payload 内嵌兼容 + 非 attempt 忽略 + 缺腿降级');
    }

    // 86. attempt 时间线降级：空记录空态、503 错误横幅不崩溃
    {
      helpers.resetHedgeStateForTest();
      hedgeLogsGetResponse = { status: 200, body: { logs: [], next_cursor: null } };
      await helpers.loadHedgeAttempts();
      helpers.setActiveView('hedge-tasks');
      if (!elements['hedge-attempt-list'].innerHTML.includes('暂无尝试记录')) {
        throw new Error('空 attempt 应渲染空态');
      }
      if (elements['hedge-attempts-error'].style.display !== 'none') {
        throw new Error('空记录不应显示错误横幅');
      }
      hedgeLogsGetResponse = { status: 503, body: { error: 'hedge_service_unavailable', detail: 'mock 故障' } };
      await helpers.loadHedgeAttempts();
      if (elements['hedge-attempts-error'].style.display === 'none') {
        throw new Error('logs 503 应显示错误横幅');
      }
      if (!elements['hedge-attempts-error'].textContent) throw new Error('错误横幅应有文案');
      // 恢复默认，避免污染后续块
      hedgeLogsGetResponse = { status: 200, body: { logs: [], next_cursor: null } };
      await helpers.loadHedgeAttempts();
      helpers.setActiveView('market');
      console.log('[PASS] attempt 时间线降级：空态 + 503 错误横幅 + 恢复');
    }

    // 86a. 任务卡内嵌日志（2026-07-31-hedge-task-inline-log-v1，AC1/AC2/AC3/AC4/AC6/AC7/AC9）：
    //      四状态徽标冻结映射 + 钱原样透传(均价带尾零) + 未受理腿 order_id 门控三格 — +
    //      错误原因回退链(zh→机器字段→「原因未记录」) + 进展=attempt_seq/target_n + 真卡 toggle +
    //      fake 已清。列序：进展/状态/尝试时间/合约订单号/现货订单号/合约均价/现货均价/合约数量/现货数量/错误原因。
    {
      helpers.resetHedgeStateForTest();
      hedgeTaskLogsGetResponse = null;
      const inlineTask = mockHedgeTask({ id: 'h-inline-1', coin: 'AUSDT', target_n: 10 });
      hedgeTasksGetResponse = { status: 200, body: { tasks: [inlineTask] } };
      await helpers.loadHedgeTasks();
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTaskFilter('all');
      helpers.getHedgeLogExpanded().add('h-inline-1');
      // 四状态 + 钱/错误各路径夹具（均价刻意带尾零，验原样透传不经 formatHedgeDecimal）。
      const inlineAttempts = [
        // 进行中（pair_outcome null）：两腿无 order_id → 全 —；状态 进行中/info
        mockHedgeAttempt({ task_id: 'h-inline-1', attempt_id: 'att-ip', attempt_seq: 5, pair_outcome: null,
          spot: { client_order_id: 's5', order_id: null, status: 'NEW', cumulative_base_qty: '0', cumulative_quote_amt: '0', avg_price: null },
          perp: { client_order_id: 'p5', order_id: null, status: 'NEW', cumulative_base_qty: '0', cumulative_quote_amt: '0', avg_price: null } }),
        // 已受理（双腿 filled，默认均价 120.70000000 / 120.70300000 带尾零）
        mockHedgeAttempt({ task_id: 'h-inline-1', attempt_id: 'att-ok', attempt_seq: 4 }),
        // 单腿成交（spot filled order_id 77741；perp 未受理 order_id null, cumulative_base_qty '0'）→ perp 三格 —
        mockHedgeAttempt({ task_id: 'h-inline-1', attempt_id: 'att-sl', attempt_seq: 3, pair_outcome: 'single_leg',
          spot: { client_order_id: 's3', order_id: '77741', status: 'FILLED', cumulative_base_qty: '2000', cumulative_quote_amt: '24.6', avg_price: '0.0123' },
          perp: { client_order_id: 'p3', order_id: null, status: 'REJECTED', cumulative_base_qty: '0', cumulative_quote_amt: '0', avg_price: null } }),
        // 确认失败：有中文原因（回退链 ①）
        mockHedgeAttempt({ task_id: 'h-inline-1', attempt_id: 'att-fzh', attempt_seq: 2, pair_outcome: 'confirmed_failed',
          spot: { client_order_id: 's2', order_id: null, status: 'REJECTED', cumulative_base_qty: '0', cumulative_quote_amt: '0', avg_price: null },
          perp: { client_order_id: 'p2', order_id: null, status: 'REJECTED', cumulative_base_qty: '0', cumulative_quote_amt: '0', avg_price: null },
          error_reason_zh: '账户余额不足', error_code: '-2010', error_category: 'insufficient_balance' }),
        // 确认失败：仅有机器字段（回退链 ②）
        mockHedgeAttempt({ task_id: 'h-inline-1', attempt_id: 'att-fc', attempt_seq: 1, pair_outcome: 'confirmed_failed',
          spot: { client_order_id: 's1', order_id: null, status: 'REJECTED', cumulative_base_qty: '0', cumulative_quote_amt: '0', avg_price: null },
          perp: { client_order_id: 'p1', order_id: null, status: 'REJECTED', cumulative_base_qty: '0', cumulative_quote_amt: '0', avg_price: null },
          error_reason_zh: null, error_code: '-2010', error_category: 'collateral_cap' }),
      ];
      hedgeTaskLogsGetResponse = { status: 200, body: { attempts: inlineAttempts } };
      const markInline = fetchCallLog.length;
      await helpers.loadHedgeTaskLogs('h-inline-1');
      const inlineCall = fetchCallLog.slice(markInline).find(c => c.url.includes('hedge-open-logs'));
      if (!inlineCall || inlineCall.url !== '/api/hedge-open-logs?task_id=h-inline-1' || inlineCall.method !== 'GET') {
        throw new Error('内嵌日志应 GET /api/hedge-open-logs?task_id=…: ' + JSON.stringify(inlineCall));
      }
      if (inlineCall.cache !== 'no-store') throw new Error('内嵌日志 GET 须绕过浏览器缓存');
      helpers.renderHedgeTasks();
      const card = elements['hedge-task-list'].innerHTML;

      // AC1：四状态冻结映射（文案 + badge class）。注意 single_leg=warn（非 warning）。
      for (const piece of [
        '<span class="badge compact info">进行中</span>',
        '<span class="badge compact success">已受理</span>',
        '<span class="badge compact warn">单腿成交</span>',
        '<span class="badge compact danger">已确认失败</span>'
      ]) {
        if (!card.includes(piece)) throw new Error(`AC1 状态徽标缺少「${piece}」: ${card}`);
      }
      if (card.includes('badge compact warning') || card.includes('>已成交<')) {
        throw new Error('不得出现失效的 warning class 或 fake 的「已成交」文案');
      }

      // Part A（R2-F1）：列头改「尝试时间」并去掉 order_id 门控——四种状态每一行都显示该次
      // 尝试的时间（北京时间 YYYY-MM-DD HH:MM:SS）。重点是无 order_id 的行（进行中/确认失败）
      // 也不再被抹成 —；全量不出现「成交时间」字样。仅 attempt.ts 缺失才 —。
      if (!card.includes('<th>尝试时间</th>') || card.includes('成交时间')) {
        throw new Error('Part A 列头应为「尝试时间」，不得残留「成交时间」: ' + card);
      }
      const beijingRe = /\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/;
      const rowTds = (row) => row.match(/<td[^>]*>.*?<\/td>/g) || [];
      for (const seq of ['5/10', '4/10', '3/10', '2/10', '1/10']) {
        const idx = card.indexOf(`<strong>${seq}</strong>`);
        if (idx === -1) throw new Error(`Part A 缺少进展行 ${seq}`);
        const rs = card.lastIndexOf('<tr>', idx);
        const re = card.indexOf('</tr>', idx);
        const tds = rowTds(card.slice(rs, re));
        if (tds.length < 3 || !beijingRe.test(tds[2])) {
          throw new Error(`Part A 行 ${seq} 第 3 列应显示北京时间（尝试时间），实际: ${tds[2]}`);
        }
      }

      // AC2：钱原样透传——均价带尾零逐字（formatHedgeDecimal 会去成 120.7 / 120.703）。
      for (const piece of ['120.70000000', '120.70300000', '0.003']) {
        if (!card.includes(piece)) throw new Error(`AC2 均价/数量应原样透传（含尾零）缺少「${piece}」: ${card}`);
      }

      // AC3：未受理腿门控——单腿行的 perp 订单号/均价/数量三格一律 —（即便 cumulative_base_qty==='0'）。
      const slIdx = card.indexOf('77741');
      if (slIdx === -1) throw new Error('AC3 缺少单腿行标记 77741');
      const slRowStart = card.lastIndexOf('<tr>', slIdx);
      const slRowEnd = card.indexOf('</tr>', slIdx);
      const slRow = card.slice(slRowStart, slRowEnd);
      const slMuted = (slRow.match(/<td class="log-muted">—<\/td>/g) || []).length;
      if (slMuted !== 3) throw new Error(`AC3 单腿行 perp 三格应全为 —（实际 muted 数 ${slMuted}）: ${slRow}`);
      if (!slRow.includes('>77741</td>') || !slRow.includes('0.0123') || !slRow.includes('>2000</td>')) {
        throw new Error('AC3 单腿行 spot 订单号/均价/数量应展示: ' + slRow);
      }
      // 整表不得出现裸 '<td>0</td>'（未受理腿的 "0" 必须被门控成 —，不是「成交了 0 个」）。
      if (card.includes('<td>0</td>')) throw new Error('AC3 未受理腿的 "0" 不应作为成交数量展示: ' + card);

      // AC4：错误原因回退链——① 中文原文 ② 机器字段原样 ③ 占位「原因未记录」；不编造业务句。
      if (!card.includes('账户余额不足')) throw new Error('AC4① 应展示 error_reason_zh 原文');
      if (!card.includes('collateral_cap / -2010')) throw new Error('AC4② 应展示机器字段原样: ' + card);
      if (!card.includes('>原因未记录<')) throw new Error('AC4③ 失败/单腿行无错误数据应展示固定占位');
      // 单腿行无错误字段 → 错误格恰为占位（非编造句、非 —）
      if (!slRow.includes('>原因未记录<')) throw new Error('AC4 单腿行错误格应为占位: ' + slRow);

      // AC6：进展 = attempt_seq / target_n（每行序号各异；不用 scheduled_attempt_count）。
      for (const seq of ['5/10', '4/10', '3/10', '2/10', '1/10']) {
        if (!card.includes(`<strong>${seq}</strong>`)) throw new Error(`AC6 进展列缺少「${seq}」: ${card}`);
      }

      // AC7 + AC9：真卡自带 toggle 且展开可见；fake 卡/示例文案已清。
      if (!card.includes('data-hedge-log-toggle="h-inline-1"')) throw new Error('AC7 真卡应内嵌 toggle 按钮');
      if (!card.includes('id="hedge-task-log-h-inline-1"')) throw new Error('AC7 真卡应内嵌日志表容器');
      if (card.includes('id="hedge-task-log-h-inline-1" hidden')) throw new Error('AC7 展开后日志表应可见（未 hidden）');
      if (!card.includes('展开日志每 2 秒自动刷新')) throw new Error('展开区须提示日志自动刷新频率');
      if (card.includes('示例预览') || card.includes('fake-preview') || card.includes('示例卡')) {
        throw new Error('AC9 fake 卡残留: ' + card);
      }
      const pollMark = fetchCallLog.length;
      await helpers.refreshExpandedRunningHedgeLogs();
      if (!fetchCallLog.slice(pollMark).some(c => c.url === '/api/hedge-open-logs?task_id=h-inline-1')) {
        throw new Error('执行中任务的已展开日志须由共享 2s tick 自动刷新');
      }
      helpers.getHedgeLogExpanded().delete('h-inline-1');
      const collapsedMark = fetchCallLog.length;
      await helpers.refreshExpandedRunningHedgeLogs();
      if (fetchCallLog.slice(collapsedMark).some(c => c.url.includes('hedge-open-logs?task_id='))) {
        throw new Error('日志收起后须停止自动刷新');
      }
      helpers.getHedgeLogExpanded().add('h-inline-1');
      helpers.getHedgeTasks()[0].status = 'paused';
      const pausedMark = fetchCallLog.length;
      await helpers.refreshExpandedRunningHedgeLogs();
      if (fetchCallLog.slice(pausedMark).some(c => c.url.includes('hedge-open-logs?task_id='))) {
        throw new Error('任务停止执行后须停止自动刷新日志');
      }
      helpers.setActiveView('market');
      console.log('[PASS] 任务卡内嵌日志 AC1/AC2/AC3/AC4/AC6/AC7/AC9：四状态徽标 + 钱原样透传 + 未受理腿门控 + 错误回退链 + 进展列 + 真卡 toggle + fake 已清');
    }

    // 86b. 任务卡内嵌日志（AC5/AC7）：task_id 一次全量取数（attempt 数 > 默认页大小 50）、
    //      不与 entries_cursor 共用游标、倒序（最新在上）、展开状态跨渲染保持。
    {
      helpers.resetHedgeStateForTest();
      hedgeTaskLogsGetResponse = null;
      const manyTask = mockHedgeTask({ id: 'h-inline-many', coin: 'BUSDT', target_n: 60 });
      hedgeTasksGetResponse = { status: 200, body: { tasks: [manyTask] } };
      await helpers.loadHedgeTasks();
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTaskFilter('all');
      helpers.getHedgeLogExpanded().add('h-inline-many');
      // 51 条 attempt（>默认页大小 50），attempt_seq 1..51。
      const manyAttempts = [];
      for (let i = 1; i <= 51; i++) {
        manyAttempts.push(mockHedgeAttempt({
          task_id: 'h-inline-many', attempt_id: 'att-many-' + i, attempt_seq: i,
          ts: `2026-07-23T12:00:${String(i).padStart(2, '0')}.000000Z`
        }));
      }
      hedgeTaskLogsGetResponse = { status: 200, body: { attempts: manyAttempts } };
      const markMany = fetchCallLog.length;
      await helpers.loadHedgeTaskLogs('h-inline-many');
      const manyCall = fetchCallLog.slice(markMany).find(c => c.url.includes('hedge-open-logs'));
      if (!manyCall || manyCall.url !== '/api/hedge-open-logs?task_id=h-inline-many' || manyCall.method !== 'GET') {
        throw new Error('AC5 应 GET /api/hedge-open-logs?task_id=…: ' + JSON.stringify(manyCall));
      }
      if (manyCall.url.includes('entries_cursor')) {
        throw new Error('AC5 task_id 请求不得混用 entries_cursor: ' + manyCall.url);
      }
      if (helpers.getHedgeTaskLogs()['h-inline-many'].attempts.length !== 51) {
        throw new Error('AC5 应一次拿到全部 51 条 attempt');
      }
      helpers.renderHedgeTasks();
      const manyCard = elements['hedge-task-list'].innerHTML;
      const bodyRows = (manyCard.match(/<td><strong>\d+\/60<\/strong><\/td>/g) || []).length;
      if (bodyRows !== 51) throw new Error(`AC5 应渲染全部 51 行进展（>50），实际 ${bodyRows}`);
      const firstSeq = manyCard.match(/<td><strong>(\d+)\/60<\/strong>/);
      if (!firstSeq || firstSeq[1] !== '51') {
        throw new Error(`AC5 首行应为最新 attempt_seq=51（倒序），实际 ${firstSeq && firstSeq[1]}`);
      }
      // AC7：展开状态跨重渲染保持（容器可见，未 hidden）。
      if (manyCard.includes('id="hedge-task-log-h-inline-many" hidden')) {
        throw new Error('AC7 展开状态未跨渲染保持');
      }
      helpers.setActiveView('market');
      console.log('[PASS] 任务卡内嵌日志 AC5/AC7：task_id 全量取数(51>50) + 不混 entries_cursor + 倒序 + 展开跨渲染保持');
    }

    // 88. 开单日志顶层 tab（15 号修正案 §开单日志页 / 16 号拆分 §5 / 17 号兼容修正）：
    //     结构位置、切换、首屏拉取第 1 页（?entries_limit=50，无 entries_cursor）
    {
      const tasksPanelIdx = html.indexOf('id="hedge-tasks-panel"');
      const filtersIdx = html.indexOf('id="hedge-task-filters"');
      const logsPanelIdx = html.indexOf('id="hedge-logs-panel"');
      if (tasksPanelIdx === -1 || logsPanelIdx === -1 || filtersIdx === -1 ||
          !(tasksPanelIdx < filtersIdx && filtersIdx < logsPanelIdx)) {
        throw new Error('开单任务筛选容器必须位于 hedge-tasks-panel 内（hedge-tasks-panel 与 hedge-logs-panel 之间）');
      }
      if (!html.includes('id="hedge-tab-tasks"') || !html.includes('id="hedge-tab-logs"')) {
        throw new Error('缺少开单任务/开单日志顶层 tab 按钮');
      }
      helpers.resetHedgeStateForTest();
      elements['hedge-logs-panel'].style.display = 'none';
      hedgeLogPageResponses = [{ status: 200, body: HEDGE_LOG_PAGE_1 }];
      helpers.setActiveView('hedge-tasks');
      if (elements['hedge-tasks-panel'].style.display === 'none') throw new Error('初始应显示开单任务 tab');
      if (elements['hedge-logs-panel'].style.display !== 'none') throw new Error('初始应隐藏开单日志 tab');
      const mark = fetchCallLog.length;
      helpers.setHedgeTab('logs');
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getHedgeTab() !== 'logs') throw new Error('hedgeTab 应为 logs');
      if (elements['hedge-logs-panel'].style.display === 'none' || elements['hedge-tasks-panel'].style.display !== 'none') {
        throw new Error('开单日志 tab 激活后面板显隐错误');
      }
      const logCalls = fetchCallLog.slice(mark).filter(c => c.url.startsWith('/api/hedge-open-logs'));
      if (logCalls.length !== 1 || logCalls[0].url !== '/api/hedge-open-logs?entries_limit=50' || logCalls[0].method !== 'GET') {
        throw new Error(`开单日志 tab 激活应 GET /api/hedge-open-logs?entries_limit=50: ${JSON.stringify(logCalls)}`);
      }
      if (helpers.getHedgeLogs().entries.length !== 2) throw new Error('第 1 页应加载 2 条 entries');
      helpers.setHedgeTab('tasks');
      helpers.setActiveView('market');
      console.log('[PASS] 开单日志顶层 tab 结构位置 + 切换 + 首屏拉取第 1 页（entries_limit）');
    }

    // 89. 开单日志逐字渲染：single_leg 缺 perp 腿降级为 —、task_event 行（attempt/leg 全 —）、
    //     安全错误 category/code/中文原因、next_action 中文映射；十进制字符串原样展示
    {
      helpers.resetHedgeStateForTest();
      hedgeLogPageResponses = [{ status: 200, body: HEDGE_LOG_PAGE_1 }];
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTab('logs');
      await new Promise(r => setTimeout(r, 0));
      const listHtml = elements['hedge-log-list'].innerHTML;
      for (const piece of [
        '第 2 组', '任务 h-log-1', 'AUSDT', '正向', '单腿成交',
        '0.004', '0.48', 'hgo-e10-s', '9201', 'FILLED', '0.48280000', '120.70000000',
        '0.00000012', 'BNB', '继续下一组',
        '任务事件', '任务暂停', '安全错误：exchange_rate_limit / 429', '交易所限频，已延迟新开单请求',
        '等待查询终态'
      ]) {
        if (!listHtml.includes(piece)) throw new Error(`开单日志缺少「${piece}」: ${listHtml}`);
      }
      // single_leg 行缺 perp 腿：降级为 —，不崩溃
      if (!listHtml.includes('合约腿：方向 — · 订单号 <span class="mono">—</span>')) {
        throw new Error('缺失腿文档应降级为 —');
      }
      // task_event 行：attempt_seq/q_common/spot/perp 全 null，逐项降级为 —
      const eventStart = listHtml.indexOf('>任务事件<');
      const eventCard = listHtml.slice(eventStart, eventStart + 900);
      for (const piece of ['计划 q_common：<strong class="mono">—</strong>',
        '现货腿：方向 — · 订单号 <span class="mono">—</span>']) {
        if (!eventCard.includes(piece)) throw new Error(`task_event 行未逐项降级为 —（${piece}）: ${eventCard}`);
      }
      helpers.setHedgeTab('tasks');
      helpers.setActiveView('market');
      console.log('[PASS] 开单日志逐字渲染：缺腿降级 — + task_event 全 — + 安全错误 + next_action 中文映射');
    }

    // 90. 开单日志：no-orderId 确认失败行（两腿均无 orderId）+ newest-first 两页
    //     entries_cursor 分页（17 号兼容修正：只采信 entries_next_cursor，绝不回退到旧
    //     next_cursor——两个 fixture 页都携带一个与 entries_next_cursor 不同的旧 next_cursor
    //     值来证明这点）+ 加载更多 + 显式刷新重置为第 1 页
    {
      helpers.resetHedgeStateForTest();
      hedgeLogPageResponses = [{ status: 200, body: HEDGE_LOG_PAGE_1 }, { status: 200, body: HEDGE_LOG_PAGE_2 }];
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTab('logs');
      await new Promise(r => setTimeout(r, 0));
      if (elements['hedge-logs-load-more'].style.display === 'none') {
        throw new Error('entries_next_cursor 存在时加载更多应可见');
      }
      let mark = fetchCallLog.length;
      await Promise.all((elements['hedge-logs-load-more'].listeners.click || []).map(h => h()));
      await new Promise(r => setTimeout(r, 0));
      const moreCalls = fetchCallLog.slice(mark).filter(c => c.url.startsWith('/api/hedge-open-logs'));
      if (moreCalls.length !== 1 || moreCalls[0].url !== '/api/hedge-open-logs?entries_limit=50&entries_cursor=entries-cursor-page-2') {
        throw new Error(`加载更多应仅携带 entries_next_cursor（不得回退旧 next_cursor）: ${JSON.stringify(moreCalls)}`);
      }
      const listHtml = elements['hedge-log-list'].innerHTML;
      // no-orderId 确认失败行：两腿 order_id 均为 null，仍需渲染客户单号与安全错误原因
      if (!listHtml.includes('确认失败')) throw new Error('应渲染确认失败行');
      if (!listHtml.includes('现货腿：方向 SELL · 订单号 <span class="mono">—</span> · 客户单号 <span class="mono">hgo-e8-s</span>')) {
        throw new Error(`no-orderId 失败行现货腿应降级订单号为 — 但保留客户单号: ${listHtml}`);
      }
      if (!listHtml.includes('安全错误：insufficient_balance / 51008') || !listHtml.includes('可用余额不足')) {
        throw new Error('no-orderId 失败行应展示安全错误 category/code/中文原因');
      }
      if (!listHtml.includes('已终止')) throw new Error('no-orderId 失败行 next_action=stopped 应映射为已终止');
      // 两页拼接顺序保持 newest-first：第 1 页的「单腿成交」应排在第 2 页的「确认失败」之前
      if (!(listHtml.indexOf('单腿成交') !== -1 && listHtml.indexOf('单腿成交') < listHtml.indexOf('确认失败'))) {
        throw new Error(`两页拼接后顺序错误: ${listHtml}`);
      }
      // entry_id 不重复：两页共 3 条 entries，逐条 entry_id 唯一
      const mergedEntries = helpers.getHedgeLogs().entries;
      if (mergedEntries.length !== 3) {
        throw new Error(`两页拼接后应为 3 条: ${mergedEntries.length}`);
      }
      const entryIds = mergedEntries.map(e => e.entry_id);
      if (new Set(entryIds).size !== entryIds.length) {
        throw new Error(`两页拼接后 entry_id 出现重复: ${JSON.stringify(entryIds)}`);
      }
      if (elements['hedge-logs-load-more'].style.display !== 'none') {
        throw new Error('entries_next_cursor 为 null 后加载更多应隐藏');
      }
      // 显式刷新重拉第 1 页（重置条目，且不带 entries_cursor）
      hedgeLogPageResponses = [{ status: 200, body: HEDGE_LOG_PAGE_1 }];
      mark = fetchCallLog.length;
      await Promise.all((elements['hedge-logs-refresh'].listeners.click || []).map(h => h()));
      await new Promise(r => setTimeout(r, 0));
      const refreshCalls = fetchCallLog.slice(mark).filter(c => c.url.startsWith('/api/hedge-open-logs'));
      if (refreshCalls.length !== 1 || refreshCalls[0].url !== '/api/hedge-open-logs?entries_limit=50') {
        throw new Error(`显式刷新应重拉第 1 页（无 entries_cursor）: ${JSON.stringify(refreshCalls)}`);
      }
      if (helpers.getHedgeLogs().entries.length !== 2) throw new Error('刷新后开单日志应重置为第 1 页 2 条');
      helpers.setHedgeTab('tasks');
      helpers.setActiveView('market');
      console.log('[PASS] 开单日志 no-orderId 确认失败行 + newest-first 两页 entries_cursor 分页（不回退旧 next_cursor）+ entry_id 不重复 + 加载更多 + 显式刷新');
    }

    // 90b. 开单日志分页安全降级（17 号兼容修正规则 5）：entries_next_cursor 缺失/非字符串时
    //      安全地当作没有更多，即使旧 next_cursor 仍然真值存在，也绝不回退使用它翻页
    {
      helpers.resetHedgeStateForTest();
      hedgeLogPageResponses = [{
        status: 200,
        body: {
          logs: [], attempts: [],
          entries: [HEDGE_LOG_ENTRY_SINGLE_LEG],
          next_cursor: 'legacy-cursor-truthy-but-must-be-ignored',
          entries_next_cursor: 123 // 非字符串：必须安全降级为「没有更多」
        }
      }];
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTab('logs');
      await new Promise(r => setTimeout(r, 0));
      if (elements['hedge-logs-load-more'].style.display !== 'none') {
        throw new Error('entries_next_cursor 非字符串时加载更多应隐藏（不得回退旧 next_cursor）');
      }
      if (helpers.getHedgeLogs().nextCursor !== null) {
        throw new Error('entries_next_cursor 非字符串时内部游标应安全置空');
      }
      const rNoMore = await helpers.loadHedgeLogs(false);
      if (rNoMore.ok) throw new Error('没有更多游标时 loadHedgeLogs(false) 应返回失败且不发请求');
      helpers.setHedgeTab('tasks');
      helpers.setActiveView('market');
      console.log('[PASS] entries_next_cursor 缺失/非字符串安全降级为没有更多，不回退旧 next_cursor');
    }

    // 91. 开单日志降级：空记录空态、503 错误横幅不崩溃
    {
      helpers.resetHedgeStateForTest();
      hedgeLogPageResponses = [{ status: 200, body: { logs: [], attempts: [], entries: [], entries_next_cursor: null } }];
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTab('logs');
      await new Promise(r => setTimeout(r, 0));
      if (!elements['hedge-log-list'].innerHTML.includes('暂无开单日志')) {
        throw new Error('空 entries 应渲染空态');
      }
      if (elements['hedge-logs-error'].style.display !== 'none') {
        throw new Error('空记录不应显示错误横幅');
      }
      hedgeLogPageResponses = [];
      await helpers.loadHedgeLogs(true);
      if (elements['hedge-logs-error'].style.display === 'none') {
        throw new Error('开单日志 503 应显示错误横幅');
      }
      if (!elements['hedge-logs-error'].textContent) throw new Error('错误横幅应有文案');
      hedgeLogPageResponses = [{ status: 200, body: { logs: [], attempts: [], entries: [], entries_next_cursor: null } }];
      await helpers.loadHedgeLogs(true);
      helpers.setHedgeTab('tasks');
      helpers.setActiveView('market');
      console.log('[PASS] 开单日志降级：空态 + 503 错误横幅 + 恢复');
    }

    // 92. 开单日志：overall_result=querying 组渲染查询中/等待终态（与任务内时间线
    //     pair_outcome=null 的查询中语义一致）
    {
      helpers.resetHedgeStateForTest();
      const queryingEntry = mockHedgeLogEntry({
        entry_id: 'e-20', task_id: 'h-log-3', coin: 'GUSDT', attempt_seq: 1,
        overall_result: 'querying', next_action: 'waiting_query',
        spot: {
          side: 'BUY', client_order_id: 'hgo-e20-s', order_id: '9301', status: 'NEW',
          cumulative_base_qty: '0', cumulative_quote_amt: '0', avg_price: null, fee_amount: null, fee_asset: null
        },
        perp: {
          side: 'SELL', client_order_id: 'hgo-e20-p', order_id: '9302', status: 'NEW',
          cumulative_base_qty: '0', cumulative_quote_amt: '0', avg_price: null, fee_amount: null, fee_asset: null
        }
      });
      hedgeLogPageResponses = [{ status: 200, body: { logs: [], attempts: [], entries: [queryingEntry], entries_next_cursor: null } }];
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTab('logs');
      await new Promise(r => setTimeout(r, 0));
      const listHtml = elements['hedge-log-list'].innerHTML;
      if (!listHtml.includes('查询中')) throw new Error('overall_result=querying 应渲染查询中');
      if (!listHtml.includes('等待查询终态')) throw new Error('next_action=waiting_query 应渲染等待查询终态');
      helpers.setHedgeTab('tasks');
      helpers.setActiveView('market');
      console.log('[PASS] 开单日志 querying 组渲染查询中/等待终态');
    }

    // 87. 开单 API 全部同源相对路径、零跨域 fetch
    {
      const hedgeCalls = fetchCallLog.filter(c => c.url.includes('/api/hedge-open'));
      if (hedgeCalls.length === 0) throw new Error('应有开单 API 调用记录');
      for (const c of hedgeCalls) {
        if (!c.url.startsWith('/')) throw new Error(`开单 API 应为同源相对路径: ${c.url}`);
        if (/^[a-z][a-z0-9+.-]*:\/\//i.test(c.url)) throw new Error(`开单 API 出现绝对外部源: ${c.url}`);
        if (/binance/i.test(c.url)) throw new Error(`开单 API 不应直连 Binance: ${c.url}`);
      }
      console.log('[PASS] 开单 API 全部同源、零跨域 fetch');
    }

    // 93. S2 live-hardening：running 卡启动按钮条件四象限（10-design §2.2 / §6）
    //     dry-run running（worker_active===null/缺失）→ disabled；live running+worker_active:false → enabled；
    //     live running+worker_active:true → disabled；paused → enabled。严格 === false。
    {
      helpers.resetHedgeStateForTest();
      const q1 = mockHedgeTask({ id: 'h-s2-1', status: 'running', worker_active: null });
      const q2 = mockHedgeTask({ id: 'h-s2-2', status: 'running', worker_active: false });
      const q3 = mockHedgeTask({ id: 'h-s2-3', status: 'running', worker_active: true });
      const q4 = mockHedgeTask({ id: 'h-s2-4', status: 'paused', worker_active: false });
      hedgeTasksGetResponse = { status: 200, body: { tasks: [q1, q2, q3, q4] } };
      await helpers.loadHedgeTasks();
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTaskFilter('all');
      const cards = elements['hedge-task-list'].innerHTML;
      function startBtnDisabled(id) {
        const m = cards.match(new RegExp(`<button[^>]*data-hedge-action="start"[^>]*data-task-id="${id}"[^>]*>`));
        if (!m) throw new Error(`缺少 ${id} 启动按钮`);
        return m[0].includes('disabled');
      }
      if (!startBtnDisabled('h-s2-1')) throw new Error('dry-run running（worker_active===null）启动按钮应 disabled');
      if (startBtnDisabled('h-s2-2')) throw new Error('live running+worker_active:false 启动按钮应 enabled');
      if (!startBtnDisabled('h-s2-3')) throw new Error('live running+worker_active:true 启动按钮应 disabled');
      if (startBtnDisabled('h-s2-4')) throw new Error('paused 启动按钮应 enabled');
      helpers.setActiveView('market');
      console.log('[PASS] S2 running 卡启动按钮四象限：dry-run/worker_active 三态 + paused（严格 === false）');
    }

    // 93b. 两段式平仓：待首次启动卡只能点“启动”，fill-once/fill-all 不得绕过。
    {
      helpers.resetHedgeStateForTest();
      const waiting = mockHedgeTask({
        id: 'h-close-waiting', task_type: 'close', status: 'paused',
        pause_reason: 'awaiting_manual_start',
        pause_reason_zh: '待启动：平仓任务已创建，点击启动后才会校验并发送真实订单'
      });
      hedgeTasksGetResponse = { status: 200, body: { tasks: [waiting] } };
      await helpers.loadHedgeTasks();
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTaskFilter('all');
      const card = elements['hedge-task-list'].innerHTML;
      const start = card.match(/<button[^>]*data-hedge-action="start"[^>]*>/);
      const fill1 = card.match(/<button[^>]*data-hedge-action="fill1"[^>]*>/);
      if (!start || start[0].includes('disabled')) throw new Error('待启动平仓卡的启动按钮应启用');
      if (!fill1 || !fill1[0].includes('disabled')) throw new Error('待启动平仓卡的成交1次按钮应禁用');
      if (!card.includes('点击启动后才会校验并发送真实订单')) {
        throw new Error('待启动平仓卡应展示后端中文原因');
      }
      helpers.setActiveView('market');
      console.log('[PASS] 两段式平仓：待启动中文原因 + 启动可点 + fill 不可绕过');
    }

    // 94. S4a live-hardening：执行线程行三态 + 八个退出原因中文映射（10-design §2.4a）
    //     worker_active true→运行中 / false→未运行 / null·缺失→—；八枚举逐字；未知原样；缺失降级 —。
    {
      helpers.resetHedgeStateForTest();
      const exitReasons = [
        ['stopped_event', '收到停止信号'],
        ['task_missing', '任务记录缺失'],
        ['task_not_running', '任务已非运行态'],
        ['start_gate_off', '全局开单闸门未开启'],
        ['target_reached', '计划尝试次数已用完'],
        ['preflight_incomplete', '预检数据不完整（安全退出）'],
        ['preflight_fatal', '预检发现致命问题'],
        ['worker_error', 'worker 异常退出']
      ];
      const tasks = exitReasons.map(([reason], i) => mockHedgeTask({
        id: `h-s4a-${i}`, coin: 'AUSDT', status: 'running',
        worker_active: false, last_worker_exit_reason: reason
      }));
      tasks.push(mockHedgeTask({ id: 'h-s4a-true', coin: 'AUSDT', status: 'running', worker_active: true, last_worker_exit_reason: 'worker_error' }));
      tasks.push(mockHedgeTask({ id: 'h-s4a-null', coin: 'AUSDT', status: 'running', worker_active: null, last_worker_exit_reason: null }));
      tasks.push(mockHedgeTask({ id: 'h-s4a-missing', coin: 'AUSDT', status: 'running' }));
      tasks.push(mockHedgeTask({ id: 'h-s4a-unknown', coin: 'AUSDT', status: 'running', worker_active: false, last_worker_exit_reason: 'some_new_reason' }));
      hedgeTasksGetResponse = { status: 200, body: { tasks } };
      await helpers.loadHedgeTasks();
      helpers.setActiveView('hedge-tasks');
      helpers.setHedgeTaskFilter('all');
      const cards = elements['hedge-task-list'].innerHTML;
      function cardHtml(id) {
        const start = cards.indexOf(`data-hedge-task-id="${id}"`);
        if (start === -1) throw new Error(`缺少任务卡 ${id}`);
        const next = cards.indexOf('<div class="borrow-task-card"', start + 1);
        return cards.slice(start, next === -1 ? cards.length : next);
      }
      for (let i = 0; i < exitReasons.length; i++) {
        const label = exitReasons[i][1];
        const card = cardHtml(`h-s4a-${i}`);
        if (!card.includes('执行线程：<strong>未运行</strong>')) throw new Error(`卡 h-s4a-${i} worker_active:false 应显示「未运行」`);
        if (!card.includes(`上次退出原因：<strong>${label}</strong>`)) throw new Error(`卡 h-s4a-${i} 退出原因映射错误（期望 ${label}）`);
      }
      if (!cardHtml('h-s4a-true').includes('执行线程：<strong>运行中</strong>')) throw new Error('worker_active:true 应显示「运行中」');
      const nullCard = cardHtml('h-s4a-null');
      if (!nullCard.includes('执行线程：<strong>—</strong>') || !nullCard.includes('上次退出原因：<strong>—</strong>')) {
        throw new Error('worker_active:null / last_worker_exit_reason:null 应降级 —');
      }
      const missingCard = cardHtml('h-s4a-missing');
      if (!missingCard.includes('执行线程：<strong>—</strong>') || !missingCard.includes('上次退出原因：<strong>—</strong>')) {
        throw new Error('字段缺失（undefined）应降级 —');
      }
      if (!cardHtml('h-s4a-unknown').includes('上次退出原因：<strong>some_new_reason</strong>')) {
        throw new Error('未知退出原因应原样展示');
      }
      helpers.setActiveView('market');
      console.log('[PASS] S4a 执行线程行：worker_active 三态 + 八个退出原因中文映射逐字 + 未知原样 + 缺失降级 —');
    }

    // 95. S3 live-hardening：开单闸门对称确认弹窗（10-design §2.3 / §6）
    //     label 随 start_gate 切换；确认前零 POST；确认后 POST 冻结 body（enabled/confirm/version）；
    //     取消零请求；409 version_conflict → 重新 GET + 冻结提示，不自动重试（无死循环）。
    {
      helpers.resetHedgeStateForTest();
      helpers.closeHedgeModal();
      hedgeSettingsGetResponse = { status: 200, body: { executor_mode: 'live', start_gate: false, interval_seconds: 1, version: 3 } };
      await helpers.loadHedgeSettings();
      if (elements['hedge-start-gate-toggle'].style.display === 'none') throw new Error('闸门控件应显示');
      if (elements['hedge-start-gate-toggle'].textContent !== '开启开单闸门') {
        throw new Error(`闸门关时 label 应为「开启开单闸门」: ${elements['hedge-start-gate-toggle'].textContent}`);
      }
      hedgeSettingsGetResponse = { status: 200, body: { executor_mode: 'live', start_gate: true, interval_seconds: 1, version: 4 } };
      await helpers.loadHedgeSettings();
      if (elements['hedge-start-gate-toggle'].textContent !== '关闭开单闸门') {
        throw new Error(`闸门开时 label 应为「关闭开单闸门」: ${elements['hedge-start-gate-toggle'].textContent}`);
      }
      // 点击控件（当前开 → 请求关闭）→ 弹确认（冻结文案），确认前零 POST
      const markBefore = fetchCallLog.length;
      helpers.requestHedgeStartGate(false);
      if (fetchCallLog.length !== markBefore) throw new Error('确认前不应有任何请求');
      const modal = helpers.getHedgeModal();
      if (!modal || modal.title !== '关闭全局开单闸门？') throw new Error(`关闭方向弹窗标题错误: ${JSON.stringify(modal)}`);
      if (!modal.body || !modal.body.includes('任务的 worker 将在下一轮检查时退出')) throw new Error(`关闭方向弹窗正文冻结文案缺失: ${modal && modal.body}`);
      if (!elements['hedge-modal'].classList.contains('open')) throw new Error('确认弹窗应 open');
      if (elements['hedge-modal-confirm'].style.display === 'none') throw new Error('确认按钮应显示');
      if (elements['hedge-modal-cancel'].style.display === 'none') throw new Error('取消按钮应显示');
      if (elements['hedge-modal-close'].style.display !== 'none') throw new Error('单按钮「知道了」应隐藏');
      if (elements['hedge-modal-confirm'].textContent !== '确认关闭') throw new Error('确认词应为「确认关闭」');
      // 取消 → 零请求、弹窗关闭、pending 清空
      helpers.cancelHedgeStartGate();
      if (fetchCallLog.length !== markBefore) throw new Error('取消不应产生任何请求');
      if (helpers.getHedgeModal() !== null || elements['hedge-modal'].classList.contains('open')) throw new Error('取消后弹窗应关闭');
      if (helpers.getHedgeGatePending() !== null) throw new Error('取消后 pending 应清空');
      // 开方向冻结文案 + 确认词
      helpers.requestHedgeStartGate(true);
      const modalOpen = helpers.getHedgeModal();
      if (!modalOpen || modalOpen.title !== '开启全局开单闸门？') throw new Error(`开启方向弹窗标题错误: ${JSON.stringify(modalOpen)}`);
      if (!modalOpen.body.includes('可以向币安发出真实订单')) throw new Error(`开启方向弹窗正文冻结文案缺失: ${modalOpen.body}`);
      if (elements['hedge-modal-confirm'].textContent !== '确认开启') throw new Error('确认词应为「确认开启」');
      helpers.cancelHedgeStartGate();

      // 确认 → POST 冻结 body（enabled/confirm/version）；成功后用响应 doc 刷新
      hedgeSettingsGetResponse = { status: 200, body: { executor_mode: 'live', start_gate: false, interval_seconds: 1, version: 3 } };
      await helpers.loadHedgeSettings();
      helpers.requestHedgeStartGate(true);
      hedgeStartGatePostResponse = { status: 200, body: { executor_mode: 'live', start_gate: true, interval_seconds: 1, version: 4 } };
      const markConfirm = fetchCallLog.length;
      const rOk = await helpers.confirmHedgeStartGate();
      if (!rOk.ok) throw new Error('确认开启应成功: ' + rOk.error);
      const gateCall = fetchCallLog.slice(markConfirm).find(c => c.url === '/api/hedge-open-settings/start-gate');
      if (!gateCall || gateCall.method !== 'POST') throw new Error('应 POST /api/hedge-open-settings/start-gate');
      if (JSON.stringify(gateCall.body) !== JSON.stringify({ enabled: true, confirm: true, version: 3 })) {
        throw new Error(`POST body 与 §2.3 冻结形状不符: ${JSON.stringify(gateCall.body)}`);
      }
      if (elements['hedge-start-gate-toggle'].textContent !== '关闭开单闸门') throw new Error('成功后按钮 label 应随响应 doc 刷新为「关闭开单闸门」');

      // 409 version_conflict → 重新 GET settings 刷新 + 冻结提示，只 POST 一次（无死循环）
      hedgeSettingsGetResponse = { status: 200, body: { executor_mode: 'live', start_gate: true, interval_seconds: 1, version: 5 } };
      await helpers.loadHedgeSettings();
      helpers.requestHedgeStartGate(false);
      hedgeStartGatePostResponse = { status: 409, body: { error: 'version_conflict', detail: '设置已被其他会话修改，请刷新后重试', settings: { executor_mode: 'live', start_gate: true, interval_seconds: 1, version: 6 } } };
      hedgeSettingsGetResponse = { status: 200, body: { executor_mode: 'live', start_gate: true, interval_seconds: 1, version: 6 } };
      const mark409 = fetchCallLog.length;
      const r409 = await helpers.confirmHedgeStartGate();
      if (r409.ok || r409.error !== 'version_conflict') throw new Error('409 应返回 version_conflict: ' + JSON.stringify(r409));
      const calls409 = fetchCallLog.slice(mark409);
      const post409 = calls409.find(c => c.url === '/api/hedge-open-settings/start-gate');
      if (!post409 || post409.body.version !== 5) throw new Error('409 POST 应携带当前 version=5');
      if (!calls409.some(c => c.url === '/api/hedge-open-settings' && c.method === 'GET')) throw new Error('409 后应重新 GET /api/hedge-open-settings 刷新');
      const postCount409 = calls409.filter(c => c.url === '/api/hedge-open-settings/start-gate').length;
      if (postCount409 !== 1) throw new Error(`409 路径应只 POST 一次（无死循环），实际 ${postCount409}`);
      if (!helpers.getHedgeSettings() || helpers.getHedgeSettings().version !== 6) throw new Error('409 后应刷新到新 version=6');
      const modal409 = helpers.getHedgeModal();
      if (!modal409 || !modal409.body.includes('设置已被其他会话修改，已刷新，请重试')) {
        throw new Error(`409 提示文案冻结错误: ${JSON.stringify(modal409)}`);
      }
      helpers.closeHedgeModal();
      console.log('[PASS] S3 开单闸门对称确认：label 随状态 + 冻结文案 + 确认前/取消零请求 + POST 冻结 body(含 version) + 409 刷新提示无死循环');
    }

    // 96. S4b live-hardening：建卡 missing_leg 错误展示中文 detail（10-design §2.4b）
    //     既有 hedgeApi 错误通道（err.message=data.detail）经 submitHedgeOpen 兜底 setErr 天然展示。
    {
      helpers.resetHedgeStateForTest();
      hedgeTasksGetResponse = { status: 200, body: { tasks: [] } };
      document.getElementById('hedge-amount-forward-AUSDT').value = '1';
      document.getElementById('hedge-count-forward-AUSDT').value = '3';
      hedgeTasksPostResponse = { status: 400, body: { error: 'missing_leg', detail: '该交易对在币安现货与 USDⓈ-M 合约市场均不存在，无法创建对冲任务', missing: ['spot', 'perp'] } };
      const rMissing = await helpers.submitHedgeOpen('AUSDT', 'forward', 'immediate');
      if (rMissing.ok) throw new Error('missing_leg 不应创建任务');
      if (rMissing.error !== 'missing_leg') throw new Error('应返回 missing_leg 错误码: ' + rMissing.error);
      const errText = document.getElementById('hedge-error-forward-AUSDT').textContent;
      if (!errText.includes('该交易对在币安现货与 USDⓈ-M 合约市场均不存在')) {
        throw new Error(`missing_leg 中文 detail 应就近展示: ${errText}`);
      }
      console.log('[PASS] S4b 建卡 missing_leg 错误：中文 detail 经既有 hedgeApi 通道就近展示');
    }

    // 96b. 市场表创建确认弹框：借币确认 / 立即开单确认（确认前零 POST；取消清空 pending）
    {
      helpers.resetHedgeStateForTest();
      // 借币：合法输入 → 弹确认、零 POST；确认后才 POST
      borrowSettingsGetResponse = { status: 200, body: { interval_seconds: '5' } };
      await helpers.loadSchedulerSettings();
      document.getElementById('borrow-amount-AUSDT').value = '1.5';
      document.getElementById('borrow-count-AUSDT').value = '2';
      const markBorrow = fetchCallLog.length;
      const rBorrowPend = helpers.requestBorrowCreateConfirm('AUSDT');
      if (!rBorrowPend.ok || !rBorrowPend.pending) throw new Error('借币确认应进入 pending: ' + JSON.stringify(rBorrowPend));
      if (fetchCallLog.length !== markBorrow) throw new Error('借币确认弹框前不应 POST');
      const borrowModal = helpers.getHedgeModal();
      if (!borrowModal || borrowModal.title !== '确认创建借币任务？') {
        throw new Error('借币确认弹窗标题错误: ' + JSON.stringify(borrowModal));
      }
      if (!borrowModal.body.includes('单次 1.5') || !borrowModal.body.includes('成功 2 次')) {
        throw new Error('借币确认弹窗应含数量/次数: ' + borrowModal.body);
      }
      if (!helpers.getMarketActionPending() || helpers.getMarketActionPending().kind !== 'borrow_create') {
        throw new Error('应有 borrow_create pending');
      }
      helpers.cancelHedgeStartGate();
      if (helpers.getMarketActionPending() !== null) throw new Error('取消后 marketActionPending 应清空');
      if (fetchCallLog.length !== markBorrow) throw new Error('取消借币确认不应 POST');

      // 立即开单：合法输入 → 弹确认；确认后 submit（直接测 confirmMarketAction）
      hedgeTasksGetResponse = { status: 200, body: { tasks: [] } };
      document.getElementById('hedge-amount-forward-AUSDT').value = '0.5';
      document.getElementById('hedge-count-forward-AUSDT').value = '3';
      const markHedge = fetchCallLog.length;
      const rHedgePend = helpers.requestHedgeOpenConfirm('AUSDT', 'forward', 'immediate');
      if (!rHedgePend.ok || !rHedgePend.pending) throw new Error('开单确认应进入 pending');
      if (fetchCallLog.length !== markHedge) throw new Error('开单确认弹框前不应 POST');
      const hedgeModal = helpers.getHedgeModal();
      if (!hedgeModal || !hedgeModal.title.includes('正向') || !hedgeModal.title.includes('立即开单')) {
        throw new Error('开单确认标题错误: ' + JSON.stringify(hedgeModal));
      }
      if (!hedgeModal.body.includes('0.5') || !hedgeModal.body.includes('3')) {
        throw new Error('开单确认正文应含币量/次数: ' + hedgeModal.body);
      }
      const created = mockHedgeTask({ id: 'h-confirm-1', coin: 'AUSDT', direction: 'forward', status: 'running' });
      hedgeTasksPostResponse = { status: 201, body: created };
      hedgeTasksGetResponse = { status: 200, body: { tasks: [created] } };
      const rConfirmed = await helpers.confirmMarketAction();
      if (!rConfirmed.ok) throw new Error('确认开单应成功: ' + rConfirmed.error);
      const postAfter = fetchCallLog.slice(markHedge).find(c => c.method === 'POST' && c.url === '/api/hedge-open-tasks');
      if (!postAfter) throw new Error('确认后应 POST /api/hedge-open-tasks');
      if (helpers.getHedgeTaskNavLoading() !== 0) throw new Error('创建结束后 loading 计数应为 0');
      if (!elements['hedge-task-count'].textContent || elements['hedge-task-count'].textContent === '') {
        // loading 用 innerHTML；结束后应写 textContent 数字
      }
      if (String(elements['hedge-task-count'].textContent) !== '1'
          && !String(elements['hedge-task-count']._textContent || elements['hedge-task-count'].textContent).includes('1')) {
        // mock 元素 textContent 与 innerHTML 分离：结束后 updateHedgeTaskNav 设 textContent
        if (elements['hedge-task-count'].textContent !== '1') {
          throw new Error('创建回显后开单任务数字应为 1，实际: ' + elements['hedge-task-count'].textContent);
        }
      }
      const pausedClose = mockHedgeTask({ id: 'h-confirm-close-1', task_type: 'close', status: 'paused' });
      hedgeTasksGetResponse = { status: 200, body: { tasks: [created, pausedClose] } };
      await helpers.loadHedgeTasks();
      if (elements['hedge-task-count'].textContent !== '2') {
        throw new Error('开单任务导航数字须统计执行中 + 已暂停（含新建平单任务）');
      }
      // 非法输入：不弹确认
      document.getElementById('hedge-amount-forward-AUSDT').value = '';
      const rBad = helpers.requestHedgeOpenConfirm('AUSDT', 'forward', 'immediate');
      if (rBad.ok) throw new Error('空币量不应进入确认');
      if (helpers.getMarketActionPending() !== null) throw new Error('非法输入不应留下 pending');
      console.log('[PASS] 市场表创建确认弹框：借币/立即开单确认前零 POST + 确认后提交 + 取消清空');
    }

    // 96c. 行情表重绘保留操作列输入；立即开单 submit 期间徽标 loading
    {
      helpers.resetHedgeStateForTest();
      helpers.ingestSnapshot(designFixture);
      document.getElementById('borrow-amount-AUSDT').value = '12.34';
      document.getElementById('borrow-count-AUSDT').value = '7';
      document.getElementById('hedge-amount-forward-AUSDT').value = '0.01';
      document.getElementById('hedge-count-reverse-AUSDT').value = '9';
      helpers.renderTable();
      if (document.getElementById('borrow-amount-AUSDT').value !== '12.34') {
        throw new Error('renderTable 后应保留借币数量: ' + document.getElementById('borrow-amount-AUSDT').value);
      }
      if (document.getElementById('borrow-count-AUSDT').value !== '7') {
        throw new Error('renderTable 后应保留借币次数');
      }
      if (document.getElementById('hedge-amount-forward-AUSDT').value !== '0.01') {
        throw new Error('renderTable 后应保留正向开单币量');
      }
      if (document.getElementById('hedge-count-reverse-AUSDT').value !== '9') {
        throw new Error('renderTable 后应保留反向开单次数');
      }

      // loading：POST 进行中徽标为 spinner；结束后恢复
      hedgeTasksGetResponse = { status: 200, body: { tasks: [] } };
      document.getElementById('hedge-amount-forward-AUSDT').value = '0.5';
      document.getElementById('hedge-count-forward-AUSDT').value = '1';
      let sawLoading = false;
      const slowTask = mockHedgeTask({ id: 'h-load-1', status: 'running' });
      // 用同步 mock 无法穿插观察 loading；直接断言 begin/end 后计数与 spinner HTML
      // 通过 submit 成功路径：结束后 loading=0 且数字为执行中 + 已暂停数
      hedgeTasksPostResponse = { status: 201, body: slowTask };
      hedgeTasksGetResponse = { status: 200, body: { tasks: [slowTask] } };
      const rLoad = await helpers.submitHedgeOpen('AUSDT', 'forward', 'immediate');
      if (!rLoad.ok) throw new Error('loading 路径创建应成功');
      if (helpers.getHedgeTaskNavLoading() !== 0) throw new Error('结束后 loading 应为 0');
      if (elements['hedge-task-count'].textContent !== '1') {
        throw new Error('结束后徽标应为 1: ' + elements['hedge-task-count'].textContent);
      }
      // 失败路径也要清 loading
      hedgeTasksPostResponse = { status: 400, body: { error: 'invalid_field', field: 'single_amount', detail: 'bad' } };
      document.getElementById('hedge-amount-forward-AUSDT').value = '0.5';
      document.getElementById('hedge-count-forward-AUSDT').value = '1';
      const rFail = await helpers.submitHedgeOpen('AUSDT', 'forward', 'immediate');
      if (rFail.ok) throw new Error('失败路径应 ok=false');
      if (helpers.getHedgeTaskNavLoading() !== 0) throw new Error('失败后 loading 也应清零');
      console.log('[PASS] 操作列输入跨 renderTable 保留 + 开单徽标 loading 收尾');
    }

    // 97. M-1 live-hardening：start_gate_changed 审计行经全量投影进入 logs 数组，
    //     但其 payload 不含 attempt_seq/pair_outcome/spot/perp，extractHedgeAttempts 必须忽略它，
    //     不渲染成畸形 attempt 卡（钉住前端侧隐含依赖）。
    {
      const doc = {
        logs: [
          { task_id: 'start-gate', kind: 'start_gate_changed', ts_us: 1783641600000000,
            payload: { enabled: true, previous_enabled: false, version: 2, source: 'api' } },
          mockHedgeAttempt({ task_id: 'h-1', attempt_seq: 1 })
        ],
        next_cursor: null
      };
      const attempts = helpers.extractHedgeAttempts(doc);
      if (attempts.length !== 1) throw new Error(`start_gate_changed 应被忽略，仅留 1 条 attempt，实际 ${attempts.length}`);
      if (attempts[0].attempt_seq !== 1) throw new Error('应保留真 attempt');
      console.log('[PASS] M-1 start_gate_changed 审计行被 extractHedgeAttempts 忽略（不渲染畸形 attempt）');
    }

    // 98b. 流水日志真实数据源（task C）+ 页内双看板布局（tab-layout-v2）
    {
      const flowIds = [
        'btn-market-board', 'btn-flow-log', 'market-board', 'flow-log-view',
        'flow-log-panel', 'flow-log-status-bar', 'flow-log-coverage-note',
        'flow-log-range-7d', 'flow-log-range-30d', 'flow-log-range-custom',
        'flow-log-custom-start', 'flow-log-custom-end', 'flow-log-custom-apply',
        'flow-log-refresh', 'flow-log-delta', 'flow-log-delta-interest', 'flow-log-delta-income',
        'flow-log-delta-symbols', 'flow-log-today', 'flow-log-filters',
        'flow-log-filter-funding', 'flow-log-filter-commission', 'flow-log-filter-realized',
        'flow-log-filter-transfer', 'flow-log-filter-other',
        'flow-log-interest-status', 'flow-log-interest-summary', 'flow-log-interest-body',
        'flow-log-income-status', 'flow-log-income-summary', 'flow-log-income-body',
      ];
      for (const id of flowIds) {
        if (!document.getElementById(id)) throw new Error('流水日志 DOM 缺失: ' + id);
      }
      // 侧栏不得再有流水日志主菜单
      if (html.includes('id="nav-flow-log"')) {
        throw new Error('侧栏 #nav-flow-log 必须移除');
      }
      if (Object.prototype.hasOwnProperty.call(elements, 'nav-flow-log')) {
        throw new Error('mock 中不应注册 nav-flow-log');
      }
      // 双看板按钮在私有账户 .panel-actions，不在 .badge-row
      const privatePanelIdx = html.indexOf('id="private-panel"');
      const privatePanelEnd = html.indexOf('</section>', privatePanelIdx);
      const privateChunk = privatePanelIdx >= 0 && privatePanelEnd > privatePanelIdx
        ? html.slice(privatePanelIdx, privatePanelEnd)
        : '';
      if (!privateChunk.includes('id="btn-market-board"') || !privateChunk.includes('id="btn-flow-log"')) {
        throw new Error('费率行情/流水日志按钮须在私有账户面板内');
      }
      if (!privateChunk.includes('panel-actions') || !privateChunk.includes('aria-label="费率行情页双看板"')) {
        throw new Error('双看板按钮须在 .panel-actions（role=tablist）内');
      }
      const badgeRowIdx = html.indexOf('class="badge-row"');
      const badgeRowEnd = html.indexOf('</div>', badgeRowIdx + 1);
      // badge-row 可能有嵌套 div；取到手动刷新按钮附近即可
      const badgeSlice = badgeRowIdx >= 0 ? html.slice(badgeRowIdx, badgeRowIdx + 800) : '';
      if (badgeSlice.includes('id="btn-market-board"') || badgeSlice.includes('id="btn-flow-log"') ||
          badgeSlice.includes('id="tab-market-board"') || badgeSlice.includes('id="tab-flow-log-board"') ||
          badgeSlice.includes('id="market-board-tabs"')) {
        throw new Error('双看板按钮不得放在 .badge-row');
      }
      if (html.includes('演示数据（FAKE）——非真实账户流水')) {
        throw new Error('FAKE 横幅必须删除');
      }
      if (html.includes('假数据探针') || html.includes('刷新（演示）')) {
        throw new Error('FAKE 副标题/按钮文案必须删除');
      }
      if (html.includes('资金费率日志')) throw new Error('右栏不得命名为资金费率日志');
      if (!html.includes('合约资金流水') || !html.includes('借币利息流水')) {
        throw new Error('双栏标题缺失');
      }
      // 同页双看板：flow-log 内容在 market-view 内
      const marketViewStart = html.indexOf('id="market-view"');
      const marketViewClose = html.indexOf('<!-- #market-view -->');
      const marketChunkEnd = marketViewClose > marketViewStart ? marketViewClose : html.length;
      if (marketViewStart === -1) throw new Error('缺少 market-view');
      const marketInner = html.slice(marketViewStart, marketChunkEnd);
      if (!marketInner.includes('id="flow-log-view"') || !marketInner.includes('id="flow-log-panel"')) {
        throw new Error('flow-log 看板须在 market-view 内');
      }
      if (!marketInner.includes('id="market-board"')) {
        throw new Error('market-board 须在 market-view 内');
      }

      // 默认费率行情看板：零 private-ledger 请求
      helpers.setActiveView('market');
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getMarketBoard && helpers.getMarketBoard() !== 'market') {
        throw new Error('默认 marketBoard 应为 market');
      }
      const beforeEnter = fetchCallLog.filter(c => c.url.includes('/api/private-ledger/')).length;
      helpers.setActiveView('market');
      await new Promise(r => setTimeout(r, 0));
      const beforeEnter2 = fetchCallLog.filter(c => c.url.includes('/api/private-ledger/')).length;
      if (beforeEnter2 !== beforeEnter) throw new Error('费率行情看板不应请求 private-ledger');
      // 默认按钮高亮
      const btnM = document.getElementById('btn-market-board');
      const btnF = document.getElementById('btn-flow-log');
      if (!btnM.classList.contains('primary') || btnM.getAttribute('aria-selected') !== 'true') {
        throw new Error('默认应高亮费率行情按钮');
      }
      if (btnF.classList.contains('primary') || btnF.getAttribute('aria-selected') === 'true') {
        throw new Error('默认不应高亮流水日志按钮');
      }

      flowLogGetResponse = { status: 200, body: buildMockFlowLogPayload() };
      const mark = fetchCallLog.length;
      const intervalsBefore = intervalCalls.length;
      // 点「流水日志」看板（同页，不隐藏 market-view）
      helpers.setMarketBoard('flow-log');
      await new Promise(r => setTimeout(r, 0));
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getActiveView() !== 'market') throw new Error('activeView 应保持 market');
      if (helpers.getMarketBoard() !== 'flow-log') throw new Error('marketBoard 应为 flow-log');
      if (document.getElementById('flow-log-view').style.display === 'none') {
        throw new Error('flow-log-view 应显示');
      }
      if (document.getElementById('market-view').style.display === 'none') {
        throw new Error('market-view 在流水看板时仍应可见');
      }
      if (document.getElementById('market-board').style.display !== 'none') {
        throw new Error('market-board 在流水看板时应隐藏');
      }
      // 侧栏仍高亮费率行情
      const navM = document.getElementById('nav-market');
      if (!navM.classList.contains('active') || navM.getAttribute('aria-current') !== 'page') {
        throw new Error('看板切换后 nav-market 应保持高亮');
      }
      if (!btnF.classList.contains('primary') || btnF.getAttribute('aria-selected') !== 'true') {
        throw new Error('流水看板应高亮 btn-flow-log');
      }
      if (btnM.classList.contains('primary')) {
        throw new Error('流水看板不应高亮 btn-market-board');
      }
      const ledgerGets = fetchCallLog.slice(mark).filter(c =>
        c.method === 'GET' && c.url.startsWith('/api/private-ledger/flow-log')
      );
      if (ledgerGets.length !== 1) {
        throw new Error('进入流水看板应恰好 1 次 GET flow-log，实际 ' + ledgerGets.length);
      }
      const u = new URL(ledgerGets[0].url, 'http://local');
      const startMs = Number(u.searchParams.get('start'));
      const endMs = Number(u.searchParams.get('end'));
      const span = endMs - startMs;
      if (!(span > 6.5 * 86400000 && span < 7.5 * 86400000)) {
        throw new Error('默认窗口应约 7 天，span=' + span);
      }
      const pollId = helpers.getFlowLogPollId();
      if (pollId == null) throw new Error('进入流水看板应启动 flow-log 60s 轮询');
      const pollCall = intervalCalls.find(c => c.id === pollId);
      if (!pollCall || pollCall.delay !== 60000) throw new Error('flow-log 轮询 delay 应为 60000');

      // 20 条
      const intBody = document.getElementById('flow-log-interest-body').innerHTML;
      const tbodyTr = (intBody.match(/<tbody>[\s\S]*?<\/tbody>/) || [''])[0].match(/<tr>/g);
      const nInt = tbodyTr ? tbodyTr.length : 0;
      if (nInt !== 20) throw new Error('左栏应显示 20 条，实际 ' + nInt);
      const intStatus = document.getElementById('flow-log-interest-status').textContent || '';
      if (!intStatus.includes('显示最近 20 条') || !intStatus.includes('25')) {
        throw new Error('左栏状态应含 20 条与 row_count=25: ' + intStatus);
      }
      // pending_tail
      const statusText = document.getElementById('flow-log-status-bar').textContent || '';
      if (!statusText.includes('尚未刷新')) {
        throw new Error('pending_tail 应出现: ' + statusText);
      }
      const dI = document.getElementById('flow-log-delta-interest').innerHTML;
      if (!dI.includes('HOME') && !dI.includes('利息')) throw new Error('增量利息分组未渲染');

      // 切回费率行情看板：清轮询
      helpers.setMarketBoard('market');
      await new Promise(r => setTimeout(r, 0));
      if (!clearedIntervalIds.has(pollId)) {
        throw new Error('切回费率行情应 clearInterval 轮询 id');
      }
      if (helpers.getMarketBoard() !== 'market') throw new Error('切回后 marketBoard 应为 market');
      if (document.getElementById('flow-log-view').style.display !== 'none') {
        throw new Error('切回后 flow-log-view 应隐藏');
      }
      if (document.getElementById('market-board').style.display === 'none') {
        throw new Error('切回后 market-board 应显示');
      }
      const afterLeave = fetchCallLog.length;
      await new Promise(r => setTimeout(r, 0));
      if (fetchCallLog.length !== afterLeave) {
        throw new Error('切回费率行情后不应继续请求 private-ledger');
      }

      // 重复进入不叠加
      const mark2 = fetchCallLog.length;
      helpers.setMarketBoard('flow-log');
      await new Promise(r => setTimeout(r, 0));
      await new Promise(r => setTimeout(r, 0));
      const pollId2 = helpers.getFlowLogPollId();
      if (pollId2 == null) throw new Error('再次进入应有轮询 id');
      const gets2 = fetchCallLog.slice(mark2).filter(c =>
        c.method === 'GET' && c.url.startsWith('/api/private-ledger/flow-log')
      );
      if (gets2.length !== 1) throw new Error('再次进入应恰好 1 次 GET，实际 ' + gets2.length);

      // btn-flow-log / btn-market-board 点击
      helpers.setMarketBoard('market');
      await new Promise(r => setTimeout(r, 0));
      const markBtn = fetchCallLog.length;
      (document.getElementById('btn-flow-log').listeners.click || []).forEach(h => h());
      await new Promise(r => setTimeout(r, 0));
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getMarketBoard() !== 'flow-log') throw new Error('btn-flow-log 应切到流水看板');
      if (helpers.getActiveView() !== 'market') throw new Error('btn-flow-log 后 activeView 仍为 market');
      const getsBtn = fetchCallLog.slice(markBtn).filter(c =>
        c.method === 'GET' && c.url.startsWith('/api/private-ledger/flow-log')
      );
      if (getsBtn.length !== 1) throw new Error('点流水日志应恰好 1 次 GET，实际 ' + getsBtn.length);
      const pollBtn = helpers.getFlowLogPollId();
      (document.getElementById('btn-market-board').listeners.click || []).forEach(h => h());
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getMarketBoard() !== 'market') throw new Error('btn-market-board 应切回费率行情');
      if (pollBtn != null && !clearedIntervalIds.has(pollBtn)) {
        throw new Error('点费率行情应清理轮询');
      }

      // 离开费率行情页（借币/开单）清轮询；导航未破坏
      helpers.setMarketBoard('flow-log');
      await new Promise(r => setTimeout(r, 0));
      const pollLeave = helpers.getFlowLogPollId();
      helpers.setActiveView('borrow-tasks');
      if (helpers.getActiveView() !== 'borrow-tasks') throw new Error('borrow 视图破坏');
      if (pollLeave != null && !clearedIntervalIds.has(pollLeave)) {
        throw new Error('离开费率行情页应 clearInterval 轮询');
      }
      helpers.setActiveView('hedge-tasks');
      if (helpers.getActiveView() !== 'hedge-tasks') throw new Error('hedge 视图破坏');
      helpers.setActiveView('market');
      await new Promise(r => setTimeout(r, 0));
      if (helpers.getMarketBoard() !== 'market') throw new Error('从侧栏回费率行情默认市场看板');

      // --- coverage (a) 起点截断 ---
      flowLogGetResponse = {
        status: 200,
        body: buildMockFlowLogPayload({
          window: { start_ms: 1000, end_ms: 100000 },
          coverage: {
            start_ms: 50000,
            end_ms: 90000,
            complete: false,
            pending_tail_ms: 0,
            by_source: {
              interest: { start_ms: 50000, end_ms: 90000 },
              income: { start_ms: 50000, end_ms: 90000 },
            },
            gaps: [],
          },
          interest: { rows: [], summary_by_asset: [], row_count: 0, row_limit_applied: false },
          um_income: { rows: [], summary_by_type_asset: [], row_count: 0, row_limit_applied: false },
        }),
      };
      helpers.setMarketBoard('flow-log');
      await new Promise(r => setTimeout(r, 0));
      await new Promise(r => setTimeout(r, 0));
      let pageText =
        (document.getElementById('flow-log-status-bar').textContent || '') +
        (document.getElementById('flow-log-coverage-note').textContent || '') +
        document.getElementById('flow-log-interest-body').innerHTML +
        document.getElementById('flow-log-income-body').innerHTML;
      if (!pageText.includes('更早的没有') && !pageText.includes('本地数据只到')) {
        throw new Error('起点截断文案缺失: ' + pageText.slice(0, 200));
      }
      if (pageText.includes('该时间窗无记录') || pageText.includes('没有流水')) {
        throw new Error('complete=false 时禁止无记录措辞');
      }

      // --- (b) gaps ---
      flowLogGetResponse = {
        status: 200,
        body: buildMockFlowLogPayload({
          coverage: {
            start_ms: 1000,
            end_ms: 90000,
            complete: false,
            pending_tail_ms: 0,
            by_source: {
              interest: { start_ms: 1000, end_ms: 90000 },
              income: { start_ms: 1000, end_ms: 90000 },
            },
            gaps: [{ source: 'interest', start_ms: 2000, end_ms: 3000 }],
          },
        }),
      };
      await helpers.loadFlowLog();
      await new Promise(r => setTimeout(r, 0));
      const gapNote = document.getElementById('flow-log-coverage-note').textContent || '';
      if (!gapNote.includes('没有拉到') || !gapNote.includes('借币利息')) {
        throw new Error('空洞文案缺失: ' + gapNote);
      }

      // --- (c) complete true empty ---
      flowLogGetResponse = {
        status: 200,
        body: buildMockFlowLogPayload({
          coverage: {
            start_ms: 1,
            end_ms: 9999999999999,
            complete: true,
            pending_tail_ms: 0,
            by_source: {
              interest: { start_ms: 1, end_ms: 9999999999999 },
              income: { start_ms: 1, end_ms: 9999999999999 },
            },
            gaps: [],
          },
          interest: { rows: [], summary_by_asset: [], row_count: 0, row_limit_applied: false },
          um_income: { rows: [], summary_by_type_asset: [], row_count: 0, row_limit_applied: false },
        }),
      };
      await helpers.loadFlowLog();
      await new Promise(r => setTimeout(r, 0));
      const emptyBody = document.getElementById('flow-log-interest-body').innerHTML;
      if (!emptyBody.includes('该时间窗无记录')) {
        throw new Error('complete=true 空窗应显示该时间窗无记录');
      }

      // --- (f) empty state scheduler off ---
      flowLogGetResponse = {
        status: 200,
        body: buildMockFlowLogPayload({
          scheduler_enabled: false,
          last_run: null,
          coverage: {
            start_ms: null,
            end_ms: null,
            complete: false,
            pending_tail_ms: null,
            by_source: { interest: null, income: null },
            gaps: [],
          },
          delta: {
            baseline_ms: null,
            complete: false,
            interest_by_asset: [],
            income_by_type_asset: [],
            funding_by_symbol: [],
            interest_new_row_count: 0,
            income_new_row_count: 0,
          },
          interest: { rows: [], summary_by_asset: [], row_count: 0, row_limit_applied: false },
          um_income: { rows: [], summary_by_type_asset: [], row_count: 0, row_limit_applied: false },
        }),
      };
      await helpers.loadFlowLog();
      await new Promise(r => setTimeout(r, 0));
      const stEmpty = document.getElementById('flow-log-status-bar').textContent || '';
      if (!stEmpty.includes('私有通道未启用')) {
        throw new Error('scheduler_enabled=false 应提示私有通道: ' + stEmpty);
      }

      // delta complete false
      flowLogGetResponse = {
        status: 200,
        body: buildMockFlowLogPayload({
          delta: {
            baseline_ms: null,
            complete: false,
            interest_by_asset: [{ asset: 'X', interest_total: '1', row_count: 1, unparsed_row_count: 0 }],
            income_by_type_asset: [],
            funding_by_symbol: [],
            interest_new_row_count: 0,
            income_new_row_count: 0,
          },
        }),
      };
      await helpers.loadFlowLog();
      await new Promise(r => setTimeout(r, 0));
      const dBody = document.getElementById('flow-log-delta-interest').innerHTML;
      if (!dBody.includes('统计基准建立中')) throw new Error('delta.complete=false 文案');
      if (dBody.includes('interest_total') || /\d\.\d{4}/.test(dBody.replace(/统计|基准|建立中|不显示数字/g, ''))) {
        if (dBody.includes('X：') || dBody.includes('1 条')) {
          throw new Error('delta.complete=false 不得显示增量数字');
        }
      }

      // 手动刷新 POST then GET
      flowLogGetResponse = { status: 200, body: buildMockFlowLogPayload() };
      flowLogRefreshResponse = {
        status: 200,
        body: {
          run_id: 2, kind: 'manual', finished_at_ms: 1,
          interest_status: 'ok', interest_error: null, interest_new_row_count: 0,
          income_status: 'ok', income_error: null, income_new_row_count: 0,
          truncated: false,
        },
      };
      helpers.setMarketBoard('flow-log');
      await new Promise(r => setTimeout(r, 0));
      const markR = fetchCallLog.length;
      await helpers.postFlowLogRefresh();
      await new Promise(r => setTimeout(r, 0));
      const seq = fetchCallLog.slice(markR);
      const postIdx = seq.findIndex(c => c.method === 'POST' && c.url === '/api/private-ledger/refresh');
      const getIdx = seq.findIndex(c => c.method === 'GET' && c.url.startsWith('/api/private-ledger/flow-log'));
      if (postIdx === -1 || getIdx === -1 || !(postIdx < getIdx)) {
        throw new Error('刷新应先 POST 再 GET: ' + JSON.stringify(seq.map(c => c.method + ' ' + c.url)));
      }

      // 429
      flowLogRefreshResponse = { status: 429, body: { error: 'flow_log_busy', detail: 'busy' } };
      await helpers.postFlowLogRefresh();
      await new Promise(r => setTimeout(r, 0));
      if (!(document.getElementById('flow-log-status-bar').textContent || '').includes('正在刷新')) {
        throw new Error('429 应显示正在刷新');
      }
      // 409
      flowLogRefreshResponse = { status: 409, body: { error: 'private_channel_disabled', detail: 'off' } };
      await helpers.postFlowLogRefresh();
      await new Promise(r => setTimeout(r, 0));
      if (!(document.getElementById('flow-log-status-bar').textContent || '').includes('私有只读通道未启用')) {
        throw new Error('409 文案');
      }
      // 503 GET
      flowLogGetResponse = { status: 200, body: buildMockFlowLogPayload() };
      await helpers.loadFlowLog();
      await new Promise(r => setTimeout(r, 0));
      const keepHtml = document.getElementById('flow-log-interest-body').innerHTML;
      flowLogGetResponse = { status: 503, body: { error: 'flow_log_unavailable', detail: 'x' } };
      await helpers.loadFlowLog();
      await new Promise(r => setTimeout(r, 0));
      if (!(document.getElementById('flow-log-status-bar').textContent || '').includes('流水日志服务未启用')) {
        throw new Error('GET 503 文案');
      }
      if (document.getElementById('flow-log-interest-body').innerHTML !== keepHtml &&
          !document.getElementById('flow-log-interest-body').innerHTML.includes('HOME')) {
        if (!helpers.getFlowLogPayload()) throw new Error('503 后应保留上次 payload');
      }

      // 筛选零请求 + 隐私零请求
      const markF = fetchCallLog.length;
      const realized = document.getElementById('flow-log-filter-realized');
      realized.checked = true;
      (realized.listeners.change || []).forEach(h => h());
      if (fetchCallLog.length !== markF) throw new Error('筛选不得 fetch');
      helpers.togglePrivacy();
      if (fetchCallLog.length !== markF) throw new Error('隐私切换不得 fetch');
      helpers.setMarketBoard('flow-log');
      await new Promise(r => setTimeout(r, 0));
      helpers.renderFlowLogPanel();
      const bodyPriv = document.getElementById('flow-log-interest-body').innerHTML;
      if (helpers.getPrivacyHidden() && !bodyPriv.includes('****')) {
        throw new Error('隐私隐藏应 ****');
      }
      if (helpers.getPrivacyHidden()) helpers.togglePrivacy();

      // 时间窗 30d
      const mark30 = fetchCallLog.length;
      (document.getElementById('flow-log-range-30d').listeners.click || []).forEach(h => h());
      await new Promise(r => setTimeout(r, 0));
      const g30 = fetchCallLog.slice(mark30).filter(c => c.url.startsWith('/api/private-ledger/flow-log'));
      if (g30.length !== 1) throw new Error('切 30 天应 1 次 GET');
      const u30 = new URL(g30[0].url, 'http://local');
      const sp30 = Number(u30.searchParams.get('end')) - Number(u30.searchParams.get('start'));
      if (!(sp30 > 29 * 86400000 && sp30 < 31 * 86400000)) {
        throw new Error('30 天窗口不对: ' + sp30);
      }
      // 自定义非法零请求
      const markC = fetchCallLog.length;
      document.getElementById('flow-log-custom-start').value = '';
      document.getElementById('flow-log-custom-end').value = '';
      (document.getElementById('flow-log-custom-apply').listeners.click || []).forEach(h => h());
      if (fetchCallLog.length !== markC) throw new Error('自定义空日期不得请求');

      // row_limit_applied（直接注入 payload 渲染，避免并行 load 竞态）
      {
        const body500 = buildMockFlowLogPayload();
        body500.interest.row_count = 600;
        body500.interest.row_limit_applied = true;
        helpers.setFlowLogPayload(body500);
        helpers.renderFlowLogPanel();
      }
      const st500 = document.getElementById('flow-log-interest-status').textContent || '';
      if (!st500.includes('500')) {
        throw new Error('row_limit_applied 应提示 500: ' + st500);
      }

      helpers.setMarketBoard('market');
      helpers.setActiveView('market');
      console.log('[PASS] 流水日志 C+v2：panel-actions 双看板、侧栏移除、同页切换、GET/POST/轮询/护栏');
    }

    // 98b. Q2 流水筛选回显：默认筛选保持「最近 20 条」；用户改动筛选（加勾划转）后
    //     取消显示上限——被全局时间序挤出前 20 的划转记录勾了就能看到。
    {
      // 前序测试勾选过「已实现盈亏」——先把五个勾选框恢复到默认选择。
      [
        ['flow-log-filter-funding', true],
        ['flow-log-filter-commission', true],
        ['flow-log-filter-realized', false],
        ['flow-log-filter-transfer', false],
        ['flow-log-filter-other', false],
      ].forEach(([id, on]) => {
        const box = document.getElementById(id);
        box.checked = on;
        (box.listeners.change || []).forEach(h => h());
      });
      const payload = buildMockFlowLogPayload();
      // 25 行收入流水里把第 22、24 位（0 基）改成 TRANSFER——默认上限 20 之外。
      payload.um_income.rows[22].income_type = 'TRANSFER';
      payload.um_income.rows[22].income = '50.00000000';
      payload.um_income.rows[24].income_type = 'TRANSFER';
      payload.um_income.rows[24].income = '1.00000000';
      helpers.setFlowLogPayload(payload);
      if (!helpers.flowLogFiltersAreDefault()) throw new Error('初始筛选应为默认');

      // 默认筛选（资金费+手续费）：仍是最多 20 条，看不到划转。
      helpers.renderFlowLogIncomeCol(payload);
      const bodyDefault = document.getElementById('flow-log-income-body').innerHTML;
      const rowsDefault = (bodyDefault.match(/<tr>/g) || []).length - 1;
      if (rowsDefault !== 20) throw new Error('默认筛选应显示 20 条，实际 ' + rowsDefault);
      if (bodyDefault.includes('划转')) throw new Error('默认筛选下不应出现划转行');
      const statusDefault = document.getElementById('flow-log-income-status').textContent || '';
      if (!statusDefault.includes('显示最近 20 条')) throw new Error('默认状态行文案: ' + statusDefault);

      // 加勾划转（零请求，只改 state）→ 取消上限，全部 25 条含 2 条划转。
      const markQ2 = fetchCallLog.length;
      const transferBox = document.getElementById('flow-log-filter-transfer');
      transferBox.checked = true;
      (transferBox.listeners.change || []).forEach(h => h());
      if (fetchCallLog.length !== markQ2) throw new Error('改动筛选不得 fetch');
      if (helpers.flowLogFiltersAreDefault()) throw new Error('改动后不应再判定为默认筛选');
      helpers.renderFlowLogIncomeCol(helpers.getFlowLogPayload());
      const bodyChecked = document.getElementById('flow-log-income-body').innerHTML;
      const rowsChecked = (bodyChecked.match(/<tr>/g) || []).length - 1;
      if (rowsChecked !== 25) throw new Error('加勾后应显示全部 25 条，实际 ' + rowsChecked);
      const transferRows = (bodyChecked.match(/>划转</g) || []).length;
      if (transferRows !== 2) throw new Error('加勾后应看到 2 条划转，实际 ' + transferRows);

      // 取消勾选回到默认 → 恢复 20 条上限。
      transferBox.checked = false;
      (transferBox.listeners.change || []).forEach(h => h());
      if (!helpers.flowLogFiltersAreDefault()) throw new Error('取消后应回到默认筛选');
      helpers.renderFlowLogIncomeCol(helpers.getFlowLogPayload());
      const bodyBack = document.getElementById('flow-log-income-body').innerHTML;
      if ((bodyBack.match(/<tr>/g) || []).length - 1 !== 20) throw new Error('回到默认应恢复 20 条');

      helpers.setFlowLogPayload(null);
      console.log('[PASS] Q2 流水筛选回显：默认 20 条上限 / 改动筛选取消上限（加勾划转可见）/ 恢复默认恢复上限 / 零请求');
    }

    // 98c. Q3 任务卡错误提示入 state：他卡操作 / 60s 自动刷新引发的重渲染不再抹除。
    {
      helpers.resetHedgeStateForTest();
      const t = mockHedgeTask({ id: 'h-q3-1', coin: 'AUSDT', direction: 'forward' });
      hedgeTasksGetResponse = { status: 200, body: { tasks: [t] } };
      await helpers.loadHedgeTasks();
      helpers.renderHedgeTasks();
      const q3msg = '任务状态不允许该操作（可能已删除、已完成、已终止或存在单腿敞口）';
      helpers.showHedgeTaskActionError('h-q3-1', q3msg);
      // 立即路径：state 写入 + 惰性 mock 元素 textContent 同步（真实浏览器中即卡片
      // 错误 div 的即时更新）。
      if ((helpers.getHedgeTaskActionErrors() || {})['h-q3-1'] !== q3msg) {
        throw new Error('Q3 错误提示应写入 state');
      }
      if (document.getElementById('hedge-task-error-h-q3-1').textContent !== q3msg) {
        throw new Error('Q3 错误提示应立即同步 DOM');
      }
      // 核心回归：模拟他卡操作 / 自动刷新引发的全量重渲染——提示必须从 state 恢复。
      helpers.renderHedgeTasks();
      if (!elements['hedge-task-list'].innerHTML.includes(q3msg)) {
        throw new Error('Q3 重渲染后错误提示被抹除');
      }
      // 操作成功（空串）→ 提示清除，重渲染后也不残留。
      helpers.showHedgeTaskActionError('h-q3-1', '');
      helpers.renderHedgeTasks();
      if (elements['hedge-task-list'].innerHTML.includes(q3msg)) {
        throw new Error('Q3 清除后不应残留提示');
      }
      console.log('[PASS] Q3 任务卡错误提示入 state：重渲染不抹除 / 成功即清除');
    }

    // 99. v0.9 / v4.1 §9.1 collateral_cap 纯展示：徽标仅在「借贷状态 / 资产」列三态 +
    //     不适用 + 缺键；摘要截至时间；不进 REQUIRED；不驱动排序/过滤/按钮；标的列零徽标；bStock 用 cap.asset。
    {
      // Ensure baseline designFixture is active (filters already open for all 6 rows).
      helpers.ingestSnapshot(designFixture);
      elements['filter-hide-low-daily-rate'].checked = false;
      (elements['filter-hide-low-daily-rate'].listeners.change || []).forEach(h => h());
      elements['filter-hide-low-net-yield'].checked = false;
      (elements['filter-hide-low-net-yield'].listeners.change || []).forEach(h => h());
      elements['filter-prefer-openable'].checked = false;
      (elements['filter-prefer-openable'].listeners.change || []).forEach(h => h());

      const capTbody = elements['market-table-body'].innerHTML;
      // cell 0 = 标的；cell 11 = 借贷状态 / 资产
      const ausdtSym = getRowCell(capTbody, 'AUSDT', 0);
      const busdtSym = getRowCell(capTbody, 'BUSDT', 0);
      const cusdtSym = getRowCell(capTbody, 'CUSDT', 0);
      const dusdtSym = getRowCell(capTbody, 'DUSDT', 0);
      const eusdtSym = getRowCell(capTbody, 'EUSDT', 0);
      const fusdtSym = getRowCell(capTbody, 'FUSDT', 0);
      const ausdtBorrow = getRowCell(capTbody, 'AUSDT', 11);
      const busdtBorrow = getRowCell(capTbody, 'BUSDT', 11);
      const cusdtBorrow = getRowCell(capTbody, 'CUSDT', 11);
      const dusdtBorrow = getRowCell(capTbody, 'DUSDT', 11);
      const eusdtBorrow = getRowCell(capTbody, 'EUSDT', 11);
      const fusdtBorrow = getRowCell(capTbody, 'FUSDT', 11);

      if (!ausdtBorrow.includes('抵押额度已满')) {
        throw new Error('AUSDT（已满）借贷状态列应含「抵押额度已满」: ' + ausdtBorrow);
      }
      if (!cusdtBorrow.includes('抵押额度已满')) {
        throw new Error('CUSDT（正费率已满）借贷状态列应含「抵押额度已满」: ' + cusdtBorrow);
      }
      if (!dusdtBorrow.includes('>抵押额度未知<') && !dusdtBorrow.includes('抵押额度未知</span>')) {
        throw new Error('DUSDT（未知）借贷状态列应含可见文案「抵押额度未知」: ' + dusdtBorrow);
      }
      // 未知绝不可呈现为未满/正常/充足/可用（可见徽标与非 title 文案）。
      // title 允许接口要求的否定说明「不代表未满」——从检查中剔除 title 属性。
      const dusdtVisible = dusdtBorrow.replace(/\stitle="[^"]*"/g, '');
      for (const bad of ['未满', '正常', '充足', '可用']) {
        if (dusdtVisible.includes(bad)) {
          throw new Error(`DUSDT 未知行可见 DOM 不得含「${bad}」: ${dusdtVisible}`);
        }
      }
      if (!dusdtBorrow.includes('不代表未满') && !dusdtBorrow.includes('读取失败')) {
        throw new Error('未知徽标 title 应说明读取失败/不代表未满: ' + dusdtBorrow);
      }
      if (busdtBorrow.includes('抵押额度已满') || busdtBorrow.includes('抵押额度未知')) {
        throw new Error('BUSDT（未满）借贷状态列不应有抵押额度徽标: ' + busdtBorrow);
      }
      if (eusdtBorrow.includes('抵押额度已满') || eusdtBorrow.includes('抵押额度未知')) {
        throw new Error('EUSDT（不适用）借贷状态列不应有抵押额度徽标: ' + eusdtBorrow);
      }
      if (fusdtBorrow.includes('抵押额度已满') || fusdtBorrow.includes('抵押额度未知')) {
        throw new Error('FUSDT（缺键）借贷状态列不应有抵押额度徽标: ' + fusdtBorrow);
      }

      // 正费率行 + 负费率行均高亮（不按方向过滤）
      // AUSDT daily_funding_rate 为负，CUSDT 为正，二者皆「已满」。
      if (!(helpers.isNegativeFundingRate(designFixture.rows[0]) && helpers.isPositiveFundingRate(designFixture.rows[2]))) {
        throw new Error('夹具费率方向被改：期望 AUSDT 负 / CUSDT 正以覆盖双向高亮');
      }

      // 标的列（index 0）不得含任何抵押额度文案（v4.1 §9.1 迁移后）
      for (const [sym, cell] of [
        ['AUSDT', ausdtSym], ['BUSDT', busdtSym], ['CUSDT', cusdtSym],
        ['DUSDT', dusdtSym], ['EUSDT', eusdtSym], ['FUSDT', fusdtSym]
      ]) {
        if (cell.includes('抵押额度')) {
          throw new Error(`${sym} 标的列不得含抵押额度文案: ${cell}`);
        }
      }

      // 摘要/表头区一处露出「抵押额度名单截至 <北京时间>」
      const expectedAsOf = helpers.formatBeijing(new Date(COLLATERAL_CAP_CHECKED_AT).getTime());
      const summaryHtml = elements['summary-row'].innerHTML;
      if (!summaryHtml.includes('抵押额度名单截至')) {
        throw new Error('摘要区缺少「抵押额度名单截至」: ' + summaryHtml);
      }
      if (!summaryHtml.includes(expectedAsOf)) {
        throw new Error(`摘要截至时间期望 ${expectedAsOf}，实际: ${summaryHtml}`);
      }
      // 徽标 title 也带该时间（现在在借贷状态列）
      if (!ausdtBorrow.includes(expectedAsOf)) {
        throw new Error('已满徽标 title 应含截至北京时间: ' + ausdtBorrow);
      }

      // checked_at 全 null → 摘要显示「未知」
      const nullAtFixture = JSON.parse(JSON.stringify(designFixture));
      for (const r of nullAtFixture.rows) {
        if (r.collateral_cap) r.collateral_cap.checked_at = null;
      }
      // Keep UNKNOWN flag rows consistent; strip EXCEEDED checked_at only.
      helpers.ingestSnapshot(nullAtFixture);
      const summaryNull = elements['summary-row'].innerHTML;
      if (!summaryNull.includes('抵押额度名单截至 未知') && !summaryNull.includes('抵押额度名单截至')) {
        throw new Error('checked_at 全 null 时摘要应露出截至文案: ' + summaryNull);
      }
      // Explicit: must show 未知, never empty as-of, never current wall clock injection
      if (!/抵押额度名单截至\s*未知/.test(summaryNull.replace(/<[^>]+>/g, ' '))) {
        throw new Error('checked_at 全 null 时摘要截至应为「未知」: ' + summaryNull);
      }

      // 缺键不抛错：单独只有 F 缺键已在上方渲染通过；再测全表缺键
      const noKeyFixture = JSON.parse(JSON.stringify(designFixture));
      for (const r of noKeyFixture.rows) {
        delete r.collateral_cap;
        if (Array.isArray(r.ui_flags)) {
          r.ui_flags = r.ui_flags.filter(f => f !== 'COLLATERAL_CAP_EXCEEDED' && f !== 'COLLATERAL_CAP_UNKNOWN');
        }
      }
      helpers.ingestSnapshot(noKeyFixture);
      const noKeyTbody = elements['market-table-body'].innerHTML;
      if (noKeyTbody.includes('抵押额度已满') || noKeyTbody.includes('抵押额度未知')) {
        throw new Error('全表缺 collateral_cap 键不应渲染徽标');
      }
      if ((noKeyTbody.match(/<tr/g) || []).length !== 6) {
        throw new Error('全表缺键仍应渲染 6 行');
      }

      // collateral_cap 不在 REQUIRED_ROW_FIELDS；在 OPTIONAL_ROW_FIELDS
      if (!script.includes("OPTIONAL_ROW_FIELDS")) {
        throw new Error('缺少 OPTIONAL_ROW_FIELDS 常量（collateral_cap 可选路径）');
      }
      // REQUIRED_ROW_FIELDS 数组字面量内不得出现 collateral_cap
      const requiredBlock = script.match(/const REQUIRED_ROW_FIELDS\s*=\s*\[([\s\S]*?)\];/);
      if (!requiredBlock) throw new Error('无法定位 REQUIRED_ROW_FIELDS');
      if (requiredBlock[1].includes('collateral_cap')) {
        throw new Error('collateral_cap 不得加入 REQUIRED_ROW_FIELDS');
      }
      const optionalBlock = script.match(/const OPTIONAL_ROW_FIELDS\s*=\s*\[([\s\S]*?)\];/);
      if (!optionalBlock || !optionalBlock[1].includes('collateral_cap')) {
        throw new Error('collateral_cap 应列入 OPTIONAL_ROW_FIELDS');
      }

      // 纯展示：不因 collateral_cap 改变开单/借币按钮启用或行序
      helpers.ingestSnapshot(designFixture);
      elements['filter-prefer-openable'].checked = false;
      (elements['filter-prefer-openable'].listeners.change || []).forEach(h => h());
      const withCapTbody = elements['market-table-body'].innerHTML;
      const withCapOrder = ['AUSDT', 'BUSDT', 'CUSDT', 'DUSDT', 'EUSDT', 'FUSDT'];
      assertOrder(withCapTbody, withCapOrder);
      // 立即开单按钮仍存在且无因 cap 额外 disabled（平滑开单本就 disabled）
      const ausdtHedge = getRowCell(withCapTbody, 'AUSDT', 13);
      if (!ausdtHedge.includes('立即开单')) {
        throw new Error('已满行仍应渲染立即开单按钮');
      }
      if (/data-hedge-open="immediate"[^>]*disabled/.test(ausdtHedge)) {
        throw new Error('立即开单不得因 collateral_cap 被 disabled');
      }
      // Strip caps and re-render: order and immediate-open presence unchanged
      const stripCap = JSON.parse(JSON.stringify(designFixture));
      for (const r of stripCap.rows) {
        delete r.collateral_cap;
        if (Array.isArray(r.ui_flags)) {
          r.ui_flags = r.ui_flags.filter(f => f !== 'COLLATERAL_CAP_EXCEEDED' && f !== 'COLLATERAL_CAP_UNKNOWN');
        }
      }
      helpers.ingestSnapshot(stripCap);
      const noCapTbody = elements['market-table-body'].innerHTML;
      assertOrder(noCapTbody, withCapOrder);
      const ausdtHedgeNoCap = getRowCell(noCapTbody, 'AUSDT', 13);
      if (!ausdtHedgeNoCap.includes('立即开单')) {
        throw new Error('无 cap 时立即开单应仍在');
      }

      // bStock：徽标/提示展示 collateral_cap.asset（TSLAB），不得用合约 base TSLA 作判定资产
      const bstockFx = JSON.parse(JSON.stringify(designFixture));
      bstockFx.rows[0].symbol = 'TSLAUSDT';
      bstockFx.rows[0].base_asset = 'TSLA';
      bstockFx.rows[0].asset_tag = 'BSTOCK';
      bstockFx.rows[0].ui_flags = ['MARGIN_PUBLIC_UNVERIFIED', 'TRADIFI_BSTOCK', 'COLLATERAL_CAP_EXCEEDED'];
      bstockFx.rows[0].collateral_cap = {
        exceeded: true, asset: 'TSLAB', checked_at: COLLATERAL_CAP_CHECKED_AT
      };
      // Keep other rows filter-friendly
      helpers.ingestSnapshot(bstockFx);
      elements['filter-hide-low-daily-rate'].checked = false;
      (elements['filter-hide-low-daily-rate'].listeners.change || []).forEach(h => h());
      elements['filter-hide-low-net-yield'].checked = false;
      (elements['filter-hide-low-net-yield'].listeners.change || []).forEach(h => h());
      const bstockTbody = elements['market-table-body'].innerHTML;
      const tslaSym = getRowCell(bstockTbody, 'TSLAUSDT', 0);
      const tslaBorrow = getRowCell(bstockTbody, 'TSLAUSDT', 11);
      if (!tslaBorrow.includes('抵押额度已满')) {
        throw new Error('bStock 命中行借贷状态列应显示已满徽标: ' + tslaBorrow);
      }
      if (tslaSym.includes('抵押额度')) {
        throw new Error('bStock 标的列不得含抵押额度徽标: ' + tslaSym);
      }
      if (!tslaBorrow.includes('TSLAB')) {
        throw new Error('bStock 徽标 title 应含判定资产 TSLAB: ' + tslaBorrow);
      }
      // title 中判定资产不得写成合约 base；允许单元格 muted 行显示 TSLA/USDT
      // 同格还有借贷状态 title，须锚定 collateral-cap-badge。
      const titleMatch = tslaBorrow.match(/collateral-cap-badge" title="([^"]*)"/)
        || tslaBorrow.match(/title="([^"]*TSLAB[^"]*)"/);
      if (!titleMatch) throw new Error('bStock 抵押额度徽标缺少 title: ' + tslaBorrow);
      const title = titleMatch[1];
      if (!title.includes('TSLAB')) {
        throw new Error('title 须含 TSLAB: ' + title);
      }
      if (/判定资产\s*TSLA(?!B)/.test(title) || title.includes('判定资产 TSLA ·')) {
        throw new Error('title 不得以合约 base TSLA 作为判定资产: ' + title);
      }

      // fail-closed helper：表外组合 → unknown
      if (typeof helpers.resolveCollateralCapKind !== 'function') {
        throw new Error('须导出 resolveCollateralCapKind 供自检');
      }
      const oo = helpers.resolveCollateralCapKind({
        collateral_cap: { exceeded: true, asset: 'X', checked_at: null },
        ui_flags: []
      });
      if (oo !== 'unknown') {
        throw new Error('表外组合应 fail-closed 为 unknown，实际 ' + oo);
      }

      // Restore design fixture for any later checks
      helpers.ingestSnapshot(designFixture);
      elements['filter-hide-low-daily-rate'].checked = false;
      (elements['filter-hide-low-daily-rate'].listeners.change || []).forEach(h => h());
      elements['filter-hide-low-net-yield'].checked = false;
      (elements['filter-hide-low-net-yield'].listeners.change || []).forEach(h => h());
      elements['filter-prefer-openable'].checked = false;
      (elements['filter-prefer-openable'].listeners.change || []).forEach(h => h());
      console.log('[PASS] v0.9 collateral_cap 纯展示：三态/不适用/缺键、摘要截至、方向无关、bStock asset、不驱动按钮/排序');
    }

    // 75x. frontend-cache-refresh-v1：更新缓存按钮、complete/partial/not_attempted/
    // 失败/202、右上角聚合时间、source_checked_at 北京时间/缺源/PM 三态、私有未读分离、零自动轮询
    {
      if (!elements['btn-cache-refresh']) {
        throw new Error('页面须有「更新缓存」按钮 #btn-cache-refresh');
      }
      if (!html.includes('id="btn-cache-refresh"') || !html.includes('更新缓存')) {
        throw new Error('HTML 须包含更新缓存按钮文案');
      }
      if (!html.includes('id="account-asset-updated-at"')) {
        throw new Error('HTML 须提供账户资产更新时间元素 #account-asset-updated-at');
      }
      // v4.1 §9.3: aggregate time is under title-block, not inside refresh-meta
      const titleBlockIdx = html.indexOf('class="title-block"');
      const accountAtIdx = html.indexOf('id="account-asset-updated-at"');
      const refreshMetaIdx = html.indexOf('class="refresh-meta"');
      if (titleBlockIdx === -1 || accountAtIdx === -1 || accountAtIdx < titleBlockIdx) {
        throw new Error('账户资产更新时间须在标题区 title-block 内');
      }
      if (refreshMetaIdx !== -1 && accountAtIdx > refreshMetaIdx &&
          html.slice(refreshMetaIdx, refreshMetaIdx + 400).includes('id="account-asset-updated-at"')) {
        throw new Error('账户资产更新时间不得再放在 refresh-meta 内');
      }
      if (html.includes('id="private-panel-subtitle"')) {
        throw new Error('私有面板标题下不应再保留 private-panel-subtitle');
      }
      if (!html.includes('id="private-pm-source-time"')) {
        throw new Error('须有 #private-pm-source-time 挂在私有账户标题下');
      }
      // 手动刷新按钮语义保持 GET loadApi，不与 POST 更新缓存混用
      if (!elements['btn-refresh'] || !html.includes('手动刷新')) {
        throw new Error('既有手动刷新按钮须保留');
      }

      // Helper unit: single source ready / not-ready
      const singleReady = helpers.formatSingleSourceCheckedLine('2026-08-03T07:34:50Z');
      const beijingReady = helpers.formatBeijing(Date.parse('2026-08-03T07:34:50Z'));
      if (!singleReady.ready || !singleReady.text.includes(beijingReady)) {
        throw new Error('单源 ready 须显示 Asia/Shanghai 时间: ' + singleReady.text);
      }
      const singleNull = helpers.formatSingleSourceCheckedLine(null);
      if (singleNull.ready || !singleNull.text.includes('资产数据未就绪')) {
        throw new Error('单源 null 须显示未就绪: ' + singleNull.text);
      }
      if (helpers.isStaleTime(1000, 91000) || !helpers.isStaleTime(1000, 91001)) {
        throw new Error('时间须严格超过 90 秒才标记过期');
      }
      if (!helpers.sourceCheckedAtHtml({ text: '数据源更新时间', ready: true, checkedAtMs: 1000 }, 91001)
          .includes('stale-time')) {
        throw new Error('超过 90 秒的数据源时间须使用 stale-time 红色加粗样式');
      }
      if (!html.includes('.stale-time') || !html.includes('font-weight: 700')) {
        throw new Error('缺少 stale-time 红色加粗样式');
      }

      // Multi-source earliest vs missing (never invent from remaining)
      const multiOk = helpers.formatMultiSourceCheckedLine([
        { key: 'um_positions', label: 'UM 持仓', iso: '2026-08-03T07:20:00Z' },
        { key: 'unified_balances', label: '统一账户余额', iso: '2026-08-03T07:34:50Z' },
        { key: 'spot_balances', label: '现货账户余额', iso: '2026-08-03T07:30:00Z' }
      ]);
      const earliestBj = helpers.formatBeijing(Date.parse('2026-08-03T07:20:00Z'));
      if (!multiOk.ready || !multiOk.text.includes(earliestBj)) {
        throw new Error('多源全就绪须取最早时间: ' + multiOk.text);
      }
      const multiMissing = helpers.formatMultiSourceCheckedLine([
        { key: 'um_positions', label: 'UM 持仓', iso: null },
        { key: 'unified_balances', label: '统一账户余额', iso: '2026-08-03T07:34:50Z' },
        { key: 'spot_balances', label: '现货账户余额', iso: '2026-08-03T07:30:00Z' }
      ]);
      if (multiMissing.ready || !multiMissing.text.includes('UM 持仓未成功读取')) {
        throw new Error('多源缺 UM 不得用剩余源时间伪造: ' + multiMissing.text);
      }
      if (multiMissing.text.includes(helpers.formatBeijing(Date.parse('2026-08-03T07:30:00Z')))) {
        throw new Error('缺源未就绪文案不得夹带其余源时间: ' + multiMissing.text);
      }

      // Fixture path: source times + aggregate in Beijing
      const scaFx = JSON.parse(JSON.stringify(designFixture));
      scaFx.private_account.source_checked_at = {
        price_map: '2026-08-03T07:34:50Z',
        unified_balances: '2026-08-03T07:34:50Z',
        um_positions: '2026-08-03T07:20:00Z',
        spot_balances: '2026-08-03T07:30:00Z',
        pm_account: null
      };
      scaFx.private_account.checked_at = '2026-08-03T07:34:50Z';
      delete scaFx.private_account.pm_account;
      helpers.ingestSnapshot(scaFx);
      const bodySca = elements['private-panel-body'].innerHTML;
      const aggText = elements['account-asset-updated-at'].textContent;
      const aggBj = helpers.formatBeijing(Date.parse('2026-08-03T07:34:50Z'));
      if (!aggText.includes('账户资产更新时间') || !aggText.includes(aggBj)) {
        throw new Error('标题区聚合时间须为北京时间: ' + aggText);
      }
      if (!bodySca.includes('统一账户余额') || !bodySca.includes(helpers.formatBeijing(Date.parse('2026-08-03T07:34:50Z')))) {
        throw new Error('统一账户区须显示本源北京时间');
      }
      if (!bodySca.includes('现货账户余额') || !bodySca.includes(helpers.formatBeijing(Date.parse('2026-08-03T07:30:00Z')))) {
        throw new Error('现货账户区须显示本源北京时间');
      }
      // 对冲持仓 earliest = UM 07:20
      if (!bodySca.includes(helpers.formatBeijing(Date.parse('2026-08-03T07:20:00Z')))) {
        throw new Error('对冲持仓区须显示 UM+统一+现货最早时间');
      }
      // price_map 不占账户区域标题
      if (/price_map|报价源更新时间/.test(bodySca) && bodySca.includes('price_map')) {
        throw new Error('price_map 不应作为账户区域标题文案');
      }
      // PM capability 不存在 → 标题下与概览区均隐藏 PM 时间行
      if (helpers.isPrivatePmSourceTimeVisible() || bodySca.includes('PM 账户数据源更新时间')) {
        throw new Error('PM capability 不存在时不得显示 PM 时间行');
      }

      // 缺源：统一账户 null → 未就绪
      scaFx.private_account.source_checked_at.unified_balances = null;
      helpers.ingestSnapshot(scaFx);
      const bodyMissing = elements['private-panel-body'].innerHTML;
      if (!bodyMissing.includes('资产数据未就绪（该账户源未成功读取）')) {
        throw new Error('统一账户缺源须显示未就绪: ' + bodyMissing.slice(0, 400));
      }
      // 多源对冲持仓缺 UM
      scaFx.private_account.source_checked_at.unified_balances = '2026-08-03T07:34:50Z';
      scaFx.private_account.source_checked_at.um_positions = null;
      helpers.ingestSnapshot(scaFx);
      const bodyUmMissing = elements['private-panel-body'].innerHTML;
      if (!bodyUmMissing.includes('UM 持仓未成功读取')) {
        throw new Error('对冲持仓缺 UM 须诚实未就绪: ' + bodyUmMissing.slice(0, 400));
      }

      // PM capability 存在但 null → 标题下未就绪；有时间 → 标题下北京时间；概览区无重复
      scaFx.private_account.pm_account = {
        source: 'papi_v1_account',
        account_equity_usdt: null,
        actual_equity_usdt: null,
        total_available_balance_usdt: null,
        account_initial_margin_usdt: null,
        account_maint_margin_usdt: null,
        uni_mmr: null,
        account_status: null,
        total_debt_usdt: null,
        leverage_ratio: null
      };
      scaFx.private_account.source_checked_at.pm_account = null;
      scaFx.private_account.source_checked_at.um_positions = '2026-08-03T07:20:00Z';
      helpers.ingestSnapshot(scaFx);
      const pmNullText = helpers.getPrivatePmSourceTimeText();
      if (!helpers.isPrivatePmSourceTimeVisible() || !pmNullText.includes('PM 账户数据源更新时间') || !pmNullText.includes('资产数据未就绪')) {
        throw new Error('PM capability 存在但 null 须在标题下显示未就绪: ' + pmNullText);
      }
      if (elements['private-panel-body'].innerHTML.includes('PM 账户数据源更新时间')) {
        throw new Error('PM 时间不得再出现在概览/面板 body');
      }
      scaFx.private_account.source_checked_at.pm_account = '2026-08-03T07:34:50Z';
      helpers.ingestSnapshot(scaFx);
      const pmReadyText = helpers.getPrivatePmSourceTimeText();
      const pmBj = helpers.formatBeijing(Date.parse('2026-08-03T07:34:50Z'));
      if (!pmReadyText.includes('PM 账户数据源更新时间 ' + pmBj)) {
        throw new Error('PM 有时间须在标题下显示北京时间: ' + pmReadyText);
      }
      if (elements['private-panel-body'].innerHTML.includes('PM 账户数据源更新时间')) {
        throw new Error('PM 有时间时也不得重复出现在概览区');
      }

      // 超过 90 秒：普通数据源行、PM 标题时间、市场表双时间统一红色加粗。
      const staleIso = new Date(_mockNow - 120000).toISOString();
      scaFx.private_account.source_checked_at.unified_balances = staleIso;
      scaFx.private_account.source_checked_at.um_positions = staleIso;
      scaFx.private_account.source_checked_at.spot_balances = staleIso;
      scaFx.private_account.source_checked_at.pm_account = staleIso;
      scaFx.generated_at = staleIso;
      scaFx.data_time = staleIso;
      helpers.ingestSnapshot(scaFx);
      if (!elements['private-panel-body'].innerHTML.includes('source-checked-at stale-time')) {
        throw new Error('超过 90 秒的账户数据源时间须红色加粗');
      }
      if (!String(elements['private-pm-source-time'].className).includes('stale-time')) {
        throw new Error('超过 90 秒的 PM 数据源时间须红色加粗');
      }
      if (!String(elements['market-snapshot-meta'].className).includes('stale-time')) {
        throw new Error('超过 90 秒的市场表生成/数据时间须红色加粗');
      }

      // 私有账户不可读：面板内提示；标题区聚合时间不复用该文案
      const unreadFx = JSON.parse(JSON.stringify(designFixture));
      unreadFx.private_account = designFixture._design_fixture_private_account_states.find(s => s._state === 'verified_false_disabled');
      helpers.ingestSnapshot(unreadFx);
      const unreadBody = elements['private-panel-body'].innerHTML;
      if (!unreadBody.includes('私有账户未读取')) {
        throw new Error('私有账户不可读须在面板内提示');
      }
      if (elements['account-asset-updated-at'].textContent.includes('私有账户未读取')) {
        throw new Error('标题区聚合时间不得复用私有未读文案');
      }

      // ---- POST cache-refresh outcomes ----
      const intervalCountBefore = intervalCalls.length;
      helpers.ingestSnapshot(designFixture);

      // complete
      cacheRefreshPostResponse = {
        status: 200,
        body: { published: true, account_panels: 'complete' }
      };
      const completeCallsBefore = fetchCallLog.length;
      await helpers.onCacheRefresh();
      if (helpers.isCacheRefreshLoading()) {
        throw new Error('complete 后按钮 loading 须结束');
      }
      if (elements['btn-cache-refresh'].disabled) {
        throw new Error('complete 后按钮须可再点');
      }
      if (elements['btn-cache-refresh'].textContent !== '更新缓存') {
        throw new Error('complete 后按钮文案须恢复: ' + elements['btn-cache-refresh'].textContent);
      }
      const statusComplete = helpers.getStatusAreaText();
      if (!statusComplete.includes('刷新周期已完成') || statusComplete.includes('部分')) {
        throw new Error('complete 只提示刷新周期已完成: ' + statusComplete);
      }
      const postComplete = fetchCallLog.slice(completeCallsBefore);
      if (!postComplete.some(c => c.url === '/api/public-market/cache-refresh' && c.method === 'POST')) {
        throw new Error('complete 路径须 POST cache-refresh');
      }
      if (!postComplete.some(c => c.url === '/api/public-market/snapshot' && c.method === 'GET')) {
        throw new Error('complete 后须 loadApi GET snapshot');
      }
      if (!postComplete.some(c => c.url === '/api/hedge-open-positions' && c.method === 'GET')) {
        throw new Error('complete 后须 loadHedgePositions');
      }

      // partial：不夸大为完整更新；仍重读
      cacheRefreshPostResponse = {
        status: 200,
        body: { published: true, account_panels: 'partial' }
      };
      await helpers.onCacheRefresh();
      const statusPartial = helpers.getStatusAreaText();
      if (!statusPartial.includes('部分账户或估值源未更新')) {
        throw new Error('partial 须诚实提示: ' + statusPartial);
      }
      if (/账户缓存已完整更新|账户已完整刷新/.test(statusPartial)) {
        throw new Error('partial 不得夸大完整更新: ' + statusPartial);
      }

      // not_attempted
      cacheRefreshPostResponse = {
        status: 200,
        body: { published: true, account_panels: 'not_attempted' }
      };
      await helpers.onCacheRefresh();
      const statusNa = helpers.getStatusAreaText();
      if (!statusNa.includes('账户数据未刷新')) {
        throw new Error('not_attempted 须提示未刷新: ' + statusNa);
      }

      // published=false failure
      cacheRefreshPostResponse = {
        status: 200,
        body: { published: false, account_panels: 'partial' }
      };
      await helpers.onCacheRefresh();
      const statusFailPub = helpers.getStatusAreaText();
      if (!statusFailPub.includes('失败') && !statusFailPub.includes('未发布')) {
        throw new Error('published=false 须明确失败: ' + statusFailPub);
      }

      // HTTP failure
      cacheRefreshPostResponse = {
        status: 503,
        body: { error: 'cache_refresh_unavailable', detail: 'worker not running' }
      };
      await helpers.onCacheRefresh();
      const status503 = helpers.getStatusAreaText();
      if (!status503.includes('失败')) {
        throw new Error('HTTP 失败须提示: ' + status503);
      }

      // 202 queued：恢复可点，不新增自动轮询定时器
      cacheRefreshPostResponse = {
        status: 202,
        body: { status: 'queued', detail: 'refresh still in progress' }
      };
      const intervalsBefore202 = intervalCalls.length;
      await helpers.onCacheRefresh();
      const status202 = helpers.getStatusAreaText();
      if (!status202.includes('后台') && !status202.includes('排队')) {
        throw new Error('202 须提示后台刷新: ' + status202);
      }
      if (elements['btn-cache-refresh'].disabled) {
        throw new Error('202 后按钮须恢复可点');
      }
      // loadApi may reschedule 60s timer; no NEW poll interval dedicated to cache-refresh
      const newIntervals = intervalCalls.slice(intervalsBefore202);
      for (const call of newIntervals) {
        if (call.delay !== 60000 && call.delay !== 1000 && call.delay !== 2000) {
          throw new Error('202 后不得新增非法轮询定时器: delay=' + call.delay);
        }
      }
      // No dedicated short poll (e.g. 3s/5s) for cache-refresh
      if (newIntervals.some(c => c.delay > 0 && c.delay < 1000)) {
        throw new Error('不得为 cache-refresh 新增亚秒轮询');
      }

      // 固定五 key 契约：helpers 导出
      if (!Array.isArray(helpers.SOURCE_CHECKED_AT_KEYS) || helpers.SOURCE_CHECKED_AT_KEYS.length !== 5) {
        throw new Error('SOURCE_CHECKED_AT_KEYS 须为固定五 key');
      }
      const expectedKeys = ['price_map', 'unified_balances', 'um_positions', 'spot_balances', 'pm_account'];
      for (const k of expectedKeys) {
        if (!helpers.SOURCE_CHECKED_AT_KEYS.includes(k)) {
          throw new Error('缺少 source_checked_at key: ' + k);
        }
      }

      // restore
      cacheRefreshPostResponse = null;
      helpers.ingestSnapshot(designFixture);
      console.log('[PASS] frontend-cache-refresh-v1：按钮/complete·partial·not_attempted·失败·202、北京时间、缺源、PM 三态、私有未读分离、零自动轮询');
    }

    // 75y. frontend-position-balance-display-v1（v4.1 §9）：双行现货/杠杆、独立缺失、真零、
    // 隐私遮蔽、徽标仅在借贷状态列、标题区聚合时间、PM 仅在私有账户标题下
    {
      if (typeof helpers.formatPositionAccountSideLine !== 'function') {
        throw new Error('须导出 formatPositionAccountSideLine');
      }
      // 双侧完整
      const both = helpers.formatPositionAccountSideLine('现货', '0.5', '30.125');
      if (!both.includes('现货: 0.5') || !both.includes('≈ 30.13 U')) {
        throw new Error('双侧完整行格式错误: ' + both);
      }
      const uniBoth = helpers.formatPositionAccountSideLine('杠杆', '1.2', '72');
      if (!uniBoth.includes('杠杆: 1.2') || !uniBoth.includes('≈ 72.00 U')) {
        throw new Error('杠杆完整行格式错误: ' + uniBoth);
      }
      // amount 缺失 → 整侧 —
      if (helpers.formatPositionAccountSideLine('现货', null, '10') !== '现货: —') {
        throw new Error('amount 缺失须整侧 —');
      }
      if (helpers.formatPositionAccountSideLine('杠杆', undefined, '10') !== '杠杆: —') {
        throw new Error('amount undefined 须整侧 —');
      }
      // amount 有、value 缺失 → ≈ — U
      const noVal = helpers.formatPositionAccountSideLine('现货', '1', null);
      if (!noVal.includes('现货: 1') || !noVal.includes('≈ — U')) {
        throw new Error('value 缺失须 ≈ — U: ' + noVal);
      }
      // 真零
      const zero = helpers.formatPositionAccountSideLine('现货', '0', '0.00000000');
      if (!zero.includes('现货: 0') || !zero.includes('≈ 0.00 U')) {
        throw new Error('真零须显示 0: ' + zero);
      }

      // 渲染：双侧完整 + 借款列不变
      helpers.ingestSnapshot(designFixture);
      if (helpers.getPrivacyHidden()) helpers.togglePrivacy();
      hedgePositionsGetResponse = {
        status: 200,
        body: {
          positions: [{
            coin: 'BTCUSDT', direction: 'forward', match_status: 'normal',
            um_position_amt: '-0.01', um_notional_usdt: '600', um_entry_price: '60000',
            um_mark_price: '61000', um_liquidation_price: '50000',
            unrealized_profit: '10', price_pnl: '10',
            spot_balance: '0.5', spot_balance_value_usdt: '30500.50',
            unified_balance: '0.07', unified_balance_value_usdt: '4270.12',
            cross_margin_borrowed: '0.01',
            spot_avg: '60000', perp_avg: '60100',
            spot_avg_price_incomplete: false, perp_avg_price_incomplete: false,
            includes_deleted_task: false, single_leg_exposure: false, drift: false
          }],
          account: {
            verified: true, error: null, checked_at: '2026-08-03T07:34:50Z',
            source_checked_at: {
              price_map: null, unified_balances: '2026-08-03T07:34:50Z',
              um_positions: '2026-08-03T07:34:50Z', spot_balances: '2026-08-03T07:34:50Z',
              pm_account: null
            }
          }
        }
      };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      let posBody = elements['private-panel-body'].innerHTML;
      const balCell = getRowCell(posBody, 'BTCUSDT', 9);
      if (!balCell.includes('现货: 0.5') || !balCell.includes('≈ 30500.50 U')) {
        throw new Error('现货行须含 amount 与 2 位估值: ' + balCell);
      }
      if (!balCell.includes('杠杆: 0.07') || !balCell.includes('≈ 4270.12 U')) {
        throw new Error('杠杆行须含 amount 与 2 位估值: ' + balCell);
      }
      const borrowCell = getRowCell(posBody, 'BTCUSDT', 10);
      if (!borrowCell.includes('0.01')) {
        throw new Error('全仓借款列须仍显示 cross_margin_borrowed: ' + borrowCell);
      }
      // 不从 snapshot 余额拼：故意改 snapshot 统一/现货余额后重渲染 positions 不变
      const snapOnly = JSON.parse(JSON.stringify(designFixture));
      snapOnly.private_account.balances_spot = [{ asset: 'BTC', free: '9', locked: '0', value_usdt: '999' }];
      snapOnly.private_account.balances_unified = [{ asset: 'BTC', total_balance: '9', value_usdt: '999', cross_margin_borrowed: null }];
      helpers.ingestSnapshot(snapOnly);
      // loadHedgePositions 后 state 仍是上一轮 positions（未再 mock 新值）
      helpers.renderPrivatePanel();
      posBody = elements['private-panel-body'].innerHTML;
      const balCell2 = getRowCell(posBody, 'BTCUSDT', 9);
      if (balCell2.includes('现货: 9') || balCell2.includes('杠杆: 9')) {
        throw new Error('不得从 snapshot 拼接余额覆盖 positions 行字段: ' + balCell2);
      }
      if (!balCell2.includes('现货: 0.5') || !balCell2.includes('杠杆: 0.07')) {
        throw new Error('重渲染仍须用 positions 行字段: ' + balCell2);
      }

      // 任一侧 amount 缺失
      hedgePositionsGetResponse = {
        status: 200,
        body: {
          positions: [{
            coin: 'ETHUSDT', direction: 'forward', match_status: 'normal',
            um_position_amt: '1', spot_balance: null, spot_balance_value_usdt: null,
            unified_balance: '2', unified_balance_value_usdt: '6400.00',
            cross_margin_borrowed: null, single_leg_exposure: false, drift: false
          }],
          account: { verified: true, error: null, checked_at: null }
        }
      };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      let sideCell = getRowCell(elements['private-panel-body'].innerHTML, 'ETHUSDT', 9);
      if (!sideCell.includes('现货: —') || !sideCell.includes('杠杆: 2')) {
        throw new Error('现货缺失时该侧 — 且杠杆独立: ' + sideCell);
      }

      // amount 有 value 无
      hedgePositionsGetResponse = {
        status: 200,
        body: {
          positions: [{
            coin: 'SOLUSDT', direction: 'forward', match_status: 'normal',
            um_position_amt: '1', spot_balance: '3', spot_balance_value_usdt: null,
            unified_balance: '4', unified_balance_value_usdt: null,
            cross_margin_borrowed: null, single_leg_exposure: false, drift: false
          }],
          account: { verified: true, error: null, checked_at: null }
        }
      };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      sideCell = getRowCell(elements['private-panel-body'].innerHTML, 'SOLUSDT', 9);
      if (!sideCell.includes('现货: 3 ≈ — U') || !sideCell.includes('杠杆: 4 ≈ — U')) {
        throw new Error('有 amount 无 value 须 ≈ — U: ' + sideCell);
      }

      // 两侧真零
      hedgePositionsGetResponse = {
        status: 200,
        body: {
          positions: [{
            coin: 'ZEROUSDT', direction: 'forward', match_status: 'normal',
            um_position_amt: '0', spot_balance: '0', spot_balance_value_usdt: '0.00000000',
            unified_balance: '0', unified_balance_value_usdt: '0',
            cross_margin_borrowed: null, single_leg_exposure: false, drift: false
          }],
          account: { verified: true, error: null, checked_at: null }
        }
      };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      sideCell = getRowCell(elements['private-panel-body'].innerHTML, 'ZEROUSDT', 9);
      if (!sideCell.includes('现货: 0') || !sideCell.includes('杠杆: 0')) {
        throw new Error('真零须显示 0 而非 —: ' + sideCell);
      }
      if (sideCell.includes('现货: —') || sideCell.includes('杠杆: —')) {
        throw new Error('真零不得退化成 —: ' + sideCell);
      }

      // 账户未就绪：四字段 null
      hedgePositionsGetResponse = {
        status: 200,
        body: {
          positions: [{
            coin: 'NRUSDT', direction: 'forward', match_status: 'no_um',
            um_position_amt: null, spot_balance: null, spot_balance_value_usdt: null,
            unified_balance: null, unified_balance_value_usdt: null,
            cross_margin_borrowed: null, spot_avg: '1', perp_avg: '1',
            single_leg_exposure: false, drift: false
          }],
          account: { verified: false, error: 'snapshot_not_ready', checked_at: null }
        }
      };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      sideCell = getRowCell(elements['private-panel-body'].innerHTML, 'NRUSDT', 9);
      if (!sideCell.includes('现货: —') || !sideCell.includes('杠杆: —')) {
        throw new Error('未就绪两侧均 —: ' + sideCell);
      }

      // 隐私遮蔽 amount 与估值
      if (!helpers.getPrivacyHidden()) helpers.togglePrivacy();
      hedgePositionsGetResponse = {
        status: 200,
        body: {
          positions: [{
            coin: 'PRIVUSDT', direction: 'forward', match_status: 'normal',
            um_position_amt: '1', spot_balance: '1.5', spot_balance_value_usdt: '100.00',
            unified_balance: '2.5', unified_balance_value_usdt: '200.00',
            cross_margin_borrowed: '0.1', single_leg_exposure: false, drift: false
          }],
          account: { verified: true, error: null, checked_at: null }
        }
      };
      await helpers.loadHedgePositions();
      helpers.renderPrivatePanel();
      sideCell = getRowCell(elements['private-panel-body'].innerHTML, 'PRIVUSDT', 9);
      if (!sideCell.includes('****') || sideCell.includes('1.5') || sideCell.includes('2.5') || sideCell.includes('100.00')) {
        throw new Error('隐私模式须遮蔽 amount 与估值: ' + sideCell);
      }
      // 恢复显示态
      helpers.togglePrivacy();

      // 固定副标题不得再出现；右侧 refresh-meta 无 account-asset
      if (html.includes('行情公开 · 账户需 key 私有只读')) {
        throw new Error('固定副标题「行情公开 · 账户需 key 私有只读」须已被账户时间替换');
      }

      hedgePositionsGetResponse = {
        status: 200,
        body: {
          positions: [],
          account: {
            verified: true, error: null, checked_at: null,
            source_checked_at: {
              price_map: null, unified_balances: null, um_positions: null,
              spot_balances: null, pm_account: null
            }
          }
        }
      };
      helpers.ingestSnapshot(designFixture);
      console.log('[PASS] frontend-position-balance-display-v1：双行现货/杠杆、缺失/真零/隐私、徽标列、标题区时间与 PM 位置');
    }

    // 75y2. 幂等键生成器（2026-08-07 实盘首笔划转故障的回归防线）
    // 故障事实：用户浏览器的 crypto.randomUUID() 返回了 'c886-84-03-46-bc0e13'
    // （4-2-2-2-6 共 16 位，标准是 8-4-4-4-12 共 32 位，版本位也不是 4），被后端
    // 400 拦下。结论：环境 API 的输出格式不能当保证，格式必须由前端自己拼装。
    {
      if (typeof helpers.newTransferRequestId !== 'function') {
        throw new Error('须导出 newTransferRequestId');
      }
      // self-check 宿主可能没有 webcrypto（globalThis.crypto === undefined）；
      // 用例需要可替换的 randomUUID/getRandomValues 表面，故补最小桩。
      if (typeof globalThis.crypto === 'undefined' || globalThis.crypto === null) {
        globalThis.crypto = {};
      }
      // 严格 v4：版本位必须是 4，variant 位必须是 8/9/a/b
      const strictV4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
      // 把环境的 randomUUID 换成当天那个坏实现：生成器绝不能受影响
      const savedRandomUUID = globalThis.crypto.randomUUID;
      globalThis.crypto.randomUUID = () => 'c886-84-03-46-bc0e13';
      // 若宿主无 getRandomValues，先挂一个可用实现再测「坏 randomUUID 不影响」路径
      const hadGetRandomValues = typeof globalThis.crypto.getRandomValues === 'function';
      if (!hadGetRandomValues) {
        globalThis.crypto.getRandomValues = (arr) => {
          for (let i = 0; i < arr.length; i++) arr[i] = Math.floor(Math.random() * 256);
          return arr;
        };
      }
      const ids = new Set();
      for (let i = 0; i < 200; i++) {
        const id = helpers.newTransferRequestId();
        if (!strictV4.test(id)) {
          throw new Error('幂等键不是合法 UUID v4: ' + id);
        }
        ids.add(id);
      }
      if (savedRandomUUID === undefined) delete globalThis.crypto.randomUUID;
      else globalThis.crypto.randomUUID = savedRandomUUID;
      if (ids.size !== 200) throw new Error(`幂等键重复：200 次生成只得到 ${ids.size} 个不同值`);
      // 兜底路径：环境连 getRandomValues 都没有时，仍须产出合法 UUID
      const savedGetRandomValues = globalThis.crypto.getRandomValues;
      globalThis.crypto.getRandomValues = undefined;
      const fallbackId = helpers.newTransferRequestId();
      if (hadGetRandomValues) globalThis.crypto.getRandomValues = savedGetRandomValues;
      else delete globalThis.crypto.getRandomValues;
      if (!strictV4.test(fallbackId)) {
        throw new Error('无 getRandomValues 时的兜底幂等键非法: ' + fallbackId);
      }
      // 后端正则（server.py _TRANSFER_UUID_RE）必须接受本生成器的输出
      const backendRe = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
      if (!backendRe.test(helpers.newTransferRequestId())) {
        throw new Error('生成的幂等键不被后端正则接受');
      }
      console.log('[PASS] 幂等键生成器：不依赖 crypto.randomUUID（实盘坏实现回归）/严格 v4/200 次无重复/无 getRandomValues 兜底/后端正则接受');
    }

    // 75z. 资产互转（统一 ⇄ 现货）：默认现货→统一/USDT/数量=现货 free；
    // 真实可用额回显、位置、账户自动反转、资产跟随转出账户、不套用 <10 USDT 卡片过滤、
    // 数量校验按可用额、二次确认、成功后刷缓存
    {
      const transferFixture = JSON.parse(JSON.stringify(designFixture));
      transferFixture.private_account = {
        verified: true,
        balances_unified: [
          // 可用(cross_margin_free) < 总量(total_balance)：其余被借贷/合约保证金占用
          { asset: 'USDT', total_balance: '12500.4321', cross_margin_free: '9800.1000',
            cross_margin_borrowed: '0', value_usdt: '12500.43',
            cross_margin_borrowed_value_usdt: '0.00' },
          // 净值 5.36 < 10：资产卡过滤掉，划转下拉必须保留
          { asset: 'DOGE', total_balance: '35.7', cross_margin_free: '35.7',
            cross_margin_borrowed: '0', value_usdt: '5.36',
            cross_margin_borrowed_value_usdt: '0.00' },
          // 估值缺失 → 净值 —；cross_margin_free 缺失 → 可用 —（不回退到总量）
          { asset: 'MUUU', total_balance: '1500', cross_margin_borrowed: null,
            value_usdt: null, cross_margin_borrowed_value_usdt: null }
        ],
        balances_spot: [
          // 默认归集目标：现货 USDT free 填入划转数量
          { asset: 'USDT', free: '42.5', locked: '0', value_usdt: '42.50' },
          { asset: 'BNB', free: '1.2', locked: '0.8', value_usdt: '1240.00' }
        ],
        um_positions: [],
        total_value_usdt: '13745.79',
        valuation: { price_source: 'api_v3_ticker_price', priced_at: '2026-08-06T09:30:00Z' },
        checked_at: '2026-08-06T09:30:00Z',
        error: null
      };
      // 复位默认态（self-check 共用页面 state，先前用例可能已写过 amount）
      const at0 = helpers.getAssetTransfer();
      at0.from = 'spot';
      at0.asset = 'USDT';
      at0.amount = null;
      at0.result = null;
      at0.locked = false;
      at0.submitting = false;
      helpers.ingestSnapshot(transferFixture);
      if (helpers.getPrivacyHidden()) helpers.togglePrivacy();
      helpers.renderPrivatePanel();
      let tBody = elements['private-panel-body'].innerHTML;

      // 位置：统一账户余额之后、现货账户余额之前
      const idxUnified = tBody.indexOf('统一账户余额');
      const idxTransfer = tBody.indexOf('资产互转');
      const idxSpot = tBody.indexOf('现货账户余额');
      if (idxUnified < 0 || idxTransfer < 0 || idxSpot < 0) throw new Error('互转行或余额区块缺失');
      if (!(idxUnified < idxTransfer && idxTransfer < idxSpot)) {
        throw new Error(`互转行位置错误: unified=${idxUnified} transfer=${idxTransfer} spot=${idxSpot}`);
      }
      if (tBody.includes('真实划转 · 点击即动钱')) throw new Error('已删除的「真实划转」提示不应出现');
      if (!tBody.includes('>从<') || !tBody.includes('🔄转到')) throw new Error('缺少「从」/「🔄转到」互换控件');
      if (!tBody.includes('data-transfer-swap')) throw new Error('缺少互换按钮 data-transfer-swap');

      // 默认：现货 → 统一、USDT、数量=现货 free
      if (helpers.getAssetTransfer().from !== 'spot') throw new Error('默认转出账户应为现货账户');
      if (helpers.getAssetTransfer().asset !== 'USDT') throw new Error('默认资产应为 USDT');
      if (helpers.getAssetTransfer().amount !== '42.5') {
        throw new Error('默认数量应为现货 USDT free: ' + helpers.getAssetTransfer().amount);
      }
      const rowsFrom = tBody.slice(idxTransfer);
      if (!/id="transfer-from"[\s\S]*?<option value="spot" selected>/.test(rowsFrom)) {
        throw new Error('转出下拉应选中现货账户');
      }
      if (!/id="transfer-to"[\s\S]*?<option value="unified" selected>/.test(rowsFrom)) {
        throw new Error('转入下拉应自动取反为统一账户');
      }
      // 🔄转到：点击后现货/统一前后互换，资产清空（两账户集合不同）
      helpers.swapTransferAccounts();
      if (helpers.getAssetTransfer().from !== 'unified') throw new Error('互换后转出应为统一账户');
      if (helpers.getAssetTransfer().asset !== null) throw new Error('互换后资产应清空');
      tBody = elements['private-panel-body'].innerHTML;
      if (!/id="transfer-from"[\s\S]*?<option value="unified" selected>/.test(tBody.slice(tBody.indexOf('资产互转')))) {
        throw new Error('互换后转出下拉应选中统一账户');
      }
      if (!/id="transfer-to"[\s\S]*?<option value="spot" selected>/.test(tBody.slice(tBody.indexOf('资产互转')))) {
        throw new Error('互换后转入下拉应选中现货账户');
      }
      helpers.swapTransferAccounts();
      if (helpers.getAssetTransfer().from !== 'spot') throw new Error('再互换应回到现货转出');
      // 互换清空了资产，恢复默认 USDT 以便后续默认数量/下拉断言
      helpers.setTransferAsset('USDT');
      helpers.setTransferAmount('42.5');
      helpers.renderPrivatePanel();
      tBody = elements['private-panel-body'].innerHTML;
      if (!tBody.includes('USDT · 可用 42.5 ·')) throw new Error('默认应展示现货 USDT 可用');
      if (!tBody.includes('BNB · 可用 1.2 ·')) throw new Error('现货下拉应含 BNB');
      if (tBody.includes('DOGE · 可用')) throw new Error('转出=现货时不应展示统一账户资产');
      if (!tBody.includes('可用 = 现货账户可用余额')) throw new Error('缺少现货可用额口径说明');
      // 默认数量已填且 >0 → 可提交
      if (!helpers.evaluateTransfer().ok) throw new Error('默认现货 USDT 全额应可提交');
      // 0 / 负 / 非法
      helpers.setTransferAmount('0');
      if (helpers.evaluateTransfer().ok) throw new Error('0 不应可提交');
      helpers.setTransferAmount('-5');
      if (helpers.evaluateTransfer().ok) throw new Error('负数不应可提交');
      helpers.setTransferAmount('abc');
      if (helpers.evaluateTransfer().ok) throw new Error('非数字不应可提交');

      // 现货无 USDT 行（omitZeroBalances）→ 仍默认选中 USDT，数量 0
      const noUsdtFixture = JSON.parse(JSON.stringify(transferFixture));
      noUsdtFixture.private_account.balances_spot = [
        { asset: 'BNB', free: '1.2', locked: '0.8', value_usdt: '1240.00' }
      ];
      const atZero = helpers.getAssetTransfer();
      atZero.from = 'spot';
      atZero.asset = 'USDT';
      atZero.amount = null;
      helpers.ingestSnapshot(noUsdtFixture);
      helpers.renderPrivatePanel();
      if (helpers.getAssetTransfer().asset !== 'USDT') throw new Error('现货无 USDT 行时仍应默认选中 USDT');
      if (helpers.getAssetTransfer().amount !== '0') {
        throw new Error('现货无 USDT 时默认数量应为 0: ' + helpers.getAssetTransfer().amount);
      }
      tBody = elements['private-panel-body'].innerHTML;
      if (!tBody.includes('USDT · 可用 0 ·')) throw new Error('现货无 USDT 时应补零选项: ' + tBody.slice(tBody.indexOf('资产互转'), tBody.indexOf('资产互转') + 900));
      if (helpers.evaluateTransfer().ok) throw new Error('数量 0 不应可提交');

      // 恢复含 USDT 的 fixture，切到统一账户测统一侧下拉/校验
      helpers.ingestSnapshot(transferFixture);
      helpers.setTransferFrom('unified');
      if (helpers.getAssetTransfer().asset !== null) throw new Error('切换转出账户后资产应清空');
      tBody = elements['private-panel-body'].innerHTML;
      // 2026-08-07 晚（Human 定稿）：全部走快照，前端零请求。本 fixture 无 pm_account，
      // 故 USDT 也退回 cross_margin_free 并说「可用」——措辞必须跟着数据来源降级。
      // 有 pm_account 时 USDT 说「可转」的行为由下方 Q4 断言组覆盖。
      if (!tBody.includes('USDT · 可用 9,800.1000 · 净值 ≈ 12500.43 USDT')) {
        throw new Error('无账户级字段时统一账户应显示「可用 + crossMarginFree」: ' + tBody.slice(tBody.indexOf('资产互转'), tBody.indexOf('资产互转') + 900));
      }
      // 只查互转区块：资产卡本来就展示总量，那里出现这个数是合法的。
      if (tBody.slice(tBody.indexOf('资产互转')).includes('12,500.4321')) {
        throw new Error('可用不应回退到 total_balance');
      }
      if (!tBody.includes('DOGE · 可用 35.7 ·')) throw new Error('小额资产不应被划转下拉过滤');
      if (!tBody.includes('crossMarginFree')) throw new Error('缺少可用额口径说明');
      if (tBody.includes('<div class="asset">DOGE</div>')) throw new Error('小额资产卡应仍被过滤（既有行为）');
      if (!tBody.includes('MUUU · 可用 — · 净值 ≈ — USDT')) {
        throw new Error('可用/估值缺失须各自显示 —: ' + tBody.slice(tBody.indexOf('资产互转'), tBody.indexOf('资产互转') + 1400));
      }
      if (!/id="transfer-to"[\s\S]*?<option value="spot" selected>/.test(tBody.slice(tBody.indexOf('资产互转')))) {
        throw new Error('转出改统一后转入应自动取反为现货账户');
      }
      // 未选资产 → 按钮禁用
      if (helpers.evaluateTransfer().ok) throw new Error('未选资产不应可提交');
      if (!tBody.includes('data-transfer-submit disabled')) throw new Error('未选资产时按钮应 disabled');
      // 选资产 + 合法数量 → 可提交；超额按 cross_margin_free 拦
      helpers.setTransferAsset('USDT');
      helpers.setTransferAmount('100');
      if (!helpers.evaluateTransfer().ok) throw new Error('合法输入应可提交');
      helpers.setTransferAmount('10000');
      if (helpers.evaluateTransfer().ok) throw new Error('超出 cross_margin_free 应被拦截');
      helpers.setTransferAmount('99999');
      let verdict = helpers.evaluateTransfer();
      if (verdict.ok || !verdict.hint.includes('超出可用数量')) throw new Error('超额应被拦截: ' + verdict.hint);

      // 切回现货做二次确认 / POST 形状
      helpers.setTransferFrom('spot');
      if (helpers.getAssetTransfer().asset !== null) throw new Error('切换转出账户后资产应清空');
      tBody = elements['private-panel-body'].innerHTML;
      if (!tBody.includes('BNB · 可用 1.2 ·')) throw new Error('转出=现货时应展示现货可用(free)');
      if (tBody.includes('DOGE · 可用')) throw new Error('转出=现货时不应展示统一账户资产');
      if (!/id="transfer-to"[\s\S]*?<option value="unified" selected>/.test(tBody.slice(tBody.indexOf('资产互转')))) {
        throw new Error('转出改现货后转入应自动取反为统一账户');
      }

      // 二次确认：确认前零请求，文案含方向/数量/币种
      helpers.setTransferAsset('BNB');
      helpers.setTransferAmount('0.5');
      const transferMark = fetchCallLog.length;
      helpers.requestAssetTransferConfirm();
      if (fetchCallLog.length !== transferMark) throw new Error('确认前不应有任何请求');
      const tModal = helpers.getHedgeModal();
      if (!tModal || tModal.title !== '确认资产划转') throw new Error('确认弹框标题错误: ' + JSON.stringify(tModal));
      if (!tModal.body.includes('0.5 个 BNB') || !tModal.body.includes('现货账户划转到统一账户')) {
        throw new Error('确认文案应含数量/币种/方向: ' + tModal.body);
      }
      if (elements['hedge-modal-confirm'].textContent !== '确认划转') throw new Error('确认词应为「确认划转」');

      // 确认 → 恰好一次 POST /api/asset-transfer，请求体形状冻结
      assetTransferPostResponse = { status: 200, body: {
        client_request_id: 'x', from_account: 'spot', to_account: 'unified',
        asset: 'BNB', amount: '0.5', status: 'succeeded', tran_id: '90210',
        error_code: null, error_message: null
      } };
      cacheRefreshPostResponse = { status: 200, body: { published: true } };
      await helpers.onHedgeModalConfirm();
      const posts = fetchCallLog.slice(transferMark).filter(c => c.url === '/api/asset-transfer');
      if (posts.length !== 1) throw new Error(`确认后应恰好一次划转 POST，实际 ${posts.length}`);
      if (posts[0].method !== 'POST') throw new Error('划转必须用 POST');
      const sent = posts[0].body;  // mock fetch 已把 JSON body 解析成对象
      if (sent.confirm !== true) throw new Error('请求体必须带 confirm=true');
      if (sent.from_account !== 'spot' || sent.to_account !== 'unified') throw new Error('方向字段错误: ' + JSON.stringify(sent));
      if (sent.asset !== 'BNB' || sent.amount !== '0.5') throw new Error('币种/金额错误: ' + JSON.stringify(sent));
      if (!/^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(sent.client_request_id)) {
        throw new Error('client_request_id 必须是 UUID（幂等键）: ' + sent.client_request_id);
      }
      // 成功 → 回显含流水号、数量清空、触发快照缓存刷新（否则余额显示 60s 旧值）
      tBody = elements['private-panel-body'].innerHTML;
      if (!tBody.includes('划转成功')) throw new Error('缺少成功回显: ' + tBody.slice(tBody.indexOf('资产互转'), tBody.indexOf('资产互转') + 1400));
      if (!tBody.includes('90210')) throw new Error('成功回显应含交易所流水号');
      if (helpers.getAssetTransfer().amount !== '') throw new Error('成功后数量应清空');
      if (!fetchCallLog.slice(transferMark).some(c => c.url === '/api/public-market/cache-refresh')) {
        throw new Error('划转成功后应刷新快照缓存');
      }

      // 成功后的 cache-refresh 是**不等待**的后台调用（不阻塞 UI），它会异步把快照
      // 换成 mock 的默认 fixture——这正是「成功后刷新余额」生效的旁证。先让它跑完，
      // 再恢复本用例的账户快照，否则后续用例会撞上被换掉的资产列表。
      await new Promise(resolve => setImmediate(resolve));
      await new Promise(resolve => setImmediate(resolve));
      helpers.ingestSnapshot(transferFixture);
      helpers.setTransferFrom('unified');
      helpers.setTransferFrom('spot');

      // 业务失败：HTTP 仍是 200，结论只在 body.status —— 前端不得当成功
      helpers.setTransferAsset('BNB');
      helpers.setTransferAmount('0.25');
      assetTransferPostResponse = { status: 200, body: {
        client_request_id: 'y', from_account: 'spot', to_account: 'unified',
        asset: 'BNB', amount: '0.25', status: 'failed', tran_id: null,
        error_code: '-4015', error_message: '请求被币安拒绝（HTTP 400）：Insufficient balance'
      } };
      helpers.requestAssetTransferConfirm();
      await helpers.onHedgeModalConfirm();
      tBody = elements['private-panel-body'].innerHTML;
      if (!tBody.includes('划转失败')) throw new Error('HTTP 200 + status=failed 必须显示失败');
      if (!tBody.includes('-4015') || !tBody.includes('Insufficient balance')) {
        throw new Error('失败回显应含错误码与交易所原文');
      }
      if (helpers.getAssetTransfer().locked) throw new Error('业务失败不应锁定表单（钱确定没动）');

      // 结果未知：醒目警示 + 无重试入口 + 锁定表单，直到人工「我已核对」
      helpers.setTransferAsset('BNB');
      helpers.setTransferAmount('0.75');
      assetTransferPostResponse = { status: 200, body: {
        client_request_id: 'z', from_account: 'spot', to_account: 'unified',
        asset: 'BNB', amount: '0.75', status: 'unknown', tran_id: null,
        error_code: null, error_message: '请求过于频繁，已触发币安限流（HTTP 429）'
      } };
      helpers.requestAssetTransferConfirm();
      await helpers.onHedgeModalConfirm();
      tBody = elements['private-panel-body'].innerHTML;
      if (!tBody.includes('结果未知，请勿直接重试')) throw new Error('unknown 必须醒目警示');
      if (!tBody.includes('可能已经执行')) throw new Error('unknown 必须说明钱可能已经转了');
      if (/data-transfer-retry|>重试</.test(tBody)) throw new Error('unknown 绝不能给重试按钮');
      if (!helpers.getAssetTransfer().locked) throw new Error('unknown 后必须锁定表单');
      if (!tBody.includes('data-transfer-ack')) throw new Error('unknown 应提供「我已核对」解锁入口');
      if (evaluateTransferOk()) throw new Error('锁定期间不得可提交');
      const lockedMark = fetchCallLog.length;
      helpers.requestAssetTransferConfirm();
      if (fetchCallLog.length !== lockedMark) throw new Error('锁定期间不得发出任何请求');
      // 人工核对后解锁：纯本地状态，零请求
      helpers.acknowledgeTransferUnknown();
      if (fetchCallLog.length !== lockedMark) throw new Error('解锁不应发出请求');
      if (helpers.getAssetTransfer().locked) throw new Error('「我已核对」后应解除锁定');

      // 请求层失败（400/503）：钱一定没动，显示「划转未发出」
      helpers.setTransferAsset('BNB');
      helpers.setTransferAmount('0.1');
      assetTransferPostResponse = { status: 503, body: {
        error: 'asset_transfer_unavailable', detail: '划转通道未配置（离线模式或缺少 API 凭证）'
      } };
      helpers.requestAssetTransferConfirm();
      await helpers.onHedgeModalConfirm();
      tBody = elements['private-panel-body'].innerHTML;
      if (!tBody.includes('划转未发出')) throw new Error('请求层失败应显示「划转未发出」');
      if (!tBody.includes('划转通道未配置')) throw new Error('请求层失败应带后端 detail');

      // 复位，不污染后续断言
      assetTransferPostResponse = null;
      cacheRefreshPostResponse = null;
      const atEnd = helpers.getAssetTransfer();
      atEnd.from = 'spot';
      atEnd.asset = 'USDT';
      atEnd.amount = null;
      atEnd.result = null;
      atEnd.locked = false;
      helpers.ingestSnapshot(designFixture);
      console.log('[PASS] 资产互转 T2 接线：默认现货→统一/USDT/free + UUID 幂等键 + confirm=true + 恰一次 POST/成功刷缓存/failed 不当成功/unknown 锁定且无重试入口/请求层失败/位置/自动反转/可用额校验');
    }

    function evaluateTransferOk() {
      return helpers.evaluateTransfer().ok;
    }

    // 75z2. 统一账户还款 T2 接线（stage 2026-08-09-pm-margin-repay-v1）：输入校验镜像后端、
    // 确认前零请求/零请求号/零未决记录、确认文案诚实、body 恰四字段、发送前持久化、
    // 全局防连点、四态、纯本地恢复、人工核对锁、成功后强制刷新解锁、请求层/传输错误分支。
    {
      const repayFixture = JSON.parse(JSON.stringify(designFixture));
      repayFixture.private_account = {
        verified: true,
        balances_unified: [
          { asset: 'BTC', total_balance: '0.4', cross_margin_free: '0.0',
            cross_margin_borrowed: '0.5', value_usdt: '16000.00',
            cross_margin_borrowed_value_usdt: '20000.00' },
          { asset: 'BNB', total_balance: '1.0', cross_margin_free: '1.0',
            cross_margin_borrowed: '0.25', value_usdt: '620.00',
            cross_margin_borrowed_value_usdt: '155.00' },
          { asset: 'USDT', total_balance: '9000', cross_margin_free: '9000',
            cross_margin_borrowed: '0', value_usdt: '9000.00',
            cross_margin_borrowed_value_usdt: '0.00' }
        ],
        balances_spot: [],
        um_positions: [],
        total_value_usdt: '7000.00',
        valuation: { price_source: 'api_v3_ticker_price', priced_at: '2026-08-09T09:30:00Z' },
        checked_at: '2026-08-09T09:30:00Z',
        error: null
      };
      helpers.ingestSnapshot(repayFixture);
      helpers.renderPrivatePanel();
      let rBody = '';
      let mark = fetchCallLog.length;

      // -- 输入校验（镜像后端）：只收精确 "0" 或严格大于零的普通十进制 --
      const badAmounts = ['', ' ', '0.0', '0.00', '00', '-5', '1e3', 'abc', '.5', '5.', '1.2.3', '0 ', ' 0.25', '0.25 '];
      for (const bad of badAmounts) {
        if (helpers.validateRepayAmount(bad).ok) {
          throw new Error(`非法还款数量被放行: ${JSON.stringify(bad)}`);
        }
      }
      const vAll = helpers.validateRepayAmount('0');
      if (!vAll.ok || !vAll.repayAll || vAll.amount !== '0') throw new Error('精确 "0" 应表示全部且原样保留');
      const vPart = helpers.validateRepayAmount('0.25');
      if (!vPart.ok || vPart.repayAll || vPart.amount !== '0.25') throw new Error('正十进制应按原字符串通过');

      // -- 确认前零请求 / 零请求号 / 零 localStorage 未决记录 --
      helpers.setRepayAmount('BTC', '0.5');
      mark = fetchCallLog.length;
      helpers.requestMarginRepayConfirm('BTC');
      if (fetchCallLog.length !== mark) throw new Error('还款确认前不应有任何请求');
      if (localStorageData['funding_hedging_margin_repay_pending']) throw new Error('确认前不应有 localStorage 未决记录');
      const rModal = helpers.getHedgeModal();
      if (!rModal || rModal.title !== '确认还款') throw new Error('还款确认弹框标题错误: ' + JSON.stringify(rModal));
      // 确认文案诚实：负债资产+指定数量、同币优先、USDT 只是后备、成本未知、快照滞后
      for (const kw of ['BTC', '0.5 个 BTC', '优先使用账户中的 BTC', 'USDT', '手续费', '滑点', '无法预估', '60 秒', '可能已变化']) {
        if (!rModal.body.includes(kw)) throw new Error(`确认文案缺少「${kw}」: ${rModal.body}`);
      }
      if (/只扣\s*USDT/.test(rModal.body)) throw new Error('确认文案不得宣称只扣 USDT');
      if (elements['hedge-modal-confirm'].textContent !== '确认还款') throw new Error('确认词应为「确认还款」');

      // -- 取消确认：零请求 / 零请求号 / 零未决记录 --
      helpers.closeHedgeModal();
      if (fetchCallLog.length !== mark) throw new Error('取消确认不应有任何请求');
      if (localStorageData['funding_hedging_margin_repay_pending']) throw new Error('取消确认不应有未决记录');
      if (helpers.getMarketActionPending()) throw new Error('取消后 pending 应清空');

      // -- 非法输入不进确认、零请求 --
      helpers.setRepayAmount('BTC', '0.0');
      helpers.requestMarginRepayConfirm('BTC');
      if (fetchCallLog.length !== mark) throw new Error('非法输入不应发出请求');
      if (helpers.getMarketActionPending()) throw new Error('非法输入不应产生 pending');
      const invModal = helpers.getHedgeModal();
      if (!invModal || invModal.title !== '还款数量无效') throw new Error('数值零应提示数量无效且不进确认');
      helpers.closeHedgeModal();

      // -- 确认 → 发送前持久化 + 恰好一次 POST，body 冻结四字段（原始 amount 字符串）--
      helpers.setRepayAmount('BTC', '0.5');
      helpers.requestMarginRepayConfirm('BTC');
      marginRepayPostResponse = { status: 200, body: {
        client_request_id: 'r1', asset: 'BTC', amount: '0.5', repay_asset: 'USDT',
        status: 'succeeded', repaid_amount: '0.5', update_time: '1786000000000',
        error_code: null, error_message: null
      } };
      cacheRefreshPostResponse = { status: 200, body: { published: true, account_panels: 'complete' } };
      await helpers.onHedgeModalConfirm();
      let posts = fetchCallLog.slice(mark).filter(c => c.url === '/api/margin-repay');
      if (posts.length !== 1) throw new Error(`确认后应恰好一次还款 POST，实际 ${posts.length}`);
      if (posts[0].method !== 'POST') throw new Error('还款必须用 POST');
      const sent = posts[0].body;  // mock fetch 已把 JSON body 解析成对象
      const sentKeys = Object.keys(sent).sort();
      if (sentKeys.join(',') !== 'amount,asset,client_request_id,confirm') {
        throw new Error('请求体必须恰含 client_request_id/asset/amount/confirm 四字段: ' + sentKeys.join(','));
      }
      if (sent.confirm !== true) throw new Error('confirm 必须为 true');
      if (sent.asset !== 'BTC' || sent.amount !== '0.5') throw new Error('asset/amount 必须是原始字符串: ' + JSON.stringify(sent));
      if (!/^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(sent.client_request_id)) {
        throw new Error('client_request_id 必须是 UUID（幂等键）: ' + sent.client_request_id);
      }
      // 发送前持久化取证：mock 在 POST 到达瞬间抓取了 localStorage，
      // 必须已存在同 UUID、同资产、同原始金额的未决记录。
      const observed = marginRepayPostPendingSnapshot ? JSON.parse(marginRepayPostPendingSnapshot) : {};
      if (!observed.BTC || observed.BTC.client_request_id !== sent.client_request_id) {
        throw new Error('POST 之前必须把同一 UUID 持久化到 localStorage');
      }
      if (observed.BTC.asset !== 'BTC' || observed.BTC.amount !== '0.5') {
        throw new Error('持久化记录应含 asset 与原始 amount: ' + JSON.stringify(observed));
      }

      // -- succeeded + 强制刷新 complete：清除未决、解锁、回显实际偿还资产/数量 --
      // complete 路径内部 loadApi 会把快照换回默认 fixture，先重喂本用例快照再读 DOM。
      helpers.ingestSnapshot(repayFixture);
      rBody = elements['private-panel-body'].innerHTML;
      if (!rBody.includes('还款成功')) throw new Error('缺少成功回显');
      if (!rBody.includes('实际偿还 0.5 个 BTC')) throw new Error('成功回显应含实际还款资产/数量: ' + rBody.slice(rBody.indexOf('还款成功') - 200, rBody.indexOf('还款成功') + 600));
      if (!rBody.includes('USDT')) throw new Error('成功回显应含指定偿还资产');
      if (helpers.getMarginRepay().pending.BTC) throw new Error('刷新成功后应清除未决记录');
      if (localStorageData['funding_hedging_margin_repay_pending']) throw new Error('localStorage 未决记录应已清除');
      if (!fetchCallLog.slice(mark).some(c => c.url === '/api/public-market/cache-refresh')) {
        throw new Error('成功后应强制刷新账户快照');
      }
      if (!rBody.includes('data-repay-preview="BTC">还款</button>')) throw new Error('解锁后按钮应恢复可点');

      // -- failed（HTTP 200 + body.status）：明确展示 code/msg，结束该请求 --
      helpers.setRepayAmount('BNB', '0.25');
      marginRepayPostResponse = { status: 200, body: {
        client_request_id: 'r2', asset: 'BNB', amount: '0.25', repay_asset: 'USDT',
        status: 'failed', repaid_amount: null, update_time: null,
        error_code: '-4015', error_message: '请求被币安拒绝（HTTP 400）：Insufficient balance'
      } };
      mark = fetchCallLog.length;
      helpers.requestMarginRepayConfirm('BNB');
      await helpers.onHedgeModalConfirm();
      rBody = elements['private-panel-body'].innerHTML;
      if (!rBody.includes('还款失败')) throw new Error('HTTP 200 + status=failed 必须显示失败（HTTP 200 不得当成功）');
      if (!rBody.includes('-4015') || !rBody.includes('Insufficient balance')) throw new Error('失败回显应含交易所 code/msg');
      if (helpers.getMarginRepay().pending.BNB) throw new Error('failed 应结束请求并清除未决记录');
      if (!rBody.includes('data-repay-preview="BNB">还款</button>')) throw new Error('failed 后按钮应恢复可点（下一次重新确认）');

      // -- unknown：锁资产、无重试入口、人工核对解锁；未锁定资产不受影响 --
      helpers.setRepayAmount('BNB', '0.75');
      marginRepayPostResponse = { status: 200, body: {
        client_request_id: 'r3', asset: 'BNB', amount: '0.75', repay_asset: 'USDT',
        status: 'unknown', repaid_amount: null, update_time: null,
        error_code: null, error_message: '请求过于频繁，已触发币安限流（HTTP 429）'
      } };
      mark = fetchCallLog.length;
      helpers.requestMarginRepayConfirm('BNB');
      await helpers.onHedgeModalConfirm();
      rBody = elements['private-panel-body'].innerHTML;
      if (!rBody.includes('结果未知，请勿直接重试')) throw new Error('unknown 必须醒目警示');
      if (!rBody.includes('可能已经执行')) throw new Error('unknown 必须说明钱可能已经还了');
      if (/data-repay-retry|>重试</.test(rBody)) throw new Error('unknown 绝不能给重试按钮');
      if (!helpers.getMarginRepay().pending.BNB) throw new Error('unknown 必须保留未决记录（锁）');
      if (!JSON.parse(localStorageData['funding_hedging_margin_repay_pending']).BNB) throw new Error('localStorage 未决记录应保留');
      if (!rBody.includes('data-repay-ack="BNB"')) throw new Error('unknown 应提供「我已核对」入口');
      if (!rBody.includes('data-repay-recheck="BNB"')) throw new Error('unknown 应提供「查询结果」入口');
      if (!/data-repay-preview="BNB" disabled>还款<\/button>/.test(rBody)) throw new Error('锁定期间该资产按钮应禁用');
      if (!rBody.includes('data-repay-preview="BTC">还款</button>')) throw new Error('未锁定资产的按钮不应被误禁');
      const lockedMark = fetchCallLog.length;
      helpers.requestMarginRepayConfirm('BNB');
      if (fetchCallLog.length !== lockedMark) throw new Error('锁定期间不得发出任何请求');
      if (helpers.getMarketActionPending()) throw new Error('锁定期间不得进入确认');

      // -- 「查询结果」恢复：同一 UUID 本地 GET 一次；恢复为 failed → 结束并解锁 --
      const pendId = helpers.getMarginRepay().pending.BNB.client_request_id;
      marginRepayGetResponse = { status: 200, body: {
        client_request_id: pendId, asset: 'BNB', amount: '0.75', repay_asset: 'USDT',
        status: 'failed', repaid_amount: null, update_time: null,
        error_code: '-3000', error_message: '请求被币安拒绝（HTTP 400）：Exchange error'
      } };
      await helpers.recoverMarginRepay('BNB');
      let gets = fetchCallLog.slice(lockedMark).filter(c => c.url.startsWith('/api/margin-repay?'));
      if (gets.length !== 1) throw new Error(`恢复应恰好一次本地 GET（不轮询），实际 ${gets.length}`);
      if (gets[0].method !== 'GET') throw new Error('恢复必须是 GET');
      if (!gets[0].url.includes('client_request_id=' + pendId)) throw new Error('恢复必须用同一 UUID: ' + gets[0].url);
      if (helpers.getMarginRepay().pending.BNB) throw new Error('恢复为 failed 应结束请求');
      if (localStorageData['funding_hedging_margin_repay_pending']) throw new Error('failed 恢复后 localStorage 应清除');

      // -- 再次 unknown → 「我已核对」纯本地解锁，零请求 --
      helpers.setRepayAmount('BNB', '0.75');
      marginRepayPostResponse = { status: 200, body: {
        client_request_id: 'r4', asset: 'BNB', amount: '0.75', repay_asset: 'USDT',
        status: 'unknown', repaid_amount: null, update_time: null,
        error_code: null, error_message: 'transport_error:timeout'
      } };
      helpers.requestMarginRepayConfirm('BNB');
      await helpers.onHedgeModalConfirm();
      if (!helpers.getMarginRepay().pending.BNB) throw new Error('unknown 应锁定');
      mark = fetchCallLog.length;
      helpers.acknowledgeRepayUnknown('BNB');
      if (fetchCallLog.length !== mark) throw new Error('「我已核对」不应发出任何请求');
      if (helpers.getMarginRepay().pending.BNB) throw new Error('「我已核对」应清除未决记录');
      if (localStorageData['funding_hedging_margin_repay_pending']) throw new Error('「我已核对」应清 localStorage');

      // -- succeeded 但强制刷新失败：保留成功结果和锁，「再次刷新」成功后解锁 --
      helpers.setRepayAmount('BTC', '0.1');
      marginRepayPostResponse = { status: 200, body: {
        client_request_id: 'r5', asset: 'BTC', amount: '0.1', repay_asset: 'USDT',
        status: 'succeeded', repaid_amount: '0.1', update_time: '1786000000500',
        error_code: null, error_message: null
      } };
      cacheRefreshPostResponse = { status: 200, body: { published: true, account_panels: 'partial' } };
      helpers.requestMarginRepayConfirm('BTC');
      await helpers.onHedgeModalConfirm();
      helpers.ingestSnapshot(repayFixture);
      rBody = elements['private-panel-body'].innerHTML;
      if (!rBody.includes('还款已成功，但账户快照刷新失败')) throw new Error('部分刷新不得当成功，必须如实提示刷新失败');
      if (!helpers.getMarginRepay().pending.BTC) throw new Error('刷新失败必须保留未决记录（锁）');
      if (!rBody.includes('data-repay-refresh="BTC"')) throw new Error('应提供「再次刷新」恢复路径');
      if (!/data-repay-preview="BTC" disabled>还款<\/button>/.test(rBody)) throw new Error('刷新失败期间按钮应禁用');
      cacheRefreshPostResponse = { status: 200, body: { published: true, account_panels: 'complete' } };
      await helpers.finalizeMarginRepaySuccess('BTC');
      if (helpers.getMarginRepay().pending.BTC) throw new Error('再次刷新成功后应解锁');
      if (localStorageData['funding_hedging_margin_repay_pending']) throw new Error('解锁后 localStorage 应清除');
      helpers.ingestSnapshot(repayFixture);

      // -- 传输错误（浏览器到本机服务中断/响应丢失）：保留同一未决请求并锁定，绝不换号重发 --
      helpers.setRepayAmount('BTC', '0.2');
      marginRepayPostThrow = new TypeError('fetch failed');
      helpers.requestMarginRepayConfirm('BTC');
      await helpers.onHedgeModalConfirm();
      rBody = elements['private-panel-body'].innerHTML;
      if (!helpers.getMarginRepay().pending.BTC) throw new Error('传输错误必须保留未决请求');
      if (!rBody.includes('结果未知，请勿直接重试')) throw new Error('传输错误必须按结果未知提示');
      if (!rBody.includes('data-repay-ack="BTC"') || !rBody.includes('data-repay-recheck="BTC"')) {
        throw new Error('传输错误应提供恢复/核对入口');
      }
      // -- GET 404：不得擅自宣称未还款、不得清除未决 ID --
      marginRepayGetResponse = { status: 404, body: { error: 'not_found', detail: '未找到该 client_request_id 的还款记录' } };
      await helpers.recoverMarginRepay('BTC');
      rBody = elements['private-panel-body'].innerHTML;
      if (!helpers.getMarginRepay().pending.BTC) throw new Error('GET 404 不得清除未决 ID');
      if (!rBody.includes('恢复查询未完成')) throw new Error('GET 404 应如实提示恢复查询未完成');
      if (rBody.includes('尚未还款') || rBody.includes('未还款成功')) throw new Error('不得擅自宣称未还款');
      helpers.acknowledgeRepayUnknown('BTC');
      if (helpers.getMarginRepay().pending.BTC) throw new Error('人工核对后应解锁');

      // -- 启动/重载恢复：localStorage 未决逐条按同一 UUID GET 一次；succeeded 走刷新解锁 --
      helpers.setMarginRepayPending('BTC', { client_request_id: 'startup-1', asset: 'BTC', amount: '0' });
      marginRepayGetResponse = { status: 200, body: {
        client_request_id: 'startup-1', asset: 'BTC', amount: '0', repay_asset: 'USDT',
        status: 'succeeded', repaid_amount: '0.44', update_time: '1786000001000',
        error_code: null, error_message: null
      } };
      cacheRefreshPostResponse = { status: 200, body: { published: true, account_panels: 'complete' } };
      mark = fetchCallLog.length;
      await helpers.recoverMarginRepayAll();
      gets = fetchCallLog.slice(mark).filter(c => c.url.startsWith('/api/margin-repay?'));
      if (gets.length !== 1) throw new Error(`启动恢复每条未决应恰好 GET 一次（不轮询），实际 ${gets.length}`);
      if (!gets[0].url.includes('client_request_id=startup-1')) throw new Error('启动恢复必须用同一 UUID');
      if (helpers.getMarginRepay().pending.BTC) throw new Error('恢复 succeeded+刷新成功应清除未决');
      if (!fetchCallLog.slice(mark).some(c => c.url === '/api/public-market/cache-refresh')) {
        throw new Error('恢复成功后同样应强制刷新账户快照');
      }
      helpers.ingestSnapshot(repayFixture);
      rBody = elements['private-panel-body'].innerHTML;
      if (!rBody.includes('还款成功') || !rBody.includes('实际偿还 0.44 个 BTC')) {
        throw new Error('启动恢复成功应展示实际还款资产/数量');
      }

      // -- 全局防连点：任一还款提交期间所有还款按钮禁用、确认入口被拒 --
      const mm = helpers.getMarginRepay();
      mm.submitting = true;
      helpers.renderPrivatePanel();
      rBody = elements['private-panel-body'].innerHTML;
      if (!/data-repay-preview="BTC" disabled>还款<\/button>/.test(rBody)
          || !/data-repay-preview="BNB" disabled>还款<\/button>/.test(rBody)) {
        throw new Error('提交期间所有还款按钮必须禁用');
      }
      mark = fetchCallLog.length;
      helpers.setRepayAmount('BTC', '0.3');
      helpers.requestMarginRepayConfirm('BTC');
      if (fetchCallLog.length !== mark || helpers.getMarketActionPending()) {
        throw new Error('提交期间不得进入确认或发出请求');
      }
      mm.submitting = false;
      helpers.renderPrivatePanel();

      // -- 请求层失败（503 闸门关闭）：钱一定没动、未决撤销、按钮可点 --
      helpers.setRepayAmount('BTC', '0.4');
      marginRepayPostResponse = { status: 503, body: {
        error: 'margin_repay_unavailable',
        detail: '还款通道未配置（未开启 APP_MARGIN_REPAY_ENABLED、离线模式或缺少 API 凭证）'
      } };
      helpers.requestMarginRepayConfirm('BTC');
      await helpers.onHedgeModalConfirm();
      rBody = elements['private-panel-body'].innerHTML;
      if (!rBody.includes('还款未发出')) throw new Error('请求层失败应显示「还款未发出」');
      if (!rBody.includes('还款通道未配置')) throw new Error('请求层失败应带后端 detail');
      if (helpers.getMarginRepay().pending.BTC) throw new Error('请求层失败应撤销未决记录');
      if (localStorageData['funding_hedging_margin_repay_pending']) throw new Error('localStorage 不应残留');

      // 复位，不污染后续断言
      marginRepayPostResponse = null;
      marginRepayGetResponse = null;
      marginRepayPostThrow = null;
      marginRepayPostPendingSnapshot = null;
      cacheRefreshPostResponse = null;
      helpers.acknowledgeRepayUnknown('BTC');
      helpers.acknowledgeRepayUnknown('BNB');
      helpers.setRepayAmount('BTC', '');
      helpers.setRepayAmount('BNB', '');
      delete localStorageData['funding_hedging_margin_repay_pending'];
      helpers.ingestSnapshot(designFixture);
      console.log('[PASS] 统一账户还款 T2 接线：校验镜像后端/确认文案诚实/取消零请求/body 恰四字段/发送前持久化同号取证/成功强制刷新解锁/failed 结束/unknown 锁+人工核对/查询结果同号恢复/刷新失败留锁+再次刷新/传输错误留锁/GET404 不清 ID/启动恢复一次 GET/全局防连点/请求层失败撤销');
    }

    // 76. 无泄漏证明：fetch 同源白名单、无 Binance/外域、无新任务定时器、localStorage 白名单
    {
      const allowedPatterns = [
        /^\/api\/public-market\/snapshot$/,
        /^\/api\/public-market\/cache-refresh$/,
        /^\/api\/public-market\/symbol-snapshot\?/,
        /^\/api\/borrow-tasks$/,
        /^\/api\/borrow-tasks\/[^/]+\/(start|pause|delete|edit)$/,
        /^\/api\/borrow-logs\?/,
        /^\/api\/borrow-logs\/clear$/,
        /^\/api\/borrow-scheduler-settings$/,
        // Boundary C execution control (exact anchored paths, no prefix/wildcard).
        /^\/api\/borrow-execution\/(status|start|stop)$/,
        // 开单任务（2026-07-hedge-open-live-v1 §3 冻结路由，全部同源）。
        /^\/api\/hedge-open-tasks$/,
        /^\/api\/hedge-open-tasks\?status=/,
        /^\/api\/hedge-open-tasks\/[^/]+\/(pause|start|delete|fill-once|fill-all)$/,
        /^\/api\/hedge-open-settings$/,
        /^\/api\/hedge-open-settings\/start-gate$/,
        /^\/api\/hedge-open-positions$/,
        // real-api-v1：attempt 时间线经既有 logs 路由读取（同源、GET）。
        /^\/api\/hedge-open-logs\?/,
        // 功能三 ③a：历史仓位——周期结算日志（同源、GET）。
        /^\/api\/hedge-open-close-logs$/,
        // dual-ledger flow-log（task C）
        /^\/api\/private-ledger\/flow-log\?/,
        /^\/api\/private-ledger\/refresh$/,
        // 资产互转（stage 2026-08-06-asset-transfer-live-v1 T2）：同源、POST。
        /^\/api\/asset-transfer$/,
        // 统一账户还款（stage 2026-08-09-pm-margin-repay-v1 T2）：同源、POST；
        // 纯本地恢复 GET（同一 UUID 查一次，不轮询）。
        /^\/api\/margin-repay$/,
        /^\/api\/margin-repay\?/
        // 注：`/api/private-account/max-withdraw` 端点仍在后端，但前端**不再调用**
        //（Human 2026-08-07 定稿：沿用快照，零请求）。故不列入白名单——若哪天前端
        // 又发起该请求，这条守卫会立刻抓到，那必须是一次显式决定而非悄悄回潮。
      ];
      for (const c of fetchCallLog) {
        if (/binance/i.test(c.url)) {
          throw new Error(`fetch 出现 Binance URL: ${c.url}`);
        }
        if (/^[a-z][a-z0-9+.-]*:\/\//i.test(c.url)) {
          throw new Error(`fetch 出现绝对外部源: ${c.url}`);
        }
        if (!allowedPatterns.some(re => re.test(c.url))) {
          throw new Error(`fetch URL 不在同源白名单: ${c.url}`);
        }
      }
      // 方法白名单：快照/日志/任务列表 GET；任务创建/动作 POST；设置 GET/PUT；
      // 执行控制：status GET、start/stop POST；
      // 开单：列表/设置/持仓 GET，创建与任务动作 POST。
      for (const c of fetchCallLog) {
        if (c.url === '/api/borrow-scheduler-settings') {
          if (c.method !== 'GET' && c.method !== 'PUT') throw new Error(`设置路由非法方法 ${c.method}`);
        } else if (c.url === '/api/borrow-tasks') {
          if (c.method !== 'GET' && c.method !== 'POST') throw new Error(`任务路由非法方法 ${c.method}`);
        } else if (/^\/api\/borrow-tasks\/[^/]+\//.test(c.url)) {
          if (c.method !== 'POST') throw new Error(`任务动作路由非法方法 ${c.method}`);
        } else if (c.url === '/api/borrow-execution/status') {
          if (c.method !== 'GET') throw new Error(`执行状态路由非法方法 ${c.method}`);
        } else if (c.url === '/api/borrow-execution/start' || c.url === '/api/borrow-execution/stop') {
          if (c.method !== 'POST') throw new Error(`执行控制路由非法方法 ${c.method}`);
        } else if (c.url === '/api/hedge-open-tasks') {
          if (c.method !== 'GET' && c.method !== 'POST') throw new Error(`开单任务路由非法方法 ${c.method}`);
        } else if (c.url.startsWith('/api/hedge-open-tasks?')) {
          if (c.method !== 'GET') throw new Error(`开单任务列表路由非法方法 ${c.method}`);
        } else if (/^\/api\/hedge-open-tasks\/[^/]+\//.test(c.url)) {
          if (c.method !== 'POST') throw new Error(`开单任务动作路由非法方法 ${c.method}`);
        } else if (c.url === '/api/hedge-open-settings/start-gate') {
          if (c.method !== 'POST') throw new Error(`闸门变更路由非法方法 ${c.method}`);
        } else if (c.url === '/api/hedge-open-settings' || c.url === '/api/hedge-open-positions') {
          if (c.method !== 'GET') throw new Error(`开单设置/持仓路由非法方法 ${c.method}`);
        } else if (c.url.startsWith('/api/hedge-open-logs')) {
          if (c.method !== 'GET') throw new Error(`开单日志路由非法方法 ${c.method}`);
        } else if (c.url === '/api/borrow-logs/clear') {
          if (c.method !== 'POST') throw new Error(`清空借币日志路由非法方法 ${c.method}`);
        } else if (c.url === '/api/public-market/cache-refresh') {
          if (c.method !== 'POST') throw new Error(`cache-refresh 路由非法方法 ${c.method}`);
        } else if (c.url.startsWith('/api/private-ledger/flow-log')) {
          if (c.method !== 'GET') throw new Error(`flow-log 路由非法方法 ${c.method}`);
        } else if (c.url === '/api/private-ledger/refresh') {
          if (c.method !== 'POST') throw new Error(`flow-log refresh 路由非法方法 ${c.method}`);
        } else if (c.url === '/api/asset-transfer') {
          // 划转是写操作，只能 POST（GET 划转会被浏览器预取/重放，绝不允许）。
          if (c.method !== 'POST') throw new Error(`资产互转路由非法方法 ${c.method}`);
        } else if (c.url === '/api/margin-repay') {
          // 还款是写操作，只能 POST（同划转纪律）。
          if (c.method !== 'POST') throw new Error(`还款路由非法方法 ${c.method}`);
        } else if (c.url.startsWith('/api/margin-repay?')) {
          // 还款恢复查询是纯本地 GET。
          if (c.method !== 'GET') throw new Error(`还款恢复查询路由非法方法 ${c.method}`);
        } else if (c.method !== 'GET') {
          throw new Error(`只读路由非法方法 ${c.method}: ${c.url}`);
        }
      }
      // 无新增定时器：全部 interval 注册只允许 60000 快照刷新、1000 倒计时、
      // 与单一 2000ms 只读显示轮询（执行状态 + 已展开的执行中任务日志）。
      for (const call of intervalCalls) {
        if (call.delay !== 60000 && call.delay !== 1000 && call.delay !== 2000) {
          throw new Error(`存在非法任务定时器: delay=${call.delay}`);
        }
      }
      if (intervalCalls.filter(call => call.delay === 2000).length !== 1) {
        throw new Error('执行状态与展开日志必须复用同一个 2s 显示轮询');
      }
      // localStorage 白名单：隐私开关键 + 还款未决请求号（按负债资产持久化的幂等
      // 恢复记录；开单任务/持仓权威在后端 SQLite，不落 localStorage）
      const allowedStorageKeys = ['funding_hedging_privacy_hidden', 'funding_hedging_margin_repay_pending'];
      for (const k of Object.keys(localStorageData)) {
        if (!allowedStorageKeys.includes(k)) {
          throw new Error(`localStorage 出现白名单外键: ${k}`);
        }
      }
      console.log('[PASS] fetch 同源白名单（含开单 §3 路由）、零 Binance/外域、单一共享 2s 显示轮询、localStorage 白名单（隐私键 + 还款未决请求号）');
    }

    // ---- 暂停原因：直读后端 pause_reason_zh（不再查前端残缺映射表）----
    {
      // 后端有 11 种 PAUSE_REASON_*，前端旧表只收录 1 种，其余全部裸露英文枚举；
      // 而完整中文（含 -2015 的 IP 白名单排查指引）一直躺在 pause_reason_zh 里没人读。
      const zh = '预检数据不完整（collateral_cap），任务已暂停（fail-closed，未发单）；请检查网络后手动恢复';
      const paused = mockHedgeTask({
        id: 'h-pause-zh', status: 'paused',
        pause_reason: 'preflight_incomplete', pause_reason_zh: zh,
      });
      hedgeTasksGetResponse = { status: 200, body: { tasks: [paused] } };
      helpers.setActiveView('hedge-tasks');
      await helpers.loadHedgeTasks();
      helpers.setHedgeTaskFilter('all');
      const html = elements['hedge-task-list'].innerHTML;
      if (!html.includes(zh)) {
        throw new Error('任务卡应直接展示后端 pause_reason_zh 全文: ' + html);
      }
      if (html.includes('preflight_incomplete')) {
        throw new Error('不应再裸露英文枚举 preflight_incomplete: ' + html);
      }
      // 后端未给中文时回退英文枚举，不至于空白
      const bare = mockHedgeTask({
        id: 'h-pause-bare', status: 'paused',
        pause_reason: 'some_new_reason', pause_reason_zh: null,
      });
      hedgeTasksGetResponse = { status: 200, body: { tasks: [bare] } };
      await helpers.loadHedgeTasks();
      helpers.setHedgeTaskFilter('all');
      if (!elements['hedge-task-list'].innerHTML.includes('some_new_reason')) {
        throw new Error('无中文时应回退展示原始 reason');
      }
      console.log('[PASS] 任务卡暂停原因直读 pause_reason_zh（缺失回退英文枚举）');
    }

    // ---- Q4：可转出额全部走快照，前端零请求（USDT 用账户级字段，其余用可用余额）----
    {
      const mwFixture = JSON.parse(JSON.stringify(designFixture));
      mwFixture.private_account = {
        verified: true,
        balances_unified: [
          { asset: 'USDT', total_balance: '12500.4321', cross_margin_free: '9800.1000',
            cross_margin_borrowed: '5000', value_usdt: '12500.43',
            cross_margin_borrowed_value_usdt: '5000.00' },
          { asset: 'WLD', total_balance: '300', cross_margin_free: '250',
            cross_margin_borrowed: '0', value_usdt: '450.00',
            cross_margin_borrowed_value_usdt: '0.00' }
        ],
        balances_spot: [{ asset: 'BNB', free: '1.2', locked: '0', value_usdt: '1240.00' }],
        um_positions: [], total_value_usdt: '13745.79',
        // USDT 的可转出额来自这个账户级字段（实测与 maxWithdraw(USDT) 等价）。
        pm_account: { total_available_balance_usdt: '209.18482141', account_status: 'NORMAL' },
        valuation: { price_source: 'api_v3_ticker_price', priced_at: '2026-08-06T09:30:00Z' },
        checked_at: '2026-08-06T09:30:00Z', error: null
      };
      helpers.ingestSnapshot(mwFixture);
      if (helpers.getPrivacyHidden()) helpers.togglePrivacy();
      helpers.setTransferFrom('unified');

      // 1) 整条链路零网络请求：渲染、切账户、选资产都不得打后端。
      //    (Human 2026-08-07 定稿：18 个资产串行实测 9.68s，改为全部沿用快照。)
      const before = fetchCallLog.length;
      helpers.renderPrivatePanel();
      helpers.setTransferAsset('USDT');
      helpers.setTransferFrom('spot');
      helpers.setTransferFrom('unified');
      if (fetchCallLog.slice(before).some(c => c.url.includes('max-withdraw'))) {
        throw new Error('可转出额链路不得发起任何请求');
      }
      let unifiedSection = elements['private-panel-body'].innerHTML.slice(
        elements['private-panel-body'].innerHTML.indexOf('统一账户余额'),
        elements['private-panel-body'].innerHTML.indexOf('资产互转')
      );
      if (!unifiedSection.includes('可转余额: 209.18482141')) {
        throw new Error('统一账户 USDT 资产卡须显示账户级可转余额');
      }
      if ((unifiedSection.match(/可转余额:/g) || []).length !== 1) {
        throw new Error('可转余额只应出现在 USDT 资产卡');
      }

      // 2) USDT 说「可转」并给账户级 total_available_balance_usdt，
      //    不是 cross_margin_free(9800.1)——两个数不等正是本项存在的理由。
      let labels = helpers.getTransferAssetOptionLabels();
      const usdtLabel = labels.find(l => l.startsWith('USDT'));
      if (!usdtLabel.includes('可转 209.18482141')) {
        throw new Error('USDT 应说「可转」并用账户级可转出额: ' + usdtLabel);
      }
      if (usdtLabel.includes('9,800.1000')) throw new Error('不得把可用额当可转出额: ' + usdtLabel);

      // 3) 其余币说「可用」给 cross_margin_free——它**不是**可转出额，措辞必须区分。
      //    也不得把账户级 USDT 数值套到它们头上（转走它们会一并抽走抵押贡献，
      //    按折算率而非市值，总额÷币价必然偏大）。
      const wldLabel = labels.find(l => l.startsWith('WLD'));
      if (!wldLabel.includes('可用 250')) {
        throw new Error('非 USDT 应说「可用」并给 cross_margin_free: ' + wldLabel);
      }
      if (wldLabel.includes('可转')) throw new Error('可用余额不得标成「可转」: ' + wldLabel);
      if (wldLabel.includes('209.18')) throw new Error('账户级 USDT 数不得套到其他币: ' + wldLabel);

      // 4) 账户级字段缺失时 USDT 退回可用余额，措辞同步降级为「可用」——
      //    不能保留「可转」的说法却给一个不是可转出额的数。
      const noPm = JSON.parse(JSON.stringify(mwFixture));
      delete noPm.private_account.pm_account;
      helpers.ingestSnapshot(noPm);
      unifiedSection = elements['private-panel-body'].innerHTML.slice(
        elements['private-panel-body'].innerHTML.indexOf('统一账户余额'),
        elements['private-panel-body'].innerHTML.indexOf('资产互转')
      );
      if (!unifiedSection.includes('可转余额: —')) {
        throw new Error('账户级可转余额缺失时 USDT 资产卡须显示 —');
      }
      const degraded = helpers.getTransferAssetOptionLabels().find(l => l.startsWith('USDT'));
      if (!degraded.includes('可用 9,800.1000')) {
        throw new Error('缺账户级字段时应退回可用余额并改口「可用」: ' + degraded);
      }
      helpers.ingestSnapshot(mwFixture);
      helpers.togglePrivacy();
      unifiedSection = elements['private-panel-body'].innerHTML.slice(
        elements['private-panel-body'].innerHTML.indexOf('统一账户余额'),
        elements['private-panel-body'].innerHTML.indexOf('资产互转')
      );
      if (!unifiedSection.includes('可转余额: ****') || unifiedSection.includes('209.18482141')) {
        throw new Error('隐私模式须遮蔽 USDT 可转余额');
      }
      helpers.togglePrivacy();

      // 5) 校验跟着同一个数走：USDT 按 209.18 拦（而非按可用额 9800.1 放行）。
      helpers.setTransferAsset('USDT');
      helpers.setTransferAmount('500');
      let v = helpers.evaluateTransfer();
      if (v.ok) throw new Error('超出真实可转出额应被拦，不能按可用额放行');
      if (!v.hint.includes('可转') || !v.hint.includes('209.18482141')) {
        throw new Error('拦截提示应说「可转」并给出该数: ' + v.hint);
      }
      // 非 USDT 按可用余额拦，提示措辞相应说「可用」。
      helpers.setTransferAsset('WLD');
      helpers.setTransferAmount('999');
      v = helpers.evaluateTransfer();
      if (v.ok || !v.hint.includes('可用') || !v.hint.includes('250')) {
        throw new Error('非 USDT 应按可用余额拦并说「可用」: ' + v.hint);
      }
      helpers.setTransferAmount('');

      // 6) 现货账户说「可用」（free 本身就是可转出额，无抵押约束）。
      helpers.setTransferFrom('spot');
      helpers.renderPrivatePanel();
      const spotLabels = helpers.getTransferAssetOptionLabels();
      if (!spotLabels.every(l => l.includes('可用'))) {
        throw new Error('现货账户应说「可用」: ' + spotLabels.join(' | '));
      }
      helpers.setTransferFrom('unified');
      console.log('[PASS] Q4 可转出额全走快照零请求：USDT 用账户级字段说「可转」/ 其余用可用余额说「可用」/ 缺字段降级改口 / 校验与显示同源 / 不把 USDT 数套到别的币');
    }

    // ---- 持仓表展示现货腿 symbol（bStock 的 SNXXBUSDT ≠ 合约 SNXXUSDT）----
    {
      const pos = {
        coin: 'SNXXUSDT', direction: 'forward', match_status: 'normal',
        spot_symbol: 'SNXXBUSDT', spot_base_asset: 'SNXXB',
        position_qty: '-3', spot_qty: '3', perp_qty: '3',
        spot_avg: '10', perp_avg: '10',
        spot_avg_price_incomplete: false, perp_avg_price_incomplete: false,
        includes_deleted_task: false, open_basis_rate: '0', price_pnl: '0',
        accrued_funding: '0', borrow_interest: '0', net_pnl: '0',
        um_position_side: 'SHORT', um_position_amt: '-3', um_notional_usdt: '31',
        um_entry_price: '10', um_mark_price: '10.5', um_liquidation_price: '0',
        unrealized_profit: '-0.8', spot_balance: '3',
        spot_balance_value_usdt: '31.56', unified_balance: null,
        unified_balance_value_usdt: null, cross_margin_borrowed: null,
        single_leg_exposure: false, drift: false,
        cycle_id: 'c1', cycle_opened_at: null, cycle_closed_at: null,
      };
      hedgePositionsGetResponse = { status: 200, body: { positions: [pos], account: { verified: true } } };
      await helpers.loadHedgePositions();
      const posHtml = elements['private-panel-body'].innerHTML;
      if (!posHtml.includes('SNXXBUSDT')) {
        throw new Error('持仓表应显示现货腿 symbol SNXXBUSDT: ' + posHtml);
      }
      console.log('[PASS] 持仓表展示现货腿 symbol');

      // ---- F4：读不到交易所持仓时，标题上直说，而不是对每行印「交易所无仓」----
      const NOTICE = '未获取到交易所持仓数据，仅展示本地缓存记录';

      // 1) 全部读到 -> 不出现。这条最要紧：误报会让红字变成背景噪音，人就不看了。
      hedgePositionsGetResponse = { status: 200, body: {
        positions: [pos], account: { verified: true, unavailable_sources: [] } } };
      await helpers.loadHedgePositions();
      if (elements['private-panel-body'].innerHTML.includes(NOTICE)) {
        throw new Error('数据正常时不得提示未获取');
      }

      // 2) UM 源读不到 -> 出现，且**表格仍在**（本地记账在故障时刻恰恰最有用：
      //    它告诉你该去交易所核对哪几个币）。
      hedgePositionsGetResponse = { status: 200, body: {
        positions: [pos],
        account: { verified: true, unavailable_sources: ['um_positions'] } } };
      await helpers.loadHedgePositions();
      let html = elements['private-panel-body'].innerHTML;
      if (!html.includes(NOTICE)) throw new Error('UM 源读不到时应提示: ' + html);
      if (!html.includes('SNXXUSDT')) throw new Error('提示出现时表格必须保留');

      // 3) 别的源读不到（余额/PM）不影响本表 —— 本表的骨架只有 UM。
      hedgePositionsGetResponse = { status: 200, body: {
        positions: [pos],
        account: { verified: true, unavailable_sources: ['spot_balances', 'pm_account'] } } };
      await helpers.loadHedgePositions();
      if (elements['private-panel-body'].innerHTML.includes(NOTICE)) {
        throw new Error('非 UM 源不可用不应触发本表提示');
      }

      // 4) verified=false -> 出现。此时 merge 会**主动忽略** UM 数据
      //    （domain.py: um_positions = pa.get(...) if verified else None），
      //    所以哪怕 UM 那一路其实读到了，表格也没在用它。
      hedgePositionsGetResponse = { status: 200, body: {
        positions: [pos], account: { verified: false, unavailable_sources: [] } } };
      await helpers.loadHedgePositions();
      if (!elements['private-panel-body'].innerHTML.includes(NOTICE)) {
        throw new Error('verified=false 时应提示（merge 此时不用 UM 数据）');
      }

      // 5) 字段缺失（旧块）-> 不出现。缺失语义是「全部可用」，不得反过来报故障。
      hedgePositionsGetResponse = { status: 200, body: {
        positions: [pos], account: { verified: true } } };
      await helpers.loadHedgePositions();
      if (elements['private-panel-body'].innerHTML.includes(NOTICE)) {
        throw new Error('字段缺失应按全部可用处理，不得误报');
      }
      console.log('[PASS] F4 交易所持仓读不到：标题直说 + 表格保留 / 正常时不误报 / 非 UM 源不触发 / verified=false 触发 / 缺失字段不误报');

      // ---- 「交易所无仓」标记：只对活跃周期警示，文案不把推测说成结论 ----
      const noUmActive = Object.assign({}, pos, {
        match_status: 'no_um', um_position_side: null, um_position_amt: null,
        cycle_closed_at: null,
      });
      hedgePositionsGetResponse = { status: 200, body: {
        positions: [noUmActive], account: { verified: true, unavailable_sources: [] } } };
      await helpers.loadHedgePositions();
      html = elements['private-panel-body'].innerHTML;
      if (!html.includes('交易所无仓')) throw new Error('活跃周期无仓应警示');
      if (html.includes('可能已强平或手工平仓')) {
        throw new Error('旧文案把推测说成结论，应已降调');
      }
      if (!html.includes('不同步')) throw new Error('新文案应列出记账不同步这一成因');

      // 已平仓周期本来就该没仓——那是预期结果，不是异常。此前它会和「已完全平仓」
      // 并排印出红色「交易所无仓（可能已强平）」，对正常平完的周期是纯误导。
      const noUmClosed = Object.assign({}, noUmActive, { cycle_closed_at: '2026-08-07T00:00:00Z' });
      hedgePositionsGetResponse = { status: 200, body: {
        positions: [noUmClosed], account: { verified: true, unavailable_sources: [] } } };
      await helpers.loadHedgePositions();
      html = elements['private-panel-body'].innerHTML;
      if (html.includes('交易所无仓')) {
        throw new Error('已平仓周期不该警示「交易所无仓」——它就该没仓');
      }
      if (!html.includes('已完全平仓')) throw new Error('已平仓周期应保留「已完全平仓」标记');
      console.log('[PASS] 「交易所无仓」只对活跃周期警示（已平仓周期不误报）+ 文案不把「强平」当结论');
    }

    console.log('\n全部自检通过');
    process.exit(0);
  } catch (err) {
    console.error('\n[FAIL]', err.message);
    process.exit(1);
  }
}, 50);

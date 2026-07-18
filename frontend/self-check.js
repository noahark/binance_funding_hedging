/**
 * 前端自检脚本：在 Node 环境下用 mock DOM 运行 index.html 的内联脚本，
 * 加载设计期 fixture 数据并断言市场表渲染结果。
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
const fetchCallLog = [];    // 记录全部 fetch URL，用于断言借币任务零网络请求

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
    get classList() {
      const self = this;
      return {
        add: (c) => { self._classList.add(c); },
        remove: (c) => { self._classList.delete(c); },
        contains: (c) => self._classList.has(c)
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
  'warnings-panel', 'warnings-list', 'warnings-raw', 'warnings-raw-content', 'margin-public-note',
  'data-source-label', 'sort-basis-badge', 'btn-refresh', 'refresh-countdown',
  'filter-search', 'filter-asset', 'filter-route', 'filter-show-perp-only', 'filter-hide-low-daily-rate',
  'summary-row', 'status-area', 'market-table-body', 'footer-note',
  'private-panel', 'private-panel-subtitle', 'private-panel-body', 'btn-privacy', 'privacy-label', 'privacy-icon-path',
  'drawer', 'drawer-backdrop', 'drawer-title', 'drawer-body', 'drawer-close',
  'nav-market', 'nav-borrow-tasks', 'borrow-task-count', 'market-view', 'borrow-task-view', 'borrow-task-list'
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

// Task B 要求前端把 annualized 字段视为当前服务契约字段；给设计期 fixture 补齐。
designFixture.rows.forEach(r => {
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
// 给 AUSDT 行附加 settled history，用于抽屉 newest-first / 负费率 / 北京时间测试。
const ausdt = designFixture.rows.find(r => r.symbol === 'AUSDT');
if (ausdt) {
  const tEnd = 1783641600000;
  const day = 86_400_000;
  ausdt.funding_history = [
    { funding_time: tEnd - 2 * day, funding_rate: '-0.00010000' },
    { funding_time: tEnd - day, funding_rate: '0.00005000' }
  ];
  // daily_funding_rate -0.00060000 * (24/8) = -0.00180000
  ausdt.annualized_funding_24h = '-0.65700000';
  // sum -0.00005000
  ausdt.annualized_funding_7d = '-0.00260714';
  ausdt.annualized_funding_30d = '-0.00060833';
}

// 为 v0.4 UI 断言使用具体数值（占位符无法被 formatFundingRate / maskAmount 有效测试）
designFixture.rows[0].borrow_validation.classic_margin.daily_interest_account = '0.00010000';
designFixture.rows[1].borrow_validation.classic_margin.daily_interest_vip0 = '0.00020000';
designFixture.private_account.balances_unified.forEach(b => { b.value_usdt = '123.45000000'; });
designFixture.private_account.balances_spot.forEach(b => { b.value_usdt = '67.89000000'; });

let fixtureToFetch = designFixture;
let historyResponse = null;
let historyResolve = null;
let historyJsonResolve = null;
let lastHistoryUrl = null;

function buildFetchResponse(response, jsonDelay) {
  return {
    ok: response.status === 200,
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

global.fetch = async (url) => {
  const urlStr = String(url);
  fetchCallLog.push(urlStr);
  if (urlStr === '/api/public-market/snapshot') {
    fetchUrl = urlStr;
    return buildFetchResponse({ status: 200, body: fixtureToFetch });
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
  throw new Error(`Unexpected fetch URL: ${urlStr}`);
};

global.document = {
  getElementById: (id) => {
    if (!elements[id]) {
      // 借币任务操作控件为按 symbol 动态生成的 id，按需惰性 mock（最小 mock 能力补足）
      if (/^borrow-(amount|count|error)-[A-Za-z0-9_]+$/.test(id)) return makeElement(id);
      throw new Error(`未 mock 的元素: ${id}`);
    }
    return elements[id];
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

    // 3. 数据说明区可见且渲染
    const warningsDisplay = elements['warnings-panel'].style.display;
    if (warningsDisplay === 'none') throw new Error('数据说明面板被隐藏');
    const marginNote = elements['margin-public-note'].innerHTML;
    if (!marginNote.includes('账户与借币验证通过私有只读 API key 读取')) {
      throw new Error('页面级杠杆可借性说明未渲染');
    }
    const warningsHtml = elements['warnings-list'].innerHTML;
    if (!warningsHtml.includes('isMarginTradingAllowed') || !warningsHtml.includes('已结算历史') || !warningsHtml.includes('bStock')) {
      throw new Error('数据说明中文内容未渲染');
    }
    const rawText = elements['warnings-raw-content'].textContent;
    if (!rawText.includes('net_daily_yield') || !rawText.includes('not_probed_this_round')) {
      throw new Error('数据说明英文原文未渲染');
    }
    console.log('[PASS] 数据说明区可见且内容已渲染');

    // 低日费率过滤默认开启：设计期 fixture 的 CUSDT daily_funding_rate 正好是边界
    // 0.00030000，默认会被隐藏（6→5）。legacy 6 行基线段在此显式关闭该过滤并重渲染，
    // 使既有断言（引用 CUSDT 的 #6/#19/#20/#28/#33/#34 等）全 6 行可见。过滤的默认
    // 开启行为由 #39 独立低费率边界场景覆盖（实现 prompt §6.2；design review 推荐 B）。
    elements['filter-hide-low-daily-rate'].checked = false;
    (elements['filter-hide-low-daily-rate'].listeners.change || []).forEach(h => h());

    // 4. 默认渲染 6 行（设计期 fixture；legacy 基线已关闭低日费率过滤）
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
    // 借币任务阶段：最终 13 列（第 13 列为「操作」）。
    if (html.includes('<th>路由分类</th>')) {
      throw new Error('默认表仍保留「路由分类」列');
    }
    if (html.includes('<th>提示标记</th>')) {
      throw new Error('默认表仍保留「提示标记」列');
    }
    if (html.includes('<th>负费率状态</th>')) {
      throw new Error('默认表仍保留独立「负费率状态」列');
    }
    const requiredHeaders = ['借贷状态 / 资产', '日净收益', '正向开单', '反向开单', '操作'];
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
    if (headerCount !== 13) {
      throw new Error(`市场表头应为 13 列，实际 ${headerCount} 列`);
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
    const ausdtFundingCell = getRowCell(tbody, 'AUSDT', 4);
    if (!ausdtFundingCell.includes('-0.060%')) {
      throw new Error(`AUSDT 资金费率期望 -0.060%，单元格 ${ausdtFundingCell}`);
    }
    const cusdtFundingCell = getRowCell(tbody, 'CUSDT', 4);
    if (!cusdtFundingCell.includes('+0.030%')) {
      throw new Error(`CUSDT 资金费率期望 +0.030%，单元格 ${cusdtFundingCell}`);
    }
    const fusdtFundingCell = getRowCell(tbody, 'FUSDT', 4);
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
      const cell = getRowCell(tbody, sym, 6);
      if (!cell.includes(expected)) {
        throw new Error(`${sym} 日费率期望 ${expected}，单元格 ${cell}`);
      }
    }
    console.log('[PASS] 日费率 string-shift 格式化（含 null→—）');

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

    // 8. 无排序控件 DOM（sort_basis 只读标注允许存在，但控制区不得有排序按钮/下拉）
    const controlsStart = html.indexOf('<div class="controls"');
    const controlsEnd = html.indexOf('</div>', controlsStart) + 6;
    const controlsHtml = html.slice(controlsStart, controlsEnd);
    if (controlsHtml.includes('排序') || controlsHtml.includes('sort') || controlsHtml.includes('Sort')) {
      throw new Error('页面控制区不应包含排序按钮或排序状态');
    }
    console.log('[PASS] 无排序控件 DOM');

    // 9. 渲染顺序 == fixture 顺序（AUSDT > BUSDT > CUSDT > DUSDT > EUSDT > FUSDT）
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
    console.log('[PASS] 手动刷新后 60s 自动刷新计时器重调度，倒计时计时器保持独立');

    // 19. 净收益列存在与格式
    const netYieldChecks = [
      ['AUSDT', '+0.04%', 'next_hourly'],
      ['BUSDT', '+0.01%', 'cross_margin_tier'],
      ['CUSDT', '+0.03%', null],
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
    if (!privateBody.includes('统一账户余额')) {
      throw new Error('私有面板未渲染统一账户余额');
    }
    if (!privateBody.includes('现货账户余额')) {
      throw new Error('私有面板未渲染现货账户余额');
    }
    if (!privateBody.includes('UM 持仓')) {
      throw new Error('私有面板未渲染 UM 持仓');
    }
    console.log('[PASS] 私有面板 verified=true 状态');

    // 23b. 时点合一：副标题显示资产更新时间，overview 不再出现估值时点/检查时点
    const privateSubtitle = elements['private-panel-subtitle'].textContent;
    if (!privateSubtitle.includes('资产更新时间')) {
      throw new Error(`verified=true 时私有面板副标题未显示资产更新时间: ${privateSubtitle}`);
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

    // 26. 私有面板 verified=false disabled 占位
    const disabledFixture = JSON.parse(JSON.stringify(designFixture));
    disabledFixture.private_account = designFixture._design_fixture_private_account_states.find(s => s._state === 'verified_false_disabled');
    helpers.ingestSnapshot(disabledFixture);
    if (elements['private-panel'].style.display === 'none') {
      throw new Error('verified=false disabled 时私有面板不应隐藏');
    }
    const disabledSubtitle = elements['private-panel-subtitle'].textContent;
    if (!disabledSubtitle.includes('私有账户未读取')) {
      throw new Error(`verified=false disabled 副标题错误: ${disabledSubtitle}`);
    }
    const disabledBody = elements['private-panel-body'].innerHTML;
    if (!disabledBody.includes('私有账户未读取')) {
      throw new Error('verified=false disabled 未显示占位文案');
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
      { symbol: 'AUSDT', position_side: 'LONG', position_amt: '1.5', entry_price: '1.00000000', mark_price: '1.00000000', unrealized_profit: '0.00000000' },
      { symbol: 'CUSDT', position_side: 'SHORT', position_amt: '-2.0', entry_price: '3.00000000', mark_price: '3.00000000', unrealized_profit: '0.00000000' }
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

    // 29. 优雅降级：新字段全缺失（旧后端）不白屏，日费率 —，净收益 —，私有面板不渲染
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
    while (pos !== -1 && tdCount < 13) {
      const close = dRowHtml.indexOf('</td>', pos);
      if (tdCount === 6) dailyCell = dRowHtml.slice(pos, close + 5);
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
    if (elements['private-panel'].style.display !== 'none') {
      throw new Error('优雅降级后无 private_account 块时不应渲染私有面板');
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

    // 33c. 最终 13 列：严格表头顺序、每行 13 个 td、empty-state colspan=13、合并列结构
    const taskCHeaders = ['标的', '标记价格 / 指数价格', '正向开单', '反向开单', '资金费率', '结算时间', '日费率', '年化 24h', '年化 7D', '年化 30D', '日净收益', '借贷状态 / 资产', '操作'];
    const theadBlock = html.slice(html.indexOf('<thead>'), html.indexOf('</thead>') + 8);
    const renderedHeaders = [...theadBlock.matchAll(/<th[^>]*>([^\u003c]*)<\/th>/g)].map(m => m[1].trim());
    if (renderedHeaders.length !== 13) {
      throw new Error(`表头数量期望 13，实际 ${renderedHeaders.length}: ${JSON.stringify(renderedHeaders)}`);
    }
    for (let i = 0; i < 13; i++) {
      if (renderedHeaders[i] !== taskCHeaders[i]) {
        throw new Error(`表头第 ${i + 1} 项期望「${taskCHeaders[i]}」，实际「${renderedHeaders[i]}」`);
      }
    }
    if (theadBlock.includes('提示标记') || theadBlock.includes('负费率状态')) {
      throw new Error('最终表头仍含「提示标记」或独立「负费率状态」');
    }
    // 每行 data row 恰好 13 个 td
    const dataRows = tbody.match(/<tr[^\u003e]*class="[^"]*selectable[^"]*"[^\u003e]*>/g) || [];
    for (const rowStart of dataRows) {
      const pos = tbody.indexOf(rowStart);
      const end = tbody.indexOf('</tr>', pos);
      const rowHtml = tbody.slice(pos, end + 5);
      const tdCount = (rowHtml.match(/<td[\s>]/g) || []).length;
      if (tdCount !== 13) {
        const symMatch = rowHtml.match(/data-symbol="([^"]+)"/);
        throw new Error(`${symMatch ? symMatch[1] : '某行'} 数据行 td 数量期望 13，实际 ${tdCount}`);
      }
    }
    // empty-state colspan=13：触发无匹配行并断言
    const originalSearch = elements['filter-search'].value;
    elements['filter-search'].value = 'NO_SUCH_SYMBOL_XYZ';
    (elements['filter-search'].listeners.input || []).forEach(h => h());
    const emptyTbody = elements['market-table-body'].innerHTML;
    if (!emptyTbody.includes('colspan="13"')) {
      throw new Error('无匹配 empty-state 未使用 colspan="13"');
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
    console.log('[PASS] 最终 13 列表头顺序、行单元格数、empty-state colspan 与合并列结构');

    // 33d. 正向/反向开单列：腿标签、价格、百分比与颜色
    // AUSDT fresh: forward -0.04%, reverse +0.04%
    const ausdtForward = getRowCell(tbody, 'AUSDT', 2);
    if (!ausdtForward.includes('合约买一') || !ausdtForward.includes('现货卖一')) {
      throw new Error('AUSDT 正向开单列上下腿标签错误: ' + ausdtForward);
    }
    if (!ausdtForward.includes('64,925.00') || !ausdtForward.includes('64,954.01000000')) {
      throw new Error('AUSDT 正向开单列价格错误: ' + ausdtForward);
    }
    if (!ausdtForward.includes('-0.04%')) {
      throw new Error('AUSDT 正向开单列百分比错误: ' + ausdtForward);
    }
    if (!ausdtForward.includes('negative')) {
      throw new Error('AUSDT 正向开单列负 spread 应使用 negative 色: ' + ausdtForward);
    }
    const ausdtReverse = getRowCell(tbody, 'AUSDT', 3);
    if (!ausdtReverse.includes('现货买一') || !ausdtReverse.includes('合约卖一')) {
      throw new Error('AUSDT 反向开单列上下腿标签错误: ' + ausdtReverse);
    }
    if (!ausdtReverse.includes('64,954.00000000') || !ausdtReverse.includes('64,925.10')) {
      throw new Error('AUSDT 反向开单列价格错误: ' + ausdtReverse);
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
    const busdtForward = getRowCell(tbody, 'BUSDT', 2);
    if (!busdtForward.includes('合约买一')) {
      throw new Error('BUSDT 正向开单列应仍渲染合约买一标签: ' + busdtForward);
    }
    if (!busdtForward.includes('现货卖一')) {
      throw new Error('BUSDT 正向开单列应渲染现货卖一标签: ' + busdtForward);
    }
    // 有效腿 futures_bid_price 显示格式化价格；缺失腿 spot_ask_price 显示 —；forward spread 显示 —
    if (!busdtForward.includes('64,925.00')) {
      throw new Error('BUSDT 正向开单列应显示有效合约买一价格 64,925.00: ' + busdtForward);
    }
    const busdtForwardDashCount = (busdtForward.match(/—/g) || []).length;
    if (busdtForwardDashCount < 2) {
      throw new Error(`BUSDT 正向开单列应至少包含 2 个 —（现货卖一 + spread），实际 ${busdtForwardDashCount}: ${busdtForward}`);
    }
    if (busdtForward.includes('-0.04%') || busdtForward.includes('+0.04%')) {
      throw new Error('BUSDT 正向开单列 forward spread 应为 —: ' + busdtForward);
    }
    const busdtReverse = getRowCell(tbody, 'BUSDT', 3);
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
    const cusdtForward = getRowCell(tbody, 'CUSDT', 2);
    const cusdtReverse = getRowCell(tbody, 'CUSDT', 3);
    if (!cusdtForward.includes('—') || !cusdtReverse.includes('—')) {
      throw new Error('CUSDT stale 开单列应显示 —: ' + cusdtForward + ' / ' + cusdtReverse);
    }
    const dusdtForward = getRowCell(tbody, 'DUSDT', 2);
    const dusdtReverse = getRowCell(tbody, 'DUSDT', 3);
    if (!dusdtForward.includes('—') || !dusdtReverse.includes('—')) {
      throw new Error('DUSDT unavailable 开单列应显示 —: ' + dusdtForward + ' / ' + dusdtReverse);
    }
    const fusdtForward = getRowCell(tbody, 'FUSDT', 2);
    const fusdtReverse = getRowCell(tbody, 'FUSDT', 3);
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
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] 负费率状态行感知的六文案派生');

    // 35. 余额卡片三行式折算 value_usdt，隐私遮蔽金额与折算值（不再使用 【: ...】）
    const privateBody2 = elements['private-panel-body'].innerHTML;
    if (privateBody2.includes('【:')) {
      throw new Error('余额卡片仍残留旧的行内折算格式 【: ...】');
    }
    if (!privateBody2.includes('≈ **** USDT')) {
      throw new Error('隐藏态下折算值应被遮蔽为 ≈ **** USDT');
    }
    helpers.togglePrivacy(); // 切换到显示态
    const shownBody2 = elements['private-panel-body'].innerHTML;
    if (!shownBody2.includes('≈ 123.45 USDT')) {
      throw new Error('显示态下统一账户余额未展示独立折算行 ≈ 123.45 USDT');
    }
    if (!shownBody2.includes('≈ 67.89 USDT')) {
      throw new Error('显示态下现货账户余额未展示独立折算行 ≈ 67.89 USDT');
    }
    helpers.togglePrivacy(); // 恢复隐藏态
    const hiddenBody2 = elements['private-panel-body'].innerHTML;
    if (!hiddenBody2.includes('≈ **** USDT')) {
      throw new Error('恢复隐藏态后折算值应再次被遮蔽');
    }
    console.log('[PASS] 余额卡片三行折算值与隐私遮蔽');

    // 36. value_usdt null 显示 "≈ — USDT"（显示态），隐藏态遮蔽为 ≈ **** USDT
    const nullValueFixture = JSON.parse(JSON.stringify(designFixture));
    nullValueFixture.private_account.balances_unified[0].value_usdt = null;
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
    const spotSection = nullValueBody.slice(spotSectionStart);
    if (!spotSection.includes('≈ — USDT')) {
      throw new Error('value_usdt null 时现货账户未显示 "≈ — USDT"');
    }
    // 隐藏态下 null 折算值应被遮蔽为 ****
    helpers.togglePrivacy();
    const hiddenNullBody = elements['private-panel-body'].innerHTML;
    if (!hiddenNullBody.includes('≈ **** USDT')) {
      throw new Error('value_usdt null 隐藏态未遮蔽折算值');
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] value_usdt null 显示占位');

    // 37. value_usdt 合法零显示 "≈ 0.00 USDT"（显示态）
    const zeroValueFixture = JSON.parse(JSON.stringify(designFixture));
    zeroValueFixture.private_account.balances_unified[0].value_usdt = '0.00000000';
    zeroValueFixture.private_account.balances_spot[0].value_usdt = '0.00000000';
    helpers.ingestSnapshot(zeroValueFixture);
    if (helpers.getPrivacyHidden()) helpers.togglePrivacy(); // 确保显示态
    const zeroValueBody = elements['private-panel-body'].innerHTML;
    if (!zeroValueBody.includes('≈ 0.00 USDT')) {
      throw new Error('value_usdt "0.00000000" 时未显示 "≈ 0.00 USDT"');
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] value_usdt 合法零显示占位');

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
    if (!unifiedAmtSection.includes('>1,234.56789000<')) {
      throw new Error('统一账户余额数量未按「整数千分位+小数原样」格式化: ' + unifiedAmtSection);
    }
    const spotAmtSection = amountBody.slice(spotAmtStart);
    if (!spotAmtSection.includes('>123,456.07890000<')) {
      throw new Error('现货余额数量未按「整数千分位+小数原样」格式化: ' + spotAmtSection);
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] 余额数量整数千分位、小数原样保留');

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
    if (metalCell.includes('danger') || metalCell.includes('accent')) {
      throw new Error('METAL 徽章不应使用 danger/accent 样式（应为中性徽章）: ' + metalCell);
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
      // (b) BUSDT 有额度
      triFixture.rows[1].negative_funding_status = 'PRIVATE_BORROW_VALIDATION_REQUIRED';
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

    // 62. 操作列：每行第 13 格恰好两个可编辑输入 + 一个确认按钮，且事件隔离
    {
      const opTbody = elements['market-table-body'].innerHTML;
      for (const sym of ['AUSDT', 'BUSDT', 'CUSDT', 'DUSDT', 'EUSDT', 'FUSDT']) {
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
      }
      if (!script.includes('stopPropagation')) {
        throw new Error('操作控件缺少事件隔离 stopPropagation');
      }
      console.log('[PASS] 操作单元格两输入一按钮、标签与事件隔离');
    }

    // 63. 借币任务导航：空态 -> 切换 -> 恢复市场视图
    {
      helpers.setActiveView('borrow-tasks');
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
      const emptyList = elements['borrow-task-list'].innerHTML;
      if (!emptyList.includes('暂无借币任务')) {
        throw new Error(`借币任务空态未渲染: ${emptyList}`);
      }
      // 导航计数初始为 0
      if (elements['borrow-task-count'].textContent !== '0') {
        throw new Error(`借币任务计数应为 0: ${elements['borrow-task-count'].textContent}`);
      }
      // 强免责声明
      if (!html.includes('未发起真实借币请求')) {
        throw new Error('借币任务视图缺少「未发起真实借币请求」声明');
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
      console.log('[PASS] 借币任务导航切换、空态与恢复市场视图');
    }

    // 64. 输入校验：非法数量/次数不创建任务
    {
      const before = helpers.getBorrowTasks().length;
      const badAmounts = ['', '   ', '0', '-5', 'abc', 'Infinity', 'NaN'];
      for (const a of badAmounts) {
        const r = helpers.createBorrowTask('AUSDT', a, '10');
        if (r.ok) {
          throw new Error(`非法数量 ${JSON.stringify(a)} 不应创建任务`);
        }
      }
      const badCounts = ['', '0', '-1', '2.5', 'abc', 'Infinity'];
      for (const c of badCounts) {
        const r = helpers.createBorrowTask('AUSDT', '1000', c);
        if (r.ok) {
          throw new Error(`非法次数 ${JSON.stringify(c)} 不应创建任务`);
        }
      }
      if (helpers.getBorrowTasks().length !== before) {
        throw new Error('非法输入不应增加任务数');
      }
      console.log('[PASS] 借币任务输入校验（数量/次数非法不创建）');
    }

    // 65. HOME 内存行创建任务（1000 / 10）与展示值；零 fetch、零新定时器
    {
      const homeFixture = JSON.parse(JSON.stringify(designFixture));
      // 仅内存改写 base_asset；symbol 保持 AUSDT，不伪造 HOMEUSDT 行情行
      homeFixture.rows[0].base_asset = 'HOME';
      helpers.ingestSnapshot(homeFixture);
      const fetchLogBefore = fetchCallLog.length;
      const intervalsBefore = intervalCalls.length;
      const r = helpers.createBorrowTask('AUSDT', '1000', '10');
      if (!r.ok) {
        throw new Error(`HOME 任务创建失败: ${r.error}`);
      }
      if (r.task.asset !== 'HOME') {
        throw new Error(`任务资产应为 HOME，实际 ${r.task.asset}`);
      }
      if (r.task.amountPerAttempt !== 1000 || r.task.successTarget !== 10 || r.task.successCount !== 0) {
        throw new Error(`任务字段错误: ${JSON.stringify(r.task)}`);
      }
      if (fetchCallLog.length !== fetchLogBefore) {
        throw new Error(`创建借币任务不应发起任何 fetch: ${fetchCallLog.slice(fetchLogBefore)}`);
      }
      if (intervalCalls.length !== intervalsBefore) {
        throw new Error('创建借币任务不应启动任何新定时器');
      }
      // 全部既有定时器仅允许 60000 自动刷新与 1000 倒计时
      for (const c of intervalCalls) {
        if (c.delay !== 60000 && c.delay !== 1000) {
          throw new Error(`存在非法借币重试定时器: delay=${c.delay}`);
        }
      }
      if (elements['borrow-task-count'].textContent !== '1') {
        throw new Error(`借币任务计数应为 1: ${elements['borrow-task-count'].textContent}`);
      }
      helpers.setActiveView('borrow-tasks');
      const listHtml = elements['borrow-task-list'].innerHTML;
      const expectedBits = ['HOME', '1,000 HOME/次', '0 / 10 次成功', '目标 10,000 HOME', '每 30 秒尝试一次', '前端演示', '未发起真实借币请求'];
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
      console.log('[PASS] HOME 任务创建、展示值、零 fetch 与零重试定时器');
    }

    // 66. 操作单元格 UI 提交路径：非法输入就近报错，合法输入创建并清除错误
    {
      const amountEl = document.getElementById('borrow-amount-AUSDT');
      const countEl = document.getElementById('borrow-count-AUSDT');
      const errorEl = document.getElementById('borrow-error-AUSDT');
      const before = helpers.getBorrowTasks().length;
      amountEl.value = 'abc';
      countEl.value = '10';
      const r1 = helpers.submitBorrowTask('AUSDT');
      if (r1.ok) {
        throw new Error('非法数量的 UI 提交不应成功');
      }
      if (!errorEl.textContent.includes('大于 0')) {
        throw new Error(`就近错误未显示: ${errorEl.textContent}`);
      }
      if (helpers.getBorrowTasks().length !== before) {
        throw new Error('非法 UI 提交不应创建任务');
      }
      amountEl.value = '500';
      countEl.value = '3';
      const r2 = helpers.submitBorrowTask('AUSDT');
      if (!r2.ok) {
        throw new Error(`合法 UI 提交失败: ${r2.error}`);
      }
      if (errorEl.textContent !== '') {
        throw new Error('合法提交后就近错误应清除');
      }
      if (helpers.getBorrowTasks().length !== before + 1) {
        throw new Error('合法 UI 提交应新增 1 条任务');
      }
      if (elements['borrow-task-count'].textContent !== String(before + 1)) {
        throw new Error(`导航计数应为 ${before + 1}: ${elements['borrow-task-count'].textContent}`);
      }
      console.log('[PASS] 操作单元格 UI 提交路径与就近错误');
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

    console.log('\n全部自检通过');
    process.exit(0);
  } catch (err) {
    console.error('\n[FAIL]', err.message);
    process.exit(1);
  }
}, 50);

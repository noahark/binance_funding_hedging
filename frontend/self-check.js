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

function makeElement(id) {
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
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    }
  };
  return el;
}

const elements = {};
const ids = [
  'warnings-panel', 'warnings-list', 'warnings-raw', 'warnings-raw-content', 'margin-public-note',
  'data-source-label', 'sort-basis-badge', 'btn-refresh', 'refresh-countdown',
  'filter-search', 'filter-asset', 'filter-route', 'filter-show-perp-only', 'filter-hide-low-daily-rate',
  'summary-row', 'status-area', 'market-table-body', 'footer-note',
  'private-panel', 'private-panel-subtitle', 'private-panel-body', 'btn-privacy', 'privacy-label', 'privacy-icon-path',
  'drawer', 'drawer-backdrop', 'drawer-title', 'drawer-body', 'drawer-close'
];
ids.forEach(id => { elements[id] = makeElement(id); });

// 加载设计期 fixture
const designFixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));

// Task B 要求前端把 annualized 字段视为当前服务契约字段；给设计期 fixture 补齐。
designFixture.rows.forEach(r => {
  if (!('annualized_funding_24h' in r)) r.annualized_funding_24h = null;
  if (!('annualized_funding_7d' in r)) r.annualized_funding_7d = null;
  if (!('annualized_funding_30d' in r)) r.annualized_funding_30d = null;
});
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

global.fetch = async (url) => {
  fetchUrl = String(url);
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => fixtureToFetch
  };
};

global.document = {
  getElementById: (id) => {
    if (!elements[id]) throw new Error(`未 mock 的元素: ${id}`);
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

    // 5. 拆列：存在独立「资金费率」「结算时间」「日费率」「净收益」列，合并列消失
    if (!html.includes('>资金费率<')) {
      throw new Error('缺少「资金费率」列名');
    }
    if (!html.includes('>结算时间<')) {
      throw new Error('缺少「结算时间」列名');
    }
    if (!html.includes('>日费率<')) {
      throw new Error('缺少「日费率」列名');
    }
    if (!html.includes('>净收益<')) {
      throw new Error('缺少「净收益」列名');
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

    // 6. 日费率 string-shift 格式化（含 null→—）
    const dailyRateChecks = [
      ['AUSDT', '-0.06%'],
      ['BUSDT', '-0.07%'],
      ['CUSDT', '+0.03%'],
      ['DUSDT', '-0.04%'],
      ['EUSDT', '-0.08%'],
      ['FUSDT', '—']
    ];
    for (const [sym, expected] of dailyRateChecks) {
      const cell = getRowCell(tbody, sym, 5);
      if (!cell.includes(expected)) {
        throw new Error(`${sym} 日费率期望 ${expected}，单元格 ${cell}`);
      }
    }
    console.log('[PASS] 日费率 string-shift 格式化（含 null→—）');

    // 6b. 年化三列格式化：AUSDT 三值齐全，BUSDT 7D/30D 为 null→—
    const ausdtAnn24 = getRowCell(tbody, 'AUSDT', 6);
    if (!ausdtAnn24.includes('-65.7%')) {
      throw new Error(`AUSDT 年化 24h 期望 -65.7%，单元格 ${ausdtAnn24}`);
    }
    const ausdtAnn7 = getRowCell(tbody, 'AUSDT', 7);
    if (!ausdtAnn7.includes('-0.260714%')) {
      throw new Error(`AUSDT 年化 7D 期望 -0.260714%，单元格 ${ausdtAnn7}`);
    }
    const ausdtAnn30 = getRowCell(tbody, 'AUSDT', 8);
    if (!ausdtAnn30.includes('-0.060833%')) {
      throw new Error(`AUSDT 年化 30D 期望 -0.060833%，单元格 ${ausdtAnn30}`);
    }
    const busdtAnn7 = getRowCell(tbody, 'BUSDT', 7);
    if (!busdtAnn7.includes('—')) {
      throw new Error(`BUSDT 年化 7D 期望 —，单元格 ${busdtAnn7}`);
    }
    const busdtAnn30 = getRowCell(tbody, 'BUSDT', 8);
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
    const headers = [...tableSection.matchAll(/<th[^\u003e]*>([^\u003c]*)\/>th>/g)].map(m => m[0]);
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

    // 16. 路由/资产/负费率状态列显示中文优先格式（v0.4 行感知的结构优先级派生）
    const enumDisplayChecks = [
      ['MARGIN_SPOT_CANDIDATE(杠杆现货候选)', '路由分类'],
      ['CRYPTO(加密货币)', '资产标签'],
      ['已验证可借', '负费率状态']
    ];
    for (const [expected, column] of enumDisplayChecks) {
      if (!tbody.includes(expected)) {
        throw new Error(`${column} 列未渲染预期格式: ${expected}`);
      }
    }
    // 结构禁用行保持结构文案，不得派生为"需私有验证"
    if (!tbody.includes('仅现货: 无杠杆借币')) {
      throw new Error('DISABLED_SPOT_ONLY 行未保持结构文案');
    }
    console.log('[PASS] 路由/资产/负费率状态列显示中文优先格式');

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
      const cell = getRowCell(tbody, sym, 9);
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
    const cusdtNetCell = getRowCell(tbody, 'CUSDT', 9);
    const ausdtNetCell = getRowCell(tbody, 'AUSDT', 9);
    if (!ausdtNetCell.includes('positive')) {
      throw new Error('AUSDT 正净收益未应用 positive 样式');
    }
    // 设计 fixture 无负净收益行；构造一个负净收益 fixture 行验证样式
    const negativeNetFixture = JSON.parse(JSON.stringify(designFixture));
    negativeNetFixture.rows[0].net_daily_yield = '-0.00020000';
    negativeNetFixture.rows[0].borrow_rate_source = null;
    helpers.ingestSnapshot(negativeNetFixture);
    const negTbody = elements['market-table-body'].innerHTML;
    const negCell = getRowCell(negTbody, 'AUSDT', 9);
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
    const vip0Cell = getRowCell(vip0Tbody, 'BUSDT', 9);
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
    if (!sortBasisBadge.textContent.includes('净收益优先')) {
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
    while (pos !== -1 && tdCount < 12) {
      const close = dRowHtml.indexOf('</td>', pos);
      if (tdCount === 5) dailyCell = dRowHtml.slice(pos, close + 5);
      if (tdCount === 9) netCell = dRowHtml.slice(pos, close + 5);
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
    const ausdtNetCell2 = getRowCell(tbody, 'AUSDT', 9);
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
    const busdtNetCell = getRowCell(vip0Tbody2, 'BUSDT', 9);
    if (!busdtNetCell.includes('日借币') || !busdtNetCell.includes('参考')) {
      throw new Error('VIP0 参考档未显示"参考"徽标: ' + busdtNetCell);
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] VIP0 参考档显示"参考"徽标');

    // 33. 正费率/无成本腿行不展示借币成本子行
    const cusdtNetCell2 = getRowCell(tbody, 'CUSDT', 9);
    if (cusdtNetCell2.includes('日借币')) {
      throw new Error('CUSDT 正费率行不应展示日借币子行');
    }
    console.log('[PASS] 正费率行不展示借币成本子行');

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
    const fusdtNetCell = getRowCell(labelTbody, 'FUSDT', 9);
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
    const metalCell = getRowCell(metalTbody, 'AUSDT', 1);
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
    //       「可借 0(已借完)」（title 含 51061，非 success），net-yield 可借子行含
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
      const ausdtNet = getRowCell(triTbody, 'AUSDT', 9);
      if (!ausdtNet.includes('可借: 0') || !ausdtNet.includes('已借完')) {
        throw new Error('AUSDT 借光 net-yield 应含「可借: 0」与「已借完」: ' + ausdtNet);
      }
      if (!ausdtNet.includes('≈ 0.00 USDT')) {
        throw new Error('AUSDT 借光 ≈USDT 应显 0.00: ' + ausdtNet);
      }
      // (b) BUSDT 有额度
      const busdtStatus = getRowCell(triTbody, 'BUSDT', 11);
      if (!busdtStatus.includes('已验证可借') || !busdtStatus.includes('badge success')) {
        throw new Error('BUSDT 有额度应渲染 success「已验证可借」: ' + busdtStatus);
      }
      const busdtNet = getRowCell(triTbody, 'BUSDT', 9);
      if (!busdtNet.includes('可借: 5.0')) {
        throw new Error('BUSDT 有额度 net-yield 应含「可借: 5.0」: ' + busdtNet);
      }
      if (!busdtNet.includes('≈ 30000.00 USDT')) {
        throw new Error('BUSDT 有额度 ≈USDT 应显 30000.00: ' + busdtNet);
      }
      if (busdtNet.includes('已借完')) {
        throw new Error('BUSDT 有额度不应含「已借完」: ' + busdtNet);
      }
      // (c) CUSDT 未探测
      const cusdtStatus = getRowCell(triTbody, 'CUSDT', 11);
      if (!cusdtStatus.includes('有利率·可借性未探测')) {
        throw new Error('CUSDT 未探测 badge 应保持「有利率·可借性未探测」: ' + cusdtStatus);
      }
      const cusdtNet = getRowCell(triTbody, 'CUSDT', 9);
      if (cusdtNet.includes('可借:')) {
        throw new Error('CUSDT 未探测（max_borrowable=null）不应展示可借子行: ' + cusdtNet);
      }
      helpers.ingestSnapshot(designFixture);
      console.log('[PASS] 借币三态（51061 借光/有额度/未探测）');
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
    if (!drawerBody.includes('-65.7%') || !drawerBody.includes('-0.260714%') || !drawerBody.includes('-0.060833%')) {
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

    console.log('\n全部自检通过');
    process.exit(0);
  } catch (err) {
    console.error('\n[FAIL]', err.message);
    process.exit(1);
  }
}, 50);

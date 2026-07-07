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

function makeElement(id) {
  const el = {
    id,
    _innerHTML: '',
    _textContent: '',
    _display: '',
    _value: '',
    _checked: false,
    listeners: {},
    get innerHTML() { return this._innerHTML; },
    set innerHTML(v) { this._innerHTML = String(v); },
    get textContent() { return this._textContent; },
    set textContent(v) { this._textContent = String(v); },
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
    }
  };
  return el;
}

const elements = {};
const ids = [
  'warnings-panel', 'warnings-list', 'warnings-raw', 'warnings-raw-content', 'margin-public-note',
  'data-source-label', 'sort-basis-badge', 'btn-refresh', 'refresh-countdown',
  'filter-search', 'filter-asset', 'filter-route', 'filter-show-perp-only',
  'summary-row', 'status-area', 'market-table-body', 'footer-note',
  'private-panel', 'private-panel-subtitle', 'private-panel-body', 'btn-privacy', 'privacy-label', 'privacy-icon-path'
];
ids.forEach(id => { elements[id] = makeElement(id); });

// 加载设计期 fixture
const designFixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));

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

    // 4. 默认渲染 6 行（设计期 fixture）
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

    // 11. 列名/文案符合契约（资金费率列不得出现"已结算"或"预测"）
    const tableSection = html.slice(html.indexOf('<table>'), html.indexOf('</table>') + 8);
    if (tableSection.includes('已结算') || tableSection.includes('预测')) {
      throw new Error('市场表区域出现"已结算"或"预测"等误导文案');
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
      const cell = getRowCell(tbody, sym, 6);
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
    const cusdtNetCell = getRowCell(tbody, 'CUSDT', 6);
    const ausdtNetCell = getRowCell(tbody, 'AUSDT', 6);
    if (!ausdtNetCell.includes('positive')) {
      throw new Error('AUSDT 正净收益未应用 positive 样式');
    }
    // 设计 fixture 无负净收益行；构造一个负净收益 fixture 行验证样式
    const negativeNetFixture = JSON.parse(JSON.stringify(designFixture));
    negativeNetFixture.rows[0].net_daily_yield = '-0.00020000';
    negativeNetFixture.rows[0].borrow_rate_source = null;
    helpers.ingestSnapshot(negativeNetFixture);
    const negTbody = elements['market-table-body'].innerHTML;
    const negCell = getRowCell(negTbody, 'AUSDT', 6);
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
    const vip0Cell = getRowCell(vip0Tbody, 'BUSDT', 6);
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
    while (pos !== -1 && tdCount < 8) {
      const close = dRowHtml.indexOf('</td>', pos);
      if (tdCount === 5) dailyCell = dRowHtml.slice(pos, close + 5);
      if (tdCount === 6) netCell = dRowHtml.slice(pos, close + 5);
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

    // 31. 成本腿命中行展示借币日利率（账户档）
    const ausdtNetCell2 = getRowCell(tbody, 'AUSDT', 6);
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
    const busdtNetCell = getRowCell(vip0Tbody2, 'BUSDT', 6);
    if (!busdtNetCell.includes('日借币') || !busdtNetCell.includes('参考')) {
      throw new Error('VIP0 参考档未显示"参考"徽标: ' + busdtNetCell);
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] VIP0 参考档显示"参考"徽标');

    // 33. 正费率/无成本腿行不展示借币成本子行
    const cusdtNetCell2 = getRowCell(tbody, 'CUSDT', 6);
    if (cusdtNetCell2.includes('日借币')) {
      throw new Error('CUSDT 正费率行不应展示日借币子行');
    }
    console.log('[PASS] 正费率行不展示借币成本子行');

    // 34. 负费率状态行感知的五文案派生
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
    // 未探测
    labelFixtureBase.rows[3].borrow_validation.verified = false;
    labelFixtureBase.rows[3].borrow_validation.error = 'not_probed_this_round';
    // 需私有验证（private channel disabled/failed）
    labelFixtureBase.rows[4].borrow_validation.verified = false;
    labelFixtureBase.rows[4].borrow_validation.error = null;
    helpers.ingestSnapshot(labelFixtureBase);
    const labelTbody = elements['market-table-body'].innerHTML;
    const labelCases = [
      { sym: 'AUSDT', label: '已验证可借', cls: 'success' },
      { sym: 'BUSDT', label: '杠杆交易对未列出', cls: 'warn' },
      { sym: 'CUSDT', label: '资产不可借', cls: 'danger' },
      { sym: 'DUSDT', label: '未探测(限速预算)', cls: 'muted' },
      { sym: 'EUSDT', label: '需私有验证', cls: 'warn' },
    ];
    for (const { sym, label, cls } of labelCases) {
      const cell = getRowCell(labelTbody, sym, 8);
      if (!cell.includes(label)) {
        throw new Error(`${sym} 负费率状态期望 "${label}"，单元格 ${cell}`);
      }
      if (!cell.includes(`badge ${cls}`)) {
        throw new Error(`${sym} 负费率状态期望 ${cls} 样式，单元格 ${cell}`);
      }
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] 负费率状态行感知的五文案派生');

    // 35. 余额卡片行内折算 value_usdt，隐私开关遮蔽金额与折算值
    const privateBody2 = elements['private-panel-body'].innerHTML;
    if (!privateBody2.includes('【: ****】')) {
      throw new Error('隐藏态下折算值应被遮蔽为 ****');
    }
    helpers.togglePrivacy(); // 切换到显示态
    const shownBody2 = elements['private-panel-body'].innerHTML;
    if (!shownBody2.includes('【: 123.45 USDT】')) {
      throw new Error('显示态下统一账户余额未展示行内折算值');
    }
    if (!shownBody2.includes('【: 67.89 USDT】')) {
      throw new Error('显示态下现货账户余额未展示行内折算值');
    }
    helpers.togglePrivacy(); // 恢复隐藏态
    const hiddenBody2 = elements['private-panel-body'].innerHTML;
    if (!hiddenBody2.includes('【: ****】')) {
      throw new Error('恢复隐藏态后折算值应再次被遮蔽');
    }
    console.log('[PASS] 余额卡片行内折算值与隐私遮蔽');

    // 36. value_usdt null 显示 "【: — USDT】"（显示态）
    const nullValueFixture = JSON.parse(JSON.stringify(designFixture));
    nullValueFixture.private_account.balances_unified[0].value_usdt = null;
    nullValueFixture.private_account.balances_spot[0].value_usdt = null;
    helpers.ingestSnapshot(nullValueFixture);
    if (helpers.getPrivacyHidden()) helpers.togglePrivacy(); // 确保显示态
    const nullValueBody = elements['private-panel-body'].innerHTML;
    const unifiedSectionStart = nullValueBody.indexOf('统一账户余额');
    const spotSectionStart = nullValueBody.indexOf('现货账户余额');
    const unifiedSection = nullValueBody.slice(unifiedSectionStart, spotSectionStart);
    if (!unifiedSection.includes('【: — USDT】')) {
      throw new Error('value_usdt null 时统一账户未显示 "【: — USDT】"');
    }
    const spotSection = nullValueBody.slice(spotSectionStart);
    if (!spotSection.includes('【: — USDT】')) {
      throw new Error('value_usdt null 时现货账户未显示 "【: — USDT】"');
    }
    // 隐藏态下 null 折算值应被遮蔽为 ****
    helpers.togglePrivacy();
    const hiddenNullBody = elements['private-panel-body'].innerHTML;
    if (!hiddenNullBody.includes('【: ****】')) {
      throw new Error('value_usdt null 隐藏态未遮蔽折算值');
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] value_usdt null 显示占位');

    // 37. value_usdt 合法零显示 "【: 0.00 USDT】"（显示态）
    const zeroValueFixture = JSON.parse(JSON.stringify(designFixture));
    zeroValueFixture.private_account.balances_unified[0].value_usdt = '0.00000000';
    zeroValueFixture.private_account.balances_spot[0].value_usdt = '0.00000000';
    helpers.ingestSnapshot(zeroValueFixture);
    if (helpers.getPrivacyHidden()) helpers.togglePrivacy(); // 确保显示态
    const zeroValueBody = elements['private-panel-body'].innerHTML;
    if (!zeroValueBody.includes('【: 0.00 USDT】')) {
      throw new Error('value_usdt "0.00000000" 时未显示 "【: 0.00 USDT】"');
    }
    helpers.ingestSnapshot(designFixture);
    console.log('[PASS] value_usdt 合法零显示占位');

    console.log('\n全部自检通过');
    process.exit(0);
  } catch (err) {
    console.error('\n[FAIL]', err.message);
    process.exit(1);
  }
}, 50);

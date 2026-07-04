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
    }
  };
  return el;
}

const elements = {};
const ids = [
  'warnings-panel', 'warnings-list', 'warnings-raw', 'warnings-raw-content', 'margin-public-note',
  'data-source-label', 'btn-refresh', 'refresh-countdown',
  'filter-search', 'filter-asset', 'filter-route', 'filter-show-perp-only',
  'summary-row', 'status-area', 'market-table-body', 'footer-note'
];
ids.forEach(id => { elements[id] = makeElement(id); });

// 10-design §4.3 设计期 fixture：AUSDT 单期费率低于 BUSDT，但日费率更高，故排第一
const designFixture = {
  "schema_version": "public-market-snapshot/v2",
  "generated_at": "2026-07-04T13:34:06Z",
  "data_time": "2026-07-04T13:34:06Z",
  "source_sample_id": "phase2-design-fixture",
  "summary": {
    "total_rows": 4,
    "route_counts": { "MARGIN_SPOT_CANDIDATE": 4 },
    "asset_tag_counts": { "CRYPTO": 4 },
    "negative_funding_status_counts": { "PRIVATE_BORROW_VALIDATION_REQUIRED": 4 }
  },
  "rows": [
    {
      "symbol": "AUSDT",
      "base_asset": "A",
      "quote_asset": "USDT",
      "asset_tag": "CRYPTO",
      "asset_tag_source": "futures_contractType_perpetual",
      "asset_tag_confidence": "HIGH",
      "route_class": "MARGIN_SPOT_CANDIDATE",
      "positive_funding_enabled": true,
      "negative_funding_status": "PRIVATE_BORROW_VALIDATION_REQUIRED",
      "futures": {
        "symbol": "AUSDT",
        "status": "TRADING",
        "contract_type": "PERPETUAL",
        "mark_price": "1.00000000",
        "index_price": "1.00000000",
        "last_funding_rate": "0.00010000",
        "next_funding_time": 1783065600000,
        "min_notional": "5",
        "step_size": "0.001"
      },
      "spot": {
        "symbol": "AUSDT",
        "status": "TRADING",
        "exists": true,
        "match_type": "exact_symbol",
        "min_notional": "5.00000000",
        "step_size": "0.00010000"
      },
      "margin_public": { "public_cross_margin_pair": null, "source": "unverified" },
      "funding_history": [],
      "ui_flags": ["MARGIN_PUBLIC_UNVERIFIED"],
      "funding_interval_hours": 4,
      "daily_funding_rate": "0.00060000"
    },
    {
      "symbol": "BUSDT",
      "base_asset": "B",
      "quote_asset": "USDT",
      "asset_tag": "CRYPTO",
      "asset_tag_source": "futures_contractType_perpetual",
      "asset_tag_confidence": "HIGH",
      "route_class": "MARGIN_SPOT_CANDIDATE",
      "positive_funding_enabled": true,
      "negative_funding_status": "PRIVATE_BORROW_VALIDATION_REQUIRED",
      "futures": {
        "symbol": "BUSDT",
        "status": "TRADING",
        "contract_type": "PERPETUAL",
        "mark_price": "2.00000000",
        "index_price": "2.00000000",
        "last_funding_rate": "0.00015000",
        "next_funding_time": 1783065600000,
        "min_notional": "5",
        "step_size": "0.001"
      },
      "spot": {
        "symbol": "BUSDT",
        "status": "TRADING",
        "exists": true,
        "match_type": "exact_symbol",
        "min_notional": "5.00000000",
        "step_size": "0.00010000"
      },
      "margin_public": { "public_cross_margin_pair": null, "source": "unverified" },
      "funding_history": [],
      "ui_flags": ["MARGIN_PUBLIC_UNVERIFIED"],
      "funding_interval_hours": 8,
      "daily_funding_rate": "0.00045000"
    },
    {
      "symbol": "CUSDT",
      "base_asset": "C",
      "quote_asset": "USDT",
      "asset_tag": "CRYPTO",
      "asset_tag_source": "futures_contractType_perpetual",
      "asset_tag_confidence": "HIGH",
      "route_class": "MARGIN_SPOT_CANDIDATE",
      "positive_funding_enabled": true,
      "negative_funding_status": "PRIVATE_BORROW_VALIDATION_REQUIRED",
      "futures": {
        "symbol": "CUSDT",
        "status": "TRADING",
        "contract_type": "PERPETUAL",
        "mark_price": "3.00000000",
        "index_price": "3.00000000",
        "last_funding_rate": "-0.00005000",
        "next_funding_time": 1783065600000,
        "min_notional": "5",
        "step_size": "0.001"
      },
      "spot": {
        "symbol": "CUSDT",
        "status": "TRADING",
        "exists": true,
        "match_type": "exact_symbol",
        "min_notional": "5.00000000",
        "step_size": "0.00010000"
      },
      "margin_public": { "public_cross_margin_pair": null, "source": "unverified" },
      "funding_history": [],
      "ui_flags": ["MARGIN_PUBLIC_UNVERIFIED"],
      "funding_interval_hours": 4,
      "daily_funding_rate": "-0.00030000"
    },
    {
      "symbol": "DUSDT",
      "base_asset": "D",
      "quote_asset": "USDT",
      "asset_tag": "CRYPTO",
      "asset_tag_source": "futures_contractType_perpetual",
      "asset_tag_confidence": "HIGH",
      "route_class": "MARGIN_SPOT_CANDIDATE",
      "positive_funding_enabled": true,
      "negative_funding_status": "PRIVATE_BORROW_VALIDATION_REQUIRED",
      "futures": {
        "symbol": "DUSDT",
        "status": "TRADING",
        "contract_type": "PERPETUAL",
        "mark_price": "4.00000000",
        "index_price": "4.00000000",
        "last_funding_rate": "0.00002000",
        "next_funding_time": 1783065600000,
        "min_notional": "5",
        "step_size": "0.001"
      },
      "spot": {
        "symbol": "DUSDT",
        "status": "TRADING",
        "exists": true,
        "match_type": "exact_symbol",
        "min_notional": "5.00000000",
        "step_size": "0.00010000"
      },
      "margin_public": { "public_cross_margin_pair": null, "source": "unverified" },
      "funding_history": [],
      "ui_flags": ["MARGIN_PUBLIC_UNVERIFIED"],
      "funding_interval_hours": 8,
      "daily_funding_rate": null
    }
  ],
  "warnings": [
    "GET /sapi/v1/margin/allPairs and /sapi/v1/margin/isolated/allPairs return HTTP 400 code -2014 without an API key, so margin_public stays unverified and is not used for route classification.",
    "premiumIndex.lastFundingRate is the real-time estimate for the CURRENT funding period and is charged at nextFundingTime; it drifts until settlement (mid-period divergence from settled history evidenced under reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/). Settled history comes from /fapi/v1/fundingRate; do not present the estimate as a settled value.",
    "TRADIFI_PERPETUAL (bStock) spot legs are joined via the baseAsset+B+quoteAsset alias (e.g. futures TSLAUSDT -> spot TSLABUSDT); bStock collateral ratio is dynamic/unknown and is not hard-coded; asset_tag is independent of route_class."
  ]
};

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
    if (!marginNote.includes('杠杆可借性未经私有验证')) {
      throw new Error('页面级杠杆可借性说明未渲染');
    }
    const warningsHtml = elements['warnings-list'].innerHTML;
    if (!warningsHtml.includes('isMarginTradingAllowed') || !warningsHtml.includes('已结算历史') || !warningsHtml.includes('bStock')) {
      throw new Error('数据说明中文内容未渲染');
    }
    const rawText = elements['warnings-raw-content'].textContent;
    if (!rawText.includes('lastFundingRate') || !rawText.includes('fapi/v1/fundingRate')) {
      throw new Error('数据说明英文原文未渲染');
    }
    console.log('[PASS] 数据说明区可见且内容已渲染');

    // 4. 默认渲染 4 行（设计期 fixture 全为 MARGIN_SPOT_CANDIDATE）
    let tbody = elements['market-table-body'].innerHTML;
    let rowCount = (tbody.match(/<tr/g) || []).length;
    if (rowCount !== 4) {
      throw new Error(`默认筛选后期望 4 行数据，实际 ${rowCount} 行`);
    }
    console.log('[PASS] 默认渲染 4 行');

    // 5. 拆列：存在独立「资金费率」「结算时间」「日费率」列，合并列消失
    if (!html.includes('>资金费率<')) {
      throw new Error('缺少「资金费率」列名');
    }
    if (!html.includes('>结算时间<')) {
      throw new Error('缺少「结算时间」列名');
    }
    if (!html.includes('>日费率<')) {
      throw new Error('缺少「日费率」列名');
    }
    if (html.includes('资金费率/结算时间')) {
      throw new Error('仍保留「资金费率/结算时间」合并列名');
    }
    console.log('[PASS] 拆列存在，合并列消失');

    // 6. 日费率 string-shift 格式化（含 null→—）
    const dailyRateChecks = [
      ['AUSDT', '+0.06%'],
      ['BUSDT', '+0.045%'],
      ['CUSDT', '-0.03%'],
      ['DUSDT', '—']
    ];
    for (const [sym, expected] of dailyRateChecks) {
      // 找到 symbol 所在行，检查其后日费率单元格内容
      const symIdx = tbody.indexOf(sym);
      if (symIdx === -1) throw new Error(`未找到 ${sym} 行`);
      const rowEnd = tbody.indexOf('</tr>', symIdx);
      const rowHtml = tbody.slice(symIdx, rowEnd);
      if (!rowHtml.includes(expected)) {
        throw new Error(`${sym} 日费率期望 ${expected}，行内容未匹配`);
      }
    }
    console.log('[PASS] 日费率 string-shift 格式化（含 null→—）');

    // 7. 结算间隔标注 4h/8h
    if (!tbody.includes('>4h<') || !tbody.includes('>8h<')) {
      throw new Error('未渲染 4h/8h 结算间隔徽标');
    }
    console.log('[PASS] 结算间隔标注 4h/8h');

    // 8. 无排序控件 DOM
    if (html.includes('排序') || html.includes('sort') || html.includes('Sort')) {
      throw new Error('页面不应包含排序按钮或排序状态');
    }
    console.log('[PASS] 无排序控件 DOM');

    // 9. 渲染顺序 == fixture 顺序（AUSDT > BUSDT > CUSDT > DUSDT）
    assertOrder(tbody, ['AUSDT', 'BUSDT', 'CUSDT', 'DUSDT']);
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

    // 12. 无交易按钮/开仓票据
    if (html.includes('手动开仓') || html.includes('下单') || html.includes('开仓')) {
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

    // 16. 路由/资产/负费率状态列显示「英文枚举(中文解释)」格式
    const enumDisplayChecks = [
      ['MARGIN_SPOT_CANDIDATE(杠杆现货候选)', '路由分类'],
      ['CRYPTO(加密货币)', '资产标签'],
      ['PRIVATE_BORROW_VALIDATION_REQUIRED(需私有借币验证)', '负费率状态']
    ];
    for (const [expected, column] of enumDisplayChecks) {
      if (!tbody.includes(expected)) {
        throw new Error(`${column} 列未渲染预期格式: ${expected}`);
      }
    }
    console.log('[PASS] 路由/资产/负费率状态列显示「英文枚举(中文解释)」格式');

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

    // 19. 优雅降级：新字段缺失（旧后端）不白屏，日费率列 —、间隔不显示
    if (!helpers.ingestSnapshot) {
      throw new Error('ingestSnapshot 未暴露，无法测试优雅降级');
    }
    const degradedFixture = JSON.parse(JSON.stringify(designFixture));
    degradedFixture.rows.forEach(r => {
      delete r.daily_funding_rate;
      delete r.funding_interval_hours;
    });
    fixtureToFetch = degradedFixture;
    helpers.ingestSnapshot(degradedFixture);
    const degradedTbody = elements['market-table-body'].innerHTML;
    const degradedRowCount = (degradedTbody.match(/<tr/g) || []).length;
    if (degradedRowCount !== 4) {
      throw new Error(`优雅降级后期望 4 行，实际 ${degradedRowCount} 行`);
    }
    // DUSDT 行：日费率单元格应为第 6 个 td
    const dRowIdx = degradedTbody.indexOf('DUSDT');
    const trStart = degradedTbody.lastIndexOf('<tr', dRowIdx);
    const dRowEnd = degradedTbody.indexOf('</tr>', trStart);
    const dRowHtml = degradedTbody.slice(trStart, dRowEnd + 5);
    // 日费率单元格：找到第 6 个 <td> ... </td>
    let tdCount = 0;
    let pos = dRowHtml.indexOf('<td');
    let dailyCell = '';
    while (pos !== -1 && tdCount < 6) {
      const close = dRowHtml.indexOf('</td>', pos);
      if (tdCount === 5) {
        dailyCell = dRowHtml.slice(pos, close + 5);
      }
      pos = dRowHtml.indexOf('<td', close + 5);
      tdCount++;
    }
    if (!dailyCell.includes('—')) {
      throw new Error('优雅降级后日费率列未显示 —');
    }
    if (degradedTbody.includes('>8h<') || degradedTbody.includes('>4h<')) {
      throw new Error('优雅降级后仍渲染结算间隔徽标');
    }
    console.log('[PASS] 优雅降级：新字段缺失不白屏，日费率 —，间隔不显示');

    console.log('\n全部自检通过');
    process.exit(0);
  } catch (err) {
    console.error('\n[FAIL]', err.message);
    process.exit(1);
  }
}, 50);
